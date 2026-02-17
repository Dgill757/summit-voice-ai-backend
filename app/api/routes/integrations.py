from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.integrations.linkedin_oauth import LinkedInOAuthService

router = APIRouter()


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

