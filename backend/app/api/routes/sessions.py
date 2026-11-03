"""Consulta semanal de sessões: GET /sessions?weekStart=YYYY-MM-DD."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.session_week import ReikiSession
from app.schemas.domain import (
    InstructorSummaryOut,
    LocationOut,
    SessionOut,
    SessionStatus,
    WeekSessionsOut,
)
from app.services import schedule_service

router = APIRouter(tags=["sessions"])


def _to_out(session: ReikiSession) -> SessionOut:
    return SessionOut(
        id=session.id,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        location=LocationOut.model_validate(session.location),
        instructor=(
            InstructorSummaryOut.model_validate(session.instructor)
            if session.instructor
            else None
        ),
        capacity=session.capacity,
        confirmed_count=None,  # inscrições chegam na Fase 2
        waitlist_count=None,
        status=SessionStatus(session.status),
        is_extra=session.is_extra,
    )


@router.get("/sessions", response_model=WeekSessionsOut)
def week_sessions(
    weekstart: str = Query(alias="weekStart", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
) -> WeekSessionsOut:
    ws = schedule_service.parse_week_start(weekstart)
    if ws is None:
        raise HTTPException(status_code=422, detail="Dados inválidos.")
    cycle = schedule_service.get_or_none_cycle(db, ws)
    sessions = schedule_service.list_week_sessions(db, ws)
    published = schedule_service.is_published(cycle)
    return WeekSessionsOut(
        week_start=ws,
        week_end=schedule_service.week_end_of(ws),
        sessions=[_to_out(s) for s in sessions],
        published=published,
    )
