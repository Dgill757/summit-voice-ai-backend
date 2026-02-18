"""
Agent registry for runtime execution.
Maps agent_id to concrete agent classes.
"""
from typing import Dict, Type

from app.agents.base import BaseAgent
from app.agents.revenue.agent_01_lead_scraper import LeadScraperAgent
from app.agents.revenue.agent_02_lead_enricher import LeadEnricherAgent
from app.agents.revenue.agent_03_outreach_sequencer import OutreachSequencerAgent
from app.agents.revenue.agent_04_reply_monitor import ReplyMonitorAgent
from app.agents.revenue.agent_05_meeting_scheduler import MeetingSchedulerAgent
from app.agents.revenue.agent_06_followup_agent import FollowupAgent
from app.agents.revenue.agent_07_pipeline_manager import PipelineManagerAgent
from app.agents.content.agent_08_content_idea_generator import ContentIdeaGeneratorAgent
from app.agents.content.agent_09_post_drafter import PostDrafterAgent
from app.agents.content.agent_10_media_creator import MediaCreatorAgent
from app.agents.content.agent_11_post_scheduler import PostSchedulerAgent
from app.agents.content.agent_12_engagement_monitor import EngagementMonitorAgent
from app.agents.content.agent_13_comment_responder import CommentResponderAgent
from app.agents.client_success.agent_14_onboarding_coordinator import OnboardingCoordinatorAgent
from app.agents.client_success.agent_15_ghl_setup_agent import GHLSetupAgent
from app.agents.client_success.agent_16_training_scheduler import TrainingSchedulerAgent
from app.agents.client_success.agent_17_checkin_agent import CheckinAgent
from app.agents.client_success.agent_18_support_ticket_handler import SupportTicketHandlerAgent
from app.agents.client_success.agent_19_performance_reporter import PerformanceReporterAgent
from app.agents.client_success.agent_20_upsell_identifier import UpsellIdentifierAgent
from app.agents.client_success.agent_21_churn_predictor import ChurnPredictorAgent
from app.agents.operations.agent_22_daily_briefer import DailyBrieferAgent
from app.agents.operations.agent_22_cost_monitor import CostMonitorAgent
from app.agents.operations.agent_23_task_coordinator import TaskCoordinatorAgent
from app.agents.operations.agent_24_anomaly_detector import AnomalyDetectorAgent
from app.agents.operations.agent_25_cost_optimizer import CostOptimizerAgent
from app.agents.operations.agent_26_system_health_monitor import SystemHealthMonitorAgent


AGENT_CLASS_MAP: Dict[int, Type[BaseAgent]] = {
    1: LeadScraperAgent,
    2: LeadEnricherAgent,
    3: OutreachSequencerAgent,
    4: FollowupAgent,
    5: ReplyMonitorAgent,
    6: FollowupAgent,
    7: PipelineManagerAgent,
    8: MeetingSchedulerAgent,
    9: ContentIdeaGeneratorAgent,
    10: PostDrafterAgent,
    11: MediaCreatorAgent,
    12: PostSchedulerAgent,
    13: EngagementMonitorAgent,
    14: CommentResponderAgent,
    15: OnboardingCoordinatorAgent,
    16: GHLSetupAgent,
    17: TrainingSchedulerAgent,
    18: CheckinAgent,
    19: SupportTicketHandlerAgent,
    20: PerformanceReporterAgent,
    21: DailyBrieferAgent,
    22: CostMonitorAgent,
    23: TaskCoordinatorAgent,
    24: AnomalyDetectorAgent,
    25: CostOptimizerAgent,
    26: SystemHealthMonitorAgent,
    27: SystemHealthMonitorAgent,
}


def get_agent_class(agent_id: int) -> Type[BaseAgent] | None:
    """Return agent class by ID or None if not found."""
    return AGENT_CLASS_MAP.get(agent_id)
