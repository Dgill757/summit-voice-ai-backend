from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import AgentSetting
from app.services.agent_executor import execute_agent


def list_workflows(db) -> list[dict[str, Any]]:
    settings = db.query(AgentSetting).order_by(AgentSetting.agent_id.asc()).all()
    return [
        {
            "id": str(s.id),
            "agent_id": s.agent_id,
            "name": s.agent_name,
            "cron": s.schedule_cron,
            "enabled": s.is_enabled,
            "config": s.config or {},
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in settings
    ]


def get_workflow(db, workflow_id: str) -> dict[str, Any] | None:
    row = db.query(AgentSetting).filter(AgentSetting.id == workflow_id).first()
    if not row:
        return None
    return {
        "id": str(row.id),
        "agent_id": row.agent_id,
        "name": row.agent_name,
        "cron": row.schedule_cron,
        "enabled": row.is_enabled,
        "config": row.config or {},
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_workflow(db, payload: dict[str, Any]) -> dict[str, Any]:
    agent_id = int(payload["agent_id"])
    row = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if row:
        row.agent_name = payload.get("name") or row.agent_name
        row.is_enabled = bool(payload.get("enabled", row.is_enabled))
        row.schedule_cron = payload.get("cron")
        row.config = payload.get("config") or row.config
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return get_workflow(db, str(row.id)) or {}
    row = AgentSetting(
        agent_id=agent_id,
        agent_name=payload["name"],
        is_enabled=bool(payload.get("enabled", True)),
        schedule_cron=payload.get("cron"),
        config=payload.get("config") or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_workflow(db, str(row.id)) or {}


def toggle_workflow(db, agent_id: int, enabled: bool) -> dict[str, Any]:
    setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not setting:
        return {"success": False, "error": "Workflow/agent not found"}
    setting.is_enabled = enabled
    setting.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "agent_id": agent_id, "enabled": enabled}


async def execute_workflow(db, workflow_id: str) -> dict[str, Any]:
    setting = db.query(AgentSetting).filter(AgentSetting.id == workflow_id).first()
    if not setting:
        return {"success": False, "error": "Workflow not found"}
    result = await execute_agent(setting.agent_id)
    return {
        "success": True,
        "workflow_id": workflow_id,
        "agent_id": setting.agent_id,
        "result": result,
    }
