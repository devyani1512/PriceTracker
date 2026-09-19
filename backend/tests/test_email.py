"""Email provider tests — HTTP APIs are what works on Render's free plan."""

from __future__ import annotations

import logging

import httpx
import pytest

from app.services import email_service
from app.services.email_service import EmailService

logger = logging.getLogger("test.email")


def _cfg(**overrides) -> dict:
    mail = {
        "provider": "brevo",
        "apiKey": "secret-key",
        "fromAddr": "from@example.com",
        "fromName": "Price Tracker",
        "host": "smtp.gmail.com",
        "port": 587,
        "user": "",
        "appPassword": "",
    }
    mail.update(overrides)
    return {"Email": mail}


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_unconfigured_is_dry_run_without_network(monkeypatch):
    def explode(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("network call attempted while unconfigured")

    monkeypatch.setattr(email_service.httpx, "post", explode)
    svc = EmailService(logger, _cfg(apiKey=""))
    assert svc.configured is False
    ok, detail = svc.send("user@example.com", "Hi", "Body")
    assert ok is True
    assert detail.startswith("dry-run")


def test_brevo_payload(monkeypatch):
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json)
        return _FakeResponse(201)

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    svc = EmailService(logger, _cfg(provider="brevo"))

    ok, detail = svc.send("user@example.com", "Subject", "Body")

    assert (ok, detail) == (True, "sent")
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == "secret-key"
    assert captured["json"]["to"] == [{"email": "user@example.com"}]
    assert captured["json"]["sender"]["email"] == "from@example.com"
    assert captured["json"]["textContent"] == "Body"


def test_sendgrid_payload(monkeypatch):
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json)
        return _FakeResponse(202)

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    svc = EmailService(logger, _cfg(provider="sendgrid"))

    ok, _ = svc.send("user@example.com", "Subject", "Body")

    assert ok is True
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["json"]["personalizations"][0]["to"] == [{"email": "user@example.com"}]


def test_http_failure_is_reported_not_raised(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("network is unreachable")

    monkeypatch.setattr(email_service.httpx, "post", fail)
    svc = EmailService(logger, _cfg(provider="brevo"))

    ok, detail = svc.send("user@example.com", "Subject", "Body")

    assert ok is False
    assert "brevo API error" in detail


def test_unknown_provider_fails_cleanly():
    svc = EmailService(logger, _cfg(provider="nope"))
    ok, detail = svc.send("user@example.com", "Subject", "Body")
    assert ok is False
    assert "unknown email provider" in detail


def test_smtp_requires_user_and_password():
    assert EmailService(logger, _cfg(provider="smtp", user="", appPassword="")).configured is False
    assert (
        EmailService(
            logger, _cfg(provider="smtp", user="u@example.com", appPassword="pw")
        ).configured
        is True
    )


@pytest.mark.parametrize("provider", ["brevo", "sendgrid", "resend"])
def test_http_providers_are_configured_with_key_and_sender(provider):
    assert EmailService(logger, _cfg(provider=provider)).configured is True
