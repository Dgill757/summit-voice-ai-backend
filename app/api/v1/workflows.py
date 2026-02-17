from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.services.workflow_engine import (
    create_workflow,
    execute_workflow,
    get_workflow,
    list_workflows,
    toggle_workflow,
)

router = APIRouter()


class WorkflowCreate(BaseModel):
    agent_id: int
    name: str
    cron: str | None = None
    enabled: bool = True
    config: dict[str, Any] = {}


@router.get("/")
async def get_workflows(db: Session = Depends(get_db)):
    return list_workflows(db)


@router.post("/")
async def post_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
):
    return create_workflow(db, payload.model_dump())


@router.get("/{workflow_id}")
async def workflow_detail(workflow_id: str, db: Session = Depends(get_db)):
    row = get_workflow(db, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return row


@router.post("/{workflow_id}/execute")
async def workflow_execute(
    workflow_id: str,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
):
    result = await execute_workflow(db, workflow_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Workflow execution failed"))
    return result


@router.post("/{agent_id}/enable")
async def enable_workflow(
    agent_id: int,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
):
    return toggle_workflow(db, agent_id, True)


@router.post("/{agent_id}/disable")
async def disable_workflow(
    agent_id: int,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
):
    return toggle_workflow(db, agent_id, False)
