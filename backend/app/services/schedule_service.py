"""Regras de domínio da agenda semanal."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cycle import WeeklyCycle
from app.models.session_week import ReikiSession

# Convenção do frontend: a semana começa na segunda-feira.
MONDAY = 0

# Fuso institucional da UFRB. Não há configuração central equivalente no
# projeto; a semana é delimitada neste fuso e convertida para UTC nas consultas.
INSTITUTIONAL_TIMEZONE = ZoneInfo("America/Bahia")


def week_start_of(day: date, *, first_weekday: int = MONDAY) -> date:
    """Normaliza qualquer data para o primeiro dia da semana (segunda-feira)."""
    offset = (day.weekday() - first_weekday) % 7
    return day - timedelta(days=offset)


def week_end_of(week_start: date) -> date:
    return week_start + timedelta(days=6)


def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    """Limites da semana no fuso institucional.

    Retorna ``[segunda 00:00 local, segunda seguinte 00:00 local)``. O limite
    superior é o instante em que a semana seguinte começa, exatamente o valor
    aceito como fim máximo de uma oferta.
    """
    ws = week_start_of(week_start)
    lower = datetime.combine(ws, time.min, tzinfo=INSTITUTIONAL_TIMEZONE)
    upper = datetime.combine(
        ws + timedelta(days=7), time.min, tzinfo=INSTITUTIONAL_TIMEZONE
    )
    return lower, upper


def week_bounds_utc(week_start: date) -> tuple[datetime, datetime]:
    """Os mesmos limites da semana, convertidos para UTC (para consultas)."""
    lower, upper = week_bounds(week_start)
    return lower.astimezone(UTC), upper.astimezone(UTC)


def week_period_error(
    starts_at: datetime, ends_at: datetime, week_start: date
) -> str | None:
    """Valida um intervalo contra a semana do ciclo.

    Retorna ``"invalid_period"`` para datas sem fuso ou fim não posterior ao
    início, ``"outside_week"`` quando o intervalo sai da semana, ou ``None``
    quando é válido. As comparações são sempre feitas entre datetimes com fuso.
    """
    for value in (starts_at, ends_at):
        if value.tzinfo is None or value.utcoffset() is None:
            return "invalid_period"
    if ends_at <= starts_at:
        return "invalid_period"

    lower, upper = week_bounds(week_start)
    if starts_at < lower or starts_at >= upper:
        return "outside_week"
    if ends_at > upper:
        return "outside_week"
    return None


def parse_week_start(value: str) -> date | None:
    """Valida `YYYY-MM-DD`; retorna None quando inválido."""
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return week_start_of(day)


def get_or_none_cycle(db: Session, week_start: date) -> WeeklyCycle | None:
    return db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == week_start))


def lock_cycle(db: Session, week_start: date) -> WeeklyCycle | None:
    """Bloqueia o ciclo da semana e recarrega seu estado do banco.

    É o primeiro bloqueio de qualquer operação que altere a agenda semanal
    (submissão de disponibilidade, criação de sessão e publicação). A ordem
    comum evita deadlocks entre essas operações concorrentes. O
    ``populate_existing`` e o ``refresh`` garantem que a fase observada seja a
    versão já confirmada por quem detinha o bloqueio.
    """
    ws = week_start_of(week_start)
    cycle = db.execute(
        select(WeeklyCycle)
        .where(WeeklyCycle.week_start == ws)
        .with_for_update(of=WeeklyCycle)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if cycle is not None:
        db.refresh(cycle)
    return cycle


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
    """Sessões da semana ordenadas pelo início, usando os limites institucionais."""
    start_dt, end_dt = week_bounds_utc(week_start)
    stmt = (
        select(ReikiSession)
        .where(ReikiSession.starts_at >= start_dt, ReikiSession.starts_at < end_dt)
        .order_by(ReikiSession.starts_at)
    )
    return list(db.scalars(stmt))

