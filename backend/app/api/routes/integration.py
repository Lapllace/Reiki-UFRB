"""Rotas necessárias às telas de participante, ministrante e coordenação."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import enforce_same_origin, require_role, require_user
from app.db.session import get_db
from app.models.cycle import WeeklyCycle
from app.models.phase2 import AvailabilityStatus, Enrollment, EnrollmentStatus
from app.models.phase3 import CoverRequest, CoverRequestStatus
from app.models.phase4 import ReallocationCase, ReallocationStatus
from app.models.phase41 import AuditEvent, Notification
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.schemas.domain import InstructorSummaryOut, LocationOut, SessionOut, SessionStatus as SessionStatusOut, WeekSessionsOut
from app.schemas.integration import (
    AppNotificationOut, AuditEventOut, CoverRequestOut, CycleTotalsOut,
    InstructorAvailabilityRowOut, InstructorSessionOut, RosterEntryOut, WeeklyCycleOut,
)
from app.services import phase2_service

instructor_router = APIRouter(prefix="/instructor", tags=["instructor"])
coordination_router = APIRouter(prefix="/coordination", tags=["coordination"])
notifications_router = APIRouter(prefix="/me", tags=["notifications"])


def _session_out(db: Session, item: ReikiSession) -> SessionOut:
    confirmed = db.scalar(select(func.count()).select_from(Enrollment).where(
        Enrollment.session_id == item.id, Enrollment.status == EnrollmentStatus.CONFIRMED
    ))
    waitlisted = db.scalar(select(func.count()).select_from(Enrollment).where(
        Enrollment.session_id == item.id, Enrollment.status == EnrollmentStatus.WAITLISTED
    ))
    return SessionOut(
        id=item.id, starts_at=item.starts_at, ends_at=item.ends_at,
        location=LocationOut.model_validate(item.location),
        instructor=InstructorSummaryOut.model_validate(item.instructor) if item.instructor else None,
        capacity=item.capacity, confirmed_count=confirmed, waitlist_count=waitlisted,
        status=SessionStatusOut(item.status), is_extra=item.is_extra,
    )


def _roster(db: Session, session_id: uuid.UUID) -> list[RosterEntryOut]:
    rows = db.scalars(select(Enrollment).where(
        Enrollment.session_id == session_id,
        Enrollment.status.in_((EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED, EnrollmentStatus.ATTENDED)),
    ).order_by(Enrollment.waitlist_position, Enrollment.created_at)).all()
    return [RosterEntryOut(
        enrollment_id=row.id, participant_name=row.participant.name,
        status=row.status.value, waitlist_position=row.waitlist_position,
    ) for row in rows]


def _can_cancel(item: ReikiSession) -> tuple[bool, str | None]:
    if item.status in (SessionStatus.CANCELLED, SessionStatus.COMPLETED):
        return False, "Sessão encerrada."
    return True, None


@instructor_router.get("/sessions", response_model=list[InstructorSessionOut])
def instructor_sessions(user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
                        db: Session = Depends(get_db)) -> list[InstructorSessionOut]:
    rows = db.scalars(select(ReikiSession).where(ReikiSession.instructor_id == user.id).order_by(ReikiSession.starts_at)).unique().all()
    return [InstructorSessionOut(session=_session_out(db, row), can_cancel=_can_cancel(row)[0],
                                 cancel_blocked_reason=_can_cancel(row)[1]) for row in rows]


@instructor_router.get("/sessions/{session_id}/roster", response_model=list[RosterEntryOut])
def instructor_roster(session_id: uuid.UUID, user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
                      db: Session = Depends(get_db)) -> list[RosterEntryOut]:
    item = db.get(ReikiSession, session_id)
    if item is None:
        raise HTTPException(404, "Sessão não encontrada.")
    if user.role == Role.INSTRUCTOR and item.instructor_id != user.id:
        raise HTTPException(403, "Você não tem acesso a esta sessão.")
    return _roster(db, session_id)


@coordination_router.get("/sessions", response_model=WeekSessionsOut)
def coordination_sessions(weekStart: str, _user: User = Depends(require_role(Role.COORDINATOR)),
                           db: Session = Depends(get_db)) -> WeekSessionsOut:
    ws = phase2_service.schedule_service.parse_week_start(weekStart)
    if ws is None:
        raise HTTPException(422, "Semana inválida.")
    rows = db.scalars(select(ReikiSession).where(
        ReikiSession.starts_at >= ws, ReikiSession.starts_at < ws + timedelta(days=7)
    ).order_by(ReikiSession.starts_at)).unique().all()
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    return WeekSessionsOut(week_start=ws, week_end=ws + timedelta(days=6),
                           sessions=[_session_out(db, row) for row in rows], published=cycle is not None)


@coordination_router.get("/sessions/{session_id}/roster", response_model=list[RosterEntryOut])
def coordination_roster(session_id: uuid.UUID, _user: User = Depends(require_role(Role.COORDINATOR)),
                        db: Session = Depends(get_db)) -> list[RosterEntryOut]:
    if db.get(ReikiSession, session_id) is None:
        raise HTTPException(404, "Sessão não encontrada.")
    return _roster(db, session_id)


@coordination_router.get("/cover-requests", response_model=list[CoverRequestOut])
def cover_requests(_user: User = Depends(require_role(Role.COORDINATOR)),
                   db: Session = Depends(get_db)) -> list[CoverRequestOut]:
    rows = db.scalars(select(CoverRequest).order_by(CoverRequest.created_at.desc())).all()
    result = []
    for row in rows:
        session = db.get(ReikiSession, row.session_id)
        if session is None:
            continue
        original = db.get(User, row.original_instructor_id) if row.original_instructor_id else None
        covered = db.get(User, row.covered_by) if row.covered_by else None
        result.append(CoverRequestOut(
            id=row.id, status=row.status.value, session=_session_out(db, session),
            original_instructor={"id": str(original.id), "name": original.name} if original else None,
            reason=row.reason, invited_count=len(row.invites), created_at=row.created_at,
            resolved_at=row.resolved_at,
            covered_by={"id": str(covered.id), "name": covered.name} if covered else None,
        ))
    return result


@coordination_router.get("/cycles/{weekStart}", response_model=WeeklyCycleOut)
def coordination_cycle(weekStart: str, _user: User = Depends(require_role(Role.COORDINATOR)),
                       db: Session = Depends(get_db)) -> WeeklyCycleOut:
    ws = phase2_service.schedule_service.parse_week_start(weekStart)
    if ws is None:
        raise HTTPException(422, "Semana inválida.")
    cycle = db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == ws))
    rows = db.scalars(select(ReikiSession).where(
        ReikiSession.starts_at >= ws, ReikiSession.starts_at < ws + timedelta(days=7)
    )).all()
    confirmed = sum(db.scalar(select(func.count()).select_from(Enrollment).where(
        Enrollment.session_id == row.id, Enrollment.status == EnrollmentStatus.CONFIRMED
    )) or 0 for row in rows)
    waitlisted = sum(db.scalar(select(func.count()).select_from(Enrollment).where(
        Enrollment.session_id == row.id, Enrollment.status == EnrollmentStatus.WAITLISTED
    )) or 0 for row in rows)
    capacity_values = [row.capacity for row in rows if row.capacity is not None]
    pending = 0
    if rows:
        pending = db.scalar(select(func.count()).select_from(ReallocationCase).where(
            ReallocationCase.status == ReallocationStatus.PENDING,
            ReallocationCase.origin_session_id.in_([row.id for row in rows]),
        )) or 0
    instructors = db.scalars(select(User).where(User.role == Role.INSTRUCTOR, User.is_active.is_(True))).all()
    return WeeklyCycleOut(
        week_start=ws, week_end=ws + timedelta(days=6),
        phase=cycle.phase.value if cycle else "collecting_availability",
        availability_deadline=None, enrollment_opens_at=None,
        totals=CycleTotalsOut(
            sessions=len(rows), capacity=sum(capacity_values) if len(capacity_values) == len(rows) else None,
            confirmed=confirmed if all(row.capacity is not None for row in rows) else None,
            waitlisted=waitlisted, uncovered=sum(row.status == SessionStatus.UNCOVERED for row in rows),
            open_cover_requests=db.scalar(select(func.count()).select_from(CoverRequest).where(CoverRequest.status == CoverRequestStatus.OPEN)) or 0,
            pending_reallocations=pending,
        ),
        instructors=[InstructorAvailabilityRowOut(instructor={"id": str(item.id), "name": item.name},
            status="pending", submitted_at=None, sessions_offered=0) for item in instructors],
    )


@coordination_router.get("/events", response_model=list[AuditEventOut])
def coordination_events(_user: User = Depends(require_role(Role.COORDINATOR)),
                        db: Session = Depends(get_db)) -> list[AuditEventOut]:
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()
    return [AuditEventOut(id=row.id, kind=row.kind, at=row.created_at,
                          actor=db.get(User, row.actor_id).name if row.actor_id and db.get(User, row.actor_id) else None,
                          description=row.description, session_id=row.session_id) for row in rows]


@notifications_router.get("/notifications", response_model=list[AppNotificationOut])
def notifications(user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[AppNotificationOut]:
    rows = db.scalars(select(Notification).where(Notification.recipient_id == user.id).order_by(Notification.created_at.desc())).all()
    return [AppNotificationOut(id=row.id, kind=row.kind, title=row.title, message=row.message,
        created_at=row.created_at, read=row.read_at is not None, session_id=row.session_id) for row in rows]


@notifications_router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(notification_id: uuid.UUID, user: User = Depends(require_user),
                            _csrf: None = Depends(enforce_same_origin), db: Session = Depends(get_db)) -> None:
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.recipient_id == user.id))
    if row is None:
        raise HTTPException(404, "Notificação não encontrada.")
    from datetime import UTC, datetime
    row.read_at = datetime.now(UTC)
    db.commit()
