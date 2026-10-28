"""Rotas da Fase 2: disponibilidade do ministrante e inscrições.

Divergência de contrato documentada: o frontend propunha `SlotOption`/`slotIds`
(slots pré-definidos pela coordenação). A regra real é o ministrante INFORMAR
seus dias/horários/locais. O backend implementa a regra real; os ajustes
necessários no frontend estão listados em `docs/FRONTEND_CONTRACT_ADJUSTMENTS.md`.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import enforce_same_origin, require_role, require_user
from app.db.session import get_db
from app.models.phase2 import AvailabilityStatus, Enrollment
from app.models.user import Role, User
from app.schemas.phase2 import (
    AvailabilityEntryKind,
    AvailabilityEntryOut,
    EnrollIn,
    EnrollmentOut,
    EnrollmentResultOut,
    PublishAvailabilityIn,
    WeeklyAvailabilityOut,
)
from app.services import phase2_service

router = APIRouter(tags=["phase2"])
availability_router = APIRouter(prefix="/instructor", tags=["availability"])
enrollments_router = APIRouter(prefix="/enrollments", tags=["enrollments"])
me_router = APIRouter(prefix="/me", tags=["me"])


def _week_bounds(ws: date) -> tuple[str, str]:
    return ws.isoformat(), (ws + timedelta(days=6)).isoformat()


def _availability_out(db: Session, instructor_id: uuid.UUID, ws: date) -> WeeklyAvailabilityOut:
    sub = phase2_service.get_availability(db, instructor_id, ws)
    cycle = phase2_service.cycle_for_week(db, ws)
    can_edit = phase2_service._can_edit(cycle)
    if sub is None:
        return WeeklyAvailabilityOut(
            week_start=ws.isoformat(),
            week_end=(ws + timedelta(days=6)).isoformat(),
            status=AvailabilityStatus.PENDING,
            can_edit=can_edit,
            locked_reason=None if can_edit else "Submissão fechada para este ciclo.",
            submitted_at=None,
            entries=[],
        )
    return WeeklyAvailabilityOut(
        week_start=ws.isoformat(),
        week_end=(ws + timedelta(days=6)).isoformat(),
        status=AvailabilityStatus(sub.status),
        can_edit=can_edit,
        locked_reason=None if can_edit else "Submissão fechada para este ciclo.",
        submitted_at=sub.submitted_at,
        note=sub.note,
        entries=[
            AvailabilityEntryOut(
                id=e.id,
                kind=AvailabilityEntryKind(e.kind),
                starts_at=e.starts_at,
                ends_at=e.ends_at,
                location_id=e.location_id,
                note=e.note,
            )
            for e in sub.entries
        ],
    )


@availability_router.get("/availability", response_model=WeeklyAvailabilityOut)
def get_availability(
    weekStart: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> WeeklyAvailabilityOut:
    if weekStart is None:
        # Semana corrente (segunda da semana atual, no fuso UTC).
        today = datetime.now(timezone.utc).date()
        ws = phase2_service.week_start_of(today)
    else:
        ws = phase2_service.schedule_service.parse_week_start(weekStart)
        if ws is None:
            raise HTTPException(status_code=422, detail="Dados inválidos.")
    if user.role != Role.INSTRUCTOR and user.role != Role.COORDINATOR:
        raise HTTPException(status_code=403, detail="Você não tem permissão para esta ação.")
    return _availability_out(db, user.id, ws)


@availability_router.post("/availability", response_model=WeeklyAvailabilityOut)
def publish_availability(
    payload: PublishAvailabilityIn,
    user: User = Depends(require_user),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> WeeklyAvailabilityOut:
    if user.role != Role.INSTRUCTOR and user.role != Role.COORDINATOR:
        raise HTTPException(status_code=403, detail="Você não tem permissão para esta ação.")
    ws = phase2_service.schedule_service.parse_week_start(payload.week_start)
    if ws is None:
        raise HTTPException(status_code=422, detail="Dados inválidos.")
    try:
        phase2_service.submit_availability(
            db,
            user,
            ws,
            unavailable=payload.unavailable,
            entries=[e.model_dump() for e in payload.entries],
            note=payload.note,
        )
    except phase2_service.AvailabilityError as exc:
        raise HTTPException(status_code=409, detail=str(exc), headers={"X-Error-Code": exc.code})
    return _availability_out(db, user.id, ws)


def _enrollment_out(db: Session, enrollment: Enrollment) -> EnrollmentOut:
    from app.models.session_week import ReikiSession

    session_row = db.get(ReikiSession, enrollment.session_id)
    can_cancel = (
        enrollment.status.value in ("confirmed", "waitlisted")
        and session_row is not None
        and session_row.status not in ("cancelled", "completed")
    )
    reason = None
    if not can_cancel:
        if enrollment.status.value not in ("confirmed", "waitlisted"):
            reason = "Inscrição já cancelada ou concluída."
        elif session_row is not None and session_row.status in ("cancelled", "completed"):
            reason = "Sessão cancelada ou concluída."
    return EnrollmentOut(
        id=enrollment.id,
        status=enrollment.status.value,
        waitlist_position=enrollment.waitlist_position,
        created_at=enrollment.created_at,
        cancelled_at=enrollment.cancelled_at,
        session_id=enrollment.session_id,
        can_cancel=can_cancel,
        cancel_blocked_reason=reason,
    )


@enrollments_router.post("", response_model=EnrollmentResultOut, status_code=201)
def create_enrollment(
    payload: EnrollIn,
    user: User = Depends(require_user),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> EnrollmentResultOut:
    try:
        enrollment = phase2_service.create_enrollment(db, user, payload.session_id)
    except phase2_service.EnrollmentError as exc:
        code_status = {
            "session_not_found": 404,
            "not_open": 409,
            "duplicate": 409,
            "capacity_undefined": 409,
        }.get(exc.code, 409)
        raise HTTPException(status_code=code_status, detail=str(exc), headers={"X-Error-Code": exc.code})
    return EnrollmentResultOut(enrollment=_enrollment_out(db, enrollment))


@enrollments_router.post("/{enrollment_id}/cancel", response_model=EnrollmentOut)
def cancel_enrollment(
    enrollment_id: uuid.UUID,
    user: User = Depends(require_user),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    try:
        enrollment = phase2_service.cancel_enrollment(db, user, enrollment_id)
    except phase2_service.EnrollmentError as exc:
        code_status = {"not_found": 404}.get(exc.code, 409)
        raise HTTPException(status_code=code_status, detail=str(exc), headers={"X-Error-Code": exc.code})
    return _enrollment_out(db, enrollment)


@me_router.get("/enrollments", response_model=list[EnrollmentOut])
def my_enrollments(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[EnrollmentOut]:
    rows = phase2_service.list_my_enrollments(db, user.id)
    return [_enrollment_out(db, e) for e in rows]
