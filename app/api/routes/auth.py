from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.core.security import create_access_token, get_current_user, verify_password
from app.schemas.auth import LoginRequest, LoginResponse, UserOut

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    if email != settings.admin_email.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(
        payload.password, settings.admin_password_hash.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    user = UserOut(id="owner", email=settings.admin_email, name=settings.admin_name)
    token = create_access_token(user.email, {"name": user.name, "uid": user.id})
    return LoginResponse(access_token=token, user=user)


@router.post("/logout")
async def logout() -> dict:
    return {"success": True}


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**user)

