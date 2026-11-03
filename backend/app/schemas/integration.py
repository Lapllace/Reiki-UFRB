"""Schemas das telas já existentes na integração 4.1."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import ApiModel, camel
from app.schemas.domain import LocationOut, SessionOut
from app.schemas.phase2 import (
    AvailabilityEntryKind,
    AvailabilityStatus,
    EnrollmentStatus,
)


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


class InstructorAvailabilityStatusOut(ApiModel):
    """Estado real da disponibilidade de um ministrante em uma semana."""

    instructor_id: uuid.UUID = Field(serialization_alias=camel("instructor_id"))
    name: str
    status: AvailabilityStatus
    submitted_at: datetime | None = Field(default=None, serialization_alias=camel("submitted_at"))
    sessions_offered: int = Field(serialization_alias=camel("sessions_offered"))


class InstructorAvailabilityRowOut(InstructorAvailabilityStatusOut):
    # Mantém o contrato existente do frontend (`instructor.id`/`instructor.name`)
    # e expõe também os campos planos usados pela gestão de ciclos.
    instructor: dict


class CycleCreateIn(ApiModel):
    week_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class CycleManagementOut(ApiModel):
    """Resposta da criação/inicialização de um ciclo semanal."""

    id: uuid.UUID
    week_start: date = Field(serialization_alias=camel("week_start"))
    status: str
    instructors: list[InstructorAvailabilityStatusOut]


class CycleStateOut(ApiModel):
    """Estado do ciclo após uma transição explícita de fase."""

    id: uuid.UUID
    week_start: date = Field(serialization_alias=camel("week_start"))
    status: str


class WeeklyCycleOut(ApiModel):
    week_start: date = Field(serialization_alias=camel("week_start"))
    week_end: date = Field(serialization_alias=camel("week_end"))
    phase: str
    availability_deadline: datetime | None = Field(default=None, serialization_alias=camel("availability_deadline"))
    enrollment_opens_at: datetime | None = Field(default=None, serialization_alias=camel("enrollment_opens_at"))
    totals: CycleTotalsOut
    instructors: list[InstructorAvailabilityRowOut]


class CoordinationAvailabilityEntryOut(ApiModel):
    """Um horário ofertado pelo ministrante, como a coordenação o enxerga."""

    id: uuid.UUID
    kind: AvailabilityEntryKind
    starts_at: datetime = Field(serialization_alias=camel("starts_at"))
    ends_at: datetime = Field(serialization_alias=camel("ends_at"))
    location: LocationOut | None = None
    note: str | None = None
    # Ofertas antigas permanecem no histórico, mas não são vigentes.
    is_current: bool = Field(default=True, serialization_alias=camel("is_current"))
    # Sessão já criada a partir desta oferta (nulo enquanto não convertida).
    converted_session_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("converted_session_id")
    )


class CoordinationInstructorAvailabilityOut(ApiModel):
    """Submissão de um ministrante ativo (ou ausência de submissão)."""

    instructor_id: uuid.UUID = Field(serialization_alias=camel("instructor_id"))
    availability_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("availability_id")
    )
    name: str
    status: AvailabilityStatus
    submitted_at: datetime | None = Field(
        default=None, serialization_alias=camel("submitted_at")
    )
    note: str | None = None
    entries: list[CoordinationAvailabilityEntryOut] = Field(default_factory=list)


class WeekAvailabilitiesOut(ApiModel):
    """Consulta administrativa das disponibilidades de uma semana."""

    week_start: date = Field(serialization_alias=camel("week_start"))
    week_end: date = Field(serialization_alias=camel("week_end"))
    cycle_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("cycle_id")
    )
    cycle_phase: str | None = Field(
        default=None, serialization_alias=camel("cycle_phase")
    )
    instructors: list[CoordinationInstructorAvailabilityOut]


class CreateSessionFromAvailabilityIn(ApiModel):
    """Conversão de uma oferta em sessão regular.

    Capacidade é dado administrativo explícito; não há valor padrão.
    Local só é necessário quando a oferta não informou um.
    """

    availability_entry_id: uuid.UUID = Field(
        serialization_alias=camel("availability_entry_id")
    )
    capacity: int = Field(gt=0)
    location_id: uuid.UUID | None = Field(
        default=None, serialization_alias=camel("location_id")
    )


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
