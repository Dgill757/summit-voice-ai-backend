"""
Outreach API Routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any

from app.database import get_db
from app.models import OutreachSequence

router = APIRouter()


@router.get("/stats")
async def get_outreach_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get outreach statistics"""

    total_sent = db.query(func.count(OutreachSequence.id)).filter(
        OutreachSequence.status == 'sent'
    ).scalar()

    total_opened = db.query(func.count(OutreachSequence.id)).filter(
        OutreachSequence.opened == True
    ).scalar()

    total_replied = db.query(func.count(OutreachSequence.id)).filter(
        OutreachSequence.replied == True
    ).scalar()

    open_rate = (total_opened / max(total_sent, 1)) * 100
    reply_rate = (total_replied / max(total_sent, 1)) * 100

    return {
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "open_rate": round(open_rate, 1),
        "reply_rate": round(reply_rate, 1)
    }
