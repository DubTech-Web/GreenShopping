import os

# Hermetic tests: pin a throwaway SQLite DB and offline mode BEFORE any app module imports.
# `app.database` binds its engine at import time from DATABASE_URL, and `app.main`'s lifespan
# runs create_all() on that engine — so without this, importing the app would connect to the
# real managed PostgreSQL from .env. Env vars outrank the .env file in pydantic-settings, so
# these win. Per-request settings are further isolated by the `test_environment` fixture below.
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["PAYSTACK_SECRET_KEY"] = ""
os.environ["PAYSTACK_PUBLIC_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    """Ensure tests run in simulated/offline mode without hitting external APIs."""
    test_settings = Settings(
        app_env="development",
        jwt_secret="test-jwt-secret-key-32-chars-long-minimum!",
        resend_api_key="",
        paystack_secret_key="",
        paystack_public_key="",
        smtp_host="",
        smtp_user="",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.services.email.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.services.payments.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.services.security.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: test_settings)
    yield


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory connection for the test
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client, email="user@example.com", password="password123", name="Test User"):
    """Helper: register a customer, verify email, and return the auth token."""
    resp = client.post(
        "/api/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    if "access_token" in body:
        return body["access_token"]
    code = body.get("dev_code")
    if code:
        v_resp = client.post("/api/auth/verify-email", json={"email": email, "code": code})
        assert v_resp.status_code == 200, v_resp.text
        return v_resp.json()["access_token"]
    # Fallback to login
    l_resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return l_resp.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

