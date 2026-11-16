from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Reply = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class Category(StrEnum):
    ACCOUNT = "account"
    BILLING = "billing"
    TECHNICAL = "technical"
    SECURITY = "security"
    OTHER = "other"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


Risk = Literal["security", "financial", "privacy", "legal"]
Route = Literal["draft_ready", "human_review"]
Reason = Literal["risk", "no_evidence", "insufficient_evidence", "model_error"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Triage(StrictInput):
    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=600)
    risk_flags: list[Risk] = Field(max_length=4)


class Draft(StrictInput):
    reply: Reply | None
    source_ids: list[str] = Field(max_length=4)

    @model_validator(mode="after")
    def require_citations_for_reply(self) -> Draft:
        if bool(self.reply) != bool(self.source_ids):
            raise ValueError(
                "Reply and source IDs must both be present or both be empty"
            )
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Source IDs must be unique")
        return self
