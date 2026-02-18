from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.config import settings


class CalendarService:
    """Google Calendar integration."""

    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID") or getattr(settings, "google_calendar_client_id", None)
        self.client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET") or getattr(settings, "google_calendar_client_secret", None)
        self.refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") or getattr(settings, "google_calendar_refresh_token", None)
        self.timezone = os.getenv("GOOGLE_CALENDAR_TZ", "America/New_York")
        self._service = None

    def _ensure_service(self):
        if self._service is not None:
            return self._service
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Google Calendar credentials are not configured")
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Google dependencies missing: {exc}") from exc

        creds = Credentials.from_authorized_user_info(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            }
        )
        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    async def create_meeting(
        self,
        title: str,
        start_time: datetime,
        duration_minutes: int,
        attendee_email: str,
        description: str = "",
    ) -> Dict[str, Any]:
        service = self._ensure_service()
        end_time = start_time + timedelta(minutes=duration_minutes)
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": self.timezone},
            "end": {"dateTime": end_time.isoformat(), "timeZone": self.timezone},
            "attendees": [{"email": attendee_email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meeting-{int(start_time.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        created = (
            service.events()
            .insert(calendarId="primary", body=event, conferenceDataVersion=1)
            .execute()
        )
        return {
            "event_id": created["id"],
            "meeting_link": created.get("hangoutLink"),
            "status": "created",
        }

    async def find_available_slots(
        self, days_ahead: int = 7, duration_minutes: int = 30
    ) -> List[datetime]:
        # Placeholder slot generation with basic intervals (full freebusy scheduling can be added next).
        now = datetime.utcnow()
        slots: List[datetime] = []
        cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        for _ in range(min(days_ahead * 8, 40)):
            slots.append(cursor)
            cursor += timedelta(hours=2)
        return slots
