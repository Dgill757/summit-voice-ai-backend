"""
Agent 20: Upsell Identifier
Identifies clients ready for upgrades or add-ons
Scores upsell opportunities
Runs weekly on Wednesday at 9 AM
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.agents.base import BaseAgent
from app.models import Client

class UpsellIdentifierAgent(BaseAgent):
    """Identifies upsell opportunities"""
    
    def __init__(self, db):
        super().__init__(agent_id=20, agent_name="Upsell Identifier", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get active clients
        active_clients = self.db.query(Client).filter(
            Client.status == 'active'
        ).all()
        
        upsell_opportunities = []
        
        for client in active_clients:
            try:
                # Calculate upsell score
                upsell_score = self._calculate_upsell_score(client)
                
                if upsell_score >= 70:
                    opportunity = {
                        "client_id": str(client.id),
                        "company_name": client.company_name,
                        "current_tier": client.subscription_tier,
                        "suggested_tier": self._suggest_upgrade(client),
                        "upsell_score": upsell_score,
                        "reasons": self._get_upsell_reasons(client)
                    }
                    
                    upsell_opportunities.append(opportunity)
                    
                    # Update client custom fields
                    if not client.custom_fields:
                        client.custom_fields = {}
                    
                    client.custom_fields['upsell_opportunity'] = {
                        "score": upsell_score,
                        "identified_date": datetime.utcnow().isoformat(),
                        "suggested_tier": opportunity['suggested_tier']
                    }
                    
            except Exception as e:
                self._log("identify_upsell", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "clients_analyzed": len(active_clients),
                "upsell_opportunities": len(upsell_opportunities),
                "opportunities": upsell_opportunities
            }
        }
    
    def _calculate_upsell_score(self, client: Client) -> int:
        """Calculate upsell readiness score"""
        score = 0
        
        # High health score = +30
        if client.health_score >= 80:
            score += 30
        elif client.health_score >= 70:
            score += 20
        
        # Long tenure = +20
        if client.onboarding_date:
            days_active = (datetime.utcnow().date() - client.onboarding_date).days
            if days_active >= 90:
                score += 20
            elif days_active >= 60:
                score += 15
            elif days_active >= 30:
                score += 10
        
        # Lower tier with good performance = +30
        if client.subscription_tier == 'starter' and client.health_score >= 75:
            score += 30
        elif client.subscription_tier == 'growth' and client.health_score >= 80:
            score += 25
        
        # High usage indicators = +20
        # In production: check call volume, feature usage, etc.
        score += 20
        
        return min(score, 100)
    
    def _suggest_upgrade(self, client: Client) -> str:
        """Suggest appropriate upgrade tier"""
        
        current = client.subscription_tier
        
        if current == 'starter':
            return 'growth'
        elif current == 'growth':
            return 'enterprise'
        else:
            return current
    
    def _get_upsell_reasons(self, client: Client) -> List[str]:
        """Get reasons why client is ready for upsell"""
        
        reasons = []
        
        if client.health_score >= 80:
            reasons.append("High satisfaction and engagement")
        
        if client.onboarding_date and (datetime.utcnow().date() - client.onboarding_date).days >= 90:
            reasons.append("Established customer with proven ROI")
        
        if client.subscription_tier == 'starter':
            reasons.append("Likely outgrowing starter features")
        
        # In production: add data-driven reasons
        reasons.append("High call volume indicating growth")
        reasons.append("Using system at capacity")
        
        return reasons
