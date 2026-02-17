"""Security and authentication helpers for single-user JWT auth."""
from __future__ import annotations

import binascii
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 60 * 12
AUTH_SCHEME = HTTPBearer(auto_error=False)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _secret_key() -> str:
    return settings.secret_key.get_secret_value()


def hash_password(password: str, salt_hex: str, iterations: int = 210000) -> str:
    """Create pbkdf2_sha256 hash string."""
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
    )
    digest_hex = binascii.hexlify(dk).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_hex}${digest_hex}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify pbkdf2_sha256 hash format: pbkdf2_sha256$iters$salt_hex$digest_hex."""
    try:
        algorithm, iter_str, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hash_password(password, salt_hex=salt_hex, iterations=int(iter_str))
        return hmac.compare_digest(expected, encoded_hash)
    except Exception:
        return False


def create_access_token(subject: str, extra: Dict[str, Any] | None = None) -> str:
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(minutes=TOKEN_TTL_MINUTES)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(AUTH_SCHEME),
) -> Dict[str, Any]:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    email = str(payload.get("sub", "")).strip().lower()
    expected = settings.admin_email.lower()
    if email != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject"
        )
    return {
        "id": "owner",
        "email": settings.admin_email,
        "name": settings.admin_name,
    }
