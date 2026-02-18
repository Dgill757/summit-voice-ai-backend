"""
Health API Routes
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import status
import os
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import check_database_connection, database_health, get_db

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    """Application and database health"""
    db = database_health()
    ok = bool(db.get("ok")) and check_database_connection()
    return JSONResponse(
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if ok else "degraded",
            "database": db,
        },
    )


@router.get("/integrations")
async def check_integrations(db: Session = Depends(get_db)) -> dict:
    """Verify external API key presence and database connectivity."""
    checks = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "apollo": bool(os.getenv("APOLLO_API_KEY")),
        "clearbit": bool(os.getenv("CLEARBIT_API_KEY")),
        "hunter": bool(os.getenv("HUNTER_API_KEY")),
        "rocketreach": bool(os.getenv("ROCKETREACH_API_KEY")),
        "sendgrid": bool(os.getenv("SENDGRID_API_KEY")),
        "linkedin": bool(os.getenv("LINKEDIN_ACCESS_TOKEN")),
        "late": bool(os.getenv("LATE_API_KEY")),
        "heygen": bool(os.getenv("HEYGEN_API_KEY")),
        "did": bool(os.getenv("DID_API_KEY")),
        "shotstack": bool(os.getenv("SHOTSTACK_API_KEY")),
        "google_calendar": bool(os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")),
        "stability": bool(os.getenv("STABILITY_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "gemini": bool(os.getenv("GOOGLE_AI_API_KEY")),
    }
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    return {
        "integrations": checks,
        "ready": all(checks.values()),
        "missing": [k for k, v in checks.items() if not v],
    }


@router.get("/health/integrations")
async def check_integrations_alias(db: Session = Depends(get_db)) -> dict:
    """Alias endpoint to match /api/v1/health/integrations contract."""
    return await check_integrations(db)
