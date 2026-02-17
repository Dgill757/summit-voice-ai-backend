from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prospect
from app.services.agent_executor import execute_agent

router = APIRouter()


class LeadCreate(BaseModel):
    company_name: Optional[str] = None
    company: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    contact_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = "new"
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    lead_score: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@router.get("/")
async def get_leads(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    source: Optional[str] = None,
    industry: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
):
    query = db.query(Prospect)
    if status:
        query = query.filter(Prospect.status == status)
    if source:
        query = query.filter(Prospect.source == source)
    if industry:
        query = query.filter(Prospect.industry.ilike(f"%{industry}%"))
    if location:
        query = query.filter(or_(Prospect.city.ilike(f"%{location}%"), Prospect.state.ilike(f"%{location}%")))
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Prospect.contact_name.ilike(like),
                Prospect.company_name.ilike(like),
                Prospect.email.ilike(like),
            )
        )
    rows = query.order_by(Prospect.created_at.desc()).offset(skip).limit(limit).all()
    return [serialize_lead(row) for row in rows]


@router.post("/")
async def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    if payload.email:
        existing = db.query(Prospect).filter(Prospect.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Lead with this email already exists")
    company_name = payload.company_name or payload.company or "Unknown"
    contact_name = payload.contact_name or " ".join(
        [x for x in [payload.first_name, payload.last_name] if x]
    ).strip() or None
    lead = Prospect(
        company_name=company_name,
        contact_name=contact_name,
        title=payload.title,
        email=payload.email,
        phone=payload.phone,
        linkedin_url=payload.linkedin_url,
        website=payload.website,
        city=payload.city,
        state=payload.state,
        industry=payload.industry or "other",
        source=payload.source or "manual",
        status=payload.status or "new",
        notes=payload.notes,
        custom_fields={"tags": auto_tags(payload)},
        scraped_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return serialize_lead(lead)


class LeadImportPayload(BaseModel):
    csv_data: str


@router.post("/import")
async def import_leads(payload: LeadImportPayload, db: Session = Depends(get_db)):
    reader = csv.DictReader(io.StringIO(payload.csv_data))
    imported = 0
    skipped = 0
    for row in reader:
        email = (row.get("email") or "").strip() or None
        if email and db.query(Prospect).filter(Prospect.email == email).first():
            skipped += 1
            continue
        lead = Prospect(
            company_name=(row.get("company_name") or row.get("company") or "Unknown").strip(),
            contact_name=(row.get("contact_name") or "").strip() or None,
            title=(row.get("title") or "").strip() or None,
            email=email,
            phone=(row.get("phone") or "").strip() or None,
            city=(row.get("city") or "").strip() or None,
            state=(row.get("state") or "").strip() or None,
            industry=(row.get("industry") or "other").strip(),
            source="manual",
            status="new",
            custom_fields={"tags": []},
            scraped_at=datetime.utcnow(),
        )
        db.add(lead)
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped, "total": imported + skipped}


@router.get("/export")
async def export_leads(db: Session = Depends(get_db)):
    leads = db.query(Prospect).order_by(Prospect.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "company_name",
            "contact_name",
            "email",
            "phone",
            "title",
            "city",
            "state",
            "industry",
            "status",
            "source",
        ],
    )
    writer.writeheader()
    for lead in leads:
        writer.writerow(
            {
                "id": str(lead.id),
                "company_name": lead.company_name,
                "contact_name": lead.contact_name,
                "email": lead.email,
                "phone": lead.phone,
                "title": lead.title,
                "city": lead.city,
                "state": lead.state,
                "industry": lead.industry,
                "status": lead.status,
                "source": lead.source,
            }
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Prospect).filter(Prospect.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return serialize_lead(lead)


@router.patch("/{lead_id}")
async def update_lead(lead_id: str, payload: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(Prospect).filter(Prospect.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    data = payload.model_dump(exclude_none=True)
    first_name = data.pop("first_name", None)
    last_name = data.pop("last_name", None)
    if first_name or last_name:
        data["contact_name"] = " ".join([x for x in [first_name, last_name] if x]).strip()
    if "company" in data and "company_name" not in data:
        data["company_name"] = data.pop("company")
    for k, v in data.items():
        setattr(lead, k, v)
    db.commit()
    db.refresh(lead)
    return serialize_lead(lead)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Prospect).filter(Prospect.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"success": True}


@router.post("/{lead_id}/enrich")
async def enrich_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Prospect).filter(Prospect.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    result = await execute_agent(2)
    return {"success": True, "lead_id": lead_id, "agent_result": result}


class TagPayload(BaseModel):
    tag_name: str


@router.post("/{lead_id}/tag")
async def add_tag(lead_id: str, payload: TagPayload, db: Session = Depends(get_db)):
    lead = db.query(Prospect).filter(Prospect.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    cf = lead.custom_fields or {}
    tags = list(cf.get("tags") or [])
    if payload.tag_name not in tags:
        tags.append(payload.tag_name)
    cf["tags"] = tags
    lead.custom_fields = cf
    db.commit()
    return {"success": True, "tags": tags}


def serialize_lead(row: Prospect) -> dict[str, Any]:
    cf = row.custom_fields or {}
    first_name = None
    last_name = None
    if row.contact_name:
        parts = row.contact_name.split()
        first_name = parts[0] if parts else None
        last_name = " ".join(parts[1:]) if len(parts) > 1 else None
    return {
        "id": str(row.id),
        "company_name": row.company_name,
        "company": row.company_name,
        "contact_name": row.contact_name,
        "first_name": first_name,
        "last_name": last_name,
        "title": row.title,
        "email": row.email,
        "phone": row.phone,
        "linkedin_url": row.linkedin_url,
        "website": row.website,
        "city": row.city,
        "state": row.state,
        "industry": row.industry,
        "source": row.source,
        "status": row.status,
        "lead_score": row.lead_score,
        "tags": cf.get("tags", []),
        "custom_fields": cf,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def auto_tags(payload: LeadCreate) -> list[str]:
    tags = []
    if payload.industry:
        tags.append(f"industry:{payload.industry.lower()}")
    if payload.city:
        tags.append(f"city:{payload.city.lower()}")
    if payload.state:
        tags.append(f"state:{payload.state.lower()}")
    return tags
