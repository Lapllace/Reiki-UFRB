"""Regras da Fase 4: reorganização administrativa e sessões extras."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.phase2 import Enrollment, EnrollmentStatus
from app.models.phase4 import (
    ReallocationAlternative,
    ReallocationCase,
    ReallocationHistory,
    ReallocationStatus,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User


class ReallocationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(UTC)


def _history(db: Session, case: ReallocationCase, action: str, actor: User | None, detail: str | None = None) -> None:
    db.add(
        ReallocationHistory(
            case_id=case.id,
            action=action,
            actor_id=actor.id if actor else None,
            detail=detail,
            created_at=_now(),
        )
    )


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
        db.add(case)
        db.flush()
        _history(db, case, "created", actor, "Inscrição afetada por sessão sem cobertura.")
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
    case = db.execute(
        select(ReallocationCase).where(ReallocationCase.id == case_id).with_for_update()
    ).scalar_one_or_none()
    if case is None:
        raise ReallocationError("not_found", "Caso de reorganização não encontrado.")
    if case.status != ReallocationStatus.PENDING:
        raise ReallocationError("already_decided", "O caso de reorganização já foi encerrado.")

    if alternative == ReallocationAlternative.FUTURE_PRIORITY:
        if target_session_id is not None:
            raise ReallocationError("invalid_target", "Prioridade futura não recebe sessão de destino.")
        case.alternative = alternative
        case.priority_granted_at = _now()
        case.status = ReallocationStatus.APPLIED
        case.decided_at = _now()
        case.decided_by = coordinator.id
        _history(db, case, "priority_granted", coordinator, "Prioridade futura registrada; não há garantia automática de vaga.")
        db.flush()
        return case

    if target_session_id is None:
        raise ReallocationError("target_required", "Informe a sessão extra de destino.")
    target = db.execute(
        select(ReikiSession).where(ReikiSession.id == target_session_id).with_for_update()
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
    _history(db, case, "applied", coordinator, f"Inscrição criada na sessão extra {target.id}.")
    db.flush()
    return case


def dismiss_reallocation(
    db: Session, coordinator: User, case_id: uuid.UUID, reason: str | None = None
) -> ReallocationCase:
    if coordinator.role != Role.COORDINATOR:
        raise ReallocationError("forbidden", "Apenas a coordenação pode dispensar reorganizações.")
    case = db.execute(
        select(ReallocationCase).where(ReallocationCase.id == case_id).with_for_update()
    ).scalar_one_or_none()
    if case is None:
        raise ReallocationError("not_found", "Caso de reorganização não encontrado.")
    if case.status != ReallocationStatus.PENDING:
        raise ReallocationError("already_decided", "O caso de reorganização já foi encerrado.")
    case.status = ReallocationStatus.DISMISSED
    case.decided_at = _now()
    case.decided_by = coordinator.id
    case.dismissal_reason = reason
    _history(db, case, "dismissed", coordinator, reason)
    db.flush()
    return case


def list_reallocations(db: Session) -> list[ReallocationCase]:
    return list(
        db.scalars(
            select(ReallocationCase).order_by(ReallocationCase.created_at.desc())
        ).unique()
    )
