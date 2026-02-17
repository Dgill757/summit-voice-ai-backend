"""
Prospects API Routes
Manage prospect pipeline
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database import get_db
from app.models import Prospect, OutreachSequence

router = APIRouter()


@router.get("/")
async def list_prospects(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List prospects with filters
    """
    query = db.query(Prospect)

    if status:
        query = query.filter(Prospect.status == status)

    if min_score:
        query = query.filter(Prospect.lead_score >= min_score)

    total = query.count()
    prospects = query.order_by(Prospect.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "prospects": [
            {
                "id": str(p.id),
                "company_name": p.company_name,
                "contact_name": p.contact_name,
                "email": p.email,
                "phone": p.phone,
                "industry": p.industry,
                "lead_score": p.lead_score,
                "status": p.status,
                "source": p.source,
                "created_at": p.created_at.isoformat()
            }
            for p in prospects
        ]
    }


@router.get("/{prospect_id}")
async def get_prospect(prospect_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get prospect details
    """
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()

    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    # Get outreach history
    outreach = db.query(OutreachSequence).filter(
        OutreachSequence.prospect_id == prospect_id
    ).order_by(OutreachSequence.created_at.desc()).all()

    return {
        "id": str(prospect.id),
        "company_name": prospect.company_name,
        "contact_name": prospect.contact_name,
        "title": prospect.title,
        "email": prospect.email,
        "phone": prospect.phone,
        "linkedin_url": prospect.linkedin_url,
        "website": prospect.website,
        "industry": prospect.industry,
        "segment": prospect.segment,
        "employee_count": prospect.employee_count,
        "revenue_estimate": float(prospect.revenue_estimate) if prospect.revenue_estimate else None,
        "lead_score": prospect.lead_score,
        "status": prospect.status,
        "source": prospect.source,
        "notes": prospect.notes,
        "created_at": prospect.created_at.isoformat(),
        "outreach_history": [
            {
                "channel": o.channel,
                "step_number": o.step_number,
                "scheduled_at": o.scheduled_at.isoformat(),
                "sent_at": o.sent_at.isoformat() if o.sent_at else None,
                "status": o.status,
                "replied": o.replied
            }
            for o in outreach
        ]
    }


@router.get("/{prospect_id}/timeline")
async def get_prospect_timeline(prospect_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get prospect activity timeline
    """
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()

    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    timeline = []

    # Add creation event
    timeline.append({
        "type": "created",
        "timestamp": prospect.created_at.isoformat(),
        "description": f"Prospect added from {prospect.source}"
    })

    # Add outreach events
    outreach = db.query(OutreachSequence).filter(
        OutreachSequence.prospect_id == prospect_id
    ).order_by(OutreachSequence.created_at).all()

    for o in outreach:
        if o.sent_at:
            timeline.append({
                "type": "outreach_sent",
                "timestamp": o.sent_at.isoformat(),
                "description": f"{o.channel.title()} sent: {o.subject_line or 'Message'}"
            })

        if o.replied:
            timeline.append({
                "type": "reply_received",
                "timestamp": o.replied_at.isoformat() if o.replied_at else o.created_at.isoformat(),
                "description": f"Replied via {o.channel}",
                "sentiment": o.reply_sentiment
            })

    return sorted(timeline, key=lambda x: x['timestamp'])
