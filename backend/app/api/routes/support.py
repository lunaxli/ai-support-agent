from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from openai import OpenAI
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import User, get_datetime_utc
from app.support.knowledge import KnowledgeBase
from app.support.models import SupportAnalysis, SupportLog, SupportReview, SupportTicket
from app.support.providers import DeepSeekProvider, MockProvider, SupportProvider
from app.support.schemas import (
    AnalysisRead,
    AuditRead,
    Capabilities,
    ReviewInput,
    ReviewRead,
    RoleUpdate,
    Status,
    StatusChange,
    TicketCreate,
    TicketDetail,
    TicketEdit,
    TicketPage,
    TicketRead,
)
from app.support.workflow import Outcome, SupportWorkflow

router = APIRouter(prefix="/tickets", tags=["tickets"])
KB = KnowledgeBase.from_directory(Path(__file__).parents[2] / "support" / "kb")
TRANSITIONS = {
    Status.OPEN: {Status.IN_PROGRESS},
    Status.IN_PROGRESS: {Status.RESOLVED},
    Status.RESOLVED: {Status.CLOSED},
}
ANALYZABLE = {Status.OPEN, Status.IN_PROGRESS}


def can_review(user: User) -> bool:
    return user.is_superuser or user.is_support_agent


def require_staff(user: User) -> None:
    if not can_review(user):
        raise HTTPException(403, "Support staff or administrator required")


def ticket_scope(user: User) -> Any:
    active = col(SupportTicket.deleted_at).is_(None)
    return active if can_review(user) else active & (SupportTicket.owner_id == user.id)


def get_ticket(
    session: SessionDep,
    user: User,
    ticket_id: UUID,
    version: int | None = None,
) -> SupportTicket:
    query = select(SupportTicket).where(
        SupportTicket.id == ticket_id, ticket_scope(user)
    )
    if version is not None:
        query = query.with_for_update().execution_options(populate_existing=True)
    ticket = session.exec(query).first()
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    if version is not None and ticket.version != version:
        raise HTTPException(409, "Ticket changed. Refresh before trying again.")
    return ticket


def record(
    session: SessionDep,
    ticket: SupportTicket,
    actor: User,
    action: str,
    **details: Any,
) -> None:
    session.add(
        SupportLog(
            ticket_id=ticket.id, actor_id=actor.id, action=action, details=details
        )
    )


def set_status(ticket: SupportTicket, status: Status) -> None:
    ticket.status = status
    ticket.version += 1
    ticket.updated_at = get_datetime_utc()


def ticket_data(ticket: SupportTicket) -> dict[str, Any]:
    return TicketRead.model_validate(ticket).model_dump()


def run_analysis(subject: str, description: str) -> Outcome:
    if settings.AI_MODE == "mock":
        return SupportWorkflow(MockProvider(), KB).run(subject, description)
    assert settings.DEEPSEEK_API_KEY is not None
    with OpenAI(
        api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
        base_url=str(settings.DEEPSEEK_BASE_URL),
        timeout=15,
        max_retries=0,
    ) as client:
        provider: SupportProvider = DeepSeekProvider(client, settings.DEEPSEEK_MODEL)
        return SupportWorkflow(provider, KB).run(subject, description)


@router.get("/capabilities", response_model=Capabilities)
def capabilities(current_user: CurrentUser) -> Capabilities:
    return Capabilities(can_review=can_review(current_user), ai_mode=settings.AI_MODE)


