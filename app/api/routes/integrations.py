from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_current_user
from app.database import get_db
from app.integrations.linkedin_oauth import LinkedInOAuthService
from app.integrations.gohighlevel import ghl_sync
from app.integrations.content_generation import (
    add_branding_to_video,
    create_did_video,
    create_heygen_video,
    get_heygen_video_status,
    post_to_all_platforms,
)

router = APIRouter()


class GenerateVideoPayload(BaseModel):
    script: str
    provider: str = "heygen"
    avatar_id: str | None = None
    presenter_id: str | None = None


class BrandVideoPayload(BaseModel):
    video_url: str
    branding: dict


class PublishPayload(BaseModel):
    body: str
    media_urls: list[str] = []
    scheduled_time: str | None = None
    platforms: list[str] | None = None


@router.get("/linkedin/authorize")
async def linkedin_authorize(
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return LinkedIn OAuth authorization URL."""
    try:
        svc = LinkedInOAuthService(db)
        return svc.get_authorization_url(state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """OAuth callback: exchange auth code for access/refresh tokens."""
    if error:
        raise HTTPException(status_code=400, detail=f"LinkedIn OAuth failed: {error} {error_description or ''}".strip())
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        svc = LinkedInOAuthService(db)
        token_data = await svc.exchange_code_for_token(code)
        return {
            "success": True,
            "provider": "linkedin",
            "state": state,
            "expires_in": token_data.get("expires_in"),
            "has_refresh_token": bool(token_data.get("refresh_token")),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {exc}")


@router.post("/linkedin/refresh")
async def linkedin_refresh(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Force refresh LinkedIn access token."""
    try:
        svc = LinkedInOAuthService(db)
        token_data = await svc.refresh_access_token()
        return {
            "success": True,
            "provider": "linkedin",
            "expires_in": token_data.get("expires_in"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {exc}")


@router.get("/linkedin/status")
async def linkedin_status(db: Session = Depends(get_db)):
    """Current LinkedIn OAuth connection status."""
    try:
        svc = LinkedInOAuthService(db)
        return svc.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/content/generate-video")
async def generate_avatar_video(
    payload: GenerateVideoPayload,
    user: dict = Depends(get_current_user),
):
    """Generate avatar video with HeyGen or D-ID."""
    try:
        provider = payload.provider.lower()
        if provider == "heygen":
            return await create_heygen_video(
                payload.script, avatar_id=payload.avatar_id or "default"
            )
        if provider in {"did", "d-id"}:
            return await create_did_video(
                payload.script, presenter_id=payload.presenter_id or "amy-Aq6OmGZnMt"
            )
        raise HTTPException(status_code=400, detail=f"Unknown provider: {payload.provider}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {exc}")


@router.get("/content/video-status/{video_id}")
async def get_video_status(video_id: str):
    try:
        return await get_heygen_video_status(video_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Status lookup failed: {exc}")


@router.post("/content/add-branding")
async def brand_video(
    payload: BrandVideoPayload,
    user: dict = Depends(get_current_user),
):
    try:
        return await add_branding_to_video(payload.video_url, payload.branding)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Branding failed: {exc}")


@router.post("/content/publish")
async def publish_content(
    payload: PublishPayload,
    user: dict = Depends(get_current_user),
):
    try:
        return await post_to_all_platforms(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Publish failed: {exc}")


@router.post("/ghl/sync")
async def sync_gohighlevel(db: Session = Depends(get_db)):
    """Manual GHL bidirectional sync."""
    result = await ghl_sync.sync_from_ghl(db)
    return result
