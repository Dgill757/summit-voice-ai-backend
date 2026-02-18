from __future__ import annotations

import importlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentSetting
from app.services.n8n_parser import n8n_parser

logger = logging.getLogger(__name__)
router = APIRouter()


class N8NConvertRequest(BaseModel):
    parsed_workflow: dict[str, Any]
    user_api_keys: dict[str, str] = Field(default_factory=dict)


class N8NDeployRequest(BaseModel):
    agent_name: str
    python_code: str
    tier: str = "Operations"
    schedule_cron: str = "0 9 * * 1-5"


@router.post("/analyze")
async def analyze_n8n_workflow(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")

    try:
        content = await file.read()
        n8n_json = json.loads(content)
        parsed = await n8n_parser.parse_workflow(n8n_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}") from exc
    except Exception as exc:
        logger.exception("N8N analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    configured_apis: dict[str, str] = {}
    missing_apis: list[dict[str, str]] = []
    for api in parsed["required_apis"]:
        env_var = api["env_var"]
        if os.getenv(env_var):
            configured_apis[env_var] = "configured"
        else:
            missing_apis.append(api)

    return {
        "success": True,
        "workflow_name": parsed["workflow_name"],
        "node_count": len(parsed["node_logic"]),
        "execution_steps": len(parsed["execution_order"]),
        "required_apis": parsed["required_apis"],
        "configured_apis": configured_apis,
        "missing_apis": missing_apis,
        "can_convert": len(missing_apis) == 0,
        "parsed_data": parsed,
    }


@router.post("/convert")
async def convert_n8n_to_agent(payload: N8NConvertRequest) -> dict[str, Any]:
    try:
        python_code = await n8n_parser.convert_to_python_agent(
            parsed_workflow=payload.parsed_workflow,
            user_api_keys=payload.user_api_keys,
        )
        try:
            compile(python_code, "<generated_n8n_agent>", "exec")
            syntax_valid = True
            syntax_error = None
        except SyntaxError as exc:
            syntax_valid = False
            syntax_error = str(exc)
        return {
            "success": True,
            "python_code": python_code,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "workflow_name": payload.parsed_workflow.get("workflow_name", "Imported Workflow"),
        }
    except Exception as exc:
        logger.exception("N8N conversion failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/deploy")
async def deploy_converted_agent(payload: N8NDeployRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    tier_map = {
        "Revenue": "revenue",
        "Content": "content",
        "ClientSuccess": "client_success",
        "Operations": "operations",
    }
    tier_folder = tier_map.get(payload.tier, "operations")

    max_agent = db.query(AgentSetting).order_by(AgentSetting.agent_id.desc()).first()
    next_agent_id = (max_agent.agent_id + 1) if max_agent else 1

    agent_row = AgentSetting(
        agent_id=next_agent_id,
        agent_name=payload.agent_name,
        tier=payload.tier,
        schedule_cron=payload.schedule_cron,
        is_enabled=False,
        config={"description": f"Imported from n8n workflow: {payload.agent_name}", "source": "n8n_import"},
    )
    db.add(agent_row)
    db.commit()
    db.refresh(agent_row)

    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", payload.agent_name.lower()).strip("_")
    filename = f"agent_{next_agent_id:02d}_{safe_name}.py"
    repo_root = Path(__file__).resolve().parents[3]
    agents_dir = repo_root / "app" / "agents" / tier_folder
    agents_dir.mkdir(parents=True, exist_ok=True)
    filepath = agents_dir / filename

    file_body = (
        f"# Auto-generated from n8n workflow import\n"
        f"# Workflow: {payload.agent_name}\n"
        f"# Generated: {datetime.utcnow().isoformat()}Z\n\n"
        f"{payload.python_code.strip()}\n"
    )
    filepath.write_text(file_body, encoding="utf-8")

    return {
        "success": True,
        "agent_id": next_agent_id,
        "agent_setting_id": str(agent_row.id),
        "filepath": str(filepath),
        "module_path": f"app.agents.{tier_folder}.{filename[:-3]}",
        "message": f"Agent '{payload.agent_name}' deployed successfully",
    }


@router.get("/test/{agent_id}")
async def test_imported_agent(agent_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    agent = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tier_map = {
        "Revenue": "revenue",
        "Content": "content",
        "ClientSuccess": "client_success",
        "Operations": "operations",
    }
    tier_folder = tier_map.get(agent.tier or "Operations", "operations")
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", agent.agent_name.lower()).strip("_")
    module_path = f"app.agents.{tier_folder}.agent_{agent.agent_id:02d}_{safe_name}"

    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not import module '{module_path}': {exc}") from exc

    execute_fn = getattr(module, "execute", None)
    if execute_fn is None or not callable(execute_fn):
        raise HTTPException(status_code=500, detail="Imported module missing async execute(config: dict)")

    try:
        result = await execute_fn(agent.config or {})
        return {"success": True, "test_result": result}
    except Exception as exc:
        logger.exception("Imported agent test execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

