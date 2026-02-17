from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/overview")
async def get_cost_overview(db: Session = Depends(get_db)):
    """Real-time cost breakdown by agent and timeframe."""
    query = text(
        """
        SELECT
            a.agent_name,
            a.tier,
            COUNT(CASE WHEN al.created_at >= NOW() - INTERVAL '1 day' THEN 1 END) AS runs_24h,
            COUNT(CASE WHEN al.created_at >= NOW() - INTERVAL '7 days' THEN 1 END) AS runs_7d,
            COUNT(CASE WHEN al.created_at >= NOW() - INTERVAL '30 days' THEN 1 END) AS runs_30d,
            COALESCE(SUM(CASE WHEN al.created_at >= NOW() - INTERVAL '1 day'
                THEN COALESCE((al.metadata->>'cost_usd')::numeric, 0) ELSE 0 END), 0) AS cost_24h,
            COALESCE(SUM(CASE WHEN al.created_at >= NOW() - INTERVAL '7 days'
                THEN COALESCE((al.metadata->>'cost_usd')::numeric, 0) ELSE 0 END), 0) AS cost_7d,
            COALESCE(SUM(CASE WHEN al.created_at >= NOW() - INTERVAL '30 days'
                THEN COALESCE((al.metadata->>'cost_usd')::numeric, 0) ELSE 0 END), 0) AS cost_30d,
            COALESCE(AVG(COALESCE((al.metadata->>'cost_usd')::numeric, 0)), 0) AS avg_cost_per_run
        FROM agent_settings a
        LEFT JOIN agent_logs al ON a.agent_id = al.agent_id
        GROUP BY a.agent_id, a.agent_name, a.tier
        ORDER BY cost_30d DESC, a.agent_id ASC
        """
    )

    rows = db.execute(query).mappings().all()
    agents = [
        {
            "name": r["agent_name"],
            "tier": r["tier"] or "Operations",
            "runs": {
                "24h": int(r["runs_24h"] or 0),
                "7d": int(r["runs_7d"] or 0),
                "30d": int(r["runs_30d"] or 0),
            },
            "cost": {
                "24h": float(r["cost_24h"] or 0),
                "7d": float(r["cost_7d"] or 0),
                "30d": float(r["cost_30d"] or 0),
            },
            "avg_per_run": float(r["avg_cost_per_run"] or 0),
        }
        for r in rows
    ]

    total_24h = sum(a["cost"]["24h"] for a in agents)
    total_7d = sum(a["cost"]["7d"] for a in agents)
    total_30d = sum(a["cost"]["30d"] for a in agents)

    return {
        "agents": agents,
        "totals": {
            "cost_24h": round(total_24h, 4),
            "cost_7d": round(total_7d, 4),
            "cost_30d": round(total_30d, 4),
            "projected_monthly": round(total_30d, 4),
        },
    }


@router.get("/breakdown")
async def get_cost_breakdown(db: Session = Depends(get_db)):
    """Cost by tier and volume for last 30 days."""
    tier_query = text(
        """
        SELECT
            a.tier,
            COUNT(al.id) AS total_runs,
            COALESCE(SUM(COALESCE((al.metadata->>'cost_usd')::numeric, 0)), 0) AS total_cost,
            COALESCE(AVG(COALESCE((al.metadata->>'cost_usd')::numeric, 0)), 0) AS avg_cost
        FROM agent_settings a
        LEFT JOIN agent_logs al
            ON al.agent_id = a.agent_id
           AND al.created_at >= NOW() - INTERVAL '30 days'
        GROUP BY a.tier
        ORDER BY total_cost DESC
        """
    )
    rows = db.execute(tier_query).mappings().all()
    return {
        "by_tier": [
            {
                "tier": r["tier"] or "Operations",
                "runs": int(r["total_runs"] or 0),
                "cost": float(r["total_cost"] or 0),
                "avg": float(r["avg_cost"] or 0),
            }
            for r in rows
        ]
    }

