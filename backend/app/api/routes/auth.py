"""Autenticação: /auth/me, /auth/login, /auth/logout."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import enforce_same_origin, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.domain import LoginIn, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        expires=settings.session_ttl_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure or settings.is_production,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


@router.get("/me", response_model=UserOut)
def read_me(user: User | None = Depends(get_current_user)) -> UserOut:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não autenticada.",
        )
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginIn,
    response: Response,
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        user = auth_service.authenticate(db, payload.email, payload.password)
    except auth_service.InvalidCredentials:
        # Mesma mensagem para e-mail inexistente e senha errada.
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "E-mail ou senha incorretos.", "code": "invalid_credentials"},
        )
    token, _ = auth_service.create_session(db, user)
    _set_cookie(response, token)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> Response:
    """Revoga a sessão e expira o cookie NA MESMA resposta.

    Importante: reutilizar a resposta injetada. Criar um novo ``Response``
    depois de modificar os cabeçalhos do injetado descartaria o ``Set-Cookie``
    de exclusão do cookie.
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        auth_service.revoke_session(db, token)
    # Expira/remove o cookie na resposta injetada (mesma resposta retornada).
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure or settings.is_production,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
