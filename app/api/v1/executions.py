from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentLog

router = APIRouter()


@router.get("/")
async def list_executions(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit).all()
    return [serialize_execution(r) for r in rows]


@router.get("/{execution_id}")
async def execution_detail(execution_id: str, db: Session = Depends(get_db)):
    row = db.query(AgentLog).filter(AgentLog.id == execution_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")
    return serialize_execution(row)


def serialize_execution(r: AgentLog) -> dict:
    return {
        "id": str(r.id),
        "agent_id": r.agent_id,
        "agent_name": r.agent_name,
        "action": r.action,
        "status": r.status,
        "message": r.message,
        "error_details": r.error_details,
        "execution_time_ms": r.execution_time_ms,
        "metadata": r.meta or {},
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

