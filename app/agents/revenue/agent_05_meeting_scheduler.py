"""
Agent 8: Meeting Scheduler
Automatically books meetings with engaged prospects.
Uses Google Calendar when configured, falls back to Calendly link.
"""
from typing import Dict, Any, Optional
import os
import httpx
from datetime import datetime

from app.agents.base import BaseAgent
from app.models import Prospect, OutreachSequence, Meeting
from app.integrations.calendar import CalendarService
from app.integrations.gohighlevel import ghl_sync


class MeetingSchedulerAgent(BaseAgent):
    """Schedules meetings with engaged prospects"""

    def __init__(self, db):
        super().__init__(agent_id=8, agent_name="Meeting Scheduler", db=db)
        self.calendly_api_key = os.getenv("CALENDLY_API_KEY")
        self.google_refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")

    async def execute(self) -> Dict[str, Any]:
        meetings_booked = 0

        if os.getenv("DEMO_MODE", "").lower() == "true":
            prospects = self.db.query(Prospect).filter(Prospect.status.in_(["engaged", "interested"]))\
                .limit(10).all()
            for prospect in prospects:
                meeting = Meeting(
                    prospect_id=prospect.id,
                    meeting_datetime=datetime.utcnow(),
                    meeting_type="discovery",
                    calendar_link="https://meet.google.com/demo-link",
                    status="scheduled",
                )
                self.db.add(meeting)
                prospect.status = "meeting_booked"
                meetings_booked += 1
            self.db.commit()
            return {
                "success": True,
                "data": {
                    "prospects_processed": len(prospects),
                    "meetings_booked": meetings_booked,
                    "demo_mode": True,
                    "cost_usd": 0,
                },
            }

        if not self.google_refresh_token and not self.calendly_api_key:
            return {
                "success": False,
                "error": "Google Calendar not configured",
                "data": {"meetings_booked": 0, "cost_usd": 0},
            }

        prospects = self.db.query(Prospect).filter(
            Prospect.status.in_(["engaged", "interested"]),
            ~Prospect.id.in_(
                self.db.query(Meeting.prospect_id).filter(
                    Meeting.status.in_(["scheduled", "confirmed"])
                )
            ),
        ).limit(20).all()

        for prospect in prospects:
            try:
                recent_reply = self.db.query(OutreachSequence).filter(
                    OutreachSequence.prospect_id == prospect.id,
                    OutreachSequence.replied == True,
                    OutreachSequence.reply_sentiment == "positive",
                ).order_by(OutreachSequence.replied_at.desc()).first()

                if recent_reply or prospect.status == "interested":
                    meeting_link = await self._generate_meeting_link(prospect)
                    if meeting_link:
                        meeting = Meeting(
                            prospect_id=prospect.id,
                            meeting_datetime=datetime.utcnow(),
                            meeting_type="discovery",
                            calendar_link=meeting_link,
                            status="scheduled",
                        )
                        self.db.add(meeting)
                        prospect.status = "meeting_booked"
                        prospect.lead_score = 100
                        self.db.commit()
                        ghl_contact_id = (prospect.custom_fields or {}).get("ghl_contact_id")
                        await ghl_sync.update_ghl_contact_status(
                            ghl_contact_id=ghl_contact_id,
                            status="meeting_booked",
                            notes=f"Meeting booked at {datetime.utcnow().isoformat()}",
                        )
                        meetings_booked += 1

            except Exception as e:
                self._log("book_meeting", "error", f"Failed for {prospect.company_name}: {str(e)}")
                continue

        return {
            "success": True,
            "data": {
                "prospects_processed": len(prospects),
                "meetings_booked": meetings_booked,
                "cost_usd": 0,
            },
        }

    async def _generate_meeting_link(self, prospect: Prospect) -> Optional[str]:
        if self.google_refresh_token:
            try:
                calendar = CalendarService()
                slots = await calendar.find_available_slots(days_ahead=3, duration_minutes=15)
                if slots:
                    event = await calendar.create_meeting(
                        title=f"Sales Call - {prospect.company_name}",
                        start_time=slots[0],
                        duration_minutes=15,
                        attendee_email=prospect.email or "dan@summitvoiceai.com",
                        description=f"Discovery call with {prospect.contact_name or prospect.company_name}",
                    )
                    return event.get("meeting_link") or event.get("event_id")
            except Exception as e:
                self._log("generate_link", "warning", f"Google Calendar failed: {str(e)}")

        if not self.calendly_api_key:
            return "https://calendly.com/summitvoiceai/discovery-call"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    "https://api.calendly.com/event_types",
                    headers={
                        "Authorization": f"Bearer {self.calendly_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if response.status_code == 200:
                    event_types = response.json().get("collection", [])
                    if event_types:
                        return event_types[0].get("scheduling_url")
        except Exception as e:
            self._log("generate_link", "warning", f"Calendly API failed: {str(e)}")

        return "https://calendly.com/summitvoiceai/discovery-call"
