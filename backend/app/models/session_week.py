"""Sessões de Reiki (encontros semanais ou extras).

Campos deliberadamente mínimos para a Fase 1. Duração, capacidade e regras
de abertura NÃO têm valores padrão inventados: o que for opcional é nulo.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk
from app.models.cycle import WeeklyCycle
from app.models.location import Location
from app.models.user import User


class SessionStatus(str, enum.Enum):
    """Compatível com `SessionStatus` do frontend."""

    SCHEDULED = "scheduled"  # publicada, inscrições ainda fechadas
    OPEN = "open"
    FULL = "full"
    CANCELLED = "cancelled"
    NEEDS_COVER = "needs_cover"
    UNCOVERED = "uncovered"
    COMPLETED = "completed"


class ReikiSession(Base, UUIDPk, Timestamped):
    __tablename__ = "reiki_sessions"

    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("weekly_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    # Nulo = cobertura pendente (sem ministrante definido).
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Horários com fuso explícito (timezone=True). ISO 8601 com offset nas respostas.
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Nulo = capacidade não definida (regra pendente institucionalmente).
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[SessionStatus] = mapped_column(
        Enum(
            SessionStatus,
            name="session_status",
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
            validate_strings=True,
        ),
        nullable=False,
        default=SessionStatus.SCHEDULED,
    )
    # Sessão extra criada fora do ciclo regular.
    is_extra: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Auditoria simples da fase 1 (histórico rico virá depois).
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    location: Mapped[Location] = relationship(Location, lazy="joined")
    instructor: Mapped[User | None] = relationship(User, lazy="joined")
    cycle: Mapped[WeeklyCycle | None] = relationship(WeeklyCycle, lazy="joined")
