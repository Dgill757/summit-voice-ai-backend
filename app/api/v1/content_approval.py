"""
Content Approval API
Review, score, and approve/reject content before publishing
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import ContentCalendar
from app.services.content_scorer import ContentScorer

router = APIRouter()


class ContentScore(BaseModel):
    human_score: int
    issues: List[str]
    character_count: int
    max_characters: int
    platform_compliant: bool
    emoji_count: int
    mdash_count: int
    ai_indicators: List[str]
    recommendation: str


class ApprovalAction(BaseModel):
    action: str  # "approve" or "reject"
    notes: Optional[str] = None


@router.get("/pending")
async def get_pending_content(
    db: Session = Depends(get_db)
):
    """Get all content pending approval"""

    pending = db.query(ContentCalendar).filter(
        ContentCalendar.status == "review"
    ).order_by(ContentCalendar.created_at.desc()).all()

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "platform": c.platform,
            "content_body": c.content_body,
            "media_url": c.media_url,
            "scheduled_date": c.scheduled_date.isoformat() if c.scheduled_date else None,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in pending
    ]


@router.get("/{content_id}/score", response_model=ContentScore)
async def score_content(
    content_id: str,
    db: Session = Depends(get_db)
):
    """Get quality score for content"""

    content = db.query(ContentCalendar).filter(ContentCalendar.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    scorer = ContentScorer()
    score = scorer.score_content(content.content_body or "", content.platform or "linkedin")

    return ContentScore(**score)


@router.post("/{content_id}/approve")
async def approve_content(
    content_id: str,
    action: ApprovalAction,
    db: Session = Depends(get_db)
):
    """Approve or reject content"""

    content = db.query(ContentCalendar).filter(ContentCalendar.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if action.action == "approve":
        content.status = "approved"
    elif action.action == "reject":
        content.status = "draft"
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    # Store approval notes in metadata
    meta = content.meta or {}
    meta['approval_notes'] = action.notes
    meta['reviewed_at'] = datetime.utcnow().isoformat()
    meta['approval_action'] = action.action
    content.meta = meta

    db.commit()

    return {
        "success": True,
        "content_id": content_id,
        "status": content.status
    }
