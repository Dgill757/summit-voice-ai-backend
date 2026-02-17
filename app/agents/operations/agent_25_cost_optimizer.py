"""
Agent 25: Cost Optimizer
Monitors API costs and usage
Identifies optimization opportunities
Runs monthly on 1st at 7 AM
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import func
from app.agents.base import BaseAgent
from app.models import AgentLog, OutreachSequence

class CostOptimizerAgent(BaseAgent):
    """Optimizes system costs"""
    
    def __init__(self, db):
        super().__init__(agent_id=25, agent_name="Cost Optimizer", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Calculate costs
        costs = await self._calculate_monthly_costs()
        
        # Find optimization opportunities
        optimizations = await self._identify_optimizations()
        
        # Generate cost report
        report = await self._generate_cost_report(costs, optimizations)
        
        return {
            "success": True,
            "data": {
                "total_cost": costs['total'],
                "costs_by_service": costs['by_service'],
                "optimization_opportunities": optimizations,
                "potential_savings": sum(opt['savings'] for opt in optimizations)
            }
        }
    
    async def _calculate_monthly_costs(self) -> Dict[str, Any]:
        """Calculate estimated monthly costs"""
        
        # This month
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Count API calls by service
        anthropic_calls = self.db.query(func.count(AgentLog.id)).filter(
            AgentLog.created_at >= start_of_month,
            AgentLog.agent_id.in_([3, 4, 8, 9, 13])  # Agents using Claude
        ).scalar()
        
        outreach_sent = self.db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.created_at >= start_of_month
        ).scalar()
        
        # Estimate costs (rough approximations)
        costs_by_service = {
            "anthropic": anthropic_calls * 0.015,  # ~$0.015 per API call
            "apollo": outreach_sent * 0.02,  # ~$0.02 per prospect
            "hunter": outreach_sent * 0.01,  # ~$0.01 per email find
            "supabase": 25.00,  # Pro plan
            "railway": 20.00,  # Backend hosting
            "vercel": 20.00,  # Frontend hosting
            "redis": 10.00,  # Redis Cloud
        }
        
        total_cost = sum(costs_by_service.values())
        
        return {
            "total": total_cost,
            "by_service": costs_by_service
        }
    
    async def _identify_optimizations(self) -> List[Dict[str, Any]]:
        """Identify cost optimization opportunities"""
        
        optimizations = []
        
        # Check for inefficient API usage
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Find agents with high error rates (wasted API calls)
        error_rates = self.db.query(
            AgentLog.agent_id,
            AgentLog.agent_name,
            func.count(AgentLog.id).filter(AgentLog.status == 'error').label('errors'),
            func.count(AgentLog.id).label('total')
        ).filter(
            AgentLog.created_at >= week_ago
        ).group_by(AgentLog.agent_id, AgentLog.agent_name).all()
        
        for agent_id, agent_name, errors, total in error_rates:
            if total > 0:
                error_rate = (errors / total) * 100
                if error_rate > 20:
                    optimizations.append({
                        "type": "high_error_rate",
                        "agent": agent_name,
                        "description": f"Agent {agent_name} has {error_rate:.1f}% error rate",
                        "savings": errors * 0.015,  # Estimated wasted API cost
                        "action": "Review and fix error handling"
                    })
        
        # Check for duplicate API calls
        # In production: analyze patterns for unnecessary redundancy
        
        # Check for over-provisioned resources
        # In production: analyze actual usage vs provisioned capacity
        
        return optimizations
    
    async def _generate_cost_report(self, costs: Dict[str, Any], optimizations: List[Dict[str, Any]]) -> str:
        """Generate cost optimization report"""
        
        report = f"MONTHLY COST REPORT - {datetime.utcnow().strftime('%B %Y')}\n\n"
        report += f"Total Cost: ${costs['total']:.2f}\n\n"
        report += "Breakdown:\n"
        
        for service, cost in costs['by_service'].items():
            report += f"  {service.title()}: ${cost:.2f}\n"
        
        if optimizations:
            report += f"\nOptimization Opportunities ({len(optimizations)}):\n"
            for opt in optimizations:
                report += f"  • {opt['description']} - Potential savings: ${opt['savings']:.2f}\n"
        
        return report
