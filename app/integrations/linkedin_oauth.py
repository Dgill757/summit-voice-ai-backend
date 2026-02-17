from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.models import OAuthToken


class LinkedInOAuthService:
    AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    PROVIDER = "linkedin"

    def __init__(self, db: Session):
        self.db = db
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "")
        self.scope = os.getenv(
            "LINKEDIN_OAUTH_SCOPE",
            "openid profile email w_member_social",
        )

    def get_authorization_url(self, state: str | None = None) -> dict[str, str]:
        if not self.client_id or not self.redirect_uri:
            raise ValueError("LinkedIn OAuth is not configured")
        state_value = state or secrets.token_urlsafe(24)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "state": state_value,
        }
        return {
            "authorization_url": f"{self.AUTHORIZE_URL}?{urlencode(params)}",
            "state": state_value,
        }

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("LinkedIn OAuth is not configured")

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        self._store_token_payload(data)
        return data

    async def refresh_access_token(self) -> dict[str, Any]:
        token_row = self.db.query(OAuthToken).filter(OAuthToken.provider == self.PROVIDER).first()
        if not token_row or not token_row.refresh_token:
            raise ValueError("No LinkedIn refresh token stored")
        if not self.client_id or not self.client_secret:
            raise ValueError("LinkedIn OAuth is not configured")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token_row.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        # Preserve previous refresh token when provider does not return a new one.
        if not data.get("refresh_token"):
            data["refresh_token"] = token_row.refresh_token
        self._store_token_payload(data)
        return data

    async def get_valid_access_token(self) -> str | None:
        token_row = self.db.query(OAuthToken).filter(OAuthToken.provider == self.PROVIDER).first()
        if not token_row:
            return None

        now_utc = datetime.now(timezone.utc)
        if token_row.expires_at is None:
            return token_row.access_token

        # Refresh proactively two minutes early.
        if token_row.expires_at <= now_utc + timedelta(minutes=2):
            try:
                refreshed = await self.refresh_access_token()
                return refreshed.get("access_token")
            except Exception:
                return None

        return token_row.access_token

    def get_status(self) -> dict[str, Any]:
        token_row = self.db.query(OAuthToken).filter(OAuthToken.provider == self.PROVIDER).first()
        if not token_row:
            return {"connected": False, "provider": self.PROVIDER}
        return {
            "connected": True,
            "provider": self.PROVIDER,
            "expires_at": token_row.expires_at.isoformat() if token_row.expires_at else None,
            "has_refresh_token": bool(token_row.refresh_token),
        }

    def _store_token_payload(self, token_payload: dict[str, Any]) -> OAuthToken:
        access_token = token_payload.get("access_token")
        if not access_token:
            raise ValueError("LinkedIn token response missing access_token")

        expires_in = int(token_payload.get("expires_in") or 0)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            if expires_in > 0
            else None
        )

        refresh_token = token_payload.get("refresh_token")
        row = self.db.query(OAuthToken).filter(OAuthToken.provider == self.PROVIDER).first()
        if row is None:
            row = OAuthToken(
                provider=self.PROVIDER,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            self.db.add(row)
        else:
            row.access_token = access_token
            if refresh_token:
                row.refresh_token = refresh_token
            row.expires_at = expires_at

        self.db.commit()
        self.db.refresh(row)
        return row

