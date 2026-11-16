from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class SupportTicket(SQLModel, table=True):
    __tablename__ = "support_ticket"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    subject: str = Field(max_length=160)
    description: str = Field(sa_type=Text)
    status: str = Field(default="open", max_length=24, index=True)
    version: int = 1
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class SupportAnalysis(SQLModel, table=True):
    __tablename__ = "support_analysis"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticket_id: UUID = Field(
        foreign_key="support_ticket.id", ondelete="CASCADE", index=True
    )
    provider: str = Field(max_length=16)
    model: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=24)
    priority: str | None = Field(default=None, max_length=12)
    summary: str | None = Field(default=None, sa_type=Text)
    risk_flags: list[str] = Field(sa_type=JSONB)
    route: str = Field(max_length=24)
    reason: str | None = Field(default=None, max_length=32)
    draft: str | None = Field(default=None, sa_type=Text)
    sources: list[dict[str, str]] = Field(sa_type=JSONB)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class SupportReview(SQLModel, table=True):
    __tablename__ = "support_review"

    analysis_id: UUID = Field(
        primary_key=True,
        foreign_key="support_analysis.id",
        ondelete="CASCADE",
    )
    reviewer_id: UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    decision: str = Field(max_length=12)
    note: str = Field(sa_type=Text)
    final_reply: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class SupportLog(SQLModel, table=True):
    __tablename__ = "support_log"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: UUID = Field(
        foreign_key="support_ticket.id", ondelete="CASCADE", index=True
    )
    actor_id: UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    action: str = Field(max_length=32)
    details: dict[str, Any] = Field(sa_type=JSONB)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
