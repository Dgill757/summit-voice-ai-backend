"""
Agent 17: Check-in Agent
Schedules and manages weekly client check-in calls
Monitors client health and satisfaction
Runs weekly on Monday at 10 AM
"""
from typing import Dict, Any
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
import os
from app.agents.base import BaseAgent
from app.models import Client, Meeting

class CheckinAgent(BaseAgent):
    """Manages client check-in calls"""
    
    def __init__(self, db):
        super().__init__(agent_id=17, agent_name="Check-in Agent", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Find active clients
        active_clients = self.db.query(Client).filter(
            Client.status == 'active'
        ).all()
        
        checkins_scheduled = 0
        
        for client in active_clients:
            try:
                # Check when last check-in was
                last_checkin = self.db.query(Meeting).filter(
                    Meeting.client_id == client.id,
                    Meeting.meeting_type == 'checkin',
                    Meeting.status == 'held'
                ).order_by(Meeting.meeting_datetime.desc()).first()
                
                # Schedule check-in if >7 days since last one
                if not last_checkin or (datetime.utcnow() - last_checkin.meeting_datetime).days >= 7:
                    # Generate personalized check-in agenda
                    agenda = await self._generate_checkin_agenda(client)
                    
                    # Schedule meeting
                    checkin_time = datetime.utcnow() + timedelta(days=3)
                    
                    meeting = Meeting(
                        client_id=client.id,
                        meeting_datetime=checkin_time,
                        duration_minutes=30,
                        meeting_type='checkin',
                        status='scheduled',
                        notes=f"Weekly Check-in\n\nAgenda:\n{agenda}",
                        calendar_link='https://calendly.com/summitvoiceai/weekly-checkin'
                    )
                    
                    self.db.add(meeting)
                    checkins_scheduled += 1
                    
            except Exception as e:
                self._log("schedule_checkin", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "checkins_scheduled": checkins_scheduled
            }
        }
    
    async def _generate_checkin_agenda(self, client: Client) -> str:
        """Generate personalized check-in agenda"""
        
        prompt = f"""Create a brief agenda for a 30-minute check-in call with this client:

Company: {client.company_name}
Industry: {client.industry}
Subscription Tier: {client.subscription_tier}
Health Score: {client.health_score}/100
Time as Client: {(datetime.utcnow().date() - client.onboarding_date).days if client.onboarding_date else 0} days

Create 3-4 agenda items focusing on:
- System performance and results
- Any issues or questions
- Optimization opportunities
- Upcoming features or upgrades

Keep it brief (3-4 bullet points):"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except:
            return "- Review system performance\n- Address any questions\n- Discuss optimization opportunities"
