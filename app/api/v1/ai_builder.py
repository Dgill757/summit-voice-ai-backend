"""
AI Agent Builder API
Generate agent configurations from natural language prompts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import re
from anthropic import Anthropic

from app.database import get_db
from app.models import AgentSetting
from app.core.security import get_current_user

router = APIRouter()


class AgentPrompt(BaseModel):
    prompt: str
    name: Optional[str] = None


class GeneratedAgent(BaseModel):
    name: str
    description: str
    schedule_cron: Optional[str]
    config: Dict[str, Any]
    workflow_steps: list


@router.post("/generate", response_model=GeneratedAgent)
async def generate_agent_from_prompt(
    prompt: AgentPrompt,
    db: Session = Depends(get_db),
):
    """
    Generate an agent configuration from a natural language prompt
    """

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic = Anthropic(api_key=anthropic_key) if anthropic_key else None

    system_prompt = """You are an AI agent configuration generator. 
    
Given a user's description of what they want an agent to do, you generate a complete agent configuration.

Respond ONLY with valid JSON in this exact format:
{
  "name": "Agent Name",
  "description": "What this agent does",
  "schedule_cron": "0 9 * * *" or null for manual trigger,
  "config": {
    "key": "value for any configuration needed"
  },
  "workflow_steps": [
    {
      "step": 1,
      "action": "describe the action",
      "tool": "api/email/sms/etc",
      "parameters": {}
    }
  ]
}

Examples:
- "Send a daily email report at 9am" -> cron: "0 9 * * *"
- "Check for new leads every 30 minutes" -> cron: "*/30 * * * *"
- "Manual trigger only" -> cron: null

Make it production-ready and detailed."""

    try:
        if anthropic is None:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        message = anthropic.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=2000,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Generate an agent configuration for: {prompt.prompt}"
            }]
        )

        response_text = message.content[0].text

        # Parse JSON response
        import json
        # Remove markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        agent_config = json.loads(response_text.strip())

        # Override name if provided
        if prompt.name:
            agent_config["name"] = prompt.name

        return GeneratedAgent(**agent_config)

    except Exception as e:
        # Deterministic fallback so the feature remains usable even if Anthropic is unavailable.
        fallback_name = prompt.name or infer_name(prompt.prompt)
        fallback_schedule = infer_schedule(prompt.prompt)
        fallback = GeneratedAgent(
            name=fallback_name,
            description=prompt.prompt.strip(),
            schedule_cron=fallback_schedule,
            config={"source": "fallback_generator"},
            workflow_steps=[
                {
                    "step": 1,
                    "action": "Parse prompt intent",
                    "tool": "nlp",
                    "parameters": {"prompt": prompt.prompt},
                },
                {
                    "step": 2,
                    "action": "Execute configured automation",
                    "tool": "workflow_engine",
                    "parameters": {},
                },
            ],
        )
        return fallback


@router.post("/create")
async def create_agent_from_generated(
    agent: GeneratedAgent,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new agent from generated configuration
    """

    # Find next available agent ID
    max_agent = db.query(AgentSetting).order_by(AgentSetting.agent_id.desc()).first()
    next_id = (max_agent.agent_id + 1) if max_agent else 27

    # Create agent setting
    new_agent = AgentSetting(
        agent_id=next_id,
        agent_name=agent.name,
        is_enabled=False,  # Start disabled
        schedule_cron=agent.schedule_cron,
        config={
            "description": agent.description,
            "workflow_steps": agent.workflow_steps,
            **agent.config
        }
    )

    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    return {
        "success": True,
        "agent_id": new_agent.agent_id,
        "message": f"Agent '{agent.name}' created successfully"
    }


def infer_schedule(prompt_text: str) -> Optional[str]:
    t = prompt_text.lower()
    if "every 5 minute" in t:
        return "*/5 * * * *"
    if "every 10 minute" in t:
        return "*/10 * * * *"
    if "every 15 minute" in t:
        return "*/15 * * * *"
    if "every 30 minute" in t:
        return "*/30 * * * *"
    if "hourly" in t or "every hour" in t:
        return "0 * * * *"
    if "daily" in t and "9am" in t:
        return "0 9 * * *"
    if "daily" in t and "8am" in t:
        return "0 8 * * *"
    if "daily" in t and "6am" in t:
        return "0 6 * * *"
    if "daily" in t:
        return "0 9 * * *"
    if "manual" in t:
        return None
    return None


def infer_name(prompt_text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9 ]+", " ", prompt_text).strip()
    words = [w for w in clean.split(" ") if w][:4]
    if not words:
        return "Custom AI Agent"
    return " ".join(w.capitalize() for w in words)
