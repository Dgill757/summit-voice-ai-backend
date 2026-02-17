from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx

from app.config import settings


class MetaMessagingService:
    """Facebook & Instagram messaging via Meta Graph API."""

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN") or getattr(settings, "meta_access_token", None)
        self.page_id = os.getenv("META_PAGE_ID") or getattr(settings, "meta_page_id", None)
        self.base_url = "https://graph.facebook.com/v18.0"
        if not self.access_token:
            raise ValueError("META_ACCESS_TOKEN is not configured")

    async def send_message(
        self, recipient_id: str, message_text: str, platform: str = "facebook"
    ) -> Dict[str, Any]:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text},
            "messaging_type": "RESPONSE",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/me/messages",
                params={"access_token": self.access_token},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return {"status": "sent", "message_id": data.get("message_id"), "recipient_id": recipient_id}

    async def get_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.page_id:
            raise ValueError("META_PAGE_ID is not configured")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/{self.page_id}/conversations",
                params={
                    "access_token": self.access_token,
                    "fields": "participants,messages,updated_time",
                    "limit": limit,
                },
            )
            response.raise_for_status()
            return response.json().get("data", [])

    async def reply_to_message(self, conversation_id: str, message_text: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            conv = await client.get(
                f"{self.base_url}/{conversation_id}",
                params={"access_token": self.access_token, "fields": "participants"},
            )
            conv.raise_for_status()
            participants = (conv.json().get("participants") or {}).get("data") or []
            recipient_id = participants[0]["id"] if participants else None
            if not recipient_id:
                raise ValueError("Could not find recipient")
        return await self.send_message(recipient_id, message_text)

