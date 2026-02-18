"""Outreach API Routes."""
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import OutreachSequence, OutreachQueue, Prospect
from app.integrations.email import EmailService

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


@router.get("/pending")
async def get_pending_outreach(db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = (
        db.query(OutreachQueue, Prospect)
        .join(Prospect, Prospect.id == OutreachQueue.prospect_id)
        .filter(OutreachQueue.status == "pending_approval")
        .order_by(OutreachQueue.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "emails": [
            {
                "id": str(q.id),
                "prospect_id": str(q.prospect_id),
                "name": p.contact_name,
                "company": p.company_name,
                "email": p.email,
                "subject": q.subject,
                "body": q.body,
                "status": q.status,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q, p in rows
        ]
    }


@router.post("/{queue_id}/approve")
async def approve_outreach(queue_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    record = db.query(OutreachQueue).filter(OutreachQueue.id == queue_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    if record.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Outreach status is {record.status}")

    prospect = db.query(Prospect).filter(Prospect.id == record.prospect_id).first()
    if not prospect or not prospect.email:
        raise HTTPException(status_code=400, detail="Prospect email is missing")

    mailer = EmailService()
    await mailer.send_email(
        to=prospect.email,
        subject=record.subject,
        html_content=record.body.replace("\n", "<br/>"),
        from_email="dan@summitvoiceai.com",
        from_name="Dan - Summit Voice AI",
    )

    record.status = "sent"
    record.sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "id": queue_id, "status": "sent"}


@router.post("/{queue_id}/reject")
async def reject_outreach(queue_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    record = db.query(OutreachQueue).filter(OutreachQueue.id == queue_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    record.status = "rejected"
    db.commit()
    return {"success": True, "id": queue_id, "status": "rejected"}
