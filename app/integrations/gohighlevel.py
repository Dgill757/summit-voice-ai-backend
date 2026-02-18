from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GoHighLevelSync:
    """Bidirectional sync helper for GoHighLevel contacts."""

    def __init__(self):
        self.api_key = os.getenv("GOHIGHLEVEL_API_KEY")
        self.location_id = os.getenv("GOHIGHLEVEL_LOCATION_ID")
        self.base_url = "https://rest.gohighlevel.com/v1"
        self.enabled = bool(self.api_key and self.location_id)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def sync_prospect_to_ghl(self, prospect_data: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"success": False, "error": "GHL not configured"}

        name = (prospect_data.get("contact_name") or prospect_data.get("name") or "").strip()
        first = name.split(" ")[0] if name else ""
        last = " ".join(name.split(" ")[1:]) if len(name.split(" ")) > 1 else ""

        payload = {
            "locationId": self.location_id,
            "firstName": first,
            "lastName": last,
            "email": prospect_data.get("email"),
            "phone": prospect_data.get("phone"),
            "companyName": prospect_data.get("company_name") or prospect_data.get("company"),
            "tags": ["Summit AI Lead", prospect_data.get("source", "Unknown")],
            "customFields": [
                {"key": "industry", "value": prospect_data.get("industry", "")},
                {"key": "status", "value": prospect_data.get("status", "")},
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/contacts",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code not in (200, 201):
                logger.error("GHL push failed: %s", response.text)
                return {"success": False, "error": response.text}
            body = response.json() if response.text else {}
            contact_id = body.get("id") or body.get("contact", {}).get("id")
            return {"success": True, "ghl_contact_id": contact_id}

    async def sync_from_ghl(self, db: Session) -> dict[str, Any]:
        if not self.enabled:
            return {"success": False, "error": "GHL not configured"}

        start_after_ms = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp() * 1000)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/contacts",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"locationId": self.location_id, "limit": 100, "startAfter": start_after_ms},
            )
            if response.status_code != 200:
                logger.error("GHL pull failed: %s", response.text)
                return {"success": False, "error": response.text}
            contacts = response.json().get("contacts", [])

        imported = 0
        for contact in contacts:
            email = contact.get("email")
            if email:
                exists = db.execute(
                    text("SELECT id FROM prospects WHERE email = :email"),
                    {"email": email},
                ).fetchone()
                if exists:
                    continue

            db.execute(
                text(
                    """
                    INSERT INTO prospects (
                        company_name, contact_name, email, phone, source, custom_fields, created_at
                    ) VALUES (
                        :company_name, :contact_name, :email, :phone, :source, :custom_fields, NOW()
                    )
                    """
                ),
                {
                    "company_name": contact.get("companyName") or "Unknown",
                    "contact_name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip() or None,
                    "email": email,
                    "phone": contact.get("phone"),
                    "source": "GoHighLevel Import",
                    "custom_fields": {"ghl_contact_id": contact.get("id")},
                },
            )
            imported += 1

        db.commit()
        return {"success": True, "contacts_imported": imported}

    async def update_ghl_contact_status(
        self,
        ghl_contact_id: str | None,
        status: str,
        notes: str = "",
    ) -> dict[str, Any]:
        if not self.enabled or not ghl_contact_id:
            return {"success": False, "error": "GHL not configured or missing contact id"}

        tag = {
            "contacted": "Contacted",
            "interested": "Interested",
            "meeting_booked": "Meeting Booked",
            "client": "Client",
            "churned": "Churned",
        }.get(status, status)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{self.base_url}/contacts/{ghl_contact_id}",
                headers=self._headers(),
                json={
                    "tags": [tag],
                    "customFields": [
                        {"key": "last_updated", "value": datetime.now(timezone.utc).isoformat()},
                        {"key": "ai_notes", "value": notes},
                    ],
                },
            )
            if response.status_code not in (200, 201):
                logger.error("GHL status update failed: %s", response.text)
                return {"success": False, "error": response.text}
        return {"success": True}


ghl_sync = GoHighLevelSync()

