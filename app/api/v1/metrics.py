from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/dashboard")
async def metrics_dashboard(db: Session = Depends(get_db)):
    try:
        service = MetricsService(db)
        return await service.get_dashboard_metrics()
    except Exception:
        return {
            "leads": {"total": 0, "new_this_week": 0, "by_status": {}, "conversion_rate": 0},
            "revenue": {"mrr": 0, "arr": 0, "active_clients": 0, "closed_won": 0},
            "agents": {"total_executions": 0, "success_rate": 0, "by_agent": {}},
            "content": {"total": 0, "published": 0},
        }


@router.get("/mrr")
async def metrics_mrr(db: Session = Depends(get_db)):
    try:
        service = MetricsService(db)
        return await service.get_revenue_metrics()
    except Exception:
        return {"mrr": 0, "arr": 0, "active_clients": 0, "closed_won": 0}


@router.get("/leads")
async def metrics_leads(db: Session = Depends(get_db)):
    try:
        service = MetricsService(db)
        return await service.get_lead_metrics()
    except Exception:
        return {"total": 0, "new_this_week": 0, "by_status": {}, "conversion_rate": 0}


@router.get("/agents")
async def metrics_agents(db: Session = Depends(get_db)):
    try:
        service = MetricsService(db)
        return await service.get_agent_metrics()
    except Exception:
        return {"total_executions": 0, "success_rate": 0, "by_agent": {}}
