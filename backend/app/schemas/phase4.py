"""Schemas da Fase 4: sessões extras e reorganizações."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.base import ApiModel, camel
from app.schemas.domain import SessionOut


class ReallocationStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class ReallocationAlternative(StrEnum):
    EXTRA_SESSION = "extra_session"
    FUTURE_PRIORITY = "future_priority"


class CreateExtraSessionIn(ApiModel):
    starts_at: datetime = Field(
        validation_alias=camel("starts_at"), serialization_alias=camel("starts_at")
    )
    ends_at: datetime = Field(
        validation_alias=camel("ends_at"), serialization_alias=camel("ends_at")
    )
    location_id: uuid.UUID = Field(
        validation_alias=camel("location_id"), serialization_alias=camel("location_id")
    )
    capacity: int = Field(gt=0)


class ApplyReallocationIn(ApiModel):
    alternative: ReallocationAlternative
    target_session_id: uuid.UUID | None = Field(
        default=None,
        validation_alias=camel("target_session_id"),
        serialization_alias=camel("target_session_id"),
    )


class DismissReallocationIn(ApiModel):
    reason: str | None = Field(default=None, max_length=500)


class ReallocationOut(ApiModel):
    id: uuid.UUID
    status: ReallocationStatus
    reason: str
    origin_session: SessionOut = Field(serialization_alias=camel("origin_session"))
    participant_count: int = Field(serialization_alias=camel("participant_count"))
    candidate_sessions: list[SessionOut] = Field(
        serialization_alias=camel("candidate_sessions")
    )
    applied_to: SessionOut | None = Field(
        default=None, serialization_alias=camel("applied_to")
    )
    alternative: ReallocationAlternative | None = None
    priority_granted_at: datetime | None = Field(
        default=None, serialization_alias=camel("priority_granted_at")
    )
    created_at: datetime = Field(serialization_alias=camel("created_at"))
    decided_at: datetime | None = Field(
        default=None, serialization_alias=camel("decided_at")
    )
