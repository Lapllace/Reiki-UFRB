"""Schemas das telas já existentes na integração 4.1."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import ApiModel, camel
from app.schemas.domain import SessionOut
from app.schemas.phase2 import EnrollmentStatus


class RosterEntryOut(ApiModel):
    enrollment_id: uuid.UUID = Field(serialization_alias=camel("enrollment_id"))
    participant_name: str = Field(serialization_alias=camel("participant_name"))
    status: EnrollmentStatus
    waitlist_position: int | None = Field(default=None, serialization_alias=camel("waitlist_position"))


class InstructorSessionOut(ApiModel):
    session: SessionOut
    can_cancel: bool = Field(serialization_alias=camel("can_cancel"))
    cancel_blocked_reason: str | None = Field(default=None, serialization_alias=camel("cancel_blocked_reason"))


class CoverRequestOut(ApiModel):
    id: uuid.UUID
    status: str
    session: SessionOut
    original_instructor: dict | None = Field(default=None, serialization_alias=camel("original_instructor"))
    reason: str | None = None
    invited_count: int = Field(serialization_alias=camel("invited_count"))
    created_at: datetime = Field(serialization_alias=camel("created_at"))
    resolved_at: datetime | None = Field(default=None, serialization_alias=camel("resolved_at"))
    covered_by: dict | None = Field(default=None, serialization_alias=camel("covered_by"))


class CycleTotalsOut(ApiModel):
    sessions: int
    capacity: int | None
    confirmed: int | None
    waitlisted: int | None
    uncovered: int
    open_cover_requests: int = Field(serialization_alias=camel("open_cover_requests"))
    pending_reallocations: int = Field(serialization_alias=camel("pending_reallocations"))


class InstructorAvailabilityRowOut(ApiModel):
    instructor: dict
    status: str
    submitted_at: datetime | None = Field(default=None, serialization_alias=camel("submitted_at"))
    sessions_offered: int = Field(serialization_alias=camel("sessions_offered"))


class WeeklyCycleOut(ApiModel):
    week_start: date = Field(serialization_alias=camel("week_start"))
    week_end: date = Field(serialization_alias=camel("week_end"))
    phase: str
    availability_deadline: datetime | None = Field(default=None, serialization_alias=camel("availability_deadline"))
    enrollment_opens_at: datetime | None = Field(default=None, serialization_alias=camel("enrollment_opens_at"))
    totals: CycleTotalsOut
    instructors: list[InstructorAvailabilityRowOut]


class AppNotificationOut(ApiModel):
    id: uuid.UUID
    kind: str
    title: str
    message: str
    created_at: datetime = Field(serialization_alias=camel("created_at"))
    read: bool
    session_id: uuid.UUID | None = Field(default=None, serialization_alias=camel("session_id"))


class AuditEventOut(ApiModel):
    id: uuid.UUID
    kind: str
    at: datetime
    actor: str | None = None
    description: str
    session_id: uuid.UUID | None = Field(default=None, serialization_alias=camel("session_id"))
