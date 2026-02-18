"""Agent 22: Cost Monitor.
Runs frequent spend checks and disables non-essential agents when over budget.
"""
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.services.cost_monitor import check_daily_spend


class CostMonitorAgent(BaseAgent):
    def __init__(self, db):
        super().__init__(agent_id=22, agent_name="Cost Monitor", db=db)

    async def execute(self) -> Dict[str, Any]:
        summary = await check_daily_spend(self.db)
        return {"success": True, "data": summary}

