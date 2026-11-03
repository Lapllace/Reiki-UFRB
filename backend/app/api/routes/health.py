"""Health checks: liveness e readiness."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> Response:
    try:
        db.execute(text("SELECT 1"))
        ok = True
        detail = "banco acessível"
    except Exception:
        ok = False
        detail = "banco indisponível"
    if not ok:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content='{"status": "unavailable", "detail": "%s"}' % detail,
            media_type="application/json",
        )
    return Response(
        content='{"status": "ok", "detail": "%s"}' % detail,
        media_type="application/json",
    )
