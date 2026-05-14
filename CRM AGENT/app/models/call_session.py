"""
Call session database models for tracking phone conversations.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class CallSession(Base):
    """Model for tracking individual call sessions."""
    
    __tablename__ = "call_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), unique=True, nullable=False, index=True)
    caller_phone = Column(String(20), nullable=False, index=True)
    contact_id = Column(String(255), nullable=True, index=True)  # Salesforce Contact ID
    
    # Call timing
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Call outcome and scoring
    lead_score = Column(Integer, default=0)
    call_outcome = Column(String(50), nullable=True)  # qualified, unqualified, callback, etc.
    
    # Conversation data (encrypted)
    conversation_summary = Column(Text, nullable=True)
    extracted_data = Column(JSON, nullable=True)  # Structured data from conversation
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<CallSession(call_sid='{self.call_sid}', phone='{self.caller_phone}')>"


class ConversationTurn(Base):
    """Model for individual conversation turns within a call."""
    
    __tablename__ = "conversation_turns"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), nullable=False, index=True)
    
    # Turn details
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Audio processing
    audio_url = Column(String(500), nullable=True)
    transcription_confidence = Column(Float, nullable=True)
    
    # Processing metadata
    processing_time_ms = Column(Integer, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    
    def __repr__(self) -> str:
        return f"<ConversationTurn(call_sid='{self.call_sid}', role='{self.role}')>"


class CallMetrics(Base):
    """Model for storing call performance metrics."""
    
    __tablename__ = "call_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), nullable=False, index=True)
    
    # Performance metrics
    avg_response_time_ms = Column(Float, nullable=True)
    total_tokens_used = Column(Integer, nullable=True)
    transcription_accuracy = Column(Float, nullable=True)
    
    # Quality metrics
    audio_quality_score = Column(Float, nullable=True)
    conversation_flow_score = Column(Float, nullable=True)
    
    # Business metrics
    lead_qualification_confidence = Column(Float, nullable=True)
    information_extraction_completeness = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self) -> str:
        return f"<CallMetrics(call_sid='{self.call_sid}')>"