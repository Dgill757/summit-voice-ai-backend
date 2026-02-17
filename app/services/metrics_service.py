from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.models import AgentLog, Client, ContentCalendar, Prospect


class MetricsService:
    def __init__(self, db):
        self.db = db

    async def get_dashboard_metrics(self) -> dict[str, Any]:
        return {
            "leads": await self.get_lead_metrics(),
            "revenue": await self.get_revenue_metrics(),
            "agents": await self.get_agent_metrics(),
            "content": await self.get_content_metrics(),
        }

    async def get_lead_metrics(self) -> dict[str, Any]:
        total = self.db.query(func.count(Prospect.id)).scalar() or 0
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_this_week = (
            self.db.query(func.count(Prospect.id)).filter(Prospect.created_at >= week_ago).scalar() or 0
        )
        statuses = [
            "new",
            "contacted",
            "qualified",
            "meeting_booked",
            "closed_won",
            "closed_lost",
            "engaged",
            "nurture",
        ]
        by_status: dict[str, int] = {}
        for s in statuses:
            by_status[s] = self.db.query(func.count(Prospect.id)).filter(Prospect.status == s).scalar() or 0
        denom = max(total - by_status.get("new", 0), 1)
        conversion = (by_status.get("closed_won", 0) / denom) * 100
        return {
            "total": total,
            "new_this_week": new_this_week,
            "by_status": by_status,
            "conversion_rate": round(conversion, 2),
        }

    async def get_revenue_metrics(self) -> dict[str, Any]:
        active_clients = (
            self.db.query(Client).filter(Client.status.in_(["active", "onboarding"])).all()
        )
        mrr = sum(float(c.monthly_value or 0) for c in active_clients)
        arr = mrr * 12
        won = self.db.query(func.count(Prospect.id)).filter(Prospect.status == "closed_won").scalar() or 0
        return {
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "active_clients": len(active_clients),
            "closed_won": won,
        }

    async def get_agent_metrics(self) -> dict[str, Any]:
        total_exec = self.db.query(func.count(AgentLog.id)).scalar() or 0
        success_exec = self.db.query(func.count(AgentLog.id)).filter(AgentLog.status == "success").scalar() or 0
        by_agent_rows = (
            self.db.query(AgentLog.agent_id, func.count(AgentLog.id))
            .group_by(AgentLog.agent_id)
            .all()
        )
        by_agent = {str(agent_id): {"executions": count} for agent_id, count in by_agent_rows}
        return {
            "total_executions": total_exec,
            "success_rate": round((success_exec / total_exec * 100), 2) if total_exec else 0.0,
            "by_agent": by_agent,
        }

    async def get_content_metrics(self) -> dict[str, Any]:
        total = self.db.query(func.count(ContentCalendar.id)).scalar() or 0
        published = (
            self.db.query(func.count(ContentCalendar.id))
            .filter(ContentCalendar.status == "published")
            .scalar()
            or 0
        )
        return {"total": total, "published": published}


def get_kpis(db) -> dict[str, Any]:
    """Backward-compatible KPI summary used by dashboard route."""
    service = MetricsService(db)
    total_leads = db.query(func.count(Prospect.id)).scalar() or 0
    active_clients = db.query(func.count(Client.id)).filter(Client.status == "active").scalar() or 0
    recent_errors = db.query(func.count(AgentLog.id)).filter(AgentLog.status == "error").scalar() or 0
    return {
        "total_leads": total_leads,
        "active_clients": active_clients,
        "upcoming_meetings": 0,
        "recent_errors": recent_errors,
    }