@router.put("/staff/{user_id}", response_model=RoleUpdate)
def update_staff(
    user_id: UUID,
    body: RoleUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> RoleUpdate:
    if not current_user.is_superuser:
        raise HTTPException(403, "Administrator required")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.is_support_agent = body.is_support_agent
    session.add(user)
    session.commit()
    return body


@router.post("/", response_model=TicketRead, status_code=201)
def create_ticket(
    body: TicketCreate, session: SessionDep, current_user: CurrentUser
) -> SupportTicket:
    ticket = SupportTicket(**body.model_dump(), owner_id=current_user.id)
    session.add(ticket)
    session.flush()
    record(session, ticket, current_user, "ticket_created")
    session.commit()
    session.refresh(ticket)
    return ticket


@router.get("/", response_model=TicketPage)
def list_tickets(
    session: SessionDep,
    current_user: CurrentUser,
    status: Status | None = None,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketPage:
    filters = [ticket_scope(current_user)]
    if status is not None:
        filters.append(SupportTicket.status == status)
    count = session.exec(
        select(func.count()).select_from(SupportTicket).where(*filters)
    ).one()
    tickets = session.exec(
        select(SupportTicket)
        .where(*filters)
        .order_by(
            col(SupportTicket.created_at).desc(),
            col(SupportTicket.id).desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return TicketPage(
        data=[TicketRead.model_validate(ticket) for ticket in tickets], count=count
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
def read_ticket(
    ticket_id: UUID, session: SessionDep, current_user: CurrentUser
) -> TicketDetail:
    ticket = get_ticket(session, current_user, ticket_id)
    analyses_query = select(SupportAnalysis).where(
        SupportAnalysis.ticket_id == ticket.id
    )
    review_query = (
        select(SupportReview)
        .join(SupportAnalysis)
        .where(SupportAnalysis.ticket_id == ticket.id)
    )
    final_reply = session.exec(
        review_query.where(SupportReview.decision == "approved")
        .order_by(col(SupportReview.created_at).desc())
        .limit(1)
    ).first()
    detail = TicketDetail(
        **ticket_data(ticket),
        final_reply=final_reply.final_reply if final_reply else None,
    )
    if can_review(current_user):
        detail.analyses = [
            AnalysisRead.model_validate(row)
            for row in session.exec(
                analyses_query.order_by(
                    col(SupportAnalysis.created_at), col(SupportAnalysis.id)
                )
            )
        ]
        detail.reviews = [
            ReviewRead.model_validate(row)
            for row in session.exec(
                review_query.order_by(
                    col(SupportReview.created_at), col(SupportReview.analysis_id)
                )
            )
        ]
        detail.logs = [
            AuditRead.model_validate(row)
            for row in session.exec(
                select(SupportLog)
                .where(SupportLog.ticket_id == ticket.id)
                .order_by(col(SupportLog.id))
            )
        ]
    return detail


@router.put("/{ticket_id}", response_model=TicketRead)
def edit_ticket(
    ticket_id: UUID,
    body: TicketEdit,
    session: SessionDep,
    current_user: CurrentUser,
) -> SupportTicket:
    ticket = get_ticket(session, current_user, ticket_id, body.version)
    if ticket.status != Status.OPEN:
        raise HTTPException(409, "Only open tickets can be edited")
    ticket.subject = body.subject
    ticket.description = body.description
    set_status(ticket, Status.OPEN)
    record(session, ticket, current_user, "ticket_edited")
    session.commit()
    session.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(
    ticket_id: UUID,
    version: Annotated[int, Query(gt=0)],
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    ticket = get_ticket(session, current_user, ticket_id, version)
    if ticket.status != Status.OPEN:
        raise HTTPException(409, "Only open tickets can be deleted")
    set_status(ticket, Status.OPEN)
    ticket.deleted_at = ticket.updated_at
    record(session, ticket, current_user, "ticket_deleted")
    session.commit()
    return Response(status_code=204)


@router.patch("/{ticket_id}/status", response_model=TicketRead)
def change_status(
    ticket_id: UUID,
    body: StatusChange,
    session: SessionDep,
    current_user: CurrentUser,
) -> SupportTicket:
    require_staff(current_user)
    ticket = get_ticket(session, current_user, ticket_id, body.version)
    previous = ticket.status
    if body.status not in TRANSITIONS.get(Status(previous), set()):
        raise HTTPException(
            409, f"Transition from {previous} to {body.status} is not allowed"
        )
    set_status(ticket, body.status)
    record(
        session,
        ticket,
        current_user,
        "status_changed",
        previous=previous,
        status=body.status,
        note=body.note,
    )
    session.commit()
    session.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/analyses", response_model=AnalysisRead, status_code=201)
def analyze(
    ticket_id: UUID,
    version: Annotated[int, Query(gt=0)],
    session: SessionDep,
    current_user: CurrentUser,
) -> SupportAnalysis:
    require_staff(current_user)
    ticket = get_ticket(session, current_user, ticket_id)
    if ticket.version != version or ticket.status not in ANALYZABLE:
        raise HTTPException(
            409,
            "Analysis requires the current version of an open or in-progress ticket",
        )
    subject, description, actor_id = ticket.subject, ticket.description, current_user.id
    session.rollback()
    outcome = run_analysis(subject, description)
    actor = session.get(User, actor_id)
    if actor is None or not actor.is_active:
        raise HTTPException(403, "Active support staff required")
    require_staff(actor)
    ticket = get_ticket(session, actor, ticket_id, version)

    triage = outcome.triage
    analysis = SupportAnalysis(
        ticket_id=ticket.id,
        provider=settings.AI_MODE,
        model=settings.DEEPSEEK_MODEL if settings.AI_MODE == "deepseek" else None,
        category=triage.category if triage else None,
        priority=triage.priority if triage else None,
        summary=triage.summary if triage else None,
        risk_flags=outcome.risk_flags,
        route=outcome.route,
        reason=outcome.reason,
        draft=outcome.draft,
        sources=[asdict(passage) for passage in outcome.sources],
    )
    session.add(analysis)
    previous = ticket.status
    set_status(ticket, Status.WAITING_REVIEW)
    record(
        session,
        ticket,
        actor,
        "analysis_recorded",
        analysis_id=str(analysis.id),
        route=analysis.route,
        reason=analysis.reason,
        previous=previous,
        status=ticket.status,
    )
    session.commit()
    session.refresh(analysis)
    return analysis


@router.post("/{ticket_id}/reviews", response_model=ReviewRead, status_code=201)
def review(
    ticket_id: UUID,
    body: ReviewInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> SupportReview:
    require_staff(current_user)
    ticket = get_ticket(session, current_user, ticket_id, body.version)
    analysis = session.exec(
        select(SupportAnalysis)
        .where(SupportAnalysis.ticket_id == ticket.id)
        .order_by(
            col(SupportAnalysis.created_at).desc(), col(SupportAnalysis.id).desc()
        )
        .limit(1)
    ).first()
    if (
        ticket.status != Status.WAITING_REVIEW
        or analysis is None
        or analysis.id != body.analysis_id
        or session.get(SupportReview, body.analysis_id) is not None
    ):
        raise HTTPException(409, "Only the current pending analysis can be reviewed")
    approved = body.decision == "approved"
    reply = (body.final_reply or analysis.draft) if approved else None
    if approved and not reply:
        raise HTTPException(422, "Provide a manual final_reply when no draft exists")
    result = SupportReview(
        analysis_id=analysis.id,
        reviewer_id=current_user.id,
        decision=body.decision,
        note=body.note,
        final_reply=reply,
    )
    session.add(result)
    set_status(ticket, Status.RESOLVED if approved else Status.IN_PROGRESS)
    record(
        session,
        ticket,
        current_user,
        "review_recorded",
        analysis_id=str(analysis.id),
        decision=body.decision,
        previous=Status.WAITING_REVIEW,
        status=ticket.status,
    )
    session.commit()
    session.refresh(result)
    return result
