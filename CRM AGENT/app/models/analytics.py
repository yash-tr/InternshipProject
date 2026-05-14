"""
Database models for analytics and reporting.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON

from app.core.database import Base


class CallEvent(Base):
    """Model for storing call events for analytics."""
    
    __tablename__ = "call_events"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # 'incoming', 'outbound', 'completed'
    outcome = Column(String(50), nullable=False)     # 'answered', 'no_answer', 'qualified', etc.
    duration = Column(Float, nullable=True)          # Call duration in seconds
    lead_score = Column(Integer, nullable=True)      # Lead qualification score
    metadata = Column(JSON, nullable=True)           # Additional event data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_call_events_created_outcome', 'created_at', 'outcome'),
        Index('idx_call_events_lead_score', 'lead_score'),
        Index('idx_call_events_duration', 'duration'),
    )


class BusinessMetric(Base):
    """Model for storing aggregated business metrics."""
    
    __tablename__ = "business_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)         # 'percentage', 'count', 'seconds', etc.
    time_range = Column(String(20), nullable=False)  # 'hour', 'day', 'week', 'month'
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_business_metrics_type_period', 'metric_type', 'period_start', 'period_end'),
        Index('idx_business_metrics_name_period', 'metric_name', 'period_start'),
    )


class CostTracking(Base):
    """Model for tracking operational costs."""
    
    __tablename__ = "cost_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(50), nullable=False, index=True)  # 'twilio', 'elevenlabs', 'openrouter'
    cost_type = Column(String(50), nullable=False)                 # 'api_call', 'usage', 'subscription'
    amount = Column(Float, nullable=False)                         # Cost amount in USD
    quantity = Column(Integer, nullable=True)                      # Number of units (calls, tokens, etc.)
    unit_cost = Column(Float, nullable=True)                       # Cost per unit
    call_sid = Column(String(50), nullable=True, index=True)       # Associated call if applicable
    metadata = Column(JSON, nullable=True)                         # Additional cost data
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_cost_tracking_service_date', 'service_name', 'recorded_at'),
        Index('idx_cost_tracking_call_sid', 'call_sid'),
    )


class PerformanceLog(Base):
    """Model for storing system performance logs."""
    
    __tablename__ = "performance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(100), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    response_time = Column(Float, nullable=False)                  # Response time in seconds
    status_code = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    user_agent = Column(String(200), nullable=True)
    ip_address = Column(String(45), nullable=True)
    request_size = Column(Integer, nullable=True)                  # Request size in bytes
    response_size = Column(Integer, nullable=True)                 # Response size in bytes
    metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_performance_logs_endpoint_time', 'endpoint', 'timestamp'),
        Index('idx_performance_logs_response_time', 'response_time'),
        Index('idx_performance_logs_status', 'status_code'),
    )


class LeadQualityTracking(Base):
    """Model for tracking lead qualification accuracy."""
    
    __tablename__ = "lead_quality_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(String(50), nullable=False, index=True)
    predicted_score = Column(Integer, nullable=False)              # AI-predicted lead score
    actual_outcome = Column(String(50), nullable=True)             # Actual outcome ('qualified', 'not_qualified', etc.)
    feedback_score = Column(Integer, nullable=True)                # Human feedback score
    prediction_confidence = Column(Float, nullable=True)           # AI confidence level
    features_used = Column(JSON, nullable=True)                    # Features used in prediction
    model_version = Column(String(20), nullable=True)              # Model version used
    predicted_at = Column(DateTime, nullable=False, index=True)
    outcome_recorded_at = Column(DateTime, nullable=True, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_lead_quality_predicted_at', 'predicted_at'),
        Index('idx_lead_quality_score_outcome', 'predicted_score', 'actual_outcome'),
    )


class ConversationAnalytics(Base):
    """Model for storing conversation-level analytics."""
    
    __tablename__ = "conversation_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(50), nullable=False, index=True)
    conversation_turns = Column(Integer, nullable=False)           # Number of conversation turns
    user_messages = Column(Integer, nullable=False)               # Number of user messages
    ai_messages = Column(Integer, nullable=False)                 # Number of AI messages
    average_response_time = Column(Float, nullable=True)          # Average AI response time
    sentiment_score = Column(Float, nullable=True)               # Overall conversation sentiment
    topics_discussed = Column(JSON, nullable=True)               # Topics identified in conversation
    objections_raised = Column(JSON, nullable=True)              # Objections raised by prospect
    objections_handled = Column(JSON, nullable=True)             # How objections were handled
    conversation_quality = Column(Float, nullable=True)          # Overall conversation quality score
    llm_calls_made = Column(Integer, nullable=False, default=0)  # Number of LLM API calls
    tokens_used = Column(Integer, nullable=True)                 # Total tokens used
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_conversation_analytics_call_sid', 'call_sid'),
        Index('idx_conversation_analytics_created_at', 'created_at'),
        Index('idx_conversation_analytics_quality', 'conversation_quality'),
    )