from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.services.integration_service import integration_status
from app.models import AgentLog, AgentSetting, Prospect, Client

router = APIRouter()


@router.get('/')
async def dashboard_data(db: Session = Depends(get_db)):
    total_leads = db.query(func.count(Prospect.id)).scalar() or 0
    agents = db.query(AgentSetting).order_by(AgentSetting.agent_id.asc()).all()
    active_agents = sum(1 for a in agents if a.is_enabled)
    recent_logs = db.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(5).all()

    healthy = db.query(func.count(Client.id)).filter((Client.health_score >= 70) | (Client.churn_risk == "low")).scalar() or 0
    at_risk = db.query(func.count(Client.id)).filter(Client.churn_risk == "medium").scalar() or 0
    churned = db.query(func.count(Client.id)).filter((Client.status == "churned") | (Client.churn_risk == "high")).scalar() or 0

    return {
        'metrics': {
            "total_leads": total_leads,
            "active_agents": active_agents,
            "mrr": 0,
            "success_rate": 0,
        },
        'recent_executions': [
            {
                "id": str(log.id),
                "agent_id": log.agent_id,
                "agent_name": log.agent_name,
                "status": log.status,
                "message": log.message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in recent_logs
        ],
        'agent_status': [
            {
                "id": a.agent_id,
                "agent_name": a.agent_name,
                "is_enabled": a.is_enabled,
                "tier": a.tier or "Operations",
                "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            }
            for a in agents
        ],
        'client_health': {
            "healthy": healthy,
            "at_risk": at_risk,
            "churned": churned,
        },
        'integrations': integration_status()['integrations'],
    }
