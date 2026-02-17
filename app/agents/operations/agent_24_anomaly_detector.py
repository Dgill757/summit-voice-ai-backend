"""
Agent 24: Anomaly Detector
Detects unusual patterns in metrics and agent behavior
Alerts on anomalies before they become problems
Runs every 4 hours
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import func
from app.agents.base import BaseAgent
from app.models import Prospect, OutreachSequence, AgentLog, PerformanceMetric

class AnomalyDetectorAgent(BaseAgent):
    """Detects anomalies in system behavior"""
    
    def __init__(self, db):
        super().__init__(agent_id=24, agent_name="Anomaly Detector", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        anomalies = []
        
        # Check for various anomalies
        anomalies.extend(await self._check_prospect_anomalies())
        anomalies.extend(await self._check_outreach_anomalies())
        anomalies.extend(await self._check_agent_anomalies())
        anomalies.extend(await self._check_performance_anomalies())
        
        # Log all anomalies
        for anomaly in anomalies:
            self._log(
                "anomaly_detected",
                "warning",
                anomaly['description'],
                metadata=anomaly
            )
        
        return {
            "success": True,
            "data": {
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies
            }
        }
    
    async def _check_prospect_anomalies(self) -> List[Dict[str, Any]]:
        """Check for unusual prospect patterns"""
        anomalies = []
        
        # Check today vs 7-day average
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        
        prospects_today = self.db.query(func.count(Prospect.id)).filter(
            func.date(Prospect.created_at) == today
        ).scalar()
        
        avg_per_day = self.db.query(func.count(Prospect.id)).filter(
            Prospect.created_at >= week_ago
        ).scalar() / 7.0
        
        # Alert if today is <50% of average
        if avg_per_day > 0 and prospects_today < (avg_per_day * 0.5):
            anomalies.append({
                "type": "prospect_drop",
                "severity": "high",
                "description": f"Prospect generation dropped to {prospects_today} (avg: {avg_per_day:.1f})",
                "current_value": prospects_today,
                "expected_value": avg_per_day
            })
        
        # Alert if unusual spike
        if prospects_today > (avg_per_day * 2):
            anomalies.append({
                "type": "prospect_spike",
                "severity": "medium",
                "description": f"Unusual prospect spike: {prospects_today} (avg: {avg_per_day:.1f})",
                "current_value": prospects_today,
                "expected_value": avg_per_day
            })
        
        return anomalies
    
    async def _check_outreach_anomalies(self) -> List[Dict[str, Any]]:
        """Check for unusual outreach patterns"""
        anomalies = []
        
        # Check reply rate
        total_sent = self.db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.status == 'sent'
        ).scalar()
        
        total_replied = self.db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.replied == True
        ).scalar()
        
        reply_rate = (total_replied / max(total_sent, 1)) * 100
        
        # Alert if reply rate drops below 5%
        if reply_rate < 5 and total_sent > 100:
            anomalies.append({
                "type": "low_reply_rate",
                "severity": "high",
                "description": f"Reply rate dropped to {reply_rate:.1f}%",
                "current_value": reply_rate,
                "expected_value": 10
            })
        
        # Check bounce rate
        total_bounced = self.db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.status == 'bounced'
        ).scalar()
        
        bounce_rate = (total_bounced / max(total_sent, 1)) * 100
        
        # Alert if bounce rate exceeds 10%
        if bounce_rate > 10:
            anomalies.append({
                "type": "high_bounce_rate",
                "severity": "critical",
                "description": f"Bounce rate at {bounce_rate:.1f}%",
                "current_value": bounce_rate,
                "expected_value": 5
            })
        
        return anomalies
    
    async def _check_agent_anomalies(self) -> List[Dict[str, Any]]:
        """Check for unusual agent behavior"""
        anomalies = []
        
        # Check error rates by agent
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        error_counts = self.db.query(
            AgentLog.agent_id,
            AgentLog.agent_name,
            func.count(AgentLog.id)
        ).filter(
            AgentLog.status == 'error',
            AgentLog.created_at >= yesterday
        ).group_by(AgentLog.agent_id, AgentLog.agent_name).all()
        
        for agent_id, agent_name, error_count in error_counts:
            if error_count > 10:
                anomalies.append({
                    "type": "high_agent_errors",
                    "severity": "high",
                    "description": f"Agent {agent_name} has {error_count} errors in 24h",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error_count": error_count
                })
        
        return anomalies
    
    async def _check_performance_anomalies(self) -> List[Dict[str, Any]]:
        """Check for performance degradation"""
        anomalies = []
        
        # Check average execution times
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        slow_agents = self.db.query(
            AgentLog.agent_id,
            AgentLog.agent_name,
            func.avg(AgentLog.execution_time_ms)
        ).filter(
            AgentLog.created_at >= yesterday,
            AgentLog.execution_time_ms.isnot(None)
        ).group_by(AgentLog.agent_id, AgentLog.agent_name).all()
        
        for agent_id, agent_name, avg_time in slow_agents:
            if avg_time and avg_time > 30000:  # >30 seconds
                anomalies.append({
                    "type": "slow_agent_performance",
                    "severity": "medium",
                    "description": f"Agent {agent_name} avg execution time: {avg_time/1000:.1f}s",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "avg_time_ms": avg_time
                })
        
        return anomalies
