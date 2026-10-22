"""Modelos da Fase 2: disponibilidade semanal e inscrições.

Convenções:
- imports: ``Base`` de ``app.db.base``, mixins de ``app.models.mixins``;
- enums persistem os VALORES (minúsculas) via ``values_callable``;
- ``Timestamped`` só nos modelos que precisam de auditoria completa.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class AvailabilityStatus(str, enum.Enum):
    """Estado da submissão do ministrante (contrato do frontend)."""

    PENDING = "pending"          # sem submissão para a semana
    SUBMITTED = "submitted"      # horários informados pelo ministrante
    UNAVAILABLE = "unavailable"  # declarou indisponibilidade para a semana


class AvailabilityEntryKind(str, enum.Enum):
    """Tipo de cada horário informado pelo ministrante."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class WeeklyAvailability(Base, UUIDPk, Timestamped):
    """Submissão de disponibilidade de um ministrante para um ciclo semanal.

    Regras:
    - um registro por (ministrante, ciclo) — unicidade no banco;
    - o ministrante INFORMA seus dias/horários/locais (não escolhe slots
      pré-definidos pela coordenação);
    - submissão distinta de indisponibilidade: ``status`` distingue os dois.
    """

    __tablename__ = "weekly_availabilities"

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("weekly_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AvailabilityStatus] = mapped_column(
        String(20), nullable=False, default=AvailabilityStatus.SUBMITTED
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Nota opcional do ministrante (ex.: "posso cobrir sextas também").
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    entries: Mapped[list["AvailabilityEntry"]] = relationship(
        back_populates="availability",
        cascade="all, delete-orphan",
        order_by="AvailabilityEntry.starts_at",
    )

    __table_args__ = (
        UniqueConstraint("cycle_id", "instructor_id", name="uq_avail_cycle_instructor"),
    )


class AvailabilityEntry(Base, UUIDPk):
    """Um horário informado pelo ministrante dentro de uma submissão.

    ``kind=available``  → posso ministrar neste dia/horário/local;
    ``kind=unavailable`` → declaro indisponibilidade neste intervalo.
    """

    __tablename__ = "availability_entries"

    availability_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("weekly_availabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AvailabilityEntryKind] = mapped_column(
        String(20), nullable=False, default=AvailabilityEntryKind.AVAILABLE
    )
    # Intervalo declarado pelo ministrante (data e hora com fuso).
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    availability: Mapped[WeeklyAvailability] = relationship(
        back_populates="entries"
    )
    location: Mapped["Location | None"] = relationship("Location", lazy="joined")

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_avail_entry_period"),
    )


class EnrollmentStatus(str, enum.Enum):
    """Estado da inscrição (contrato do frontend)."""

    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    ATTENDED = "attended"
    CANCELLED = "cancelled"


class Enrollment(Base, UUIDPk, Timestamped):
    """Inscrição de um participante em uma sessão.

    Decisões (confirmada vs fila) são SEMPRE do servidor. Capacidade
    indefinida bloqueia inscrição confirmada (não significa ilimitada).
    """

    __tablename__ = "enrollments"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reiki_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reallocation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "reallocation_cases.id",
            name="fk_enrollments_reallocation_id",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(String(20), nullable=False)
    # Posição na fila (1 = próximo). Nula fora de ``waitlisted``.
    waitlist_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped["ReikiSession"] = relationship("ReikiSession", lazy="joined")
    participant: Mapped["User"] = relationship("User", lazy="joined")

    __table_args__ = (
        # Sem inscrição duplicada ativa (participante, sessão).
        Index(
            "uq_enrollments_session_participant_active",
            "session_id",
            "participant_id",
            unique=True,
            postgresql_where=text("status IN ('confirmed', 'waitlisted', 'attended')"),
        ),
        CheckConstraint(
            "status != 'waitlisted' OR waitlist_position IS NOT NULL",
            name="ck_enrollments_waitlist_position",
        ),
    )

# O filtro parcial usa SQL cru: no PostgreSQL é um índice parcial real
# (WHERE status IN (...)), que só impõe unicidade entre inscrições ativas.
