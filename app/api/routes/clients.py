"""
Clients API Routes
Manage active clients
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import Client, Meeting
from app.core.security import get_current_user

router = APIRouter()


class ClientCreate(BaseModel):
    company_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    monthly_value: Optional[float] = 0
    notes: Optional[str] = None
    status: Optional[str] = "active"
    subscription_tier: Optional[str] = "standard"


@router.get("/")
async def list_clients(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    List all clients
    """
    query = db.query(Client)

    if status:
        query = query.filter(Client.status == status)

    clients = query.order_by(Client.created_at.desc()).all()

    return [
        {
            "id": str(c.id),
            "company_name": c.company_name,
            "email": c.email,
            "status": c.status,
            "subscription_tier": c.subscription_tier,
            "monthly_value": float(c.monthly_value) if c.monthly_value else None,
            "health_score": c.health_score,
            "churn_risk": c.churn_risk,
            "onboarding_date": c.onboarding_date.isoformat() if c.onboarding_date else None
        }
        for c in clients
    ]


@router.post("/")
async def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    client = Client(
        company_name=payload.company_name,
        email=payload.email,
        phone=payload.phone,
        monthly_value=payload.monthly_value,
        status=payload.status or "active",
        subscription_tier=payload.subscription_tier or "standard",
        custom_fields={"notes": payload.notes} if payload.notes else {},
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {
        "id": str(client.id),
        "company_name": client.company_name,
        "email": client.email,
        "phone": client.phone,
        "monthly_value": float(client.monthly_value or 0),
        "status": client.status,
        "subscription_tier": client.subscription_tier,
    }


@router.get("/{client_id}")
async def get_client(client_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get client details
    """
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "id": str(client.id),
        "company_name": client.company_name,
        "primary_contact_name": client.primary_contact_name,
        "email": client.email,
        "phone": client.phone,
        "website": client.website,
        "industry": client.industry,
        "segment": client.segment,
        "status": client.status,
        "subscription_tier": client.subscription_tier,
        "monthly_value": float(client.monthly_value) if client.monthly_value else None,
        "health_score": client.health_score,
        "churn_risk": client.churn_risk,
        "onboarding_date": client.onboarding_date.isoformat() if client.onboarding_date else None,
        "contract_start": client.contract_start.isoformat() if client.contract_start else None,
        "contract_end": client.contract_end.isoformat() if client.contract_end else None,
        "ghl_sub_account_id": client.ghl_sub_account_id,
        "custom_fields": client.custom_fields
    }


@router.get("/{client_id}/dashboard")
async def get_client_dashboard(client_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get client-specific dashboard metrics
    """
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Calculate days as client
    days_active = 0
    if client.onboarding_date:
        days_active = (datetime.utcnow().date() - client.onboarding_date).days

    # Get recent meetings
    recent_meetings = db.query(Meeting).filter(
        Meeting.client_id == client_id,
        Meeting.status == 'held'
    ).order_by(Meeting.meeting_datetime.desc()).limit(5).all()

    # Calculate metrics (in production, these would come from real data)
    metrics = {
        "calls_handled": 850,  # Simulated
        "appointments_booked": 67,
        "revenue_generated": 28500,
        "response_time_avg": "12 seconds"
    }

    return {
        "client": {
            "id": str(client.id),
            "company_name": client.company_name,
            "status": client.status,
            "health_score": client.health_score,
            "days_active": days_active
        },
        "metrics": metrics,
        "recent_meetings": [
            {
                "date": m.meeting_datetime.isoformat(),
                "type": m.meeting_type,
                "notes": m.notes
            }
            for m in recent_meetings
        ]
    }
