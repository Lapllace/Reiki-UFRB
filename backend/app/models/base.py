"""Compatibilidade: Base e mixins vivem em ``app.db.base`` e ``app.models.mixins``.

Módulo mantido apenas para não quebrar imports antigos; prefira:
``from app.db.base import Base`` e ``from app.models.mixins import UUIDPk, Timestamped``.
"""

from app.db.base import Base  # noqa: F401
from app.models.mixins import Timestamped, UUIDPk, utcnow  # noqa: F401
