"""
Meetings API Routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import Meeting

router = APIRouter()


@router.get("/")
async def list_meetings(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all meetings"""
    meetings = db.query(Meeting).order_by(Meeting.meeting_datetime.desc()).limit(100).all()

    return [
        {
            "id": str(m.id),
            "prospect_id": str(m.prospect_id) if m.prospect_id else None,
            "client_id": str(m.client_id) if m.client_id else None,
            "meeting_datetime": m.meeting_datetime.isoformat(),
            "meeting_type": m.meeting_type,
            "status": m.status,
            "zoom_link": m.zoom_link
        }
        for m in meetings
    ]


@router.get("/upcoming")
async def get_upcoming_meetings(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get upcoming meetings"""
    meetings = db.query(Meeting).filter(
        Meeting.status == 'scheduled',
        Meeting.meeting_datetime >= datetime.utcnow()
    ).order_by(Meeting.meeting_datetime).all()

    return [
        {
            "id": str(m.id),
            "meeting_datetime": m.meeting_datetime.isoformat(),
            "meeting_type": m.meeting_type,
            "zoom_link": m.zoom_link
        }
        for m in meetings
    ]
