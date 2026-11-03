"""Engine e fábrica de sessões SQLAlchemy (síncrono, psycopg3)."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    return create_engine(url, pool_pre_ping=True, future=True)


engine = create_db_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: garante commit/rollback e fechamento da sessão."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database(db: Session) -> bool:
    """Verificação simples de conectividade (usada pelo /health/ready)."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
