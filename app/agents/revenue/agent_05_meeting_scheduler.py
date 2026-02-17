"""
Agent 5: Meeting Scheduler
Automatically books meetings with engaged prospects
Integrates with Calendly and sends calendar invites
Runs every 10 minutes
"""
from typing import Dict, Any, Optional
import os
import httpx
from datetime import datetime
from app.agents.base import BaseAgent
from app.models import Prospect, OutreachSequence, Meeting

class MeetingSchedulerAgent(BaseAgent):
    """Schedules meetings with engaged prospects"""
    
    def __init__(self, db):
        super().__init__(agent_id=5, agent_name="Meeting Scheduler", db=db)
        self.calendly_api_key = os.getenv("CALENDLY_API_KEY")
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        meetings_booked = 0
        
        # Find prospects who replied positively and need meetings
        prospects = self.db.query(Prospect).filter(
            Prospect.status == 'engaged',
            ~Prospect.id.in_(
                self.db.query(Meeting.prospect_id).filter(
                    Meeting.status.in_(['scheduled', 'confirmed'])
                )
            )
        ).limit(20).all()
        
        for prospect in prospects:
            try:
                # Check if they explicitly asked for a meeting
                recent_reply = self.db.query(OutreachSequence).filter(
                    OutreachSequence.prospect_id == prospect.id,
                    OutreachSequence.replied == True,
                    OutreachSequence.reply_sentiment == 'positive'
                ).order_by(OutreachSequence.replied_at.desc()).first()
                
                if recent_reply:
                    # Try to book meeting
                    meeting_link = await self._generate_meeting_link(prospect)
                    
                    if meeting_link:
                        # Create meeting record
                        meeting = Meeting(
                            prospect_id=prospect.id,
                            meeting_datetime=datetime.utcnow(),  # Will be updated when they book
                            meeting_type='discovery',
                            calendar_link=meeting_link,
                            status='scheduled'
                        )
                        
                        self.db.add(meeting)
                        
                        # Update prospect status
                        prospect.status = 'meeting_booked'
                        prospect.lead_score = 100
                        
                        self.db.commit()
                        meetings_booked += 1
                        
                        # TODO: Send email with meeting link
                        
            except Exception as e:
                self._log("book_meeting", "error", f"Failed for {prospect.company_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "prospects_processed": len(prospects),
                "meetings_booked": meetings_booked
            }
        }
    
    async def _generate_meeting_link(self, prospect: Prospect) -> Optional[str]:
        """Generate Calendly meeting link"""
        
        if not self.calendly_api_key:
            # Return default Calendly link if no API key
            return "https://calendly.com/summitvoiceai/discovery-call"
        
        try:
            async with httpx.AsyncClient() as client:
                # Calendly API to get event types
                url = "https://api.calendly.com/event_types"
                
                headers = {
                    "Authorization": f"Bearer {self.calendly_api_key}",
                    "Content-Type": "application/json"
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    event_types = data.get('collection', [])
                    
                    # Find "Discovery Call" event type
                    for event_type in event_types:
                        if 'discovery' in event_type.get('name', '').lower():
                            return event_type.get('scheduling_url')
                    
                    # Return first event type if no match
                    if event_types:
                        return event_types[0].get('scheduling_url')
                
        except Exception as e:
            self._log("generate_link", "warning", f"Calendly API failed: {str(e)}")
        
        # Fallback to default link
        return "https://calendly.com/summitvoiceai/discovery-call"
