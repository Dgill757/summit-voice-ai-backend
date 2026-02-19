"""
Agent 3: Outreach Sequencer
Creates and schedules multi-channel outreach sequences
Target: 200+ outreach messages daily
Channels: Email, LinkedIn, SMS, Voice
"""
from typing import Dict, Any, List
import os
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import Prospect, OutreachSequence, OutreachQueue
from app.integrations.email import EmailService
from app.integrations.gohighlevel import ghl_sync
from app.config import REVENUE_SPRINT_MODE
from app.prompts.outreach_templates import generate_outreach_email

class OutreachSequencerAgent(BaseAgent):
    """Creates personalized outreach sequences"""
    
    def __init__(self, db):
        super().__init__(agent_id=3, agent_name="Outreach Sender", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.email_service = EmailService()
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        max_daily = self.config.get('max_daily', 200)
        if REVENUE_SPRINT_MODE.get("enabled"):
            max_daily = min(max_daily, REVENUE_SPRINT_MODE.get("daily_outreach_target", 50), REVENUE_SPRINT_MODE.get("sendgrid_daily_limit", 100))
        
        require_approval = os.getenv("OUTREACH_REQUIRE_APPROVAL", "true").lower() == "true"

        # Get qualified prospects who haven't been contacted yet
        prospects = self.db.query(Prospect).filter(
            Prospect.status == 'qualified',
            Prospect.email.isnot(None),
            Prospect.phone.isnot(None),
            Prospect.source == "Apollo",
        ).limit(max_daily).all()

        emails_sent = 0
        queued_for_approval = 0

        for prospect in prospects:
            try:
                custom = prospect.custom_fields or {}
                if custom.get("contacted_at"):
                    continue

                email_data = await generate_outreach_email({
                    "name": prospect.contact_name,
                    "company": prospect.company_name,
                    "city": prospect.city,
                    "state": prospect.state,
                    "title": prospect.title,
                })
                subject = email_data["subject"]
                email_body = email_data["body"]

                if require_approval:
                    queued_count = self.db.query(OutreachQueue).filter(
                        OutreachQueue.status == "pending_approval"
                    ).count()
                    if queued_count < 10:
                        self.db.add(
                            OutreachQueue(
                                prospect_id=prospect.id,
                                subject=subject,
                                body=email_body,
                                status="pending_approval",
                            )
                        )
                        self.db.commit()
                        queued_for_approval += 1
                        continue

                await self.email_service.send_email(
                    to=prospect.email,
                    subject=subject,
                    html_content=email_body.replace("\n", "<br/>"),
                    from_email="dan@summitvoiceai.com",
                    from_name="Dan - Summit Voice AI",
                )

                custom["contacted_at"] = datetime.utcnow().isoformat()
                custom["outreach_channel"] = "email"
                prospect.custom_fields = custom
                prospect.status = "contacted"
                emails_sent += 1
                self.db.commit()
                ghl_contact_id = (prospect.custom_fields or {}).get("ghl_contact_id")
                await ghl_sync.update_ghl_contact_status(
                    ghl_contact_id=ghl_contact_id,
                    status="contacted",
                    notes=f"Cold email sent at {datetime.utcnow().isoformat()}",
                )
                    
            except Exception as e:
                self._log("send_outreach", "error", f"Failed for {prospect.company_name}: {str(e)}")
                continue

        return {
            "success": True,
            "data": {
                "prospects_processed": len(prospects),
                "emails_sent": emails_sent,
                "queued_for_approval": queued_for_approval,
                "approval_mode": require_approval,
                "cost_usd": round(emails_sent * 0.003, 4),
            },
        }

    async def _generate_initial_email(self, prospect: Prospect) -> str:
        prompt = f"""
Generate a concise cold email under 100 words.
Prospect: {prospect.contact_name or 'Owner'} at {prospect.company_name}
Location: {prospect.city}, {prospect.state}
Offer: AI voice system that helps roofing companies capture missed calls and book appointments.
CTA: ask for a 15-minute call.
Tone: conversational, not pushy.
"""
        try:
            msg = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception:
            name = prospect.contact_name or "there"
            return (
                f"Hi {name},\n\n"
                f"I noticed {prospect.company_name} is growing in {prospect.city or 'your market'}. "
                "We help roofing teams capture every inbound call and book more jobs with AI voice.\n\n"
                "Open to a 15-minute walkthrough this week?\n\nDan"
            )
    
    async def _generate_sequence(self, prospect: Prospect) -> List[Dict[str, Any]]:
        """Generate personalized 7-step outreach sequence using Claude"""
        
        # Build context for Claude
        prompt = f"""Create a personalized 7-step outreach sequence for this prospect:

Company: {prospect.company_name}
Contact: {prospect.contact_name or 'Decision Maker'}
Title: {prospect.title or 'Owner'}
Industry: {prospect.industry}
Location: {prospect.city}, {prospect.state}

Our Service: Voice AI for {prospect.industry} companies - answers calls 24/7, books appointments, never misses a lead.

Create a sequence with these steps:
1. Initial Email (Day 1) - Value proposition
2. LinkedIn Connection Request (Day 2) - Personal approach
3. Follow-up Email (Day 4) - Case study/social proof
4. LinkedIn Message (Day 6) - If connected
5. Email with Video (Day 8) - Demo video
6. SMS (Day 10) - Brief check-in
7. Breakup Email (Day 14) - Last chance

For each step, provide:
- channel (email/linkedin/sms)
- subject_line (if email)
- message_content (personalized, conversational, focused on THEIR pain points)

Make it sound human, not salesy. Focus on solving their problem (missed calls = lost revenue).

Return ONLY valid JSON array with this structure:
[
  {
    "step": 1,
    "channel": "email",
    "subject_line": "...",
    "message_content": "...",
    "days_from_start": 0
  },
  ...
]"""

        try:
            # Call Claude API
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract JSON from response
            response_text = message.content[0].text
            
            # Parse JSON (Claude should return valid JSON)
            import json
            sequence = json.loads(response_text)
            
            return sequence
            
        except Exception as e:
            self._log("generate_sequence", "error", f"Claude API failed: {str(e)}")
            
            # Fallback to template sequence
            return self._get_template_sequence(prospect)
    
    def _get_template_sequence(self, prospect: Prospect) -> List[Dict[str, Any]]:
        """Fallback template sequence if Claude fails"""
        
        company = prospect.company_name
        name = prospect.contact_name or "there"
        industry = prospect.industry or "home services"
        
        return [
            {
                "step": 1,
                "channel": "email",
                "subject_line": f"Quick question about {company}'s phone coverage",
                "message_content": f"Hi {name},\n\nI noticed {company} might be missing calls when your team is busy or after hours. In the {industry} industry, every missed call can mean $500-2000 in lost revenue.\n\nWe built a voice AI that answers every call in your company's voice, books appointments, and qualifies leads 24/7.\n\nWould you be open to a quick 15-min demo this week?\n\nBest,\nDan\nSummit Voice AI",
                "days_from_start": 0
            },
            {
                "step": 2,
                "channel": "linkedin",
                "subject_line": "",
                "message_content": f"Hi {name}, I help {industry} companies capture every lead with AI voice assistants. I'd love to connect and share how companies like yours are booking 40% more appointments. Let's connect!",
                "days_from_start": 2
            },
            {
                "step": 3,
                "channel": "email",
                "subject_line": f"How [similar {industry} company] booked 43 more jobs/month",
                "message_content": f"Hi {name},\n\nFollowing up on my message about phone coverage for {company}.\n\nA {industry} company in [nearby city] was missing 20+ calls per week. After implementing our voice AI:\n- 43 additional jobs booked per month\n- 24/7 phone coverage\n- Zero missed calls\n\nROI: $18,000+ in first month.\n\nWant to see how this works for {company}? 15 minutes this week?\n\nBest,\nDan",
                "days_from_start": 4
            },
            {
                "step": 4,
                "channel": "linkedin",
                "subject_line": "",
                "message_content": f"Hey {name}, thanks for connecting! Did you get a chance to see my email about capturing every inbound call for {company}? I have a quick demo video if you're interested.",
                "days_from_start": 6
            },
            {
                "step": 5,
                "channel": "email",
                "subject_line": "2-minute demo video",
                "message_content": f"Hi {name},\n\nI made a quick video showing exactly how our voice AI works for {industry} companies.\n\nWatch it here: [DEMO_VIDEO_LINK]\n\nYou'll see:\n- How it answers calls naturally\n- Books appointments automatically  \n- Integrates with your calendar\n\n2 minutes. Worth checking out?\n\nBest,\nDan",
                "days_from_start": 8
            },
            {
                "step": 6,
                "channel": "sms",
                "subject_line": "",
                "message_content": f"Hi {name}, Dan from Summit Voice AI. Still interested in seeing how we can help {company} capture more calls? Quick call this week? - Dan",
                "days_from_start": 10
            },
            {
                "step": 7,
                "channel": "email",
                "subject_line": "Last check - closing your file",
                "message_content": f"Hi {name},\n\nI haven't heard back, so I'm guessing now isn't the right time for {company}.\n\nI'll close your file - but if you ever want to:\n- Capture every inbound call\n- Book more appointments on autopilot\n- Stop losing $10K+/month to missed calls\n\nJust reply to this email. Happy to help anytime.\n\nBest of luck!\nDan",
                "days_from_start": 14
            }
        ]
    
    async def _create_sequence_records(self, prospect: Prospect, sequence: List[Dict[str, Any]]):
        """Create OutreachSequence records in database"""
        
        campaign_name = f"{prospect.industry.upper()}_OUTREACH_{datetime.now().strftime('%Y%m')}"
        
        for step in sequence:
            try:
                scheduled_time = datetime.utcnow() + timedelta(days=step['days_from_start'])
                
                outreach = OutreachSequence(
                    prospect_id=prospect.id,
                    campaign_name=campaign_name,
                    channel=step['channel'],
                    step_number=step['step'],
                    message_content=step['message_content'],
                    subject_line=step.get('subject_line', ''),
                    scheduled_at=scheduled_time,
                    status='scheduled'
                )
                
                self.db.add(outreach)
                
            except Exception as e:
                self._log("create_sequence_record", "warning", f"Failed step {step['step']}: {str(e)}")
                continue
        
        self.db.commit()
