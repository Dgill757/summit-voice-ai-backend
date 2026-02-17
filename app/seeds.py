from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentSetting

AGENT_SEED_DATA: list[dict[str, Any]] = [
    {"agent_id": 1, "agent_name": "Lead Scraper", "tier": "Revenue", "schedule_cron": "0 6 * * *", "description": "Finds roofing companies via Apollo and Google Maps"},
    {"agent_id": 2, "agent_name": "Lead Enricher", "tier": "Revenue", "schedule_cron": "0 7 * * *", "description": "Enriches leads with Clearbit and Hunter data"},
    {"agent_id": 3, "agent_name": "Outreach Sender", "tier": "Revenue", "schedule_cron": "0 8 * * 1-5", "description": "Sends cold email campaigns and outreach sequences"},
    {"agent_id": 4, "agent_name": "Follow-Up Manager", "tier": "Revenue", "schedule_cron": "0 9 * * 1-5", "description": "Manages follow-up and nurture sequences"},
    {"agent_id": 5, "agent_name": "LinkedIn Prospector", "tier": "Revenue", "schedule_cron": "0 10 * * 1-5", "description": "Sources prospects from LinkedIn"},
    {"agent_id": 6, "agent_name": "Offer Generator", "tier": "Revenue", "schedule_cron": "0/30 * * * *", "description": "Creates AI-powered custom proposals"},
    {"agent_id": 7, "agent_name": "Pipeline Manager", "tier": "Revenue", "schedule_cron": "0 17 * * 1-5", "description": "Maintains CRM stages and opportunity pipeline"},
    {"agent_id": 8, "agent_name": "Meeting Scheduler", "tier": "Revenue", "schedule_cron": "0 * * * *", "description": "Books discovery calls and confirms meetings"},
    {"agent_id": 9, "agent_name": "Content Idea Generator", "tier": "Content", "schedule_cron": "0 8 * * 1", "description": "Generates weekly content ideas"},
    {"agent_id": 10, "agent_name": "Content Writer", "tier": "Content", "schedule_cron": "0 9 * * 2", "description": "Writes social posts and content drafts"},
    {"agent_id": 11, "agent_name": "Image Generator", "tier": "Content", "schedule_cron": "0 10 * * 2", "description": "Creates visual assets for campaigns"},
    {"agent_id": 12, "agent_name": "Content Scheduler", "tier": "Content", "schedule_cron": "0 11 * * 3", "description": "Schedules content across social platforms"},
    {"agent_id": 13, "agent_name": "Engagement Monitor", "tier": "Content", "schedule_cron": "0/30 8-18 * * 1-5", "description": "Tracks comments and engagement signals"},
    {"agent_id": 14, "agent_name": "Trend Analyzer", "tier": "Content", "schedule_cron": "0 7 * * 1", "description": "Discovers trending content opportunities"},
    {"agent_id": 15, "agent_name": "Client Onboarder", "tier": "ClientSuccess", "schedule_cron": "0 * * * *", "description": "Automates onboarding workflows"},
    {"agent_id": 16, "agent_name": "Health Monitor", "tier": "ClientSuccess", "schedule_cron": "0 8 * * *", "description": "Calculates client health and churn signals"},
    {"agent_id": 17, "agent_name": "Report Generator", "tier": "ClientSuccess", "schedule_cron": "0 9 * * 1", "description": "Builds weekly and monthly client reports"},
    {"agent_id": 18, "agent_name": "Churn Predictor", "tier": "ClientSuccess", "schedule_cron": "0 8 * * *", "description": "Flags accounts with churn risk"},
    {"agent_id": 19, "agent_name": "Upsell Identifier", "tier": "ClientSuccess", "schedule_cron": "0 10 * * 1", "description": "Finds expansion and upsell opportunities"},
    {"agent_id": 20, "agent_name": "NPS Collector", "tier": "ClientSuccess", "schedule_cron": "0 9 1 * *", "description": "Collects and tracks satisfaction feedback"},
    {"agent_id": 21, "agent_name": "Daily Briefing", "tier": "Operations", "schedule_cron": "0 7 * * 1-5", "description": "Publishes daily executive operations brief"},
    {"agent_id": 22, "agent_name": "Cost Monitor", "tier": "Operations", "schedule_cron": "0/15 * * * *", "description": "Monitors API and infrastructure spend"},
    {"agent_id": 23, "agent_name": "Error Handler", "tier": "Operations", "schedule_cron": "0/5 * * * *", "description": "Detects and routes runtime errors"},
    {"agent_id": 24, "agent_name": "Backup Manager", "tier": "Operations", "schedule_cron": "0 2 * * *", "description": "Runs routine backup and validation jobs"},
    {"agent_id": 25, "agent_name": "Performance Optimizer", "tier": "Operations", "schedule_cron": "0 3 * * 0", "description": "Optimizes pipelines and execution performance"},
    {"agent_id": 26, "agent_name": "Compliance Checker", "tier": "Operations", "schedule_cron": "0 4 * * 0", "description": "Ensures policy and best-practice compliance"},
]


def seed_agents(db: Session) -> int:
    existing_count = db.query(AgentSetting).count()
    if existing_count >= 26:
        return 0

    existing_by_id = {row.agent_id: row for row in db.query(AgentSetting).all()}
    inserted = 0
    for item in AGENT_SEED_DATA:
        row = existing_by_id.get(item["agent_id"])
        cfg = {"description": item["description"]}
        if row is None:
            db.add(
                AgentSetting(
                    agent_id=item["agent_id"],
                    agent_name=item["agent_name"],
                    tier=item["tier"],
                    is_enabled=False,
                    schedule_cron=item["schedule_cron"],
                    config=cfg,
                )
            )
            inserted += 1
        else:
            row.agent_name = item["agent_name"]
            row.tier = item["tier"]
            row.schedule_cron = row.schedule_cron or item["schedule_cron"]
            current_cfg = row.config or {}
            if not current_cfg.get("description"):
                current_cfg["description"] = item["description"]
            row.config = current_cfg

    db.commit()
    return inserted
