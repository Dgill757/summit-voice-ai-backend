from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/dashboard")
async def metrics_dashboard(db: Session = Depends(get_db)):
    service = MetricsService(db)
    return await service.get_dashboard_metrics()


@router.get("/mrr")
async def metrics_mrr(db: Session = Depends(get_db)):
    service = MetricsService(db)
    return await service.get_revenue_metrics()


@router.get("/leads")
async def metrics_leads(db: Session = Depends(get_db)):
    service = MetricsService(db)
    return await service.get_lead_metrics()


@router.get("/agents")
async def metrics_agents(db: Session = Depends(get_db)):
    service = MetricsService(db)
    return await service.get_agent_metrics()

