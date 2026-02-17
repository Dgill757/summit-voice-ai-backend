"""
Agent 7: Pipeline Manager
Manages entire revenue pipeline
Updates lead scores, identifies stalled deals, provides forecasting
Runs daily at 8 AM
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import func
from app.agents.base import BaseAgent
from app.models import Prospect, Meeting, OutreachSequence, PerformanceMetric

class PipelineManagerAgent(BaseAgent):
    """Manages and optimizes the revenue pipeline"""
    
    def __init__(self, db):
        super().__init__(agent_id=7, agent_name="Pipeline Manager", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # 1. Update all lead scores
        scores_updated = await self._update_lead_scores()
        
        # 2. Identify and handle stalled deals
        stalled_handled = await self._handle_stalled_deals()
        
        # 3. Calculate pipeline metrics
        metrics = await self._calculate_pipeline_metrics()
        
        # 4. Save metrics to database
        await self._save_metrics(metrics)
        
        # 5. Identify hot leads
        hot_leads = await self._identify_hot_leads()
        
        return {
            "success": True,
            "data": {
                "scores_updated": scores_updated,
                "stalled_deals_handled": stalled_handled,
                "metrics": metrics,
                "hot_leads_count": len(hot_leads)
            }
        }
    
    async def _update_lead_scores(self) -> int:
        """Update lead scores for all active prospects"""
        count = 0
        
        prospects = self.db.query(Prospect).filter(
            Prospect.status.in_(['new', 'qualified', 'contacted', 'engaged', 'meeting_booked'])
        ).all()
        
        for prospect in prospects:
            try:
                old_score = prospect.lead_score
                new_score = self._calculate_dynamic_score(prospect)
                
                if new_score != old_score:
                    prospect.lead_score = new_score
                    count += 1
                    
            except Exception as e:
                self._log("update_score", "warning", f"Failed for {prospect.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        return count
    
    def _calculate_dynamic_score(self, prospect: Prospect) -> int:
        """Calculate dynamic lead score based on engagement"""
        score = 0
        
        # Base contact info (max 40 points)
        if prospect.email:
            score += 20
        if prospect.phone:
            score += 10
        if prospect.website:
            score += 10
        
        # Company info (max 20 points)
        if prospect.employee_count:
            if 10 <= prospect.employee_count <= 50:
                score += 15  # Sweet spot
            elif 5 <= prospect.employee_count < 10:
                score += 10
            elif prospect.employee_count > 50:
                score += 5
        
        if prospect.revenue_estimate and prospect.revenue_estimate > 500000:
            score += 5
        
        # Engagement level (max 40 points)
        # Check outreach interactions
        outreach_count = self.db.query(OutreachSequence).filter(
            OutreachSequence.prospect_id == prospect.id
        ).count()
        
        opened_count = self.db.query(OutreachSequence).filter(
            OutreachSequence.prospect_id == prospect.id,
            OutreachSequence.opened == True
        ).count()
        
        replied_count = self.db.query(OutreachSequence).filter(
            OutreachSequence.prospect_id == prospect.id,
            OutreachSequence.replied == True
        ).count()
        
        # Opened emails = +10
        if opened_count > 0:
            score += 10
        
        # Replied = +20
        if replied_count > 0:
            score += 20
        
        # Has meeting = +10
        has_meeting = self.db.query(Meeting).filter(
            Meeting.prospect_id == prospect.id
        ).first()
        
        if has_meeting:
            score += 10
        
        return min(score, 100)
    
    async def _handle_stalled_deals(self) -> int:
        """Identify and handle stalled deals"""
        count = 0
        
        # Prospects in "engaged" for 14+ days = stalled
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        
        stalled = self.db.query(Prospect).filter(
            Prospect.status == 'engaged',
            Prospect.updated_at < two_weeks_ago
        ).all()
        
        for prospect in stalled:
            try:
                # Move to nurture status
                prospect.status = 'nurture'
                prospect.lead_score = max(prospect.lead_score - 20, 0)
                count += 1
                
                self._log(
                    "stalled_deal",
                    "info",
                    f"Moved {prospect.company_name} to nurture",
                    metadata={"prospect_id": str(prospect.id)}
                )
                
            except Exception as e:
                self._log("handle_stalled", "error", f"Failed for {prospect.company_name}: {str(e)}")
                continue
        
        self.db.commit()
        return count
    
    async def _calculate_pipeline_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive pipeline metrics"""
        
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Total prospects by stage
        total_prospects = self.db.query(func.count(Prospect.id)).scalar()
        
        new_prospects = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'new'
        ).scalar()
        
        qualified = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'qualified'
        ).scalar()
        
        contacted = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'contacted'
        ).scalar()
        
        engaged = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'engaged'
        ).scalar()
        
        meeting_booked = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'meeting_booked'
        ).scalar()
        
        closed_won = self.db.query(func.count(Prospect.id)).filter(
            Prospect.status == 'closed_won'
        ).scalar()
        
        # Outreach metrics
        total_outreach = self.db.query(func.count(OutreachSequence.id)).scalar()
        
        sent_this_week = self.db.query(func.count(OutreachSequence.id)).filter(
            OutreachSequence.sent_at >= week_ago
        ).scalar()
        
        opened_rate = self.db.query(
            func.count(OutreachSequence.id).filter(OutreachSequence.opened == True)
        ).scalar() / max(total_outreach, 1) * 100
        
        reply_rate = self.db.query(
            func.count(OutreachSequence.id).filter(OutreachSequence.replied == True)
        ).scalar() / max(total_outreach, 1) * 100
        
        # Meeting metrics
        total_meetings = self.db.query(func.count(Meeting.id)).scalar()
        
        upcoming_meetings = self.db.query(func.count(Meeting.id)).filter(
            Meeting.status == 'scheduled',
            Meeting.meeting_datetime >= datetime.utcnow()
        ).scalar()
        
        held_this_month = self.db.query(func.count(Meeting.id)).filter(
            Meeting.status == 'held',
            Meeting.meeting_datetime >= month_ago
        ).scalar()
        
        # Conversion rates
        contact_to_engaged = (engaged / max(contacted, 1)) * 100
        engaged_to_meeting = (meeting_booked / max(engaged, 1)) * 100
        meeting_to_closed = (closed_won / max(total_meetings, 1)) * 100
        
        # Velocity metrics
        avg_days_to_meeting = self._calculate_avg_days_to_meeting()
        avg_days_to_close = self._calculate_avg_days_to_close()
        
        return {
            "pipeline": {
                "total_prospects": total_prospects,
                "new": new_prospects,
                "qualified": qualified,
                "contacted": contacted,
                "engaged": engaged,
                "meeting_booked": meeting_booked,
                "closed_won": closed_won
            },
            "outreach": {
                "total_sent": total_outreach,
                "sent_this_week": sent_this_week,
                "open_rate": round(opened_rate, 2),
                "reply_rate": round(reply_rate, 2)
            },
            "meetings": {
                "total": total_meetings,
                "upcoming": upcoming_meetings,
                "held_this_month": held_this_month
            },
            "conversion_rates": {
                "contact_to_engaged": round(contact_to_engaged, 2),
                "engaged_to_meeting": round(engaged_to_meeting, 2),
                "meeting_to_closed": round(meeting_to_closed, 2)
            },
            "velocity": {
                "avg_days_to_meeting": avg_days_to_meeting,
                "avg_days_to_close": avg_days_to_close
            }
        }
    
    def _calculate_avg_days_to_meeting(self) -> float:
        """Calculate average days from first contact to meeting"""
        # Get prospects with meetings
        prospects_with_meetings = self.db.query(Prospect).filter(
            Prospect.status.in_(['meeting_booked', 'closed_won'])
        ).limit(100).all()
        
        if not prospects_with_meetings:
            return 0.0
        
        total_days = 0
        count = 0
        
        for prospect in prospects_with_meetings:
            # Find first outreach
            first_outreach = self.db.query(OutreachSequence).filter(
                OutreachSequence.prospect_id == prospect.id
            ).order_by(OutreachSequence.created_at.asc()).first()
            
            # Find first meeting
            first_meeting = self.db.query(Meeting).filter(
                Meeting.prospect_id == prospect.id
            ).order_by(Meeting.created_at.asc()).first()
            
            if first_outreach and first_meeting:
                days = (first_meeting.created_at - first_outreach.created_at).days
                total_days += days
                count += 1
        
        return round(total_days / max(count, 1), 1)
    
    def _calculate_avg_days_to_close(self) -> float:
        """Calculate average days from first contact to closed won"""
        closed_prospects = self.db.query(Prospect).filter(
            Prospect.status == 'closed_won'
        ).limit(100).all()
        
        if not closed_prospects:
            return 0.0
        
        total_days = 0
        count = 0
        
        for prospect in closed_prospects:
            if prospect.scraped_at:
                days = (datetime.utcnow() - prospect.scraped_at).days
                total_days += days
                count += 1
        
        return round(total_days / max(count, 1), 1)
    
    async def _save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to performance_metrics table"""
        
        today = datetime.utcnow().date()
        
        # Save key metrics
        metrics_to_save = [
            ("revenue", "total_prospects", metrics['pipeline']['total_prospects']),
            ("revenue", "closed_won", metrics['pipeline']['closed_won']),
            ("revenue", "open_rate", metrics['outreach']['open_rate']),
            ("revenue", "reply_rate", metrics['outreach']['reply_rate']),
            ("revenue", "upcoming_meetings", metrics['meetings']['upcoming']),
            ("revenue", "avg_days_to_meeting", metrics['velocity']['avg_days_to_meeting']),
            ("revenue", "avg_days_to_close", metrics['velocity']['avg_days_to_close'])
        ]
        
        for category, name, value in metrics_to_save:
            try:
                metric = PerformanceMetric(
                    date=today,
                    metric_category=category,
                    metric_name=name,
                    metric_value=value,
                    comparison_period='daily',
                    meta=metrics
                )
                
                self.db.add(metric)
                
            except Exception as e:
                self._log("save_metric", "warning", f"Failed to save {name}: {str(e)}")
                continue
        
        self.db.commit()
    
    async def _identify_hot_leads(self) -> List[Prospect]:
        """Identify hot leads that need immediate attention"""
        
        # Hot = score > 80, engaged or meeting_booked status
        hot_leads = self.db.query(Prospect).filter(
            Prospect.lead_score >= 80,
            Prospect.status.in_(['engaged', 'meeting_booked'])
        ).all()
        
        return hot_leads
