"""
Agent 26: System Health Monitor
Monitors overall system health
Checks database, API, agents, integrations
Runs every 5 minutes
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import os
import httpx
from sqlalchemy import func, text
from app.agents.base import BaseAgent
from app.models import AgentSetting, AgentLog
from app.database import engine

class SystemHealthMonitorAgent(BaseAgent):
    """Monitors system health"""
    
    def __init__(self, db):
        super().__init__(agent_id=26, agent_name="System Health Monitor", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        health_checks = []
        
        # Check database
        db_health = await self._check_database_health()
        health_checks.append(db_health)
        
        # Check agents
        agent_health = await self._check_agent_health()
        health_checks.append(agent_health)
        
        # Check external APIs
        api_health = await self._check_api_health()
        health_checks.append(api_health)
        
        # Calculate overall health score
        all_healthy = all(check['status'] == 'healthy' for check in health_checks)
        health_score = sum(1 for check in health_checks if check['status'] == 'healthy') / len(health_checks) * 100
        
        return {
            "success": True,
            "data": {
                "overall_status": "healthy" if all_healthy else "degraded",
                "health_score": health_score,
                "checks": health_checks
            }
        }
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        
        try:
            # Test database connection
            connection = engine.connect()
            
            # Run simple query
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            
            connection.close()
            
            return {
                "component": "database",
                "status": "healthy",
                "message": "Database responsive",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self._log("db_health_check", "error", f"Database unhealthy: {str(e)}")
            
            return {
                "component": "database",
                "status": "unhealthy",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_agent_health(self) -> Dict[str, Any]:
        """Check agent execution health"""
        
        try:
            # Check recent agent activity
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            recent_runs = self.db.query(func.count(AgentLog.id)).filter(
                AgentLog.created_at >= hour_ago
            ).scalar()
            
            recent_errors = self.db.query(func.count(AgentLog.id)).filter(
                AgentLog.created_at >= hour_ago,
                AgentLog.status == 'error'
            ).scalar()
            
            error_rate = (recent_errors / max(recent_runs, 1)) * 100
            
            if error_rate > 50:
                status = "unhealthy"
                message = f"High error rate: {error_rate:.1f}%"
            elif error_rate > 20:
                status = "degraded"
                message = f"Elevated error rate: {error_rate:.1f}%"
            else:
                status = "healthy"
                message = f"Agents running normally ({recent_runs} executions/hour)"
            
            return {
                "component": "agents",
                "status": status,
                "message": message,
                "error_rate": error_rate,
                "recent_runs": recent_runs,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "component": "agents",
                "status": "unhealthy",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_api_health(self) -> Dict[str, Any]:
        """Check external API connectivity"""
        
        try:
            # Test Anthropic API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": os.getenv("ANTHROPIC_API_KEY", "")},
                    timeout=5.0
                )
                
                # We expect a 4xx because no request body, but connection works
                if response.status_code in [400, 401, 403]:
                    status = "healthy"
                    message = "External APIs accessible"
                else:
                    status = "degraded"
                    message = f"API returned unexpected status: {response.status_code}"
                
        except Exception as e:
            status = "unhealthy"
            message = f"API connectivity issue: {str(e)}"
        
        return {
            "component": "external_apis",
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
