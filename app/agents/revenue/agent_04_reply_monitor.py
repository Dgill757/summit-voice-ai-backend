"""
Agent 4: Reply Monitor
Monitors email, LinkedIn, SMS for prospect replies
Categorizes sentiment and triggers appropriate actions
Runs every 15 minutes
"""
from typing import Dict, Any, List, Optional
import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import OutreachSequence, Prospect

class ReplyMonitorAgent(BaseAgent):
    """Monitors and processes prospect replies"""
    
    def __init__(self, db):
        super().__init__(agent_id=4, agent_name="Reply Monitor", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        replies_processed = 0
        
        # Check email replies
        email_replies = await self._check_email_replies()
        replies_processed += len(email_replies)
        
        # Process each reply
        for reply in email_replies:
            await self._process_reply(reply)
        
        return {
            "success": True,
            "data": {
                "replies_found": replies_processed,
                "channels_monitored": ["email"]
            }
        }
    
    async def _check_email_replies(self) -> List[Dict[str, Any]]:
        """Check IMAP inbox for new replies"""
        replies = []
        
        try:
            # Connect to email via IMAP
            imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
            email_address = os.getenv("OUTREACH_EMAIL")
            email_password = os.getenv("OUTREACH_EMAIL_PASSWORD")
            
            if not email_address or not email_password:
                return replies
            
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_address, email_password)
            mail.select("inbox")
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            
            if status == "OK":
                email_ids = messages[0].split()
                
                for email_id in email_ids[-50:]:  # Process last 50 unread
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    
                    if status == "OK":
                        # Parse email
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Extract sender
                        from_email = email.utils.parseaddr(msg.get("From"))[1]
                        
                        # Extract subject
                        subject = decode_header(msg.get("Subject"))[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()
                        
                        # Extract body
                        body = self._get_email_body(msg)
                        
                        # Find matching prospect by email
                        prospect = self.db.query(Prospect).filter(
                            Prospect.email == from_email
                        ).first()
                        
                        if prospect:
                            replies.append({
                                "prospect_id": prospect.id,
                                "from_email": from_email,
                                "subject": subject,
                                "body": body,
                                "received_at": datetime.utcnow()
                            })
                        
                        # Mark as read
                        mail.store(email_id, "+FLAGS", "\\Seen")
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            self._log("check_email", "error", f"Email check failed: {str(e)}")
        
        return replies
    
    def _get_email_body(self, msg) -> str:
        """Extract email body from message"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode()
                        break
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                pass
        
        return body
    
    async def _process_reply(self, reply: Dict[str, Any]):
        """Process a single reply"""
        
        try:
            prospect_id = reply['prospect_id']
            body = reply['body']
            
            # Analyze sentiment using Claude
            sentiment = await self._analyze_sentiment(body)
            
            # Find the most recent outreach for this prospect
            outreach = self.db.query(OutreachSequence).filter(
                OutreachSequence.prospect_id == prospect_id,
                OutreachSequence.status == 'sent'
            ).order_by(OutreachSequence.sent_at.desc()).first()
            
            if outreach:
                # Update outreach record
                outreach.replied = True
                outreach.replied_at = reply['received_at']
                outreach.reply_content = body
                outreach.reply_sentiment = sentiment
                outreach.status = 'replied'
            
            # Update prospect status based on sentiment
            prospect = self.db.query(Prospect).filter(
                Prospect.id == prospect_id
            ).first()
            
            if prospect:
                if sentiment in ['positive', 'question']:
                    prospect.status = 'engaged'
                    prospect.lead_score = min(prospect.lead_score + 20, 100)
                elif sentiment == 'objection':
                    prospect.status = 'engaged'
                    prospect.lead_score = max(prospect.lead_score - 10, 0)
                elif sentiment == 'negative':
                    prospect.status = 'closed_lost'
                    prospect.lead_score = 0
            
            self.db.commit()
            
            self._log(
                "process_reply",
                "success",
                f"Processed reply from {prospect.company_name}",
                metadata={"sentiment": sentiment}
            )
            
        except Exception as e:
            self._log("process_reply", "error", f"Failed to process reply: {str(e)}")
            self.db.rollback()
    
    async def _analyze_sentiment(self, reply_text: str) -> str:
        """Analyze reply sentiment using Claude"""
        
        prompt = f"""Analyze this prospect's reply and categorize the sentiment:

Reply: "{reply_text}"

Categories:
- positive: They're interested, want to learn more, or ready to book a meeting
- negative: Definitely not interested, unsubscribe, or angry
- neutral: Acknowledging but not committing
- question: Asking for clarification or more information
- objection: Interested but has concerns (price, timing, etc)

Return ONLY ONE WORD: positive, negative, neutral, question, or objection"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=10,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            sentiment = message.content[0].text.strip().lower()
            
            # Validate response
            valid_sentiments = ['positive', 'negative', 'neutral', 'question', 'objection']
            if sentiment in valid_sentiments:
                return sentiment
            
        except Exception as e:
            self._log("analyze_sentiment", "warning", f"Claude analysis failed: {str(e)}")
        
        # Fallback: Basic keyword analysis
        reply_lower = reply_text.lower()
        
        if any(word in reply_lower for word in ['interested', 'yes', 'sure', 'sounds good', 'when', 'available']):
            return 'positive'
        elif any(word in reply_lower for word in ['not interested', 'unsubscribe', 'remove', 'stop']):
            return 'negative'
        elif any(word in reply_lower for word in ['how', 'what', 'why', 'explain', '?']):
            return 'question'
        elif any(word in reply_lower for word in ['but', 'however', 'expensive', 'cost', 'later']):
            return 'objection'
        else:
            return 'neutral'
