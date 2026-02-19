from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/week-1-report")
async def get_week_1_report(db: Session = Depends(get_db)):
    """Week-1 operational report for lead, outreach, and cost performance."""
    leads_total = db.execute(text("SELECT COUNT(*) FROM prospects")).scalar() or 0
    leads_real = db.execute(text("SELECT COUNT(*) FROM prospects WHERE source = 'Apollo'")).scalar() or 0
    leads_enriched = db.execute(text("SELECT COUNT(*) FROM prospects WHERE phone IS NOT NULL")).scalar() or 0
    leads_contacted = db.execute(
        text("SELECT COUNT(*) FROM prospects WHERE custom_fields->>'contacted_at' IS NOT NULL")
    ).scalar() or 0
    emails_queued = db.execute(
        text("SELECT COUNT(*) FROM outreach_queue WHERE status = 'pending_approval'")
    ).scalar() or 0
    meetings_booked = db.execute(
        text("SELECT COUNT(*) FROM prospects WHERE status = 'meeting_booked'")
    ).scalar() or 0

    cost_data = db.execute(
        text(
            """
            SELECT
                s.agent_name,
                COUNT(l.id) AS runs,
                COALESCE(SUM(COALESCE((l.metadata->>'cost_usd')::numeric, 0)), 0) AS cost
            FROM agent_logs l
            JOIN agent_settings s ON s.agent_id = l.agent_id
            WHERE l.created_at >= NOW() - INTERVAL '7 days'
            GROUP BY s.agent_name
            ORDER BY cost DESC
            """
        )
    ).mappings().all()

    total_cost_7d = sum(float(row["cost"] or 0) for row in cost_data)

    agent_stats = db.execute(
        text(
            """
            SELECT
                s.agent_name,
                s.tier,
                COUNT(l.id) AS total_runs,
                SUM(CASE WHEN l.status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
                CASE
                    WHEN COUNT(l.id) = 0 THEN 0
                    ELSE ROUND(SUM(CASE WHEN l.status = 'success' THEN 1.0 ELSE 0 END) / COUNT(l.id) * 100, 2)
                END AS success_rate
            FROM agent_settings s
            LEFT JOIN agent_logs l
              ON l.agent_id = s.agent_id
             AND l.created_at >= NOW() - INTERVAL '7 days'
            GROUP BY s.agent_name, s.tier
            ORDER BY total_runs DESC
            """
        )
    ).mappings().all()

    replies = 0
    recommendations = generate_week_1_recommendations(
        leads_real, leads_enriched, leads_contacted, replies, meetings_booked, total_cost_7d, agent_stats
    )

    return {
        "report_period": "Week 1 - Last 7 Days",
        "generated_at": datetime.utcnow().isoformat(),
        "pipeline_metrics": {
            "total_leads": leads_total,
            "real_leads": leads_real,
            "demo_leads": leads_total - leads_real,
            "enriched": leads_enriched,
            "enrichment_rate": f"{(leads_enriched / leads_real * 100):.1f}%" if leads_real > 0 else "0%",
            "contacted": leads_contacted,
            "contact_rate": f"{(leads_contacted / leads_enriched * 100):.1f}%" if leads_enriched > 0 else "0%",
            "replies": replies,
            "reply_rate": f"{(replies / leads_contacted * 100):.1f}%" if leads_contacted > 0 else "0%",
            "meetings_booked": meetings_booked,
            "meeting_rate": f"{(meetings_booked / replies * 100):.1f}%" if replies > 0 else "0%",
        },
        "cost_analysis": {
            "total_7d": f"${total_cost_7d:.2f}",
            "cost_per_lead": f"${(total_cost_7d / leads_real):.2f}" if leads_real > 0 else "$0.00",
            "cost_per_contact": f"${(total_cost_7d / leads_contacted):.2f}" if leads_contacted > 0 else "$0.00",
            "by_agent": [
                {"agent": row["agent_name"], "runs": int(row["runs"] or 0), "cost": f"${float(row['cost'] or 0):.2f}"}
                for row in cost_data
            ],
        },
        "agent_performance": [
            {
                "agent": row["agent_name"],
                "tier": row["tier"] or "Operations",
                "total_runs": int(row["total_runs"] or 0),
                "successful_runs": int(row["successful_runs"] or 0),
                "success_rate": f"{float(row['success_rate'] or 0):.2f}%",
            }
            for row in agent_stats
        ],
        "recommendations": recommendations,
    }


def generate_week_1_recommendations(
    leads: int,
    enriched: int,
    contacted: int,
    replies: int,
    meetings: int,
    cost: float,
    agent_stats,
):
    recs = []

    if leads < 300:
        recs.append("Lead volume low. Increase Lead Scraper frequency to 2x daily.")

    enrichment_rate = (enriched / leads * 100) if leads > 0 else 0
    if enrichment_rate < 70:
        recs.append(f"Enrichment rate is {enrichment_rate:.0f}%. Improve enrichment waterfall quality.")

    contact_rate = (contacted / enriched * 100) if enriched > 0 else 0
    if contact_rate < 50:
        recs.append(f"Contact rate is {contact_rate:.0f}%. Raise outreach throughput.")

    if contacted > 0 and replies == 0:
        recs.append("No replies yet. Review subject lines and outreach template mix.")

    cost_per_lead = (cost / leads) if leads > 0 else 0
    if cost_per_lead > 0.10:
        recs.append(f"Cost per lead is ${cost_per_lead:.2f}. Disable low-ROI agents.")

    failing_agents = [a for a in agent_stats if float(a["success_rate"] or 0) < 50]
    if failing_agents:
        recs.append(f"{len(failing_agents)} agents are below 50% success. Check recent errors in logs.")

    if not recs:
        recs.append("System performance is stable. Continue week-1 observation.")

    return recs
