"""Schemas da Fase 2: disponibilidade semanal e inscrições (camelCase)."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import ApiModel, camel


class AvailabilityStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    UNAVAILABLE = "unavailable"


class AvailabilityEntryKind(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class AvailabilityEntryIn(BaseModel):
    """Um horário INFORMADO pelo ministrante (não um slot pré-definido)."""

    kind: AvailabilityEntryKind = AvailabilityEntryKind.AVAILABLE
    starts_at: datetime = Field(serialization_alias=camel("starts_at"))
    ends_at: datetime = Field(serialization_alias=camel("ends_at"))
    location_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("location_id")
    )
    note: str | None = Field(default=None, max_length=200)


class AvailabilityEntryOut(ApiModel):
    id: uuid.UUID
    kind: AvailabilityEntryKind
    starts_at: datetime = Field(serialization_alias=camel("starts_at"))
    ends_at: datetime = Field(serialization_alias=camel("ends_at"))
    location_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("location_id")
    )
    note: str | None = None


class WeeklyAvailabilityOut(ApiModel):
    """`WeeklyAvailability` do frontend (contrato ajustado)."""

    week_start: str = Field(serialization_alias=camel("week_start"))
    week_end: str = Field(serialization_alias=camel("week_end"))
    status: AvailabilityStatus
    can_edit: bool = Field(serialization_alias=camel("can_edit"))
    locked_reason: str | None = Field(
        default=None, serialization_alias=camel("locked_reason")
    )
    submitted_at: datetime | None = Field(
        default=None, serialization_alias=camel("submitted_at")
    )
    note: str | None = None
    entries: list[AvailabilityEntryOut] = []


class PublishAvailabilityIn(BaseModel):
    """Submissão de disponibilidade. `unavailable=true` declara a semana inteira."""

    week_start: str = Field(serialization_alias=camel("week_start"), pattern=r"^\d{4}-\d{2}-\d{2}$")
    unavailable: bool = False
    note: str | None = Field(default=None, max_length=500)
    entries: list[AvailabilityEntryIn] = []


class EnrollmentStatus(StrEnum):
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    ATTENDED = "attended"
    CANCELLED = "cancelled"


class MyEnrollmentRefOut(ApiModel):
    id: uuid.UUID
    status: EnrollmentStatus
    waitlist_position: int | None = Field(
        default=None, serialization_alias=camel("waitlist_position")
    )


class EnrollmentOut(ApiModel):
    """`Enrollment` do frontend."""

    id: uuid.UUID
    status: EnrollmentStatus
    waitlist_position: int | None = Field(
        default=None, serialization_alias=camel("waitlist_position")
    )
    created_at: datetime = Field(serialization_alias=camel("created_at"))
    cancelled_at: datetime | None = Field(
        default=None, serialization_alias=camel("cancelled_at")
    )
    session_id: uuid.UUID = Field(serialization_alias=camel("session_id"))
    can_cancel: bool = Field(serialization_alias=camel("can_cancel"))
    cancel_blocked_reason: str | None = Field(
        default=None, serialization_alias=camel("cancel_blocked_reason")
    )


class EnrollIn(BaseModel):
    session_id: uuid.UUID = Field(serialization_alias=camel("session_id"))


class EnrollmentResultOut(ApiModel):
    """`EnrollmentResult` do frontend — decisão SEMPRE do servidor."""

    enrollment: EnrollmentOut


# ------------------------- Fase 3: cobertura -------------------------


class CoverRequestStatus(StrEnum):
    OPEN = "open"
    COVERED = "covered"
    UNCOVERED = "uncovered"


class CoverInviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    TAKEN = "taken"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class CoverInviteOut(ApiModel):
    """`CoverInvite` do frontend — sem dados de outros ministrantes."""

    id: uuid.UUID
    status: CoverInviteStatus
    session_id: uuid.UUID = Field(serialization_alias=camel("session_id"))
    created_at: datetime = Field(serialization_alias=camel("created_at"))
    expires_at: datetime | None = Field(
        default=None, serialization_alias=camel("expires_at")
    )
    # Preenchido apenas quando `accepted` (o próprio usuário assumiu).
    accepted: bool = False


class AcceptCoverResultOut(ApiModel):
    """`AcceptCoverResult` do frontend — decisão sempre do servidor."""

    outcome: str  # accepted | already_taken | expired
    invite: CoverInviteOut


class CancelSessionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
