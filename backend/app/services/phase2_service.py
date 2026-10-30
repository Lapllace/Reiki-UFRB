"""Regras da Fase 2: disponibilidade semanal, publicação da agenda e inscrições.

Politica de concorrência (PostgreSQL): inscrições usam SELECT ... FOR UPDATE
na linha da sessão para serializar a decisão de vagas. Em SQLite os testes
unitários exercitam apenas a lógica, não o bloqueio.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityEntryKind,
    AvailabilityStatus,
    Enrollment,
    EnrollmentStatus,
    WeeklyAvailability,
)
from app.models.user import Role, User
from app.services import schedule_service
from app.services.schedule_service import week_start_of

MONDAY = 0


class AvailabilityError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class EnrollmentError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# --------------------------- Disponibilidade ---------------------------


def cycle_for_week(db: Session, week_start: date):
    return schedule_service.get_or_none_cycle(db, week_start)


def _can_edit(cycle) -> bool:
    """Disponibilidade é editável até o ciclo sair de coleta.

    `collecting_availability` e `enrollment_pending` permitem editar
    (a segunda ainda é antes da abertura das inscrições). Fases seguintes
    bloqueiam; exceções da coordenação ficam para etapa futura.
    """
    from app.models.cycle import CyclePhase

    if cycle is None:
        return False
    return cycle.phase in (
        CyclePhase.COLLECTING_AVAILABILITY,
        CyclePhase.ENROLLMENT_PENDING,
    )


def get_availability(
    db: Session, instructor_id: uuid.UUID, week_start: date
) -> WeeklyAvailability | None:
    from app.models.cycle import WeeklyCycle

    return db.scalar(
        select(WeeklyAvailability)
        .join(WeeklyCycle, WeeklyAvailability.cycle_id == WeeklyCycle.id)
        .where(
            WeeklyAvailability.instructor_id == instructor_id,
            WeeklyCycle.week_start == week_start,
        )
    )


def submit_availability(
    db: Session,
    instructor: User,
    week_start: date,
    *,
    unavailable: bool,
    entries: list[dict],
    note: str | None = None,
) -> WeeklyAvailability:
    """Cria ou atualiza a submissão do ministrante para a semana.

    - Uma submissão por (ministrante, semana) — upsert idempotente.
    - Indisponibilidade declarada não é ausência: status explícito.
    """
    from app.models.cycle import CyclePhase, WeeklyCycle
    from app.models.location import Location

    ws = week_start_of(week_start)
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    if cycle is None:
        raise AvailabilityError("cycle_not_found", "Semana sem ciclo criado.")
    if not _can_edit(cycle):
        raise AvailabilityError(
            "locked", "Submissão fechada para este ciclo."
        )

    if unavailable:
        if entries:
            raise AvailabilityError(
                "invalid_entries",
                "Não informe horários quando declarar indisponibilidade.",
            )
    elif not entries:
        raise AvailabilityError(
            "empty_entries", "Informe horários ou declare indisponibilidade."
        )

    # Valida locais e períodos.
    for e in entries:
        if e["ends_at"] <= e["starts_at"]:
            raise AvailabilityError("invalid_entries", "Período inválido.")
        if e.get("location_id") is not None:
            if db.get(Location, e["location_id"]) is None:
                raise AvailabilityError("invalid_entries", "Local inexistente.")

    # Upsert: cria ou substitui entries, preservando o registro.
    availability = db.scalar(
        select(WeeklyAvailability).where(
            WeeklyAvailability.instructor_id == instructor.id,
            WeeklyAvailability.cycle_id == cycle.id,
        )
    )
    if availability is None:
        availability = WeeklyAvailability(
            cycle_id=cycle.id,
            instructor_id=instructor.id,
            status=AvailabilityStatus.UNAVAILABLE
            if unavailable
            else AvailabilityStatus.SUBMITTED,
            submitted_at=datetime.now(UTC),
            note=note,
        )
        db.add(availability)
        db.flush()
    else:
        availability.status = (
            AvailabilityStatus.UNAVAILABLE
            if unavailable
            else AvailabilityStatus.SUBMITTED
        )
        availability.submitted_at = datetime.now(UTC)
        availability.note = note
        # Remove os horários anteriores (cascade delete-orphan).
        availability.entries.clear()
        db.flush()

    if not unavailable:
        for e in entries:
            availability.entries.append(
                AvailabilityEntry(
                    kind=AvailabilityEntryKind.AVAILABLE,
                    starts_at=e["starts_at"],
                    ends_at=e["ends_at"],
                    location_id=e.get("location_id"),
                    note=e.get("note"),
                )
            )
    db.flush()
    return availability


def count_active_instructors(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.INSTRUCTOR, User.is_active.is_(True))
    )


def count_submitted_for_cycle(db: Session, cycle_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(WeeklyAvailability)
        .where(WeeklyAvailability.cycle_id == cycle_id)
    )


def all_instructors_submitted(db: Session, cycle) -> bool:
    """Agenda só abre quando todos os ministrantes ativos submeteram
    (disponibilidade ou indisponibilidade)."""
    if cycle is None:
        return False
    return count_submitted_for_cycle(db, cycle.id) >= count_active_instructors(db)


def publish_week(db: Session, week_start: date):
    """Publica a agenda da semana: transicional e idempotente.

    - Exige que todos os ministrantes ativos tenham submetido.
    - Exige capacidade configurada em todas as sessões da semana.
    - Repetir não duplica: só transforma `collecting_availability` →
      `enrollment_pending`/`enrollment_open` uma vez.
    """
    from app.models.cycle import CyclePhase, WeeklyCycle

    ws = week_start_of(week_start)
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    if cycle is None:
        raise AvailabilityError("cycle_not_found", "Semana sem ciclo criado.")
    if not all_instructors_submitted(db, cycle):
        raise AvailabilityError(
            "incomplete",
            "Agenda só abre quando todos os ministrantes ativos submeteram.",
        )
    # Verificar que todas as sessões da semana têm capacidade definida
    from app.services.schedule_service import list_week_sessions
    from app.models.session_week import ReikiSession
    sessions = list_week_sessions(db, ws)
    for s in sessions:
        if s.capacity is None:
            raise AvailabilityError(
                "capacity_undefined",
                f"Sessão {s.id} não tem capacidade definida. "
                "Configure a capacidade antes de publicar a agenda.",
            )
    if cycle.phase == CyclePhase.COLLECTING_AVAILABILITY:
        cycle.phase = CyclePhase.ENROLLMENT_PENDING
        db.flush()
    return cycle


# ------------------------------ Inscrições ------------------------------


def get_enrollment(db: Session, enrollment_id: uuid.UUID) -> Enrollment | None:
    return db.get(Enrollment, enrollment_id)


def create_enrollment(db: Session, participant: User, session_id: uuid.UUID) -> Enrollment:
    """Inscrição decidida pelo servidor, atomicamente.

    - Sessão deve estar `open` (ou `full`, para fila).
    - Capacidade indefinida bloqueia (não é ilimitada).
    - Lock da linha da sessão (FOR UPDATE) serializa decisões simultâneas.
    - Unicidade parcial no banco impede dupla inscrição ativa.
    """
    from app.models.session_week import ReikiSession

    # Lock pessimista da sessão: decisões de vaga são serializadas.
    # of=ReikiSession evita bloquear relacionamentos joined nullable (instructor, cycle).
    session_row = db.execute(
        select(ReikiSession).where(ReikiSession.id == session_id).with_for_update(of=ReikiSession)
    ).scalar_one_or_none()
    if session_row is None:
        raise EnrollmentError("session_not_found", "Sessão não encontrada.")

    now = datetime.now(UTC)
    if session_row.status not in ("open", "full"):
        raise EnrollmentError(
            "not_open", "Inscrições fechadas para esta sessão."
        )

    existing = db.scalar(
        select(Enrollment).where(
            Enrollment.session_id == session_id,
            Enrollment.participant_id == participant.id,
            Enrollment.status.in_(["confirmed", "waitlisted"]),
        )
    )
    if existing is not None:
        raise EnrollmentError("duplicate", "Você já tem inscrição nesta sessão.")

    confirmed = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.session_id == session_id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    )
    if session_row.capacity is None:
        raise EnrollmentError(
            "capacity_undefined",
            "Capacidade desta sessão não foi configurada; inscrição indisponível.",
        )
    if confirmed < session_row.capacity:
        enrollment = Enrollment(
            session_id=session_id,
            participant_id=participant.id,
            status=EnrollmentStatus.CONFIRMED,
        )
        if session_row.status == "full":
            session_row.status = "open"
    else:
        enrollment = Enrollment(
            session_id=session_id,
            participant_id=participant.id,
            status=EnrollmentStatus.WAITLISTED,
            waitlist_position=_next_waitlist_position(db, session_id),
        )
        session_row.status = "full"
    db.add(enrollment)
    db.flush()
    # A sessão pode ter passado de `open` para `full` ao preencher a última
    # vaga (ou voltar a `open` se o estado anterior estava inconsistente).
    _reconcile_session_capacity(db, session_row)
    return enrollment


def _next_waitlist_position(db: Session, session_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(Enrollment.waitlist_position)).where(
            Enrollment.session_id == session_id,
            Enrollment.status == EnrollmentStatus.WAITLISTED,
        )
    )
    return (current or 0) + 1


def cancel_enrollment(
    db: Session, participant: User, enrollment_id: uuid.UUID, reason: str | None = None
) -> Enrollment:
    """Cancelamento transacional; promove o próximo da fila na mesma transação.

    Ordem de bloqueios: sessão → inscrição. É a mesma ordem usada por
    `create_enrollment()` (sessão) e por `apply_reallocation()` (sessão de
    destino → inscrição de origem), evitando ciclos de espera.
    """
    from app.models.session_week import ReikiSession

    # Identifica a sessão e a bloqueia ANTES da inscrição. A leitura via JOIN
    # não confia no identity map: a sessão é recarregada do banco (populate_existing)
    # já sob o lock.
    session_row = db.execute(
        select(ReikiSession)
        .join(Enrollment, Enrollment.session_id == ReikiSession.id)
        .where(Enrollment.id == enrollment_id)
        .with_for_update(of=ReikiSession)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if session_row is None:
        raise EnrollmentError("not_found", "Inscrição não encontrada.")

    # Só então bloqueia a inscrição, recarregando-a do banco.
    # of=Enrollment evita bloquear relacionamentos joined nullable.
    enrollment = db.execute(
        select(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .with_for_update(of=Enrollment)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    # Revalida depois dos bloqueios: a inscrição pode ter sido cancelada,
    # promovida ou a sessão pode ter mudado entre a leitura e o lock.
    if (
        enrollment is None
        or enrollment.participant_id != participant.id
        or enrollment.session_id != session_row.id
    ):
        raise EnrollmentError("not_found", "Inscrição não encontrada.")
    if enrollment.status not in (EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED):
        raise EnrollmentError(
            "not_cancellable",
            "Somente inscrições confirmadas ou na fila podem ser canceladas.",
        )

    if session_row.status in ("cancelled", "completed"):
        raise EnrollmentError(
            "session_closed", "Sessão não admite cancelamento neste estado."
        )

    # Guarda o estado ANTES de alterar: a promoção só é devida quando uma
    # inscrição CONFIRMED libera vaga. Cancelar alguém da fila não abre vaga.
    original_status = enrollment.status

    enrollment.status = EnrollmentStatus.CANCELLED
    enrollment.cancelled_at = datetime.now(UTC)
    enrollment.cancel_reason = reason
    if original_status == EnrollmentStatus.WAITLISTED:
        enrollment.waitlist_position = None

    # Garante que o status da inscrição esteja visível nas consultas de promoção
    # (a aplicação usa autoflush=False).
    db.flush()

    # Promoção da fila na MESMA transação somente quando uma vaga confirmada
    # se abre em sessão que ainda admite inscrições. Sessões sem cobertura ou
    # encerradas apenas renumera a fila restante.
    if (
        original_status == EnrollmentStatus.CONFIRMED
        and session_row.status in ("open", "full")
    ):
        _promote_next_from_waitlist(db, session_row)
    else:
        renumber_waitlist(db, session_row.id)
    db.flush()
    # Fecha a transação com o status da sessão coerente com as inscrições
    # confirmadas (sessões `uncovered`/`cancelled`/`completed` são preservadas).
    _reconcile_session_capacity(db, session_row)
    return enrollment


def _reconcile_session_capacity(db: Session, session_row) -> None:
    """Sincroniza `open`/`full` com a contagem de confirmados."""
    if session_row.status not in ("open", "full"):
        return
    if session_row.capacity is None:
        return
    session_row.status = (
        "full"
        if _confirmed_count(db, session_row.id) >= session_row.capacity
        else "open"
    )


def renumber_waitlist(db: Session, session_id: uuid.UUID) -> None:
    """Renumera a fila restante de forma determinística (1 = próximo)."""
    remaining = db.scalars(
        select(Enrollment)
        .where(
            Enrollment.session_id == session_id,
            Enrollment.status == EnrollmentStatus.WAITLISTED,
        )
        .order_by(
            Enrollment.waitlist_position,
            Enrollment.created_at,
            Enrollment.id,
        )
    ).all()
    for pos, enr in enumerate(remaining, start=1):
        enr.waitlist_position = pos


def _promote_next_from_waitlist(db: Session, session_row) -> None:
    # Lock pessimista da inscrição selecionada da fila.
    # of=Enrollment evita bloquear relacionamentos joined nullable.
    next_wait = db.scalar(
        select(Enrollment)
        .where(
            Enrollment.session_id == session_row.id,
            Enrollment.status == EnrollmentStatus.WAITLISTED,
        )
        .order_by(
            Enrollment.waitlist_position,
            Enrollment.created_at,
            Enrollment.id,
        )
        .limit(1)
        .with_for_update(of=Enrollment)
    )
    if next_wait is None:
        if session_row.status == "full":
            session_row.status = "open"
        return
    next_wait.status = EnrollmentStatus.CONFIRMED
    next_wait.waitlist_position = None
    # Com autoflush=False, o flush abaixo torna a promoção visível antes de
    # recalcular posições e contagem de confirmados.
    db.flush()
    renumber_waitlist(db, session_row.id)
    if session_row.capacity is not None and _confirmed_count(db, session_row.id) >= session_row.capacity:
        session_row.status = "full"


def _confirmed_count(db: Session, session_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.session_id == session_id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    )


def list_my_enrollments(db: Session, participant_id: uuid.UUID) -> list[Enrollment]:
    return list(
        db.scalars(
            select(Enrollment)
            .where(Enrollment.participant_id == participant_id)
            .order_by(Enrollment.created_at)
        )
    )
