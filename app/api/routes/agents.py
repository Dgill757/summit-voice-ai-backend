"""
Agents API Routes
Manage and inspect automation agents
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.database import get_db
from app.models import AgentSetting, AgentLog
from app.agents.registry import get_agent_class
from app.websockets.connection_manager import manager

router = APIRouter()


@router.get("/")
async def list_agents(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List configured agents with normalized frontend-friendly fields."""
    agents = db.query(AgentSetting).order_by(AgentSetting.agent_id.asc()).all()
    response: List[Dict[str, Any]] = []
    for a in agents:
        last_log = (
            db.query(AgentLog)
            .filter(AgentLog.agent_id == a.agent_id)
            .order_by(AgentLog.created_at.desc())
            .first()
        )
        status = (last_log.status if last_log and last_log.status else "unknown")
        last_message = (last_log.message if last_log and last_log.message else None)

        # Normalized keys for frontend plus legacy keys for compatibility.
        response.append(
            {
                "id": a.agent_id,
                "name": a.agent_name,
                "enabled": a.is_enabled,
                "schedule": a.schedule_cron,
                "last_run": a.last_run_at.isoformat() if a.last_run_at else None,
                "next_run": a.next_run_at.isoformat() if a.next_run_at else None,
                "status": status,
                "last_message": last_message,
                "agent_id": a.agent_id,
                "agent_name": a.agent_name,
                "is_enabled": a.is_enabled,
                "schedule_cron": a.schedule_cron,
                "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
                "next_run_at": a.next_run_at.isoformat() if a.next_run_at else None,
            }
        )
    return response


@router.get("/logs")
async def recent_agent_logs(limit: int = 100, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Recent agent execution logs"""
    logs = db.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(l.id),
            "agent_id": l.agent_id,
            "agent_name": l.agent_name,
            "action": l.action,
            "status": l.status,
            "message": l.message,
            "execution_time_ms": l.execution_time_ms,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.get("/scheduler/status")
async def scheduler_status() -> Dict[str, Any]:
    """Basic scheduler heartbeat endpoint."""
    return {
        "scheduler": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a single agent with latest execution context."""
    agent = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    last_log = (
        db.query(AgentLog)
        .filter(AgentLog.agent_id == agent_id)
        .order_by(AgentLog.created_at.desc())
        .first()
    )
    return {
        "id": agent.agent_id,
        "name": agent.agent_name,
        "enabled": agent.is_enabled,
        "schedule": agent.schedule_cron,
        "config": agent.config or {},
        "last_run": agent.last_run_at.isoformat() if agent.last_run_at else None,
        "next_run": agent.next_run_at.isoformat() if agent.next_run_at else None,
        "last_status": last_log.status if last_log else "unknown",
        "last_message": last_log.message if last_log else None,
    }


@router.post("/{agent_id}/run")
async def run_agent_now(agent_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Execute an agent immediately."""
    setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not setting.is_enabled:
        raise HTTPException(status_code=400, detail="Agent is disabled")

    agent_class = get_agent_class(agent_id)
    if agent_class is None:
        raise HTTPException(status_code=501, detail=f"Agent {agent_id} is not registered")

    await manager.broadcast(
        "agent_execution",
        {
            "agent_id": agent_id,
            "agent_name": setting.agent_name,
            "status": "starting",
            "message": f"Agent {setting.agent_name} is starting execution",
        },
    )

    agent = agent_class(db=db)
    result = await agent.run()

    # Best-effort schedule metadata updates.
    setting.last_run_at = datetime.utcnow()
    if result.get("success"):
        db.commit()
    else:
        db.commit()

    success = bool(result.get("success", False))
    await manager.broadcast(
        "agent_execution",
        {
            "agent_id": agent_id,
            "agent_name": setting.agent_name,
            "status": "completed" if success else "error",
            "message": f"Agent {setting.agent_name} completed",
            "result": result,
        },
    )

    return {
        "success": success,
        "agent_id": agent_id,
        "agent_name": setting.agent_name,
        "result": result,
    }


@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Enable an agent."""
    setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Agent not found")
    setting.is_enabled = True
    db.commit()
    return {"success": True, "agent_id": agent_id, "enabled": True}


@router.post("/{agent_id}/disable")
async def disable_agent(agent_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Disable an agent."""
    setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Agent not found")
    setting.is_enabled = False
    db.commit()
    return {"success": True, "agent_id": agent_id, "enabled": False}


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: int, limit: int = 50, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get recent logs for a specific agent."""
    logs = (
        db.query(AgentLog)
        .filter(AgentLog.agent_id == agent_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(l.id),
            "agent_id": l.agent_id,
            "agent_name": l.agent_name,
            "action": l.action,
            "status": l.status,
            "message": l.message,
            "error_details": l.error_details,
            "execution_time_ms": l.execution_time_ms,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
