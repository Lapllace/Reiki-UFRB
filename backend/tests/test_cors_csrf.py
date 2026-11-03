"""Testes de CORS e proteção contra CSRF."""

from fastapi.testclient import TestClient


def test_cors_allowed_origin(client: TestClient) -> None:
    resp = client.get(
        "/locations",
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin_no_header(client: TestClient) -> None:
    resp = client.get("/locations", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("access-control-allow-origin") is None


def test_cors_preflight(client: TestClient) -> None:
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_state_changing_request_from_disallowed_origin_rejected(
    client: TestClient, make_user
) -> None:
    user = make_user()
    resp = client.post(
        "/auth/login",
        json={"email": user.email, "password": "senha-teste-123"},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
