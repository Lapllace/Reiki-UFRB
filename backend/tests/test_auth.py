"""Testes de autenticação: login, me, logout, cookie e permissões."""

from fastapi.testclient import TestClient

from app.models.user import Role
from tests.conftest import login

PASSWORD = "senha-teste-123"


def test_login_success_sets_cookie(client: TestClient, make_user) -> None:
    user = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    resp = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email
    assert body["role"] == "participant"
    # camelCase e sem hash/senha
    assert "password" not in body and "passwordHash" not in body
    set_cookie = resp.headers["set-cookie"]
    assert "httponly" in set_cookie.lower()
    assert "samesite=" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()


def test_login_wrong_password(client: TestClient, make_user) -> None:
    user = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    resp = client.post(
        "/auth/login", json={"email": user.email, "password": "errada-12345"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert "detail" in body


def test_login_unknown_email_same_error(client: TestClient, make_user) -> None:
    make_user(role=Role.PARTICIPANT, password=PASSWORD)
    resp = client.post(
        "/auth/login", json={"email": "fantasma@x.local", "password": "qualquer-123"}
    )
    assert resp.status_code == 401


def test_me_without_session(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_session(client: TestClient, make_user) -> None:
    user = make_user(role=Role.INSTRUCTOR, password=PASSWORD)
    login(client, user.email, PASSWORD)
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "instructor"
    assert body["id"] == str(user.id)


def test_logout_invalidates_session(client: TestClient, make_user) -> None:
    user = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    login(client, user.email, PASSWORD)
    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_role_restriction(client: TestClient, make_user) -> None:
    # Dependência require_role validada com uma rota efêmera sobre a própria
    # app do fixture (mesma configuração e mesmo banco das demais provas).
    from fastapi import Depends
    from fastapi.testclient import TestClient as TC

    from app.api.deps import require_role

    app = client.app

    @app.get("/_test/coordinator-only")
    def only_coordinator(user=Depends(require_role(Role.COORDINATOR))):
        return {"ok": True}

    participant = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    coordinator = make_user(role=Role.COORDINATOR, password=PASSWORD)

    c1 = TC(app)
    login(c1, participant.email, PASSWORD)
    assert c1.get("/_test/coordinator-only").status_code == 403

    c2 = TC(app)
    login(c2, coordinator.email, PASSWORD)
    assert c2.get("/_test/coordinator-only").status_code == 200
    # Remove a rota efêmera para não contaminar outros testes.
    app.router.routes = [
        r for r in app.router.routes if getattr(r, "path", "") != "/_test/coordinator-only"
    ]


def test_logout_deletes_cookie_and_revokes_session(
    client: TestClient, make_user, db
) -> None:
    """Logout: 204, Set-Cookie de expiração presente e sessão revogada no banco."""
    from datetime import UTC, datetime

    from app.models.session_auth import AuthSession

    user = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    login(client, user.email, PASSWORD)

    # Token puro é capturado do Set-Cookie do login.
    import re

    cookie_line = re.search(
        r"reiki_session=([^;]+)", client.get("/auth/me").headers.get("set-cookie", "")
    )
    # /auth/me não seta cookie; captura via jar do TestClient.
    token = None
    for cookie in client.cookies.jar:
        if cookie.name == "reiki_session":
            token = cookie.value
    assert token, "cookie de sessão não encontrado após login"

    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    # Cabeçalho de exclusão do cookie preservado na resposta.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "reiki_session=" in set_cookie
    assert 'max-age=0' in set_cookie.lower() or "expires=" in set_cookie.lower()
    assert "GMT" in set_cookie

    # Sessão revogada no banco.
    session_row = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == __import__("hashlib").sha256(token.encode()).hexdigest())
        .one_or_none()
    )
    assert session_row is not None
    assert session_row.revoked_at is not None
    assert not session_row.is_valid(datetime.now(UTC))

    # Após logout, /auth/me volta a 401.
    assert client.get("/auth/me").status_code == 401


def test_logout_without_session_returns_204(client: TestClient) -> None:
    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    assert "reiki_session=" in resp.headers.get("set-cookie", "")
