"""
Agent 23: Task Coordinator
Coordinates tasks across all agents
Manages dependencies and priorities
Runs every 2 hours
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.agents.base import BaseAgent
from app.models import AgentSetting, AgentLog

class TaskCoordinatorAgent(BaseAgent):
    """Coordinates tasks across all agents"""
    
    def __init__(self, db):
        super().__init__(agent_id=23, agent_name="Task Coordinator", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Check all agent schedules
        agents = self.db.query(AgentSetting).filter(
            AgentSetting.is_enabled == True
        ).all()
        
        tasks_due = []
        tasks_overdue = []
        
        for agent in agents:
            try:
                # Check if agent should run now
                if self._should_run_now(agent):
                    tasks_due.append({
                        "agent_id": agent.agent_id,
                        "agent_name": agent.agent_name,
                        "schedule": agent.schedule_cron,
                        "last_run": agent.last_run_at.isoformat() if agent.last_run_at else None
                    })
                
                # Check if agent is overdue
                if self._is_overdue(agent):
                    tasks_overdue.append({
                        "agent_id": agent.agent_id,
                        "agent_name": agent.agent_name,
                        "last_run": agent.last_run_at.isoformat() if agent.last_run_at else None
                    })
                    
            except Exception as e:
                self._log("check_agent", "error", f"Failed for agent {agent.agent_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "total_agents": len(agents),
                "tasks_due": len(tasks_due),
                "tasks_overdue": len(tasks_overdue),
                "due_tasks": tasks_due,
                "overdue_tasks": tasks_overdue
            }
        }
    
    def _should_run_now(self, agent: AgentSetting) -> bool:
        """Check if agent should run now based on schedule"""
        
        if not agent.next_run_at:
            return True
        
        return agent.next_run_at <= datetime.utcnow()
    
    def _is_overdue(self, agent: AgentSetting) -> bool:
        """Check if agent is overdue to run"""
        
        if not agent.last_run_at:
            return False
        
        # Define "overdue" thresholds by agent
        overdue_thresholds = {
            1: 6,   # Lead Scraper - should run every 4 hours
            2: 2,   # Lead Enricher - should run every 30 min
            3: 24,  # Outreach Sequencer - should run twice daily
            4: 1,   # Reply Monitor - should run every 15 min
            5: 1,   # Meeting Scheduler - should run every 10 min
            # Add others as needed
        }
        
        threshold_hours = overdue_thresholds.get(agent.agent_id, 24)
        hours_since_run = (datetime.utcnow() - agent.last_run_at).total_seconds() / 3600
        
        return hours_since_run > threshold_hours
