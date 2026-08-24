"""Authentication tests (Spec §9 → Authentication: registration, login, invalid credentials)."""
from tests.conftest import auth_header, register


def test_register_returns_token(client):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    code = resp.json()["dev_code"]
    assert code
    verify_resp = client.post("/api/auth/verify-email", json={"email": "ada@example.com", "code": code})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["access_token"]


def test_register_duplicate_email_rejected(client):
    register(client, email="dup@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"name": "Other", "email": "dup@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_login_success(client):
    register(client, email="login@example.com", password="password123")
    resp = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_invalid_credentials(client):
    register(client, email="real@example.com", password="password123")
    resp = client.post(
        "/api/auth/login", json={"email": "real@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401  # not authenticated


def test_protected_route_with_token(client):
    token = register(client, email="me@example.com")
    resp = client.get("/api/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert body["is_admin"] is False
