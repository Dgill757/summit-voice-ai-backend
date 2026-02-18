"""
SQLAlchemy models for Summit Voice AI.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ARRAY, Boolean, Column, DECIMAL, Date, DateTime, ForeignKey, Integer, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(Text, nullable=False)
    contact_name = Column(Text)
    title = Column(Text)
    email = Column(Text)
    phone = Column(Text)
    linkedin_url = Column(Text)
    website = Column(Text)
    address = Column(Text)
    city = Column(Text)
    state = Column(Text)
    zip_code = Column(Text)
    industry = Column(Text)
    segment = Column(Text)
    employee_count = Column(Integer)
    revenue_estimate = Column(DECIMAL(15, 2))
    tech_stack = Column(Text)
    source = Column(Text)
    lead_score = Column(Integer, default=0)
    status = Column(Text, default="new")
    notes = Column(Text)
    custom_fields = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime(timezone=True))
    enriched_at = Column(DateTime(timezone=True))


class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    campaign_name = Column(Text)
    channel = Column(Text)
    step_number = Column(Integer, nullable=False)
    message_content = Column(Text, nullable=False)
    subject_line = Column(Text)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    opened = Column(Boolean, default=False)
    opened_at = Column(DateTime(timezone=True))
    clicked = Column(Boolean, default=False)
    clicked_at = Column(DateTime(timezone=True))
    replied = Column(Boolean, default=False)
    replied_at = Column(DateTime(timezone=True))
    reply_content = Column(Text)
    reply_sentiment = Column(Text)
    status = Column(Text, default="scheduled")
    meta = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OutreachQueue(Base):
    __tablename__ = "outreach_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Text, default="pending_approval")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True))


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="SET NULL"))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    meeting_datetime = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=30)
    meeting_type = Column(Text)
    calendar_link = Column(Text)
    zoom_link = Column(Text)
    status = Column(Text, default="scheduled")
    outcome = Column(Text)
    notes = Column(Text)
    recording_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(Text, nullable=False)
    primary_contact_name = Column(Text)
    email = Column(Text)
    phone = Column(Text)
    website = Column(Text)
    industry = Column(Text)
    segment = Column(Text)
    onboarding_date = Column(Date)
    subscription_tier = Column(Text)
    monthly_value = Column(DECIMAL(10, 2))
    status = Column(Text, default="active")
    ghl_sub_account_id = Column(Text)
    contract_start = Column(Date)
    contract_end = Column(Date)
    billing_cycle = Column(Text)
    next_billing_date = Column(Date)
    health_score = Column(Integer, default=50)
    churn_risk = Column(Text, default="low")
    custom_fields = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContentCalendar(Base):
    __tablename__ = "content_calendar"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    content_type = Column(Text)
    platform = Column(Text)
    content_body = Column(Text)
    media_url = Column(Text)
    scheduled_date = Column(Date)
    scheduled_time = Column(Time)
    published_at = Column(DateTime(timezone=True))
    status = Column(Text, default="draft")
    target_audience = Column(Text)
    keywords = Column(ARRAY(Text))
    performance_goal = Column(Text)
    meta = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Engagement(Base):
    __tablename__ = "engagements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content_calendar.id", ondelete="CASCADE"))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    platform = Column(Text)
    engagement_type = Column(Text)
    engagement_datetime = Column(DateTime(timezone=True), server_default=func.now())
    user_info = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)
    metric_category = Column(Text)
    metric_name = Column(Text, nullable=False)
    metric_value = Column(DECIMAL(15, 2))
    comparison_period = Column(Text)
    comparison_value = Column(DECIMAL(15, 2))
    variance_percent = Column(DECIMAL(5, 2))
    meta = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(Integer, nullable=False)
    agent_name = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    status = Column(Text)
    message = Column(Text)
    error_details = Column(Text)
    execution_time_ms = Column(Integer)
    meta = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentSetting(Base):
    __tablename__ = "agent_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(Integer, nullable=False, unique=True)
    agent_name = Column(Text, nullable=False)
    tier = Column(Text, default="Operations")
    is_enabled = Column(Boolean, default=True)
    schedule_cron = Column(Text)
    config = Column(JSONB, default=dict)
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(Text, nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
