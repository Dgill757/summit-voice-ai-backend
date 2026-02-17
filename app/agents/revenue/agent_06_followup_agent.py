"""
Agent 6: Follow-up Agent
Sends personalized follow-ups after meetings
Maintains engagement with prospects who went dark
Runs daily at 10 AM
"""
from typing import Dict, Any, List
import os
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import Meeting, Prospect, OutreachSequence

class FollowupAgent(BaseAgent):
    """Handles all follow-up communications"""
    
    def __init__(self, db):
        super().__init__(agent_id=6, agent_name="Follow-up Agent", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        followups_sent = 0
        
        # 1. Follow up after held meetings
        post_meeting = await self._followup_post_meeting()
        followups_sent += post_meeting
        
        # 2. Follow up with dark prospects (no reply in 7+ days)
        dark_prospects = await self._followup_dark_prospects()
        followups_sent += dark_prospects
        
        # 3. Follow up with no-shows
        no_shows = await self._followup_no_shows()
        followups_sent += no_shows
        
        return {
            "success": True,
            "data": {
                "followups_sent": followups_sent,
                "post_meeting": post_meeting,
                "dark_prospects": dark_prospects,
                "no_shows": no_shows
            }
        }
    
    async def _followup_post_meeting(self) -> int:
        """Send follow-ups after meetings that were held"""
        count = 0
        
        # Find meetings held in last 24 hours without follow-up
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        meetings = self.db.query(Meeting).filter(
            Meeting.status == 'held',
            Meeting.meeting_datetime >= yesterday,
            Meeting.meeting_datetime < datetime.utcnow()
        ).all()
        
        for meeting in meetings:
            try:
                prospect = self.db.query(Prospect).filter(
                    Prospect.id == meeting.prospect_id
                ).first()
                
                if not prospect:
                    continue
                
                # Check if we already sent a follow-up
                existing_followup = self.db.query(OutreachSequence).filter(
                    OutreachSequence.prospect_id == prospect.id,
                    OutreachSequence.created_at >= meeting.meeting_datetime,
                    OutreachSequence.meta['type'].astext == 'post_meeting_followup'
                ).first()
                
                if existing_followup:
                    continue
                
                # Generate personalized follow-up
                message = await self._generate_post_meeting_followup(prospect, meeting)
                
                if message:
                    # Create outreach record
                    outreach = OutreachSequence(
                        prospect_id=prospect.id,
                        campaign_name="POST_MEETING_FOLLOWUP",
                        channel="email",
                        step_number=1,
                        message_content=message['content'],
                        subject_line=message['subject'],
                        scheduled_at=datetime.utcnow() + timedelta(hours=2),
                        status='scheduled',
                        meta={"type": "post_meeting_followup", "meeting_id": str(meeting.id)}
                    )
                    
                    self.db.add(outreach)
                    count += 1
                
            except Exception as e:
                self._log("post_meeting_followup", "error", f"Failed for meeting {meeting.id}: {str(e)}")
                continue
        
        self.db.commit()
        return count
    
    async def _followup_dark_prospects(self) -> int:
        """Follow up with prospects who went dark"""
        count = 0
        
        # Find prospects contacted 7+ days ago with no reply
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        prospects = self.db.query(Prospect).filter(
            Prospect.status == 'contacted',
            Prospect.updated_at < week_ago
        ).limit(50).all()
        
        for prospect in prospects:
            try:
                # Check last outreach
                last_outreach = self.db.query(OutreachSequence).filter(
                    OutreachSequence.prospect_id == prospect.id
                ).order_by(OutreachSequence.created_at.desc()).first()
                
                if not last_outreach:
                    continue
                
                # Generate re-engagement message
                message = await self._generate_reengagement_message(prospect)
                
                if message:
                    outreach = OutreachSequence(
                        prospect_id=prospect.id,
                        campaign_name="RE_ENGAGEMENT",
                        channel="email",
                        step_number=1,
                        message_content=message['content'],
                        subject_line=message['subject'],
                        scheduled_at=datetime.utcnow() + timedelta(hours=1),
                        status='scheduled',
                        meta={"type": "reengagement"}
                    )
                    
                    self.db.add(outreach)
                    count += 1
                
            except Exception as e:
                self._log("dark_prospect_followup", "error", f"Failed for {prospect.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        return count
    
    async def _followup_no_shows(self) -> int:
        """Follow up with no-show prospects"""
        count = 0
        
        # Find no-show meetings from last 3 days
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        
        meetings = self.db.query(Meeting).filter(
            Meeting.status == 'no_show',
            Meeting.meeting_datetime >= three_days_ago
        ).all()
        
        for meeting in meetings:
            try:
                prospect = self.db.query(Prospect).filter(
                    Prospect.id == meeting.prospect_id
                ).first()
                
                if not prospect:
                    continue
                
                # Check if we already sent no-show follow-up
                existing = self.db.query(OutreachSequence).filter(
                    OutreachSequence.prospect_id == prospect.id,
                    OutreachSequence.meta['type'].astext == 'no_show_followup',
                    OutreachSequence.created_at >= meeting.meeting_datetime
                ).first()
                
                if existing:
                    continue
                
                # Generate no-show follow-up
                message = await self._generate_no_show_followup(prospect, meeting)
                
                if message:
                    outreach = OutreachSequence(
                        prospect_id=prospect.id,
                        campaign_name="NO_SHOW_FOLLOWUP",
                        channel="email",
                        step_number=1,
                        message_content=message['content'],
                        subject_line=message['subject'],
                        scheduled_at=datetime.utcnow() + timedelta(hours=1),
                        status='scheduled',
                        meta={"type": "no_show_followup", "meeting_id": str(meeting.id)}
                    )
                    
                    self.db.add(outreach)
                    
                    # Update prospect back to engaged status
                    prospect.status = 'engaged'
                    
                    count += 1
                
            except Exception as e:
                self._log("no_show_followup", "error", f"Failed for meeting {meeting.id}: {str(e)}")
                continue
        
        self.db.commit()
        return count
    
    async def _generate_post_meeting_followup(self, prospect: Prospect, meeting: Meeting) -> Dict[str, str]:
        """Generate personalized post-meeting follow-up"""
        
        prompt = f"""Write a warm, personal follow-up email after a discovery call.

Prospect: {prospect.company_name}
Contact: {prospect.contact_name}
Meeting Notes: {meeting.notes or 'Great conversation about voice AI for their business'}

The email should:
1. Thank them for their time
2. Recap key points discussed
3. Provide next steps (contract, demo, implementation)
4. Include a clear call-to-action
5. Sound human and enthusiastic (not salesy)

Keep it under 150 words.

Return JSON with this exact structure:
{{
  "subject": "Great talking with you today!",
  "content": "Hi [name],\n\n[email content here]\n\nBest,\nDan"
}}"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            return json.loads(message.content[0].text)
            
        except Exception as e:
            self._log("generate_followup", "warning", f"Claude failed, using template: {str(e)}")
            
            # Fallback template
            return {
                "subject": f"Great talking with you, {prospect.contact_name}!",
                "content": f"""Hi {prospect.contact_name},

Thanks for taking the time to chat today! I loved hearing about {prospect.company_name}'s growth plans.

Based on our conversation, I'm confident our voice AI can help you capture every inbound call and book 40% more appointments.

Next steps:
1. I'll send over the contract tomorrow
2. We can start implementation next week
3. You'll be live in 5 business days

Sound good? Hit reply and let me know!

Best,
Dan
Summit Voice AI"""
            }
    
    async def _generate_reengagement_message(self, prospect: Prospect) -> Dict[str, str]:
        """Generate re-engagement message for dark prospects"""
        
        name = prospect.contact_name or "there"
        company = prospect.company_name
        
        return {
            "subject": f"Still thinking about {company}?",
            "content": f"""Hi {name},

I haven't heard back, so I'm guessing the timing wasn't right for {company}.

No worries at all - but I wanted to check in one more time.

We just helped a similar {prospect.industry} company book 43 more appointments last month using our voice AI. They're now capturing 100% of inbound calls instead of missing 20+ per week.

If you ever want to explore how this could work for {company}, just reply to this email. Happy to help.

Otherwise, I'll let you be!

Best,
Dan
Summit Voice AI"""
        }
    
    async def _generate_no_show_followup(self, prospect: Prospect, meeting: Meeting) -> Dict[str, str]:
        """Generate follow-up for no-show prospects"""
        
        name = prospect.contact_name or "there"
        
        return {
            "subject": "We missed you yesterday",
            "content": f"""Hi {name},

We had a call scheduled yesterday but didn't connect. No worries - I know things come up!

Want to reschedule? Here's my calendar:
{meeting.calendar_link or 'https://calendly.com/summitvoiceai/discovery-call'}

Or if now's not the right time, just let me know and I'll follow up later.

Looking forward to connecting!

Best,
Dan
Summit Voice AI"""
        }
