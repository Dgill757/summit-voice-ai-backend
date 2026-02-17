"""
Agent 22: Daily Briefer
Generates daily executive briefing with key metrics and priorities
Runs daily at 6 AM
"""
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func
from anthropic import AsyncAnthropic
import os
from app.agents.base import BaseAgent
from app.models import Prospect, Client, Meeting, OutreachSequence, ContentCalendar, AgentLog

class DailyBrieferAgent(BaseAgent):
    """Generates daily executive briefing"""
    
    def __init__(self, db):
        super().__init__(agent_id=22, agent_name="Daily Briefer", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Collect all metrics
        metrics = await self._collect_daily_metrics()
        
        # Generate executive summary
        briefing = await self._generate_briefing(metrics)
        
        # In production: Email this to Dan
        # For now, just log it
        
        self._log(
            "daily_briefing",
            "success",
            "Generated daily briefing",
            metadata={"briefing": briefing, "metrics": metrics}
        )
        
        return {
            "success": True,
            "data": {
                "briefing": briefing,
                "metrics": metrics
            }
        }
    
    async def _collect_daily_metrics(self) -> Dict[str, Any]:
        """Collect all key metrics for the day"""
        
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Revenue Pipeline Metrics
        new_prospects_today = self.db.query(func.count(Prospect.id)).filter(
            func.date(Prospect.created_at) == today
        ).scalar()
        
        total_prospects = self.db.query(func.count(Prospect.id)).scalar()
        
        engaged_prospects = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'engaged'
        ).scalar()
        
        meetings_today = self.db.query(func.count(Meeting.id)).filter(
            func.date(Meeting.meeting_datetime) == today,
            Meeting.status.in_(['scheduled', 'confirmed'])
        ).scalar()
        
        # Outreach Metrics
        outreach_sent_today = self.db.query(func.count(OutreachSequence.id)).filter(
            func.date(OutreachSequence.sent_at) == today
        ).scalar()
        
        replies_today = self.db.query(func.count(OutreachSequence.id)).filter(
            func.date(OutreachSequence.replied_at) == today
        ).scalar()
        
        # Client Metrics
        total_clients = self.db.query(func.count(Client.id)).filter(
            Client.status == 'active'
        ).scalar()
        
        onboarding_clients = self.db.query(func.count(Client.id)).filter(
            Client.status == 'onboarding'
        ).scalar()
        
        high_risk_clients = self.db.query(func.count(Client.id)).filter(
            Client.churn_risk == 'high'
        ).scalar()
        
        # Content Metrics
        content_published_today = self.db.query(func.count(ContentCalendar.id)).filter(
            func.date(ContentCalendar.published_at) == today
        ).scalar()
        
        content_scheduled = self.db.query(func.count(ContentCalendar.id)).filter(
            ContentCalendar.status == 'scheduled'
        ).scalar()
        
        # Agent Performance
        agent_errors_today = self.db.query(func.count(AgentLog.id)).filter(
            func.date(AgentLog.created_at) == today,
            AgentLog.status == 'error'
        ).scalar()
        
        agents_run_today = self.db.query(func.count(func.distinct(AgentLog.agent_id))).filter(
            func.date(AgentLog.created_at) == today
        ).scalar()
        
        return {
            "date": today.isoformat(),
            "revenue": {
                "new_prospects_today": new_prospects_today,
                "total_prospects": total_prospects,
                "engaged_prospects": engaged_prospects,
                "meetings_today": meetings_today,
                "outreach_sent_today": outreach_sent_today,
                "replies_today": replies_today
            },
            "clients": {
                "total_active": total_clients,
                "onboarding": onboarding_clients,
                "high_risk": high_risk_clients
            },
            "content": {
                "published_today": content_published_today,
                "scheduled": content_scheduled
            },
            "operations": {
                "agents_run": agents_run_today,
                "errors": agent_errors_today
            }
        }
    
    async def _generate_briefing(self, metrics: Dict[str, Any]) -> str:
        """Generate executive briefing using Claude"""
        
        prompt = f"""Generate a concise daily executive briefing based on these metrics:

Date: {metrics['date']}

REVENUE PIPELINE:
- New prospects today: {metrics['revenue']['new_prospects_today']}
- Total prospects: {metrics['revenue']['total_prospects']}
- Engaged prospects: {metrics['revenue']['engaged_prospects']}
- Meetings today: {metrics['revenue']['meetings_today']}
- Outreach sent: {metrics['revenue']['outreach_sent_today']}
- Replies received: {metrics['revenue']['replies_today']}

CLIENTS:
- Active clients: {metrics['clients']['total_active']}
- Onboarding: {metrics['clients']['onboarding']}
- High churn risk: {metrics['clients']['high_risk']}

CONTENT:
- Published today: {metrics['content']['published_today']}
- Scheduled: {metrics['content']['scheduled']}

SYSTEM:
- Agents run: {metrics['operations']['agents_run']}
- Errors: {metrics['operations']['errors']}

Write a brief (150-200 word) executive summary:
1. Key wins and highlights
2. Important numbers and trends
3. Items needing attention
4. Top 3 priorities for today

Keep it punchy and actionable:"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except Exception as e:
            self._log("generate_briefing", "error", f"Claude failed: {str(e)}")
            
            # Fallback briefing
            return f"""DAILY BRIEFING - {metrics['date']}

HIGHLIGHTS:
- {metrics['revenue']['new_prospects_today']} new prospects added
- {metrics['revenue']['meetings_today']} meetings scheduled today
- {metrics['clients']['total_active']} active clients

ATTENTION NEEDED:
- {metrics['clients']['high_risk']} clients at churn risk
- {metrics['operations']['errors']} system errors today

PRIORITIES:
1. Follow up on engaged prospects
2. Address high-risk client concerns
3. Review content calendar"""
