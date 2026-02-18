from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx


class LateClient:
    """Unified social publishing client using getlate.dev."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("LATE_API_KEY")
        self.base_url = (base_url or os.getenv("LATE_API_BASE") or "https://getlate.dev/api/v1").rstrip("/")
        if not self.api_key:
            raise ValueError("LATE_API_KEY is not configured")

    async def publish(
        self,
        *,
        platform: str,
        text: str,
        media_url: str | None = None,
        scheduled_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish a post to one platform through LATE."""
        payload: dict[str, Any] = {
            "platform": platform.lower(),
            "text": text or "",
        }
        if media_url:
            payload["media_url"] = media_url
        if scheduled_at:
            payload["scheduled_at"] = scheduled_at.isoformat()
        if metadata:
            payload["metadata"] = metadata

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/posts", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json() if response.content else {}

        # Normalize common shapes from proxy APIs.
        return {
            "ok": True,
            "id": data.get("id") or data.get("post_id") or data.get("data", {}).get("id"),
            "status": data.get("status") or "published",
            "raw": data,
        }

