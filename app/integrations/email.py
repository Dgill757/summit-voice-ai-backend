from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx

from app.config import settings


class EmailService:
    """Email sending via SendGrid or SMTP."""

    def __init__(self):
        self.sendgrid_key = os.getenv("SENDGRID_API_KEY") or getattr(settings, "sendgrid_api_key", None)
        self.smtp_host = os.getenv("SMTP_HOST") or getattr(settings, "smtp_host", None)
        self.smtp_port = int(os.getenv("SMTP_PORT", getattr(settings, "smtp_port", 587)))
        self.smtp_username = os.getenv("SMTP_USERNAME") or getattr(settings, "smtp_username", None)
        self.smtp_password = os.getenv("SMTP_PASSWORD") or getattr(settings, "smtp_password", None)
        self.default_from_email = os.getenv("DEFAULT_FROM_EMAIL", "noreply@summitvoiceai.com")
        self.default_from_name = os.getenv("DEFAULT_FROM_NAME", "Summit Voice AI")

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        from_email = from_email or self.default_from_email
        from_name = from_name or self.default_from_name
        if self.sendgrid_key:
            return await self._send_via_sendgrid(to, subject, html_content, from_email, from_name)
        return await self._send_via_smtp(to, subject, html_content, from_email, from_name)

    async def _send_via_sendgrid(
        self, to: str, subject: str, html_content: str, from_email: str, from_name: str
    ) -> Dict[str, Any]:
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_content}],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.sendgrid_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return {"status": "sent", "message_id": response.headers.get("X-Message-Id"), "to": to}

    async def _send_via_smtp(
        self, to: str, subject: str, html_content: str, from_email: str, from_name: str
    ) -> Dict[str, Any]:
        if not all([self.smtp_host, self.smtp_username, self.smtp_password]):
            raise ValueError("SMTP is not configured and SendGrid key is missing")
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{from_name} <{from_email}>"
        message["To"] = to
        message.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(message)
        return {"status": "sent", "to": to}

