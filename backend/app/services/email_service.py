"""Email delivery: SMTP for local/dev, HTTP APIs for Render.

Render's **free** web services block outbound traffic to SMTP ports 25/465/587,
so Gmail SMTP cannot work there. When ``Email.provider`` is an HTTP provider we
send over HTTPS (port 443) instead:

* ``brevo``    — POST https://api.brevo.com/v3/smtp/email
* ``sendgrid`` — POST https://api.sendgrid.com/v3/mail/send
* ``resend``   — POST https://api.resend.com/emails

Kept deliberately small and transport-only: build a message, send it, report
what happened. Business rules live in the notification service.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import httpx

_HTTP_ENDPOINTS = {
    "brevo": "https://api.brevo.com/v3/smtp/email",
    "sendgrid": "https://api.sendgrid.com/v3/mail/send",
    "resend": "https://api.resend.com/emails",
}


class EmailService:
    def __init__(self, logger: logging.Logger, cfg: dict):
        mail = cfg["Email"]
        self.logger = logger
        self.provider = str(mail.get("provider") or "smtp").strip().lower()
        self.host = str(mail.get("host") or "smtp.gmail.com")
        self.port = int(mail.get("port") or 587)
        self.user = str(mail.get("user") or "")
        self.app_password = str(mail.get("appPassword") or "")
        self.api_key = str(mail.get("apiKey") or "")
        self.from_addr = str(mail.get("fromAddr") or self.user)
        self.from_name = str(mail.get("fromName") or "Price Tracker")

    @property
    def configured(self) -> bool:
        if self.provider == "smtp":
            return bool(self.user and self.app_password and self.from_addr)
        return bool(self.api_key and self.from_addr)

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> tuple[bool, str]:
        """Return (sent, detail). Unconfigured email is a logged dry-run."""
        if not self.configured:
            self.logger.info(
                "email dry-run (%s not configured) -> %s | %s\n%s",
                self.provider,
                to,
                subject,
                text,
            )
            return True, f"dry-run: {self.provider} not configured"

        if self.provider == "smtp":
            return self._send_smtp(to, subject, text, html)
        return self._send_http(to, subject, text, html)

    # ------------------------------------------------------------------ SMTP
    def _send_smtp(self, to: str, subject: str, text: str, html: str | None) -> tuple[bool, str]:
        message = EmailMessage()
        message["From"] = formataddr((self.from_name, self.from_addr))
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(self.user, self.app_password)
                server.send_message(message)
            self.logger.info("email sent to %s: %s", to, subject)
            return True, "sent"
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("email send failed to %s", to)
            return False, f"SMTP error: {exc}"

    # ------------------------------------------------------------------ HTTP API
    def _send_http(self, to: str, subject: str, text: str, html: str | None) -> tuple[bool, str]:
        endpoint = _HTTP_ENDPOINTS.get(self.provider)
        if endpoint is None:
            return False, f"unknown email provider: {self.provider}"

        headers, payload = self._http_request(to, subject, text, html)
        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("email send failed to %s via %s", to, self.provider)
            return False, f"{self.provider} API error: {exc}"

        self.logger.info("email sent to %s: %s", to, subject)
        return True, "sent"

    def _http_request(
        self, to: str, subject: str, text: str, html: str | None
    ) -> tuple[dict, dict]:
        if self.provider == "brevo":
            payload: dict = {
                "sender": {"email": self.from_addr, "name": self.from_name},
                "to": [{"email": to}],
                "subject": subject,
                "textContent": text,
            }
            if html:
                payload["htmlContent"] = html
            return {"api-key": self.api_key, "accept": "application/json"}, payload

        if self.provider == "sendgrid":
            content = [{"type": "text/plain", "value": text}]
            if html:
                content.append({"type": "text/html", "value": html})
            return {"Authorization": f"Bearer {self.api_key}"}, {
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": self.from_addr, "name": self.from_name},
                "subject": subject,
                "content": content,
            }

        if self.provider == "resend":
            payload = {
                "from": formataddr((self.from_name, self.from_addr)),
                "to": [to],
                "subject": subject,
                "text": text,
            }
            if html:
                payload["html"] = html
            return {"Authorization": f"Bearer {self.api_key}"}, payload

        return {}, {}
