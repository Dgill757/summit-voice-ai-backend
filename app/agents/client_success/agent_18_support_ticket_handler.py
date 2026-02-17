"""
Agent 18: Support Ticket Handler
Monitors and responds to client support requests
Categorizes and prioritizes tickets
Runs every 15 minutes
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
import os
from app.agents.base import BaseAgent
from app.models import Client

class SupportTicketHandlerAgent(BaseAgent):
    """Handles client support tickets"""
    
    def __init__(self, db):
        super().__init__(agent_id=18, agent_name="Support Ticket Handler", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # In production, this would integrate with:
        # - Email inbox for support@summitvoiceai.com
        # - Intercom/Zendesk/Freshdesk
        # - Slack channel for support requests
        
        # For now, we'll simulate by checking client health scores
        # Clients with declining health likely need support
        
        clients_needing_support = self.db.query(Client).filter(
            Client.status == 'active',
            Client.health_score < 70
        ).all()
        
        tickets_handled = 0
        
        for client in clients_needing_support:
            try:
                # Generate support outreach
                message = await self._generate_support_message(client)
                
                # Log support contact
                self._log(
                    "proactive_support",
                    "info",
                    f"Reached out to {client.company_name}",
                    metadata={"health_score": client.health_score, "message": message}
                )
                
                tickets_handled += 1
                
            except Exception as e:
                self._log("handle_ticket", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "proactive_outreach": tickets_handled
            }
        }
    
    async def _generate_support_message(self, client: Client) -> str:
        """Generate proactive support message"""
        
        prompt = f"""Write a brief, caring support email to this client:

Company: {client.company_name}
Health Score: {client.health_score}/100 (declining)
Subscription: {client.subscription_tier}

The email should:
1. Check in on how things are going
2. Offer help proactively
3. Provide direct contact method
4. Sound personal and caring (not automated)

Keep it under 100 words:"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except:
            return f"Hi! I noticed your account might need some attention. Everything going okay with the Voice AI system? I'm here if you need anything - just reply to this email or call me directly. -Dan"
