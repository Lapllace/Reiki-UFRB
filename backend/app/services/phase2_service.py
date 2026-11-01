"""Regras da Fase 2: disponibilidade semanal, publicação da agenda e inscrições.

Politica de concorrência (PostgreSQL): inscrições usam SELECT ... FOR UPDATE
na linha da sessão para serializar a decisão de vagas. Em SQLite os testes
unitários exercitam apenas a lógica, não o bloqueio.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityEntryKind,
    AvailabilityStatus,
    Enrollment,
    EnrollmentStatus,
    WeeklyAvailability,
)
from app.models.session_week import ReikiSession, SessionStatus
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
    """Disponibilidade só é editável enquanto o ciclo coleta disponibilidade.

    A montagem da agenda termina quando ela é publicada (`enrollment_pending`);
    a partir daí o reenvio é bloqueado, inclusive nas fases seguintes.
    """
    from app.models.cycle import CyclePhase

    if cycle is None:
        return False
    return cycle.phase == CyclePhase.COLLECTING_AVAILABILITY


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
    # O ciclo é o primeiro e único bloqueio de coordenação entre submissões e
    # publicação. A fase só é verificada depois de recarregar a instância.
    cycle = schedule_service.lock_cycle(db, ws)
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

    # Valida locais e períodos contra a semana institucional do ciclo.
    for e in entries:
        error = schedule_service.week_period_error(
            e["starts_at"], e["ends_at"], ws
        )
        if error == "invalid_period":
            raise AvailabilityError("invalid_entries", "Período inválido.")
        if error == "outside_week":
            raise AvailabilityError(
                "outside_week",
                "O período deve estar dentro da semana do ciclo.",
            )
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
        # Preserva o histórico: as ofertas anteriores deixam de ser vigentes
        # em vez de serem apagadas. Assim a FK das sessões já convertidas
        # continua apontando para a oferta original.
        for entry in availability.entries:
            entry.is_current = False
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
                    is_current=True,
                )
            )
    db.flush()
    return availability


@dataclass(frozen=True)
class InstructorAvailabilitySummary:
    """Resumo do estado real de um ministrante ativo para uma semana."""

    instructor_id: uuid.UUID
    name: str
    status: str
    submitted_at: datetime | None
    sessions_offered: int


def instructor_availability_summary(
    db: Session, week_start: date
) -> list[InstructorAvailabilitySummary]:
    """Estado real de cada ministrante ativo para a semana informada.

    A data é normalizada para segunda-feira. Ministrantes inativos não entram
    no resultado. Sem ciclo criado, todos ficam `pending` (não é o mesmo que
    indisponibilidade).
    """
    from app.models.cycle import WeeklyCycle

    ws = week_start_of(week_start)
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    instructors = db.scalars(
        select(User)
        .where(User.role == Role.INSTRUCTOR, User.is_active.is_(True))
        .order_by(User.name, User.id)
    ).all()

    submissions: dict[uuid.UUID, tuple[WeeklyAvailability, int]] = {}
    if cycle is not None:
        rows = db.execute(
            select(WeeklyAvailability, func.count(AvailabilityEntry.id))
            .outerjoin(
                AvailabilityEntry,
                and_(
                    AvailabilityEntry.availability_id == WeeklyAvailability.id,
                    AvailabilityEntry.kind == AvailabilityEntryKind.AVAILABLE.value,
                    AvailabilityEntry.is_current.is_(True),
                ),
            )
            .where(WeeklyAvailability.cycle_id == cycle.id)
            .group_by(WeeklyAvailability.id)
        ).all()
        submissions = {sub.instructor_id: (sub, count) for sub, count in rows}

    summary: list[InstructorAvailabilitySummary] = []
    for instructor in instructors:
        submission, available_count = submissions.get(instructor.id, (None, 0))
        if submission is None:
            status = AvailabilityStatus.PENDING.value
            submitted_at = None
            sessions_offered = 0
        elif submission.status == AvailabilityStatus.UNAVAILABLE:
            status = AvailabilityStatus.UNAVAILABLE.value
            submitted_at = _submission_timestamp(submission)
            sessions_offered = 0
        else:
            # Submissão com `unavailable=False`: conta apenas entradas `available`.
            status = AvailabilityStatus.SUBMITTED.value
            submitted_at = _submission_timestamp(submission)
            sessions_offered = available_count
        summary.append(
            InstructorAvailabilitySummary(
                instructor_id=instructor.id,
                name=instructor.name,
                status=status,
                submitted_at=submitted_at,
                sessions_offered=sessions_offered,
            )
        )
    return summary


def _submission_timestamp(submission: WeeklyAvailability) -> datetime:
    return (
        submission.submitted_at
        or submission.updated_at
        or submission.created_at
    )


def create_or_get_cycle(db: Session, week_start: date):
    """Cria o ciclo da semana se não existir; devolve ``(ciclo, criado)``.

    Idempotente e seguro sob concorrência: a unicidade de `week_start` no banco
    decide a corrida; o perdedor relê o ciclo criado pelo vencedor.
    """
    from app.models.cycle import CyclePhase, WeeklyCycle

    ws = week_start_of(week_start)
    existing = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    if existing is not None:
        return existing, False

    cycle = WeeklyCycle(
        week_start=ws,
        phase=CyclePhase.COLLECTING_AVAILABILITY,
    )
    try:
        with db.begin_nested():
            db.add(cycle)
            db.flush()
    except IntegrityError:
        # Outra transação criou o mesmo ciclo. O INSERT bloqueou até ela
        # concluir; a releitura enxerga o registro vencedor.
        if cycle in db:
            db.expunge(cycle)
        existing = db.scalar(
            select(WeeklyCycle).where(WeeklyCycle.week_start == ws)
        )
        if existing is None:
            raise
        return existing, False
    return cycle, True


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
        .join(User, WeeklyAvailability.instructor_id == User.id)
        .where(
            WeeklyAvailability.cycle_id == cycle_id,
            User.role == Role.INSTRUCTOR,
            User.is_active.is_(True)
        )
    )


def all_instructors_submitted(db: Session, cycle) -> bool:
    """Agenda só abre quando todos os ministrantes ativos submeteram
    (disponibilidade ou indisponibilidade)."""
    if cycle is None:
        return False
    return count_submitted_for_cycle(db, cycle.id) >= count_active_instructors(db)


def _session_status_value(session_row: ReikiSession) -> str:
    status = session_row.status
    return status.value if isinstance(status, SessionStatus) else str(status)


def _validate_session_periods(
    sessions: list[ReikiSession], week_start: date
) -> None:
    """Horários coerentes e dentro da semana institucional.

    Sessões canceladas/concluídas são preservadas como histórico e não
    impedem a publicação ou a abertura.
    """
    for session_row in sessions:
        if _session_status_value(session_row) in (
            SessionStatus.CANCELLED.value,
            SessionStatus.COMPLETED.value,
        ):
            continue
        error = schedule_service.week_period_error(
            session_row.starts_at, session_row.ends_at, week_start
        )
        if error == "invalid_period":
            raise AvailabilityError(
                "invalid_period",
                f"Sessão {session_row.id} tem período inválido.",
            )
        if error == "outside_week":
            raise AvailabilityError(
                "outside_week",
                f"Sessão {session_row.id} está fora da semana do ciclo.",
            )


def _validate_session_capacity(
    sessions: list[ReikiSession],
    *,
    statuses: tuple[str, ...] | None = None,
) -> None:
    """Capacidade explícita e positiva.

    ``statuses=None`` mantém a validação de publicação sobre todas as sessões
    da semana (comportamento anterior). Na abertura, apenas estados que podem
    receber inscrição são exigidos; canceladas/concluídas/sem cobertura são
    preservadas.
    """
    for session_row in sessions:
        if statuses is not None and _session_status_value(session_row) not in statuses:
            continue
        if session_row.capacity is None:
            raise AvailabilityError(
                "capacity_undefined",
                f"Sessão {session_row.id} não tem capacidade definida. "
                "Configure a capacidade antes de publicar a agenda.",
            )
        if session_row.capacity <= 0:
            raise AvailabilityError(
                "invalid_capacity",
                f"Sessão {session_row.id} tem capacidade inválida.",
            )


def _validate_no_session_conflicts(sessions: list[ReikiSession]) -> None:
    """Rejeita sobreposição de ministrante ou local em sessões ativas.

    Canceladas/concluídas não ocupam a agenda. A verificação é feita em
    memória sobre as sessões já bloqueadas/validadas pela operação atual.
    """
    active = [
        session_row
        for session_row in sessions
        if _session_status_value(session_row)
        not in (SessionStatus.CANCELLED.value, SessionStatus.COMPLETED.value)
    ]
    ordered = sorted(active, key=lambda row: (row.starts_at, str(row.id)))
    last_end: dict[tuple[str, uuid.UUID], datetime] = {}
    for session_row in ordered:
        keys: list[tuple[str, uuid.UUID]] = [("location", session_row.location_id)]
        if session_row.instructor_id is not None:
            keys.append(("instructor", session_row.instructor_id))
        for key in keys:
            previous_end = last_end.get(key)
            if previous_end is not None and session_row.starts_at < previous_end:
                label = "ministrante" if key[0] == "instructor" else "local"
                raise AvailabilityError(
                    "schedule_conflict",
                    f"A agenda tem sessões sobrepostas para o mesmo {label}.",
                )
        for key in keys:
            current_end = last_end.get(key)
            if current_end is None or session_row.ends_at > current_end:
                last_end[key] = session_row.ends_at


def publish_week(db: Session, week_start: date):
    """Publica formalmente a agenda da semana.

    - Normaliza a data para segunda-feira e exige o ciclo existente.
    - Exige que todos os ministrantes ATIVOS tenham submetido disponibilidade
      ou declarado indisponibilidade.
    - Preserva as validações de capacidade e acrescenta horários/consistência.
    - ``collecting_availability`` → ``enrollment_pending`` apenas uma vez.
      Publicações repetidas (inclusive em fases posteriores) são idempotentes
      e nunca regridem o ciclo.
    - NÃO abre inscrições: isso é uma ação separada e explícita.
    """
    ws = week_start_of(week_start)
    # Mesma ordem de bloqueio das submissões e da criação de sessões.
    cycle = schedule_service.lock_cycle(db, ws)
    if cycle is None:
        raise AvailabilityError("cycle_not_found", "Semana sem ciclo criado.")

    # Já publicado/avançado: repetir não altera fase nem volta atrás.
    if cycle.phase != CyclePhase.COLLECTING_AVAILABILITY:
        return cycle

    if not all_instructors_submitted(db, cycle):
        raise AvailabilityError(
            "incomplete",
            "Agenda só abre quando todos os ministrantes ativos submeteram.",
        )

    # Publicação valida TODAS as sessões vinculadas ao ciclo — não apenas as
    # que caem nos limites temporais da semana usados pela listagem pública.
    # Uma sessão com `cycle_id` do ciclo e horário fora da semana institucional
    # precisa bloquear a publicação em vez de ser silenciosamente ignorada.
    sessions = list(
        db.scalars(
            select(ReikiSession)
            .where(ReikiSession.cycle_id == cycle.id)
            .order_by(ReikiSession.starts_at, ReikiSession.id)
            .execution_options(populate_existing=True)
        ).unique()
    )
    _validate_session_periods(sessions, ws)
    _validate_session_capacity(sessions)
    _validate_no_session_conflicts(sessions)

    cycle.phase = CyclePhase.ENROLLMENT_PENDING
    db.flush()
    return cycle


def open_enrollment(db: Session, week_start: date):
    """Abre explicitamente as inscrições de um ciclo já publicado.

    - Exige ``enrollment_pending``; nunca abre direto da coleta.
    - Revalida a agenda publicada (sessões, horários, capacidade e conflitos).
    - Bloqueia o ciclo e as sessões antes de decidir, preservando
      canceladas/concluídas/sem cobertura.
    - ``scheduled`` com cobertura → ``open`` (ou ``full`` se já lotada).
    - Repetição em ``enrollment_open`` é idempotente. Fases posteriores não
      regridem.
    """
    ws = week_start_of(week_start)
    cycle = schedule_service.lock_cycle(db, ws)
    if cycle is None:
        raise AvailabilityError("cycle_not_found", "Semana sem ciclo criado.")

    if cycle.phase == CyclePhase.ENROLLMENT_OPEN:
        return cycle
    if cycle.phase == CyclePhase.COLLECTING_AVAILABILITY:
        raise AvailabilityError(
            "not_published",
            "Publique a agenda antes de abrir as inscrições.",
        )
    if cycle.phase != CyclePhase.ENROLLMENT_PENDING:
        raise AvailabilityError(
            "invalid_cycle_phase",
            "O ciclo já avançou para uma fase que não admite abertura de inscrições.",
        )

    # Bloqueia as sessões do ciclo em ordem determinística. Isso serializa a
    # abertura com cancelamentos/cobertura, que bloqueiam a linha da sessão.
    sessions = list(
        db.scalars(
            select(ReikiSession)
            .where(ReikiSession.cycle_id == cycle.id)
            .order_by(ReikiSession.starts_at, ReikiSession.id)
            .with_for_update(of=ReikiSession)
            .execution_options(populate_existing=True)
        ).unique()
    )
    if not sessions:
        raise AvailabilityError(
            "empty_agenda",
            "A agenda publicada não tem sessões para abrir inscrições.",
        )

    _validate_session_periods(sessions, ws)
    _validate_session_capacity(
        sessions,
        statuses=(
            SessionStatus.SCHEDULED.value,
            SessionStatus.OPEN.value,
            SessionStatus.FULL.value,
        ),
    )
    _validate_no_session_conflicts(sessions)

    enrollable = [
        session_row
        for session_row in sessions
        if session_row.instructor_id is not None
        and _session_status_value(session_row)
        in (
            SessionStatus.SCHEDULED.value,
            SessionStatus.OPEN.value,
            SessionStatus.FULL.value,
        )
    ]
    if not enrollable:
        raise AvailabilityError(
            "no_enrollable_sessions",
            "A agenda publicada não tem sessões com cobertura para inscrição.",
        )

    # A abertura reconcilia o status com as inscrições efetivamente
    # confirmadas. O status anterior (`full`) não é prova de lotação: pode
    # estar desatualizado depois de cancelamentos ou ajustes manuais.
    confirmed_counts = _confirmed_counts(db, [row.id for row in enrollable])
    decisions: list[tuple[ReikiSession, SessionStatus]] = []
    for session_row in enrollable:
        confirmed = confirmed_counts.get(session_row.id, 0)
        capacity = session_row.capacity
        if capacity is None or capacity <= 0:
            raise AvailabilityError(
                "invalid_capacity",
                f"Sessão {session_row.id} tem capacidade inválida.",
            )
        if confirmed > capacity:
            raise AvailabilityError(
                "capacity_exceeded",
                f"Sessão {session_row.id} tem {confirmed} inscrições confirmadas "
                f"para capacidade {capacity}; corrija a inconsistência antes de "
                "abrir as inscrições.",
            )
        decisions.append(
            (
                session_row,
                SessionStatus.FULL
                if confirmed == capacity
                else SessionStatus.OPEN,
            )
        )

    # Só altera a agenda depois de todas as sessões passarem na validação.
    for session_row, status in decisions:
        session_row.status = status

    cycle.phase = CyclePhase.ENROLLMENT_OPEN
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

    # 1. Leitura inicial SEM lock para descobrir o cycle_id antes de qualquer bloqueio.
    session_preview = db.execute(
        select(ReikiSession).where(ReikiSession.id == session_id)
    ).scalar_one_or_none()
    if session_preview is None:
        raise EnrollmentError('session_not_found', 'Sessão não encontrada.')

    # 2. Se há ciclo associado, bloqueia o WeeklyCycle PRIMEIRO (ordem: ciclo → sessão).
    cycle = None
    if not session_preview.is_extra and session_preview.cycle_id is not None:
        cycle = db.execute(
            select(WeeklyCycle)
            .where(WeeklyCycle.id == session_preview.cycle_id)
            .with_for_update(of=WeeklyCycle)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if cycle is not None:
            db.refresh(cycle)

    # 3. Agora bloqueia a ReikiSession com FOR UPDATE e populate_existing.
    session_row = db.execute(
        select(ReikiSession)
        .where(ReikiSession.id == session_id)
        .with_for_update(of=ReikiSession)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if session_row is None:
        raise EnrollmentError('session_not_found', 'Sessão não encontrada.')

    # 4. Confirma que o cycle_id não mudou entre a leitura prévia e o lock.
    if session_row.cycle_id != session_preview.cycle_id:
        raise EnrollmentError(
            'cycle_changed',
            'O ciclo associado à sessão foi alterado entre a leitura e o bloqueio.',
        )

    # Sessões regulares vinculadas a um ciclo só permitem inscrição quando o ciclo
    # está em ENROLLMENT_OPEN. Sessões extras (is_extra=True) são independentes.
    if cycle is not None and cycle.phase != CyclePhase.ENROLLMENT_OPEN:
        raise EnrollmentError(
            'cycle_not_open',
            f"Inscrições só são permitidas quando o ciclo está em ENROLLMENT_OPEN. "
            f"Fase atual: {cycle.phase}.",
        )
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

    confirmed = _confirmed_count(db, session_id)
    if session_row.capacity is None:
        raise EnrollmentError(
            "capacity_undefined",
            "Capacidade desta sessão não foi configurada; inscrição indisponível.",
        )
    if confirmed > session_row.capacity:
        # Estado inconsistente: não amplia a fila nem mascara a capacidade.
        raise EnrollmentError(
            "capacity_exceeded",
            "As inscrições confirmadas excedem a capacidade desta sessão.",
        )
    if confirmed < session_row.capacity:
        enrollment = Enrollment(
            session_id=session_id,
            participant_id=participant.id,
            status=EnrollmentStatus.CONFIRMED,
        )
        # `full` com vaga é estado desatualizado; a contagem real decide.
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


def _confirmed_counts(
    db: Session, session_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Contagem de inscrições CONFIRMED por sessão, em uma única consulta."""
    if not session_ids:
        return {}
    rows = db.execute(
        select(Enrollment.session_id, func.count())
        .where(
            Enrollment.session_id.in_(session_ids),
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
        .group_by(Enrollment.session_id)
    ).all()
    return {session_id: count for session_id, count in rows}


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
