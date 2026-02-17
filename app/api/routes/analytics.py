"""
Analytics API Routes
System-wide analytics and metrics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Prospect, Client, Meeting, ContentCalendar, OutreachSequence, PerformanceMetric

router = APIRouter()


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Dashboard overview metrics
    """
    # Revenue metrics
    total_prospects = db.query(func.count(Prospect.id)).scalar()
    engaged_prospects = db.query(func.count(Prospect.id)).filter(Prospect.status == 'engaged').scalar()

    # Client metrics
    total_clients = db.query(func.count(Client.id)).filter(Client.status == 'active').scalar()

    # Meeting metrics
    upcoming_meetings = db.query(func.count(Meeting.id)).filter(
        Meeting.status == 'scheduled',
        Meeting.meeting_datetime >= datetime.utcnow()
    ).scalar()

    # Content metrics
    published_this_month = db.query(func.count(ContentCalendar.id)).filter(
        ContentCalendar.status == 'published',
        ContentCalendar.published_at >= datetime.utcnow().replace(day=1)
    ).scalar()

    # Outreach metrics
    total_sent = db.query(func.count(OutreachSequence.id)).filter(
        OutreachSequence.status == 'sent'
    ).scalar()

    total_replied = db.query(func.count(OutreachSequence.id)).filter(
        OutreachSequence.replied == True
    ).scalar()

    reply_rate = (total_replied / max(total_sent, 1)) * 100

    return {
        "revenue": {
            "total_prospects": total_prospects,
            "engaged_prospects": engaged_prospects,
            "reply_rate": round(reply_rate, 1)
        },
        "clients": {
            "total_active": total_clients
        },
        "meetings": {
            "upcoming": upcoming_meetings
        },
        "content": {
            "published_this_month": published_this_month
        }
    }
