from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)

DAILY_LIMIT = 5.00
WEEKLY_LIMIT = 30.00


async def check_daily_spend(db: Session | None = None) -> dict[str, Any]:
    own_session = False
    if db is None:
        db = next(get_db())
        own_session = True
    try:
        today = db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(COALESCE((metadata->>'cost_usd')::numeric, 0)), 0) AS total_cost,
                    COUNT(*) AS executions
                FROM agent_logs
                WHERE created_at >= CURRENT_DATE
                """
            )
        ).mappings().first()

        week = db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(COALESCE((metadata->>'cost_usd')::numeric, 0)), 0) AS total_cost,
                    COUNT(*) AS executions
                FROM agent_logs
                WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE)
                """
            )
        ).mappings().first()

        alerts: list[str] = []
        today_spend = float(today["total_cost"] if today else 0)
        week_spend = float(week["total_cost"] if week else 0)
        if today_spend > DAILY_LIMIT:
            alerts.append(f"Daily spend high: ${today_spend:.2f} (limit ${DAILY_LIMIT:.2f})")
            await disable_expensive_agents(db)
        if week_spend > WEEKLY_LIMIT:
            alerts.append(f"Weekly spend high: ${week_spend:.2f} (limit ${WEEKLY_LIMIT:.2f})")

        credit_status = await check_api_credits()
        if (credit_status.get("apollo_credits_remaining") or 10**9) < 500:
            alerts.append("Apollo credits low (<500)")
        if (credit_status.get("hunter_credits_remaining") or 10**9) < 5:
            alerts.append("Hunter credits low (<5)")

        for a in alerts:
            logger.warning(a)

        return {
            "today_spend": today_spend,
            "today_executions": int(today["executions"] if today else 0),
            "week_spend": week_spend,
            "week_executions": int(week["executions"] if week else 0),
            "alerts": alerts,
            "credit_status": credit_status,
        }
    finally:
        if own_session:
            db.close()


async def disable_expensive_agents(db: Session) -> None:
    db.execute(
        text(
            """
            UPDATE agent_settings
            SET is_enabled = false
            WHERE agent_name IN ('Content Idea Generator', 'Image Generator', 'Trend Analyzer')
            """
        )
    )
    db.commit()


async def check_api_credits() -> dict[str, Any]:
    apollo_credits = None
    hunter_credits = None
    apollo_key = os.getenv("APOLLO_API_KEY")
    hunter_key = os.getenv("HUNTER_API_KEY")

    async with httpx.AsyncClient(timeout=20.0) as client:
        if apollo_key:
            try:
                r = await client.get(
                    "https://api.apollo.io/v1/auth/health",
                    headers={"X-Api-Key": apollo_key},
                )
                if r.is_success:
                    apollo_credits = (r.json() or {}).get("credits_remaining")
            except Exception:
                apollo_credits = None

        if hunter_key:
            try:
                r = await client.get(
                    "https://api.hunter.io/v2/account",
                    params={"api_key": hunter_key},
                )
                if r.is_success:
                    hunter_credits = (
                        ((r.json() or {}).get("data") or {})
                        .get("requests", {})
                        .get("searches", {})
                        .get("available")
                    )
            except Exception:
                hunter_credits = None

    return {
        "apollo_credits_remaining": apollo_credits,
        "hunter_credits_remaining": hunter_credits,
    }

