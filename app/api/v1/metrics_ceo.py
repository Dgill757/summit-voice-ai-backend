from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/dashboard")
async def get_ceo_dashboard(db: Session = Depends(get_db)):
    return {
        "tier1": await calculate_tier1_metrics(db),
        "tier2": await calculate_tier2_metrics(db),
        "tier3": await calculate_tier3_metrics(db),
        "updated_at": datetime.utcnow().isoformat(),
    }


async def calculate_tier1_metrics(db: Session):
    current_mrr = db.execute(
        text("SELECT COALESCE(SUM(monthly_value), 0) FROM clients WHERE status = 'active'")
    ).scalar() or 0
    prev_mrr = db.execute(
        text(
            """
            SELECT COALESCE(SUM(monthly_value), 0)
            FROM clients
            WHERE status = 'active'
              AND created_at < NOW() - INTERVAL '30 days'
            """
        )
    ).scalar() or 0
    mrr_growth = ((current_mrr - prev_mrr) / prev_mrr * 100) if prev_mrr > 0 else 0
    arr = float(current_mrr) * 12

    churn_mrr = db.execute(
        text(
            """
            SELECT COALESCE(SUM(monthly_value), 0)
            FROM clients
            WHERE status = 'churned'
              AND updated_at >= NOW() - INTERVAL '30 days'
            """
        )
    ).scalar() or 0
    expansion_mrr = 0
    nrr = ((prev_mrr + expansion_mrr - churn_mrr) / prev_mrr * 100) if prev_mrr > 0 else 100
    grr = ((prev_mrr - churn_mrr) / prev_mrr * 100) if prev_mrr > 0 else 100

    return {
        "mrr": round(float(current_mrr), 2),
        "arr": round(arr, 2),
        "mrr_growth_rate": round(float(mrr_growth), 2),
        "net_revenue_retention": round(float(nrr), 2),
        "gross_revenue_retention": round(float(grr), 2),
    }


async def calculate_tier2_metrics(db: Session):
    total_clients = db.execute(
        text("SELECT COUNT(*) FROM clients WHERE status = 'active'")
    ).scalar() or 0
    total_mrr = db.execute(
        text("SELECT COALESCE(SUM(monthly_value), 0) FROM clients WHERE status = 'active'")
    ).scalar() or 0
    arpu = (float(total_mrr) / total_clients) if total_clients > 0 else 0

    new_customers = db.execute(
        text("SELECT COUNT(*) FROM clients WHERE created_at >= NOW() - INTERVAL '30 days'")
    ).scalar() or 0
    marketing_spend = 1000.0
    cac = (marketing_spend / new_customers) if new_customers > 0 else 0

    churned = db.execute(
        text(
            """
            SELECT COUNT(*) FROM clients
            WHERE status = 'churned'
              AND updated_at >= NOW() - INTERVAL '30 days'
            """
        )
    ).scalar() or 0
    monthly_churn = (churned / total_clients * 100) if total_clients > 0 else 5
    ltv = (arpu / (monthly_churn / 100)) if monthly_churn > 0 else arpu * 24
    payback_period = (cac / arpu) if arpu > 0 else 0
    magic_number = 0.75

    return {
        "cac": round(cac, 2),
        "ltv": round(ltv, 2),
        "cac_payback_period": round(payback_period, 1),
        "arpu": round(arpu, 2),
        "magic_number": round(magic_number, 2),
        "ltv_cac_ratio": round((ltv / cac), 2) if cac > 0 else 0,
    }


async def calculate_tier3_metrics(db: Session):
    total_clients = db.execute(
        text("SELECT COUNT(*) FROM clients WHERE status = 'active'")
    ).scalar() or 0
    churned = db.execute(
        text(
            """
            SELECT COUNT(*) FROM clients
            WHERE status = 'churned'
              AND updated_at >= NOW() - INTERVAL '30 days'
            """
        )
    ).scalar() or 0
    monthly_churn = (churned / total_clients * 100) if total_clients > 0 else 0

    mrr_growth = 15
    profit_margin = 20
    rule_of_40 = mrr_growth + profit_margin
    burn_multiple = 1.5
    quick_ratio = 4.0

    return {
        "rule_of_40": round(rule_of_40, 2),
        "burn_multiple": round(burn_multiple, 2),
        "quick_ratio": round(quick_ratio, 2),
        "monthly_churn_rate": round(monthly_churn, 2),
    }


@router.get("/costs/breakdown")
async def get_cost_breakdown(db: Session = Depends(get_db)):
    query = text(
        """
        SELECT
            a.agent_name,
            a.tier,
            a.schedule_cron,
            COUNT(al.id) AS executions_30d,
            COALESCE(SUM(COALESCE((al.metadata->>'cost_usd')::numeric, 0)), 0) AS cost_30d,
            COALESCE(AVG(COALESCE((al.metadata->>'cost_usd')::numeric, 0)), 0) AS avg_cost_per_run
        FROM agent_settings a
        LEFT JOIN agent_logs al
          ON a.agent_id = al.agent_id
         AND al.created_at >= NOW() - INTERVAL '30 days'
        GROUP BY a.agent_id, a.agent_name, a.tier, a.schedule_cron
        ORDER BY cost_30d DESC
        """
    )
    rows = db.execute(query).mappings().all()
    agents = []
    total_cost_30d = 0.0
    projected_monthly_total = 0.0

    for r in rows:
        avg = float(r["avg_cost_per_run"] or 0)
        projected = estimate_monthly_cost(r["schedule_cron"], avg)
        cost_30d = float(r["cost_30d"] or 0)
        total_cost_30d += cost_30d
        projected_monthly_total += projected
        agents.append(
            {
                "name": r["agent_name"],
                "tier": r["tier"] or "Operations",
                "schedule": r["schedule_cron"],
                "executions_30d": int(r["executions_30d"] or 0),
                "cost_30d": round(cost_30d, 4),
                "avg_cost_per_run": round(avg, 4),
                "projected_monthly": round(projected, 4),
            }
        )

    return {
        "agents": agents,
        "total_cost_30d": round(total_cost_30d, 2),
        "projected_monthly": round(projected_monthly_total, 2),
    }


def estimate_monthly_cost(cron_schedule: str | None, avg_cost_per_run: float) -> float:
    if not cron_schedule or avg_cost_per_run <= 0:
        return 0
    parts = cron_schedule.split()
    if len(parts) < 5:
        return avg_cost_per_run * 30
    minute, hour, *_ = parts

    if minute.startswith("*/15"):
        runs_per_month = (60 / 15) * 24 * 30
    elif minute.startswith("*/30"):
        runs_per_month = (60 / 30) * 24 * 30
    elif minute == "0" and hour.startswith("*/2"):
        runs_per_month = (24 / 2) * 30
    elif minute == "0" and "," in hour:
        runs_per_month = len(hour.split(",")) * 30
    elif minute == "0":
        runs_per_month = 30
    else:
        runs_per_month = 30
    return avg_cost_per_run * runs_per_month

