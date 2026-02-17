from __future__ import annotations

import os
from typing import Any, Dict

from app.config import settings


class SMSService:
    """SMS sending via Twilio."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID") or getattr(settings, "twilio_account_sid", None)
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN") or getattr(settings, "twilio_auth_token", None)
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER") or getattr(settings, "twilio_phone_number", None)

    async def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        if not all([self.account_sid, self.auth_token, self.from_number]):
            return {"status": "failed", "error": "Twilio credentials not configured", "to": to}
        try:
            from twilio.rest import Client  # lazy import so dependency is optional
        except Exception as exc:
            return {"status": "failed", "error": f"Twilio dependency missing: {exc}", "to": to}

        try:
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(body=message, from_=self.from_number, to=to)
            return {"status": "sent", "sid": msg.sid, "to": to}
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "to": to}

