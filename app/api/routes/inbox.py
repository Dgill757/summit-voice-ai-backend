from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/unread-count")
async def get_inbox_unread_count(db: Session = Depends(get_db)) -> dict[str, int]:
    """
    Return unread inbox count for dashboard badge.
    Falls back to outreach approval queue when an inbox table is not present.
    """
    try:
        count = db.execute(text("SELECT COUNT(*) FROM inbox WHERE status = 'unread'")).scalar() or 0
        return {"count": int(count)}
    except SQLAlchemyError:
        # Current production schema may not have an inbox table yet.
        queued = db.execute(
            text("SELECT COUNT(*) FROM outreach_queue WHERE status = 'pending_approval'")
        ).scalar() or 0
        return {"count": int(queued)}
