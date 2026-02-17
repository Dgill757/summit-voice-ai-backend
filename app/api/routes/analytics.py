"""
Analytics API Routes
System-wide analytics and metrics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models import Prospect, Client, Meeting, ContentCalendar, OutreachSequence, PerformanceMetric

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Dashboard overview metrics
    """
    try:
        # Revenue metrics
        total_prospects = db.query(func.count(Prospect.id)).scalar() or 0
        engaged_prospects = db.query(func.count(Prospect.id)).filter(Prospect.status == 'engaged').scalar() or 0

        # Client metrics
        total_clients = db.query(func.count(Client.id)).filter(Client.status == 'active').scalar() or 0

        # Meeting metrics
        upcoming_meetings = db.query(func.count(Meeting.id)).filter(
            Meeting.status == 'scheduled',
            Meeting.meeting_datetime >= datetime.utcnow()
        ).scalar() or 0

        # Content metrics
        published_this_month = db.query(func.count(ContentCalendar.id)).filter(
            ContentCalendar.status == 'published',
            ContentCalendar.published_at >= datetime.utcnow().replace(day=1)
        ).scalar() or 0

        # Outreach metrics
        total_sent = db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.status == 'sent'
        ).scalar() or 0

        total_replied = db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.replied == True
        ).scalar() or 0

        reply_rate = (total_replied / max(total_sent, 1)) * 100
        active_agents = total_clients  # Temporary proxy until dedicated agents stats source is wired.
        success_rate = round(reply_rate, 1)

        return {
            "total_leads": total_prospects,
            "active_agents": active_agents,
            "mrr": 0,
            "success_rate": success_rate,
            "revenue": {
                "total_prospects": total_prospects,
                "engaged_prospects": engaged_prospects,
                "reply_rate": success_rate
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
    except Exception as exc:
        logger.exception("Failed to build analytics overview: %s", exc)
        return {
            "total_leads": 0,
            "active_agents": 0,
            "mrr": 0,
            "success_rate": 0,
            "revenue": {
                "total_prospects": 0,
                "engaged_prospects": 0,
                "reply_rate": 0
            },
            "clients": {
                "total_active": 0
            },
            "meetings": {
                "upcoming": 0
            },
            "content": {
                "published_this_month": 0
            }
        }
