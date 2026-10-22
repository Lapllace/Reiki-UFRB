"""Rotas administrativas da Fase 4."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import enforce_same_origin, require_role
from app.db.session import get_db
from app.models.phase2 import Enrollment, EnrollmentStatus
from app.models.phase4 import ReallocationAlternative, ReallocationCase
from app.models.session_week import ReikiSession
from app.models.user import Role, User
from app.schemas.domain import (
    InstructorSummaryOut,
    LocationOut,
    SessionOut,
    SessionStatus,
)
from app.schemas.phase4 import (
    ApplyReallocationIn,
    CreateExtraSessionIn,
    DismissReallocationIn,
    ReallocationOut,
)
from app.services import phase4_service

router = APIRouter(prefix="/coordination", tags=["coordination"])


def _session_out(db: Session, session: ReikiSession) -> SessionOut:
    confirmed = db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.session_id == session.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    )
    waitlisted = db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.session_id == session.id,
            Enrollment.status == EnrollmentStatus.WAITLISTED,
        )
    )
    return SessionOut(
        id=session.id,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        location=LocationOut.model_validate(session.location),
        instructor=(
            InstructorSummaryOut.model_validate(session.instructor)
            if session.instructor else None
        ),
        capacity=session.capacity,
        confirmed_count=confirmed,
        waitlist_count=waitlisted,
        status=SessionStatus(session.status),
        is_extra=session.is_extra,
    )


def _case_out(db: Session, case: ReallocationCase) -> ReallocationOut:
    candidates = list(
        db.scalars(
            select(ReikiSession).where(
                ReikiSession.is_extra.is_(True),
                ReikiSession.status.in_(("open", "full")),
                ReikiSession.id != case.origin_session_id,
            ).order_by(ReikiSession.starts_at)
        )
    )
    reason = "Sessão sem cobertura; inscrição requer reorganização."
    return ReallocationOut(
        id=case.id,
        status=case.status,
        reason=reason,
        origin_session=_session_out(db, case.origin_session),
        participant_count=1,
        candidate_sessions=[_session_out(db, item) for item in candidates],
        applied_to=_session_out(db, case.target_session) if case.target_session else None,
        alternative=case.alternative,
        priority_granted_at=case.priority_granted_at,
        created_at=case.created_at,
        decided_at=case.decided_at,
    )


@router.get("/reallocations", response_model=list[ReallocationOut])
def list_reallocations(
    _user: User = Depends(require_role(Role.COORDINATOR)),
    db: Session = Depends(get_db),
) -> list[ReallocationOut]:
    return [_case_out(db, case) for case in phase4_service.list_reallocations(db)]


@router.post("/reallocations/{case_id}/apply", response_model=ReallocationOut)
def apply_reallocation(
    case_id: uuid.UUID,
    payload: ApplyReallocationIn,
    user: User = Depends(require_role(Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> ReallocationOut:
    try:
        case = phase4_service.apply_reallocation(
            db, user, case_id, alternative=payload.alternative,
            target_session_id=payload.target_session_id,
        )
    except phase4_service.ReallocationError as exc:
        code_status = {"not_found": 404, "forbidden": 403}.get(exc.code, 409)
        raise HTTPException(
            status_code=code_status, detail=str(exc),
            headers={"X-Error-Code": exc.code},
        )
    return _case_out(db, case)


@router.post("/reallocations/{case_id}/dismiss", response_model=ReallocationOut)
def dismiss_reallocation(
    case_id: uuid.UUID,
    payload: DismissReallocationIn | None = None,
    user: User = Depends(require_role(Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> ReallocationOut:
    try:
        case = phase4_service.dismiss_reallocation(
            db, user, case_id, payload.reason if payload else None
        )
    except phase4_service.ReallocationError as exc:
        code_status = {"not_found": 404, "forbidden": 403}.get(exc.code, 409)
        raise HTTPException(
            status_code=code_status, detail=str(exc),
            headers={"X-Error-Code": exc.code},
        )
    return _case_out(db, case)


@router.post("/sessions/extra", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_extra_session(
    payload: CreateExtraSessionIn,
    user: User = Depends(require_role(Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> SessionOut:
    try:
        session = phase4_service.create_extra_session(
            db, user, starts_at=payload.starts_at, ends_at=payload.ends_at,
            location_id=payload.location_id, capacity=payload.capacity,
        )
    except phase4_service.ReallocationError as exc:
        code_status = {"forbidden": 403, "location_inactive": 409}.get(exc.code, 422)
        raise HTTPException(
            status_code=code_status, detail=str(exc),
            headers={"X-Error-Code": exc.code},
        )
    return _session_out(db, session)
