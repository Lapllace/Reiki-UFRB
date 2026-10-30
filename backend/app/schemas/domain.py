"""Schemas de domínio compatíveis com os tipos TypeScript do frontend.

Campos serializam em camelCase (startsAt, weekStart, mapUrl, createdAt...)
por meio de `serialization_alias` explícito — sem mágica global.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import camel


class Role(StrEnum):
    PARTICIPANT = "participant"
    INSTRUCTOR = "instructor"
    COORDINATOR = "coordinator"


class UserOut(BaseModel):
    """`User` do frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=200)


class LocationOut(BaseModel):
    """`Location` do frontend. Opcionais podem ser nulos."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None = None
    reference: str | None = Field(default=None, serialization_alias=camel("reference"))
    map_url: str | None = Field(default=None, serialization_alias=camel("map_url"))
    notes: str | None = None


class SessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    OPEN = "open"
    FULL = "full"
    CANCELLED = "cancelled"
    NEEDS_COVER = "needs_cover"
    UNCOVERED = "uncovered"
    COMPLETED = "completed"


class InstructorSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class SessionOut(BaseModel):
    """`Session` do frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    starts_at: datetime = Field(serialization_alias=camel("starts_at"))
    ends_at: datetime = Field(serialization_alias=camel("ends_at"))
    location: LocationOut
    instructor: InstructorSummaryOut | None = None
    capacity: int | None = None
    confirmed_count: int | None = Field(
        default=None, serialization_alias=camel("confirmed_count")
    )
    waitlist_count: int | None = Field(default=None, serialization_alias=camel("waitlist_count"))
    status: SessionStatus
    is_extra: bool = Field(default=False, serialization_alias=camel("is_extra"))


class WeekSessionsOut(BaseModel):
    """`WeekSessions` do frontend."""

    week_start: date = Field(serialization_alias=camel("week_start"))
    week_end: date = Field(serialization_alias=camel("week_end"))
    sessions: list[SessionOut]
    published: bool


class ErrorResponse(BaseModel):
    """Corpo de erro compatível com `messageFromBody` do frontend."""

    detail: str
    code: str | None = None
