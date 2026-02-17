"""
Agent 14: Onboarding Coordinator
Manages client onboarding process from contract to go-live
Creates tasks, schedules kickoff calls, tracks progress
Runs daily at 9 AM
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.agents.base import BaseAgent
from app.models import Client, Meeting

class OnboardingCoordinatorAgent(BaseAgent):
    """Coordinates client onboarding"""
    
    def __init__(self, db):
        super().__init__(agent_id=14, agent_name="Onboarding Coordinator", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Find new clients in onboarding status
        onboarding_clients = self.db.query(Client).filter(
            Client.status == 'onboarding'
        ).all()
        
        processed = 0
        
        for client in onboarding_clients:
            try:
                # Check onboarding stage
                stage = self._get_onboarding_stage(client)
                
                # Take action based on stage
                if stage == 'kickoff':
                    await self._schedule_kickoff(client)
                elif stage == 'setup':
                    await self._monitor_setup(client)
                elif stage == 'training':
                    await self._schedule_training(client)
                elif stage == 'golive':
                    await self._prepare_golive(client)
                elif stage == 'complete':
                    await self._complete_onboarding(client)
                
                processed += 1
                
            except Exception as e:
                self._log("coordinate_onboarding", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "clients_processed": processed
            }
        }
    
    def _get_onboarding_stage(self, client: Client) -> str:
        """Determine current onboarding stage"""
        
        # Check custom_fields for onboarding progress
        onboarding = client.custom_fields.get('onboarding', {})
        
        if not onboarding.get('kickoff_completed'):
            return 'kickoff'
        elif not onboarding.get('ghl_setup_completed'):
            return 'setup'
        elif not onboarding.get('training_completed'):
            return 'training'
        elif not onboarding.get('golive_completed'):
            return 'golive'
        else:
            return 'complete'
    
    async def _schedule_kickoff(self, client: Client):
        """Schedule kickoff call"""
        
        # Check if kickoff already scheduled
        existing = self.db.query(Meeting).filter(
            Meeting.client_id == client.id,
            Meeting.meeting_type == 'checkin',
            Meeting.status.in_(['scheduled', 'confirmed'])
        ).first()
        
        if not existing:
            # Create kickoff meeting
            kickoff_time = datetime.utcnow() + timedelta(days=1)
            
            meeting = Meeting(
                client_id=client.id,
                meeting_datetime=kickoff_time,
                duration_minutes=60,
                meeting_type='checkin',
                status='scheduled',
                notes='Onboarding Kickoff Call',
                calendar_link='https://calendly.com/summitvoiceai/onboarding-kickoff'
            )
            
            self.db.add(meeting)
            self.db.commit()
            
            self._log(
                "schedule_kickoff",
                "success",
                f"Scheduled kickoff for {client.company_name}"
            )
    
    async def _monitor_setup(self, client: Client):
        """Monitor GHL setup progress"""
        
        # Check if setup is taking too long
        onboarding = client.custom_fields.get('onboarding', {})
        kickoff_date = onboarding.get('kickoff_date')
        
        if kickoff_date:
            days_since = (datetime.utcnow().date() - datetime.fromisoformat(kickoff_date).date()).days
            
            if days_since > 3:
                # Send reminder
                self._log(
                    "setup_delayed",
                    "warning",
                    f"Setup delayed for {client.company_name} - {days_since} days"
                )
    
    async def _schedule_training(self, client: Client):
        """Schedule training session"""
        
        # Similar to kickoff scheduling
        pass
    
    async def _prepare_golive(self, client: Client):
        """Prepare for go-live"""
        
        # Final checks before activation
        pass
    
    async def _complete_onboarding(self, client: Client):
        """Complete onboarding process"""
        
        client.status = 'active'
        client.custom_fields['onboarding']['completed_date'] = datetime.utcnow().isoformat()
        
        self.db.commit()
        
        self._log(
            "onboarding_complete",
            "success",
            f"Completed onboarding for {client.company_name}"
        )
