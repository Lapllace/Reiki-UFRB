"""Pacote de modelos SQLAlchemy 2.x.

Importar este pacote registra todos os modelos nos metadados de
``app.db.base.Base``. Usado pelo Alembic e por quem precisa dos modelos juntos.
"""

from app.db.base import Base
from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityEntryKind,
    AvailabilityStatus,
    Enrollment,
    EnrollmentStatus,
    WeeklyAvailability,
)
from app.models.phase3 import (
    CoverInvite,
    CoverInviteStatus,
    CoverRequest,
    CoverRequestStatus,
)
from app.models.phase4 import (
    ReallocationAlternative,
    ReallocationCase,
    ReallocationHistory,
    ReallocationStatus,
)
from app.models.session_auth import AuthSession
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User

__all__ = [
    "AuthSession",
    "AvailabilityEntry",
    "AvailabilityEntryKind",
    "AvailabilityStatus",
    "Base",
    "CyclePhase",
    "CoverInvite",
    "CoverInviteStatus",
    "CoverRequest",
    "CoverRequestStatus",
    "Enrollment",
    "EnrollmentStatus",
    "Location",
    "ReikiSession",
    "Role",
    "ReallocationAlternative",
    "ReallocationCase",
    "ReallocationHistory",
    "ReallocationStatus",
    "SessionStatus",
    "User",
    "WeeklyAvailability",
    "WeeklyCycle",
]
