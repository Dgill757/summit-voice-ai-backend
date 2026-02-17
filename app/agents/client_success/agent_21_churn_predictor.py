"""
Agent 21: Churn Predictor
Predicts client churn risk using ML indicators
Triggers retention workflows
Runs weekly on Monday at 8 AM
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.agents.base import BaseAgent
from app.models import Client, Meeting

class ChurnPredictorAgent(BaseAgent):
    """Predicts and prevents client churn"""
    
    def __init__(self, db):
        super().__init__(agent_id=21, agent_name="Churn Predictor", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get active clients
        active_clients = self.db.query(Client).filter(
            Client.status == 'active'
        ).all()
        
        at_risk_count = 0
        
        for client in active_clients:
            try:
                # Calculate churn risk
                risk_score, risk_factors = self._calculate_churn_risk(client)
                
                # Update client churn risk
                old_risk = client.churn_risk
                
                if risk_score >= 70:
                    client.churn_risk = 'high'
                elif risk_score >= 40:
                    client.churn_risk = 'medium'
                else:
                    client.churn_risk = 'low'
                
                # If risk increased, trigger retention workflow
                if client.churn_risk == 'high' and old_risk != 'high':
                    await self._trigger_retention_workflow(client, risk_factors)
                    at_risk_count += 1
                
                # Update client custom fields
                if not client.custom_fields:
                    client.custom_fields = {}
                
                client.custom_fields['churn_analysis'] = {
                    "risk_score": risk_score,
                    "risk_factors": risk_factors,
                    "last_analyzed": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                self._log("predict_churn", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "clients_analyzed": len(active_clients),
                "high_risk_clients": at_risk_count
            }
        }
    
    def _calculate_churn_risk(self, client: Client) -> tuple:
        """Calculate churn risk score and identify factors"""
        
        risk_score = 0
        risk_factors = []
        
        # Low health score = HIGH RISK
        if client.health_score < 50:
            risk_score += 40
            risk_factors.append("Very low health score")
        elif client.health_score < 70:
            risk_score += 25
            risk_factors.append("Declining health score")
        
        # No recent check-ins = RISK
        last_meeting = self.db.query(Meeting).filter(
            Meeting.client_id == client.id,
            Meeting.status == 'held'
        ).order_by(Meeting.meeting_datetime.desc()).first()
        
        if not last_meeting:
            risk_score += 20
            risk_factors.append("No recent engagement")
        elif last_meeting and (datetime.utcnow() - last_meeting.meeting_datetime).days > 30:
            risk_score += 15
            risk_factors.append("No check-in in 30+ days")
        
        # Approaching contract end = RISK
        if client.contract_end:
            days_until_renewal = (client.contract_end - datetime.utcnow().date()).days
            if days_until_renewal <= 30:
                risk_score += 20
                risk_factors.append("Contract renewal approaching")
        
        # Payment issues = HIGH RISK
        # In production: check for failed payments
        
        # Low usage = RISK
        # In production: check call volume, feature usage
        
        # Support tickets = RISK
        # In production: check for unresolved support issues
        
        return min(risk_score, 100), risk_factors
    
    async def _trigger_retention_workflow(self, client: Client, risk_factors: List[str]):
        """Trigger retention workflow for at-risk client"""
        
        # Schedule urgent check-in
        urgent_checkin = Meeting(
            client_id=client.id,
            meeting_datetime=datetime.utcnow() + timedelta(days=1),
            duration_minutes=30,
            meeting_type='checkin',
            status='scheduled',
            notes=f"URGENT: Retention Check-in\n\nRisk Factors:\n" + "\n".join(f"- {f}" for f in risk_factors),
            calendar_link='https://calendly.com/summitvoiceai/urgent-checkin'
        )
        
        self.db.add(urgent_checkin)
        
        self._log(
            "churn_risk_detected",
            "warning",
            f"High churn risk for {client.company_name}",
            metadata={
                "risk_factors": risk_factors,
                "health_score": client.health_score
            }
        )
