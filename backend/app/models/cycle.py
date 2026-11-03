"""Ciclo semanal — representação da semana e de sua fase.

A semana é identificada pela data do seu primeiro dia (convenção do frontend:
semana começa na SEGUNDA-FEIRA, `weekStart` em `YYYY-MM-DD`).
"""

import enum
from datetime import date

from sqlalchemy import Date, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class CyclePhase(str, enum.Enum):
    """Fases compatíveis com `CyclePhase` do frontend."""

    COLLECTING_AVAILABILITY = "collecting_availability"
    ENROLLMENT_PENDING = "enrollment_pending"
    ENROLLMENT_OPEN = "enrollment_open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class WeeklyCycle(Base, UUIDPk, Timestamped):
    __tablename__ = "weekly_cycles"

    # Data da segunda-feira da semana; única no banco.
    week_start: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    phase: Mapped[CyclePhase] = mapped_column(
        Enum(
            CyclePhase,
            name="cycle_phase",
            native_enum=False,
            length=40,
            values_callable=lambda e: [m.value for m in e],
            validate_strings=True,
        ),
        nullable=False,
        default=CyclePhase.COLLECTING_AVAILABILITY,
    )
    # Semana sem ciclo criado = ainda não publicada (`published: false` no frontend).
    # `published` não é coluna: deriva da existência do ciclo e da fase.

    # Prazos opcionais — só preencher quando definidos institucionalmente.
    availability_deadline_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WeeklyCycle {self.week_start} {self.phase}>"
