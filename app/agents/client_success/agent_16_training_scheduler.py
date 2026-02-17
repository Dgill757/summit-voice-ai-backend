"""
Agent 16: Training Scheduler
Schedules training sessions for new clients
Sends reminders and follow-ups
Runs weekly on Monday at 8 AM
"""
from typing import Dict, Any
from datetime import datetime, timedelta
from app.agents.base import BaseAgent
from app.models import Client, Meeting

class TrainingSchedulerAgent(BaseAgent):
    """Schedules client training sessions"""
    
    def __init__(self, db):
        super().__init__(agent_id=16, agent_name="Training Scheduler", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Find clients who completed GHL setup but haven't had training
        clients_needing_training = self.db.query(Client).filter(
            Client.status == 'onboarding',
            Client.custom_fields['onboarding']['ghl_setup_completed'].astext == 'true',
            Client.custom_fields['onboarding']['training_completed'].astext != 'true'
        ).all()
        
        scheduled = 0
        
        for client in clients_needing_training:
            try:
                # Check if training already scheduled
                existing = self.db.query(Meeting).filter(
                    Meeting.client_id == client.id,
                    Meeting.meeting_type == 'checkin',
                    Meeting.notes.like('%Training%'),
                    Meeting.status.in_(['scheduled', 'confirmed'])
                ).first()
                
                if not existing:
                    # Schedule training session
                    training_time = datetime.utcnow() + timedelta(days=2)
                    
                    meeting = Meeting(
                        client_id=client.id,
                        meeting_datetime=training_time,
                        duration_minutes=90,
                        meeting_type='checkin',
                        status='scheduled',
                        notes='Voice AI Platform Training Session',
                        calendar_link='https://calendly.com/summitvoiceai/training'
                    )
                    
                    self.db.add(meeting)
                    scheduled += 1
                    
            except Exception as e:
                self._log("schedule_training", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "trainings_scheduled": scheduled
            }
        }
