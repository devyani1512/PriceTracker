"""Email delivery via SMTP (Gmail app password by default).

Kept deliberately small and transport-only: build a message, send it, report
what happened. Business rules live in the notification service.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr


class EmailService:
    def __init__(self, logger: logging.Logger, cfg: dict):
        mail = cfg["Email"]
        self.logger = logger
        self.host = str(mail.get("host") or "smtp.gmail.com")
        self.port = int(mail.get("port") or 587)
        self.user = str(mail.get("user") or "")
        self.app_password = str(mail.get("appPassword") or "")
        self.from_addr = str(mail.get("fromAddr") or self.user)
        self.from_name = str(mail.get("fromName") or "Price Tracker")

    @property
    def configured(self) -> bool:
        return bool(self.user and self.app_password and self.from_addr)

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> tuple[bool, str]:
        """Return (sent, detail). Unconfigured SMTP is a logged dry-run."""
        if not self.configured:
            self.logger.info(
                "email dry-run (SMTP not configured) -> %s | %s\n%s", to, subject, text
            )
            return True, "dry-run: SMTP not configured"

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
