from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ai_schemas import Category, Priority, Reason, Reply, Risk, Route, StrictInput


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_REVIEW = "waiting_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCreate(StrictInput):
    subject: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=6000)


class TicketEdit(TicketCreate):
    version: int = Field(gt=0, strict=True)


class StatusChange(StrictInput):
    version: int = Field(gt=0, strict=True)
    status: Status
    note: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_note(self) -> Self:
        if self.status == Status.RESOLVED and self.note is None:
            raise ValueError("A resolution note is required")
        return self


class ReviewInput(StrictInput):
    version: int = Field(gt=0, strict=True)
    analysis_id: UUID
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=1000)
    final_reply: Reply | None = None

    @model_validator(mode="after")
    def reject_final_reply(self) -> Self:
        if self.decision == "rejected" and self.final_reply is not None:
            raise ValueError("A rejected analysis cannot include a final reply")
        return self


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Evidence(ReadModel):
    passage_id: str
    title: str
    path: str
    excerpt: str


class AnalysisRead(ReadModel):
    id: UUID
    provider: Literal["mock", "deepseek"]
    model: str | None
    category: Category | None
    priority: Priority | None
    summary: str | None
    risk_flags: list[Risk]
    route: Route
    reason: Reason | None
    draft: str | None
    sources: list[Evidence]
    created_at: datetime


class ReviewRead(ReadModel):
    analysis_id: UUID
    reviewer_id: UUID | None
    decision: Literal["approved", "rejected"]
    note: str
    final_reply: str | None
    created_at: datetime


class AuditRead(ReadModel):
    action: str
    actor_id: UUID | None
    details: dict
    created_at: datetime


class TicketRead(ReadModel):
    id: UUID
    owner_id: UUID
    subject: str
    description: str
    status: Status
    version: int
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketRead):
    final_reply: str | None = None
    analyses: list[AnalysisRead] = Field(default_factory=list)
    reviews: list[ReviewRead] = Field(default_factory=list)
    logs: list[AuditRead] = Field(default_factory=list)


class TicketPage(BaseModel):
    data: list[TicketRead]
    count: int


class Capabilities(BaseModel):
    can_review: bool
    ai_mode: Literal["mock", "deepseek"]


class RoleUpdate(StrictInput):
    is_support_agent: bool = Field(strict=True)
