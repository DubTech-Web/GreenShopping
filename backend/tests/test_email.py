import logging
import smtplib

import httpx

from app.config import Settings
from app.services import email as email_service


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300


class FakeHttpClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, endpoint, *, headers, json):
        self.request = (endpoint, headers, json)
        if self.error:
            raise self.error
        return self.response


class FakeSMTP:
    instances = []
    login_error = None

    def __init__(self, *_args, **_kwargs):
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        pass

    def login(self, *_args):
        if self.__class__.login_error:
            raise self.__class__.login_error

    def send_message(self, _message):
        pass


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "email_provider": "brevo",
        "brevo_api_key": "test-api-key",
        "brevo_from_email": "verified@example.com",
        "brevo_from_name": "GreenShopping Test",
        "smtp_host": "smtp.gmail.com",
        "smtp_user": "sender@gmail.com",
        "smtp_password": "test-smtp-password",
        "smtp_from_email": "GreenShopping <sender@gmail.com>",
    }
    values.update(overrides)
    return Settings(**values)


def _patch_smtp(monkeypatch, *, login_error=None):
    FakeSMTP.instances = []
    FakeSMTP.login_error = login_error
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)


def test_brevo_sends_expected_transactional_payload(monkeypatch):
    client = FakeHttpClient(response=FakeResponse(201))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(email_service.httpx, "Client", lambda **_kwargs: client)
    _patch_smtp(monkeypatch)

    assert email_service.send_email("recipient@example.com", "Welcome", "<p>Hello</p>")

    endpoint, headers, payload = client.request
    assert endpoint == "https://api.brevo.com/v3/smtp/email"
    assert headers["api-key"] == "test-api-key"
    assert payload == {
        "sender": {"name": "GreenShopping Test", "email": "verified@example.com"},
        "to": [{"email": "recipient@example.com"}],
        "subject": "Welcome",
        "htmlContent": "<p>Hello</p>",
    }
    assert FakeSMTP.instances == []


def test_rejected_brevo_request_falls_back_and_failed_smtp_returns_false(
    monkeypatch, caplog
):
    client = FakeHttpClient(response=FakeResponse(401))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(email_service.httpx, "Client", lambda **_kwargs: client)
    _patch_smtp(
        monkeypatch,
        login_error=smtplib.SMTPAuthenticationError(535, b"test-smtp-password"),
    )

    with caplog.at_level(logging.WARNING, logger="greenshopping.email"):
        assert not email_service.send_email(
            "recipient@example.com", "Sensitive subject", "<p>654321</p>"
        )

    assert len(FakeSMTP.instances) == 1
    assert "test-api-key" not in caplog.text
    assert "test-smtp-password" not in caplog.text
    assert "654321" not in caplog.text
    assert "Sensitive subject" not in caplog.text


def test_uncertain_brevo_timeout_does_not_send_duplicate_fallback(monkeypatch):
    client = FakeHttpClient(error=httpx.ReadTimeout("request timed out"))
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(email_service.httpx, "Client", lambda **_kwargs: client)
    _patch_smtp(monkeypatch)

    assert not email_service.send_email("recipient@example.com", "Welcome", "<p>Hello</p>")
    assert FakeSMTP.instances == []


def test_provider_defaults_follow_application_environment():
    assert Settings(app_env="development").preferred_email_provider == "smtp"
    assert Settings(app_env="production").preferred_email_provider == "brevo"
    assert Settings(app_env="production", email_provider="smtp").preferred_email_provider == "smtp"
