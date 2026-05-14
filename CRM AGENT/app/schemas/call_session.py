"""
Pydantic schemas for call session data validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, validator, root_validator

from .base import (
    BaseSchema, TimestampMixin, CallStatus, CallOutcome, 
    validate_phone_number, validate_call_sid, validate_salesforce_id,
    sanitize_text_input
)


class CallSessionBase(BaseSchema):
    """Base schema for call session data."""
    call_sid: str = Field(..., description="Twilio Call SID")
    caller_phone: str = Field(..., description="Caller's phone number")
    contact_id: Optional[str] = Field(None, description="Salesforce Contact ID")
    lead_score: int = Field(default=0, ge=0, le=100, description="Lead qualification score")
    call_outcome: Optional[CallOutcome] = Field(None, description="Final call outcome")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('caller_phone')
    def validate_caller_phone(cls, v):
        return validate_phone_number(v)
    
    @validator('contact_id')
    def validate_contact_id(cls, v):
        if v:
            return validate_salesforce_id(v)
        return v


class CallSessionCreate(CallSessionBase):
    """Schema for creating a new call session."""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "caller_phone": "+15551234567",
                "contact_id": "0031234567890AB",
                "lead_score": 0,
                "start_time": "2024-01-01T12:00:00Z"
            }
        }
    }


class CallSessionUpdate(BaseSchema):
    """Schema for updating an existing call session."""
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = Field(None, ge=0, description="Call duration in seconds")
    lead_score: Optional[int] = Field(None, ge=0, le=100)
    call_outcome: Optional[CallOutcome] = None
    conversation_summary: Optional[str] = Field(None, max_length=2000)
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Structured data from conversation")
    
    @validator('conversation_summary')
    def validate_conversation_summary(cls, v):
        if v:
            return sanitize_text_input(v, max_length=2000)
        return v
    
    @validator('extracted_data')
    def validate_extracted_data(cls, v):
        if v and not isinstance(v, dict):
            raise ValueError("extracted_data must be a dictionary")
        return v


class CallSessionResponse(CallSessionBase, TimestampMixin):
    """Schema for call session API responses."""
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    conversation_summary: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    
    model_config = {"from_attributes": True}


class CallMetricsBase(BaseSchema):
    """Base schema for call metrics."""
    call_sid: str = Field(..., description="Twilio Call SID")
    avg_response_time_ms: Optional[float] = Field(None, ge=0, description="Average response time in milliseconds")
    total_tokens_used: Optional[int] = Field(None, ge=0, description="Total LLM tokens consumed")
    transcription_accuracy: Optional[float] = Field(None, ge=0, le=1, description="Speech transcription accuracy")
    audio_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Audio quality assessment")
    conversation_flow_score: Optional[float] = Field(None, ge=0, le=1, description="Conversation flow quality")
    lead_qualification_confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence in lead scoring")
    information_extraction_completeness: Optional[float] = Field(None, ge=0, le=1, description="Data extraction completeness")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)


class CallMetricsCreate(CallMetricsBase):
    """Schema for creating call metrics."""
    pass


class CallMetricsResponse(CallMetricsBase, TimestampMixin):
    """Schema for call metrics API responses."""
    id: int
    
    model_config = {"from_attributes": True}


class CallSessionWithMetrics(CallSessionResponse):
    """Schema for call session with associated metrics."""
    metrics: Optional[CallMetricsResponse] = None
    conversation_turns: List['ConversationTurnResponse'] = Field(default_factory=list)


# Forward reference resolution
from .conversation import ConversationTurnResponse
CallSessionWithMetrics.update_forward_refs()