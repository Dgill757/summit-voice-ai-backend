from __future__ import annotations

import os
from typing import Any

import httpx


async def create_heygen_video(script: str, avatar_id: str = "default") -> dict[str, Any]:
    """Generate avatar video via HeyGen API."""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        raise ValueError("HEYGEN_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": api_key},
            json={
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id,
                            "avatar_style": "normal",
                        },
                        "voice": {"type": "text", "input_text": script},
                    }
                ],
                "dimension": {"width": 1920, "height": 1080},
                "aspect_ratio": "16:9",
            },
        )
        response.raise_for_status()
        return response.json()


async def get_heygen_video_status(video_id: str) -> dict[str, Any]:
    """Check HeyGen video generation status."""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        raise ValueError("HEYGEN_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers={"X-Api-Key": api_key},
        )
        response.raise_for_status()
        return response.json()


async def create_did_video(script: str, presenter_id: str = "amy-Aq6OmGZnMt") -> dict[str, Any]:
    """Generate avatar video via D-ID API."""
    api_key = os.getenv("DID_API_KEY")
    if not api_key:
        raise ValueError("DID_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.d-id.com/talks",
            headers={
                "Authorization": f"Basic {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "script": {
                    "type": "text",
                    "input": script,
                    "provider": {"type": "microsoft", "voice_id": "en-US-JennyNeural"},
                },
                "source_url": "https://d-id-public-bucket.s3.amazonaws.com/alice.jpg",
                "config": {"fluent": True, "stitch": True},
            },
        )
        response.raise_for_status()
        return response.json()


async def add_branding_to_video(video_url: str, branding_config: dict[str, Any]) -> dict[str, Any]:
    """Add branding, captions, overlays via Shotstack API."""
    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        raise ValueError("SHOTSTACK_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.shotstack.io/v1/render",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "timeline": {
                    "tracks": [
                        {
                            "clips": [
                                {
                                    "asset": {"type": "video", "src": video_url},
                                    "start": 0,
                                    "length": "auto",
                                }
                            ]
                        },
                        {
                            "clips": [
                                {
                                    "asset": {
                                        "type": "image",
                                        "src": branding_config.get("logo_url"),
                                        "width": 200,
                                        "height": 100,
                                    },
                                    "start": 0,
                                    "length": "auto",
                                    "position": "topRight",
                                }
                            ]
                        },
                    ]
                },
                "output": {"format": "mp4", "resolution": "1080"},
            },
        )
        response.raise_for_status()
        return response.json()


async def post_to_all_platforms(content: dict[str, Any]) -> dict[str, Any]:
    """Publish multi-platform content via LATE API."""
    api_key = os.getenv("LATE_API_KEY")
    if not api_key:
        raise ValueError("LATE_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.getlate.dev/v1/post",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "platforms": content.get(
                    "platforms", ["linkedin", "twitter", "facebook", "instagram", "tiktok"]
                ),
                "content": content.get("body"),
                "media": content.get("media_urls", []),
                "scheduled_time": content.get("scheduled_time"),
            },
        )
        response.raise_for_status()
        return response.json()

