"""
Health API Routes
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import status

from app.database import check_database_connection, database_health

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
