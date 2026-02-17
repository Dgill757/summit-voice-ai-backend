"""
Base Agent Class - Foundation for all Summit Voice AI agents
Every agent inherits from this class
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AgentLog, AgentSetting

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_id: int, agent_name: str, db: Session):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.db = db
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load agent configuration from database"""
        try:
            setting = self.db.query(AgentSetting).filter(
                AgentSetting.agent_id == self.agent_id
            ).first()
            
            if setting:
                return setting.config or {}
            return {}
        except Exception as e:
            logger.error(f"Error loading config for agent {self.agent_id}: {str(e)}")
            return {}
    
    def _log(self, action: str, status: str, message: str,
             error_details: Optional[str] = None,
             execution_time_ms: Optional[int] = None,
             metadata: Optional[Dict[str, Any]] = None):
        """Log agent activity to database"""
        try:
            log = AgentLog(
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                action=action,
                status=status,
                message=message,
                error_details=error_details,
                execution_time_ms=execution_time_ms,
                meta=metadata or {}
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error logging for agent {self.agent_id}: {str(e)}")
            self.db.rollback()
    
    def _update_last_run(self):
        """Update the last run timestamp"""
        try:
            setting = self.db.query(AgentSetting).filter(
                AgentSetting.agent_id == self.agent_id
            ).first()
            
            if setting:
                setting.last_run_at = datetime.utcnow()
                self.db.commit()
        except Exception as e:
            logger.error(f"Error updating last run for agent {self.agent_id}: {str(e)}")
            self.db.rollback()
    
    def is_enabled(self) -> bool:
        """Check if agent is enabled"""
        try:
            setting = self.db.query(AgentSetting).filter(
                AgentSetting.agent_id == self.agent_id
            ).first()
            return setting.is_enabled if setting else False
        except Exception as e:
            logger.error(f"Error checking if agent {self.agent_id} is enabled: {str(e)}")
            return False
    
    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        Main execution method - must be implemented by each agent
        Returns: Dict with 'success' bool and 'data' dict
        """
        pass
    
    async def run(self) -> Dict[str, Any]:
        """
        Wrapper method that handles logging and error handling
        """
        if not self.is_enabled():
            return {
                "success": False,
                "message": f"Agent {self.agent_name} is disabled"
            }
        
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting agent {self.agent_name} (ID: {self.agent_id})")
            
            # Execute the agent's main logic
            result = await self.execute()
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log success
            self._log(
                action="execute",
                status="success",
                message=f"Agent completed successfully",
                execution_time_ms=execution_time,
                metadata=result.get('data', {})
            )
            
            # Update last run
            self._update_last_run()
            
            logger.info(f"Agent {self.agent_name} completed in {execution_time}ms")
            
            return result
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log error
            self._log(
                action="execute",
                status="error",
                message=f"Agent failed: {str(e)}",
                error_details=str(e),
                execution_time_ms=execution_time
            )
            
            logger.error(f"Agent {self.agent_name} failed: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "message": f"Agent {self.agent_name} failed"
            }
