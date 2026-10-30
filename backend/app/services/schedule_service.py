"""Regras de domínio da agenda semanal."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cycle import WeeklyCycle
from app.models.session_week import ReikiSession

# Convenção do frontend: a semana começa na segunda-feira.
MONDAY = 0


def week_start_of(day: date, *, first_weekday: int = MONDAY) -> date:
    """Normaliza qualquer data para o primeiro dia da semana (segunda-feira)."""
    offset = (day.weekday() - first_weekday) % 7
    return day - timedelta(days=offset)


def week_end_of(week_start: date) -> date:
    return week_start + timedelta(days=6)


def parse_week_start(value: str) -> date | None:
    """Valida `YYYY-MM-DD`; retorna None quando inválido."""
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return week_start_of(day)


def get_or_none_cycle(db: Session, week_start: date) -> WeeklyCycle | None:
    return db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == week_start))


def is_published(cycle: WeeklyCycle | None) -> bool:
    """Semana publicada = existe ciclo em fase de publicação/andamento.

    Fases `collecting_availability` e `enrollment_pending` indicam que a agenda
    ainda NÃO está aberta ao público (`published: false`).
    """
    if cycle is None:
        return False
    from app.models.cycle import CyclePhase

    return cycle.phase not in (
        CyclePhase.COLLECTING_AVAILABILITY,
        CyclePhase.ENROLLMENT_PENDING,
    )


def list_week_sessions(db: Session, week_start: date) -> list[ReikiSession]:
    """Sessões da semana ordenadas pelo início, filtrando pelo intervalo de datas."""
    week_end = week_end_of(week_start)
    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    stmt = (
        select(ReikiSession)
        .where(ReikiSession.starts_at >= start_dt, ReikiSession.starts_at < end_dt)
        .order_by(ReikiSession.starts_at)
    )
    return list(db.scalars(stmt))

