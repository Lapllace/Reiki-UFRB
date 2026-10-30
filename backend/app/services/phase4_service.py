"""Regras da Fase 4: reorganização administrativa e sessões extras."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.phase2 import Enrollment, EnrollmentStatus
from app.models.phase4 import (
    ReallocationAlternative,
    ReallocationCase,
    ReallocationHistory,
    ReallocationStatus,
)
from app.models.phase41 import AuditEvent
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services.phase2_service import renumber_waitlist


class ReallocationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(UTC)


def _history(db: Session, case_id: uuid.UUID, action: str, actor: User | None, detail: str | None = None) -> None:
    """Register a history event linked to a ReallocationCase.

    This function must NOT be used with arbitrary case_id for session
    opening — use log_audit_event() instead for standalone audit events.
    """
    db.add(
        ReallocationHistory(
            case_id=case_id,
            action=action,
            actor_id=actor.id if actor else None,
            detail=detail,
            created_at=_now(),
        )
    )


def log_audit_event(
    db: Session,
    *,
    kind: str,
    description: str,
    actor: User | None,
    session_id: uuid.UUID | None = None,
) -> AuditEvent:
    """Register a standalone audit event (e.g. session opening).

    This uses the AuditEvent model, not ReallocationHistory, so it does
    not require a ReallocationCase association.
    """
    event = AuditEvent(
        kind=kind,
        description=description,
        actor_id=actor.id if actor else None,
        session_id=session_id,
        created_at=_now(),
    )
    db.add(event)
    db.flush()
    return event


def create_cases_for_uncovered_session(
    db: Session, session_id: uuid.UUID, actor: User | None = None
) -> list[ReallocationCase]:
    """Cria no máximo um caso por inscrição ativa da sessão sem cobertura."""
    enrollments = db.scalars(
        select(Enrollment).where(
            Enrollment.session_id == session_id,
            Enrollment.status.in_(
                (EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED)
            ),
        )
    ).all()
    cases: list[ReallocationCase] = []
    for enrollment in enrollments:
        existing = db.scalar(
            select(ReallocationCase).where(
                ReallocationCase.origin_enrollment_id == enrollment.id
            )
        )
        if existing is not None:
            cases.append(existing)
            continue
        case = ReallocationCase(
            origin_session_id=session_id,
            origin_enrollment_id=enrollment.id,
            participant_id=enrollment.participant_id,
            status=ReallocationStatus.PENDING,
        )
        try:
            with db.begin_nested():
                db.add(case)
                db.flush()
        except IntegrityError:
            case = db.scalar(
                select(ReallocationCase).where(
                    ReallocationCase.origin_enrollment_id == enrollment.id
                )
            )
            if case is None:
                raise
        else:
            _history(db, case.id, "created", actor, "Inscrição afetada por sessão sem cobertura.")
        cases.append(case)
    db.flush()
    return cases


def create_extra_session(
    db: Session,
    coordinator: User,
    *,
    starts_at: datetime,
    ends_at: datetime,
    location_id: uuid.UUID,
    capacity: int,
) -> ReikiSession:
    if coordinator.role != Role.COORDINATOR:
        raise ReallocationError("forbidden", "Apenas a coordenação pode criar sessões extras.")
    if ends_at <= starts_at:
        raise ReallocationError("invalid_period", "O horário final deve ser posterior ao inicial.")
    if capacity <= 0:
        raise ReallocationError("invalid_capacity", "A capacidade deve ser maior que zero.")
    location = db.get(Location, location_id)
    if location is None or not location.is_active:
        raise ReallocationError("location_inactive", "O local não existe ou está inativo.")
    session = ReikiSession(
        starts_at=starts_at,
        ends_at=ends_at,
        location_id=location.id,
        capacity=capacity,
        status=SessionStatus.SCHEDULED,
        is_extra=True,
        created_by=coordinator.id,
    )
    db.add(session)
    db.flush()
    return session


def open_session(
    db: Session, coordinator: User, session_id: uuid.UUID
) -> ReikiSession:
    """Abrir uma sessão (SCHEDULED → OPEN).

    Regras (Point 3 do plano):
    - NÃO permitir que sessão FULL seja reaberta automaticamente.
    - Apenas SCHEDULED pode transitar para OPEN.
    - Confirmar contagens de inscrições e estado real no banco antes.
    """
    if coordinator.role != Role.COORDINATOR:
        raise ReallocationError("forbidden", "Apenas a coordenação pode abrir sessões.")

    # Lock pessimista da sessão para evitar transições concorrentes.
    # of=ReikiSession evita bloquear relacionamentos joined nullable (instructor, cycle).
    session = db.execute(
        select(ReikiSession).where(ReikiSession.id == session_id).with_for_update(of=ReikiSession)
    ).scalar_one_or_none()
    if session is None:
        raise ReallocationError("not_found", "Sessão não encontrada.")

    # Refresh para garantir que o objeto reflita o estado atual do banco após o lock
    db.refresh(session)

    # Regra: FULL não pode ser reaberto automaticamente
    if session.status == SessionStatus.FULL:
        raise ReallocationError(
            "session_full",
            "Não é possível reabrir uma sessão FULL. "
            "A capacidade máxima foi atingida e a sessão requer decisão administrativa.",
        )

    # Apenas SCHEDULED pode abrir (validação após o lock)
    if session.status != SessionStatus.SCHEDULED:
        raise ReallocationError(
            "invalid_status",
            f"Sessão não pode ser aberta no estado '{session.status}'. Apenas SCHEDULED.",
        )

    # Confirmar capacidade no banco
    from sqlalchemy import func as _func

    confirmed = db.scalar(
        select(_func.count())
        .select_from(Enrollment)
        .where(Enrollment.session_id == session.id, Enrollment.status == EnrollmentStatus.CONFIRMED)
    )
    if session.capacity is None:
        raise ReallocationError(
            "capacity_undefined",
            "Não é possível abrir sessão sem capacidade definida.",
        )
    if confirmed >= session.capacity:
        raise ReallocationError(
            "session_full",
            "Não é possível abrir sessão: todas as vagas já estão confirmadas.",
        )

    # Transição SCHEDULED → OPEN (ocorre apenas uma vez devido ao lock)
    session.status = SessionStatus.OPEN
    db.add(session)
    db.flush()

    # Registro via log_audit_event() (AuditEvent, não ReallocationHistory)
    # Somente quando a transição ocorrer efetivamente.
    log_audit_event(
        db=db,
        kind="session_opened",
        description=f"Sessão extra {session.id} aberta para inscrições.",
        actor=coordinator,
        session_id=session.id,
    )

    return session


def _lock_origin_session(db: Session, case: ReallocationCase) -> ReikiSession:
    """Bloqueia a sessão de origem antes de alterar a inscrição original.

    `_cancel_origin_enrollment()` pode chamar `renumber_waitlist()` sobre a
    sessão de origem. Sem o lock da linha, duas reorganizações concorrentes da
    mesma sessão poderiam renumerar a fila ao mesmo tempo e produzir posições
    inconsistentes. A leitura recarrega do banco (`populate_existing`) já sob o
    lock e valida a existência e a associação com `case.origin_session_id`.
    """
    origin_session = db.execute(
        select(ReikiSession)
        .where(ReikiSession.id == case.origin_session_id)
        .with_for_update(of=ReikiSession)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if origin_session is None:
        raise ReallocationError(
            "origin_session_mismatch",
            "Sessão de origem não encontrada para o caso de reorganização.",
        )
    return origin_session


def _validated_origin_enrollment(
    db: Session,
    case: ReallocationCase,
    origin_session: ReikiSession,
) -> Enrollment:
    """Valida e bloqueia a inscrição original antes de qualquer alteração.

    A sessão de origem já deve estar bloqueada por `_lock_origin_session()`,
    preservando a ordem: caso → destino → origem → inscrição original.
    """
    # SELECT ... FOR UPDATE: serializa decisões concorrentes sobre a mesma
    # inscrição, mantendo o bloqueio até o fim da transação corrente.
    origin_enrollment = db.execute(
        select(Enrollment)
        .where(Enrollment.id == case.origin_enrollment_id)
        .with_for_update(of=Enrollment)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if origin_enrollment is None:
        raise ReallocationError(
            "origin_enrollment_not_found",
            "Inscrição de origem não encontrada."
        )
    if origin_enrollment.participant_id != case.participant_id:
        raise ReallocationError(
            "origin_access_denied",
            "Inscrição de origem não pertence ao participante do caso."
        )
    if (
        origin_enrollment.session_id != case.origin_session_id
        or origin_enrollment.session_id != origin_session.id
    ):
        raise ReallocationError(
            "origin_session_mismatch",
            "Inscrição de origem não pertence à sessão original do caso."
        )
    if origin_enrollment.status not in (EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED):
        raise ReallocationError(
            "origin_status_invalid",
            "Inscrição de origem não está mais em estado compatível com a reorganização."
        )
    return origin_enrollment


def _cancel_origin_enrollment(
    db: Session,
    origin_enrollment: Enrollment,
    *,
    reason: str,
) -> None:
    """Encerra a inscrição original preservando a integridade da fila.

    A sessão de origem está sem cobertura; por isso não há promoção de
    ninguém da fila. Se a origem era WAITLISTED, limpa a posição e apenas
    renumera os restantes para manter a ordem determinística.
    """
    original_status = origin_enrollment.status
    origin_enrollment.status = EnrollmentStatus.CANCELLED
    origin_enrollment.cancelled_at = _now()
    origin_enrollment.cancel_reason = reason
    if original_status == EnrollmentStatus.WAITLISTED:
        origin_enrollment.waitlist_position = None
        # Com autoflush=False, o flush torna o cancelamento visível antes de
        # recalcular as posições restantes.
        db.flush()
        renumber_waitlist(db, origin_enrollment.session_id)


def apply_reallocation(
    db: Session,
    coordinator: User,
    case_id: uuid.UUID,
    *,
    alternative: ReallocationAlternative,
    target_session_id: uuid.UUID | None = None,
) -> ReallocationCase:
    if coordinator.role != Role.COORDINATOR:
        raise ReallocationError("forbidden", "Apenas a coordenação pode aplicar reorganizações.")
    # Lock pessimista do caso de reorganização.
    # of=ReallocationCase evita bloquear relacionamentos joined nullable.
    case = db.execute(
        select(ReallocationCase).where(ReallocationCase.id == case_id).with_for_update(of=ReallocationCase)
    ).scalar_one_or_none()
    if case is None:
        raise ReallocationError("not_found", "Caso de reorganização não encontrado.")
    if case.status != ReallocationStatus.PENDING:
        raise ReallocationError("already_decided", "O caso de reorganização já foi encerrado.")

    if alternative == ReallocationAlternative.FUTURE_PRIORITY:
        if target_session_id is not None:
            raise ReallocationError("invalid_target", "Prioridade futura não recebe sessão de destino.")
        # Ordem: caso → sessão de origem → inscrição original.
        origin_session = _lock_origin_session(db, case)
        origin_enrollment = _validated_origin_enrollment(db, case, origin_session)
        _cancel_origin_enrollment(db, origin_enrollment, reason="future_priority")
        case.alternative = alternative
        case.priority_granted_at = _now()
        case.status = ReallocationStatus.APPLIED
        case.decided_at = _now()
        case.decided_by = coordinator.id
        _history(
            db,
            case.id,
            "priority_granted",
            coordinator,
            "Prioridade futura registrada e inscrição original encerrada; "
            "não há garantia automática de vaga.",
        )
        db.flush()
        return case

    if target_session_id is None:
        raise ReallocationError("target_required", "Informe a sessão extra de destino.")
    # Lock pessimista da sessão extra de destino.
    # of=ReikiSession evita bloquear relacionamentos joined nullable (instructor, cycle).
    target = db.execute(
        select(ReikiSession).where(ReikiSession.id == target_session_id).with_for_update(of=ReikiSession)
    ).scalar_one_or_none()
    if target is None:
        raise ReallocationError("target_not_found", "Sessão de destino não encontrada.")
    if not target.is_extra:
        raise ReallocationError("target_not_extra", "O encaminhamento exige uma sessão extra.")
    if target.status not in (SessionStatus.OPEN, SessionStatus.FULL):
        raise ReallocationError("target_not_open", "A sessão extra ainda não está aberta para inscrições.")
    if target.capacity is None:
        raise ReallocationError("capacity_undefined", "A sessão de destino não possui capacidade definida.")
    duplicate = db.scalar(
        select(Enrollment).where(
            Enrollment.session_id == target.id,
            Enrollment.participant_id == case.participant_id,
            Enrollment.status.in_(
                (EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED, EnrollmentStatus.ATTENDED)
            ),
        )
    )
    if duplicate is not None:
        raise ReallocationError("duplicate", "O participante já possui inscrição ativa na sessão de destino.")
    confirmed = db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.session_id == target.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    )
    if confirmed >= target.capacity:
        raise ReallocationError("target_full", "A sessão de destino está lotada.")

    # Fecha a inscrição de origem para evitar dupla inscrição ativa.
    # Ordem de bloqueios: caso → destino → origem → inscrição original.
    # O lock da sessão de origem serializa `renumber_waitlist()` de
    # reorganizações concorrentes sobre a mesma fila.
    origin_session = _lock_origin_session(db, case)
    origin_enrollment = _validated_origin_enrollment(db, case, origin_session)
    _cancel_origin_enrollment(db, origin_enrollment, reason="reallocated")
    db.add(
        Enrollment(
            session_id=target.id,
            participant_id=case.participant_id,
            status=EnrollmentStatus.CONFIRMED,
            waitlist_position=None,
            reallocation_id=case.id,
        )
    )
    target.status = SessionStatus.FULL if confirmed + 1 >= target.capacity else SessionStatus.OPEN
    case.alternative = alternative
    case.target_session_id = target.id
    case.status = ReallocationStatus.APPLIED
    case.decided_at = _now()
    case.decided_by = coordinator.id
    _history(db, case.id, "applied", coordinator, f"Inscrição criada na sessão extra {target.id}.")
    db.flush()
    return case


def dismiss_reallocation(
    db: Session, coordinator: User, case_id: uuid.UUID, reason: str | None = None
) -> ReallocationCase:
    if coordinator.role != Role.COORDINATOR:
        raise ReallocationError("forbidden", "Apenas a coordenação pode dispensar reorganizações.")
    # Lock pessimista do caso de reorganização.
    # of=ReallocationCase evita bloquear relacionamentos joined nullable.
    case = db.execute(
        select(ReallocationCase).where(ReallocationCase.id == case_id).with_for_update(of=ReallocationCase)
    ).scalar_one_or_none()
    if case is None:
        raise ReallocationError("not_found", "Caso de reorganização não encontrado.")
    if case.status != ReallocationStatus.PENDING:
        raise ReallocationError("already_decided", "O caso de reorganização já foi encerrado.")
    case.status = ReallocationStatus.DISMISSED
    case.decided_at = _now()
    case.decided_by = coordinator.id
    case.dismissal_reason = reason
    _history(db, case.id, "dismissed", coordinator, reason)
    db.flush()
    return case


def list_reallocations(db: Session) -> list[ReallocationCase]:
    return list(
        db.scalars(
            select(ReallocationCase).order_by(ReallocationCase.created_at.desc())
        ).unique()
    )
