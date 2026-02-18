from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal
from app.api.v1.metrics_ceo import (
    calculate_tier1_metrics,
    calculate_tier2_metrics,
    calculate_tier3_metrics,
    get_cost_breakdown,
)

router = APIRouter()


@router.get("/dashboard/live")
async def stream_dashboard_metrics():
    async def event_generator():
        while True:
            db = SessionLocal()
            try:
                tier1 = await calculate_tier1_metrics(db)
                tier2 = await calculate_tier2_metrics(db)
                tier3 = await calculate_tier3_metrics(db)
                costs = await get_cost_breakdown(db=db)  # type: ignore[arg-type]
                payload = {
                    "dashboard": {
                        "tier1": tier1,
                        "tier2": tier2,
                        "tier3": tier3,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    "costs": costs,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield {"event": "metrics", "data": json.dumps(payload)}
                await asyncio.sleep(5)
            except Exception as exc:
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}
                await asyncio.sleep(5)
            finally:
                db.close()

    return EventSourceResponse(event_generator())


@router.get("/agents/status")
async def stream_agent_status():
    async def event_generator():
        while True:
            db = SessionLocal()
            try:
                query = text(
                    """
                    SELECT
                        a.agent_name,
                        al.status,
                        al.created_at,
                        COALESCE((al.metadata->>'cost_usd')::numeric, 0) AS cost_usd
                    FROM agent_logs al
                    JOIN agent_settings a ON al.agent_id = a.agent_id
                    WHERE al.created_at >= NOW() - INTERVAL '5 minutes'
                    ORDER BY al.created_at DESC
                    LIMIT 10
                    """
                )
                rows = db.execute(query).mappings().all()
                payload = [
                    {
                        "agent": r["agent_name"],
                        "status": r["status"],
                        "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
                        "cost": float(r["cost_usd"] or 0),
                    }
                    for r in rows
                ]
                yield {"event": "agent_activity", "data": json.dumps(payload)}
                await asyncio.sleep(2)
            finally:
                db.close()

    return EventSourceResponse(event_generator())

