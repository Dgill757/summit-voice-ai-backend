"""
Agent 19: Performance Reporter
Generates and sends monthly performance reports to clients
Shows ROI, key metrics, insights
Runs monthly on 1st at 8 AM
"""
from typing import Dict, Any
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
import os
from app.agents.base import BaseAgent
from app.models import Client, PerformanceMetric

class PerformanceReporterAgent(BaseAgent):
    """Generates client performance reports"""
    
    def __init__(self, db):
        super().__init__(agent_id=19, agent_name="Performance Reporter", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get all active clients
        active_clients = self.db.query(Client).filter(
            Client.status == 'active'
        ).all()
        
        reports_generated = 0
        
        for client in active_clients:
            try:
                # Generate performance report
                report = await self._generate_report(client)
                
                if report:
                    # In production, this would:
                    # - Create PDF report
                    # - Email to client
                    # - Save to client portal
                    
                    self._log(
                        "generate_report",
                        "success",
                        f"Generated report for {client.company_name}",
                        metadata={"report_summary": report[:200]}
                    )
                    
                    reports_generated += 1
                    
            except Exception as e:
                self._log("generate_report", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "reports_generated": reports_generated
            }
        }
    
    async def _generate_report(self, client: Client) -> str:
        """Generate performance report content"""
        
        # Calculate metrics for the client
        # In production, this would query actual performance data
        
        # Simulated metrics
        calls_answered = 850
        appointments_booked = 67
        revenue_generated = 28500
        response_time_avg = "12 seconds"
        
        prompt = f"""Create a compelling monthly performance report for this client:

Company: {client.company_name}
Industry: {client.industry}
Subscription: {client.subscription_tier}

This Month's Results:
- Calls Answered: {calls_answered}
- Appointments Booked: {appointments_booked}
- Estimated Revenue Generated: ${revenue_generated:,}
- Average Response Time: {response_time_avg}

Write a brief report (200-300 words) that:
1. Highlights the wins and ROI
2. Shows month-over-month improvement
3. Provides actionable insights
4. Ends with forward-looking goals

Make it compelling and data-driven:"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except:
            return f"Monthly Performance Report for {client.company_name}\n\nYour Voice AI system answered {calls_answered} calls and booked {appointments_booked} appointments this month, generating approximately ${revenue_generated:,} in new revenue."
