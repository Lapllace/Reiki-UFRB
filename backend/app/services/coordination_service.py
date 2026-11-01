"""Regras administrativas do ciclo: consulta de disponibilidades e sessões.

A coordenação consulta o que cada ministrante ativo ofertou na semana e
converte uma oferta em sessão regular. A conversão NÃO publica a agenda,
NÃO abre inscrições e NÃO altera a fase do ciclo: apenas cria a sessão em
``scheduled``.

Concorrência (PostgreSQL): a linha da oferta é bloqueada com
``SELECT ... FOR UPDATE`` e o índice único em
``reiki_sessions.availability_entry_id`` é a garantia final contra converter
a mesma oferta duas vezes.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityEntryKind,
    AvailabilityStatus,
    WeeklyAvailability,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services.schedule_service import (
    lock_cycle,
    week_end_of,
    week_period_error,
    week_start_of,
)


class CoordinationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# Sessões nesses estados não bloqueiam novos horários: já não ocupam a agenda.
INACTIVE_SESSION_STATUSES = (
    SessionStatus.CANCELLED.value,
    SessionStatus.COMPLETED.value,
)

AVAILABILITY_ENTRY_UNIQUE_CONSTRAINT = "uq_reiki_sessions_availability_entry"


def _is_availability_entry_unique_violation(exc: IntegrityError) -> bool:
    """Reconhece SOMENTE a unicidade de ``availability_entry_id``.

    ``IntegrityError`` cobre qualquer restrição do banco. Converter toda
    violação em ``entry_already_converted`` esconderia, por exemplo, uma FK
    inválida. O nome da restrição vem do diagnóstico do psycopg; o fallback
    textual cobre SQLite e mensagens sem ``diag``.
    """
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name == AVAILABILITY_ENTRY_UNIQUE_CONSTRAINT:
        return True

    message = " ".join(
        part
        for part in (
            str(orig) if orig is not None else "",
            str(exc),
        )
        if part
    )
    return (
        AVAILABILITY_ENTRY_UNIQUE_CONSTRAINT in message
        or "reiki_sessions.availability_entry_id" in message
    )


# --------------------------- Disponibilidades ---------------------------


@dataclass(frozen=True)
class AvailabilityEntryView:
    id: uuid.UUID
    kind: str
    starts_at: datetime
    ends_at: datetime
    location: Location | None
    note: str | None
    is_current: bool
    converted_session_id: uuid.UUID | None


@dataclass(frozen=True)
class InstructorAvailabilityView:
    instructor_id: uuid.UUID
    availability_id: uuid.UUID | None
    name: str
    status: str
    submitted_at: datetime | None
    note: str | None
    entries: tuple[AvailabilityEntryView, ...]


@dataclass(frozen=True)
class WeekAvailabilityView:
    week_start: date
    week_end: date
    cycle: WeeklyCycle | None
    instructors: tuple[InstructorAvailabilityView, ...]


def _status_value(value) -> str:
    return value.value if isinstance(value, AvailabilityStatus) else str(value)


def get_week_availabilities(
    db: Session, week_start: date
) -> WeekAvailabilityView:
    """Estado real de cada ministrante ativo para a semana informada.

    - A data é normalizada para segunda-feira.
    - Ministrantes inativos não aparecem.
    - Sem submissão = ``pending``; indisponibilidade declarada = ``unavailable``
      (estados distintos, com ``submitted_at`` quando houver registro).
    - Sem ciclo criado, todos ficam ``pending`` e o ciclo é nulo.
    """
    ws = week_start_of(week_start)
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    instructors = db.scalars(
        select(User)
        .where(User.role == Role.INSTRUCTOR, User.is_active.is_(True))
        .order_by(User.name, User.id)
    ).all()

    submissions: dict[uuid.UUID, WeeklyAvailability] = {}
    entries_by_instructor: dict[uuid.UUID, list[AvailabilityEntry]] = {}
    converted: dict[uuid.UUID, uuid.UUID] = {}
    if cycle is not None:
        rows = db.scalars(
            select(WeeklyAvailability).where(
                WeeklyAvailability.cycle_id == cycle.id
            )
        ).all()
        submissions = {row.instructor_id: row for row in rows}
        instructor_by_availability = {
            row.id: row.instructor_id for row in rows
        }
        if instructor_by_availability:
            entries = db.scalars(
                select(AvailabilityEntry)
                .where(
                    AvailabilityEntry.availability_id.in_(
                        list(instructor_by_availability)
                    )
                )
                .order_by(
                    AvailabilityEntry.is_current.desc(),
                    AvailabilityEntry.starts_at,
                    AvailabilityEntry.id,
                )
            ).all()
            for entry in entries:
                owner = instructor_by_availability.get(entry.availability_id)
                if owner is not None:
                    entries_by_instructor.setdefault(owner, []).append(entry)
            if entries:
                converted = dict(
                    db.execute(
                        select(
                            ReikiSession.availability_entry_id,
                            ReikiSession.id,
                        ).where(
                            ReikiSession.availability_entry_id.in_(
                                [entry.id for entry in entries]
                            )
                        )
                    ).all()
                )

    result: list[InstructorAvailabilityView] = []
    for instructor in instructors:
        submission = submissions.get(instructor.id)
        if submission is None:
            result.append(
                InstructorAvailabilityView(
                    instructor_id=instructor.id,
                    availability_id=None,
                    name=instructor.name,
                    status=AvailabilityStatus.PENDING.value,
                    submitted_at=None,
                    note=None,
                    entries=(),
                )
            )
            continue
        result.append(
            InstructorAvailabilityView(
                instructor_id=instructor.id,
                availability_id=submission.id,
                name=instructor.name,
                status=_status_value(submission.status),
                submitted_at=submission.submitted_at,
                note=submission.note,
                entries=tuple(
                    AvailabilityEntryView(
                        id=entry.id,
                        kind=entry.kind.value
                        if isinstance(entry.kind, AvailabilityEntryKind)
                        else str(entry.kind),
                        starts_at=entry.starts_at,
                        ends_at=entry.ends_at,
                        location=entry.location,
                        note=entry.note,
                        is_current=entry.is_current,
                        converted_session_id=converted.get(entry.id),
                    )
                    for entry in entries_by_instructor.get(instructor.id, [])
                ),
            )
        )
    return WeekAvailabilityView(
        week_start=ws,
        week_end=week_end_of(ws),
        cycle=cycle,
        instructors=tuple(result),
    )


# ----------------------------- Sessões ---------------------------------


def _entry_kind(entry: AvailabilityEntry) -> str:
    return (
        entry.kind.value
        if isinstance(entry.kind, AvailabilityEntryKind)
        else str(entry.kind)
    )


def _resolve_location(
    db: Session,
    entry: AvailabilityEntry,
    requested_location_id: uuid.UUID | None,
) -> Location:
    """Local da oferta prevalece; sem oferta, a coordenação deve informar um."""
    if entry.location_id is not None:
        if (
            requested_location_id is not None
            and requested_location_id != entry.location_id
        ):
            raise CoordinationError(
                "location_mismatch",
                "O local informado difere do local ofertado pelo ministrante.",
            )
        location_id = entry.location_id
    else:
        if requested_location_id is None:
            raise CoordinationError(
                "location_required",
                "A oferta não informa local; informe o local da sessão.",
            )
        location_id = requested_location_id

    location = db.execute(
        select(Location)
        .where(Location.id == location_id)
        .with_for_update(of=Location)
    ).scalar_one_or_none()
    if location is None:
        raise CoordinationError("location_not_found", "Local não encontrado.")
    if not location.is_active:
        raise CoordinationError(
            "location_inactive", "O local não existe ou está inativo."
        )
    return location


def has_session_conflict(
    db: Session,
    *,
    starts_at: datetime,
    ends_at: datetime,
    instructor_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
) -> bool:
    """Sobreposição real de intervalos entre sessões ativas.

    Dois intervalos se sobrepõem quando ``existente.início < novo.fim`` e
    ``existente.fim > novo.início``. Canceladas/concluídas não ocupam agenda.
    """
    stmt = select(ReikiSession.id).where(
        ReikiSession.starts_at < ends_at,
        ReikiSession.ends_at > starts_at,
        ReikiSession.status.not_in(INACTIVE_SESSION_STATUSES),
    )
    if instructor_id is not None:
        stmt = stmt.where(ReikiSession.instructor_id == instructor_id)
    if location_id is not None:
        stmt = stmt.where(ReikiSession.location_id == location_id)
    return db.scalar(stmt.limit(1)) is not None


def create_regular_session(
    db: Session,
    coordinator: User,
    week_start: date,
    *,
    availability_entry_id: uuid.UUID,
    capacity: int,
    location_id: uuid.UUID | None = None,
) -> ReikiSession:
    """Cria uma sessão regular a partir de uma oferta de disponibilidade.

    Regras:
    - o ciclo da semana precisa existir e estar em ``collecting_availability``;
    - a oferta precisa pertencer a esse ciclo, ser ``kind=available`` e ser
      vigente;
    - o ministrante precisa estar ativo;
    - o intervalo é revalidado contra a semana institucional e usado
      exatamente como ofertado;
    - a capacidade é explícita e positiva;
    - o local é o da oferta; se ela não informar, é obrigatório informar;
    - não pode haver sobreposição com outra sessão ativa do ministrante nem
      do local;
    - a mesma oferta não pode ser convertida duas vezes.

    A sessão nasce ``scheduled`` e ``is_extra=False``. A fase do ciclo e a
    publicação da agenda não são alteradas.
    """
    if coordinator.role != Role.COORDINATOR:
        raise CoordinationError(
            "forbidden", "Apenas a coordenação pode criar sessões regulares."
        )
    if capacity is None or capacity <= 0:
        raise CoordinationError(
            "invalid_capacity", "A capacidade deve ser maior que zero."
        )

    ws = week_start_of(week_start)
    # Primeiro bloqueio: o ciclo. Serializa criação de sessão, reenvio de
    # disponibilidade e publicação, e recarrega a fase consolidada.
    cycle = lock_cycle(db, ws)
    if cycle is None:
        raise CoordinationError(
            "cycle_not_found", "Semana sem ciclo criado."
        )
    if cycle.phase != CyclePhase.COLLECTING_AVAILABILITY:
        raise CoordinationError(
            "invalid_cycle_phase",
            "Sessões regulares só podem ser criadas durante a coleta de "
            "disponibilidade.",
        )

    # Bloqueia a oferta antes de qualquer decisão: serializa conversões
    # simultâneas da mesma oferta e eventuais reenvios do ministrante.
    entry = db.execute(
        select(AvailabilityEntry)
        .where(AvailabilityEntry.id == availability_entry_id)
        .with_for_update(of=AvailabilityEntry)
    ).scalar_one_or_none()
    if entry is None:
        raise CoordinationError(
            "entry_not_found", "Oferta de disponibilidade não encontrada."
        )

    availability = db.get(WeeklyAvailability, entry.availability_id)
    if availability is None:
        raise CoordinationError(
            "entry_not_found", "Oferta de disponibilidade não encontrada."
        )
    if availability.cycle_id != cycle.id:
        raise CoordinationError(
            "entry_not_in_cycle",
            "A oferta de disponibilidade pertence a outra semana.",
        )

    # Revalida o intervalo: a oferta pode ter sido gravada antes desta regra
    # ou alterada por outro caminho. O horário validado é usado sem ajustes.
    period_error = week_period_error(entry.starts_at, entry.ends_at, ws)
    if period_error == "invalid_period":
        raise CoordinationError(
            "invalid_period", "O período da oferta é inválido."
        )
    if period_error == "outside_week":
        raise CoordinationError(
            "outside_week",
            "O período da oferta está fora da semana do ciclo.",
        )

    if _entry_kind(entry) != AvailabilityEntryKind.AVAILABLE.value:
        raise CoordinationError(
            "entry_unavailable",
            "Somente horários ofertados como disponíveis podem virar sessão.",
        )

    # Depois do lock da oferta, uma conversão anterior já está visível.
    existing = db.scalar(
        select(ReikiSession.id).where(
            ReikiSession.availability_entry_id == entry.id
        )
    )
    if existing is not None:
        raise CoordinationError(
            "entry_already_converted",
            "Esta oferta de disponibilidade já foi convertida em sessão.",
        )
    if not entry.is_current:
        raise CoordinationError(
            "entry_not_current",
            "Esta oferta é histórica e não pode mais ser convertida.",
        )

    instructor = db.execute(
        select(User)
        .where(User.id == availability.instructor_id)
        .with_for_update(of=User)
    ).scalar_one_or_none()
    if (
        instructor is None
        or instructor.role != Role.INSTRUCTOR
        or not instructor.is_active
    ):
        raise CoordinationError(
            "instructor_inactive",
            "O ministrante da oferta não está ativo.",
        )

    location = _resolve_location(db, entry, location_id)

    if has_session_conflict(
        db,
        starts_at=entry.starts_at,
        ends_at=entry.ends_at,
        instructor_id=instructor.id,
    ):
        raise CoordinationError(
            "instructor_conflict",
            "O ministrante já tem sessão ativa nesse intervalo.",
        )
    if has_session_conflict(
        db,
        starts_at=entry.starts_at,
        ends_at=entry.ends_at,
        location_id=location.id,
    ):
        raise CoordinationError(
            "location_conflict",
            "O local já tem sessão ativa nesse intervalo.",
        )

    session_row = ReikiSession(
        cycle_id=cycle.id,
        instructor_id=instructor.id,
        location_id=location.id,
        availability_entry_id=entry.id,
        starts_at=entry.starts_at,
        ends_at=entry.ends_at,
        capacity=capacity,
        status=SessionStatus.SCHEDULED,
        is_extra=False,
        created_by=coordinator.id,
    )
    try:
        with db.begin_nested():
            db.add(session_row)
            db.flush()
    except IntegrityError as exc:
        # Fallback do índice único: outra transação converteu a oferta
        # entre a checagem e o INSERT. Outras violações de integridade
        # (FK, PK, etc.) NÃO são conversão duplicada e seguem propagadas.
        if not _is_availability_entry_unique_violation(exc):
            raise
        raise CoordinationError(
            "entry_already_converted",
            "Esta oferta de disponibilidade já foi convertida em sessão.",
        ) from exc
    db.flush()
    return session_row
