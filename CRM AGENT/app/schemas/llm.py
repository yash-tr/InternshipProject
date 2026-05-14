"""
Pydantic schemas for LLM service data validation.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import Field, validator

from .base import BaseSchema, TimestampMixin, validate_call_sid, sanitize_text_input


class TokenUsageBase(BaseSchema):
    """Base schema for token usage tracking."""
    prompt_tokens: int = Field(0, ge=0, description="Number of prompt tokens used")
    completion_tokens: int = Field(0, ge=0, description="Number of completion tokens used")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    cost_estimate: float = Field(0.0, ge=0, description="Estimated cost in USD")


class TokenUsageResponse(TokenUsageBase):
    """Schema for token usage API responses."""
    model_config = {"from_attributes": True}


class LLMRequestBase(BaseSchema):
    """Base schema for LLM requests."""
    call_sid: str = Field(..., description="Twilio Call SID")
    user_input: str = Field(..., min_length=1, max_length=5000, description="User's input message")
    max_tokens: Optional[int] = Field(150, ge=1, le=1000, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Response creativity level")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('user_input')
    def validate_user_input(cls, v):
        return sanitize_text_input(v, max_length=5000)


class LLMRequestCreate(LLMRequestBase):
    """Schema for creating LLM requests."""
    contact_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Salesforce contact context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Recent conversation history")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "user_input": "I'm interested in your services",
                "contact_context": {
                    "Name": "John Doe",
                    "Company": "Acme Corp",
                    "Industry": "Technology"
                },
                "max_tokens": 150,
                "temperature": 0.7
            }
        }
    }


class LLMResponseBase(BaseSchema):
    """Base schema for LLM responses."""
    response_text: str = Field(..., description="Generated AI response")
    tokens_used: int = Field(..., ge=0, description="Number of tokens consumed")
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    model_name: str = Field(..., description="LLM model used for generation")


class LLMResponseCreate(LLMResponseBase):
    """Schema for creating LLM responses."""
    call_sid: str = Field(..., description="Twilio Call SID")
    analysis_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Conversation analysis insights")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('response_text')
    def validate_response_text(cls, v):
        return sanitize_text_input(v, max_length=1000)


class LLMResponseResponse(LLMResponseBase, TimestampMixin):
    """Schema for LLM response API responses."""
    id: int
    call_sid: str
    analysis_data: Optional[Dict[str, Any]] = None
    
    model_config = {"from_attributes": True}


class ConversationAnalysisBase(BaseSchema):
    """Base schema for conversation analysis."""
    call_sid: str = Field(..., description="Twilio Call SID")
    intent: str = Field(..., description="Detected conversation intent")
    confidence: float = Field(..., ge=0, le=1, description="Intent detection confidence")
    buying_signals: List[str] = Field(default_factory=list, description="Detected buying signals")
    objections: List[str] = Field(default_factory=list, description="Identified objections")
    key_topics: List[str] = Field(default_factory=list, description="Main conversation topics")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('intent')
    def validate_intent(cls, v):
        return sanitize_text_input(v, max_length=100)
    
    @validator('buying_signals', 'objections', 'key_topics')
    def validate_string_lists(cls, v):
        return [sanitize_text_input(item, max_length=200) for item in v if item]


class ConversationAnalysisCreate(ConversationAnalysisBase):
    """Schema for creating conversation analysis."""
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_analysis_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw analysis output")


class ConversationAnalysisResponse(ConversationAnalysisBase, TimestampMixin):
    """Schema for conversation analysis API responses."""
    id: int
    analysis_timestamp: datetime
    raw_analysis_data: Optional[Dict[str, Any]] = None
    
    model_config = {"from_attributes": True}


class LeadScoringBase(BaseSchema):
    """Base schema for lead scoring."""
    call_sid: str = Field(..., description="Twilio Call SID")
    lead_score: int = Field(..., ge=0, le=100, description="Lead qualification score (0-100)")
    scoring_factors: Dict[str, Any] = Field(default_factory=dict, description="Factors that influenced the score")
    confidence: float = Field(..., ge=0, le=1, description="Scoring confidence level")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)


class LeadScoringCreate(LeadScoringBase):
    """Schema for creating lead scoring."""
    scoring_timestamp: datetime = Field(default_factory=datetime.utcnow)
    conversation_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Context used for scoring")


class LeadScoringResponse(LeadScoringBase, TimestampMixin):
    """Schema for lead scoring API responses."""
    id: int
    scoring_timestamp: datetime
    conversation_context: Optional[Dict[str, Any]] = None
    
    model_config = {"from_attributes": True}


class ConversationSessionBase(BaseSchema):
    """Base schema for conversation sessions."""
    call_sid: str = Field(..., description="Twilio Call SID")
    contact_context: Dict[str, Any] = Field(default_factory=dict, description="Salesforce contact information")
    extracted_information: Dict[str, Any] = Field(default_factory=dict, description="Information extracted from conversation")
    current_intent: Optional[str] = Field(None, description="Current conversation intent")
    lead_score: int = Field(0, ge=0, le=100, description="Current lead qualification score")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('current_intent')
    def validate_current_intent(cls, v):
        if v:
            return sanitize_text_input(v, max_length=100)
        return v


class ConversationSessionCreate(ConversationSessionBase):
    """Schema for creating conversation sessions."""
    session_start: datetime = Field(default_factory=datetime.utcnow)


class ConversationSessionUpdate(BaseSchema):
    """Schema for updating conversation sessions."""
    contact_context: Optional[Dict[str, Any]] = None
    extracted_information: Optional[Dict[str, Any]] = None
    current_intent: Optional[str] = None
    lead_score: Optional[int] = Field(None, ge=0, le=100)
    
    @validator('current_intent')
    def validate_current_intent(cls, v):
        if v:
            return sanitize_text_input(v, max_length=100)
        return v


class ConversationSessionResponse(ConversationSessionBase, TimestampMixin):
    """Schema for conversation session API responses."""
    id: int
    session_start: datetime
    session_end: Optional[datetime] = None
    total_tokens_used: int = Field(0, ge=0, description="Total tokens consumed in session")
    total_cost_estimate: float = Field(0.0, ge=0, description="Total estimated cost")
    
    model_config = {"from_attributes": True}


class LLMHealthCheck(BaseSchema):
    """Schema for LLM service health check."""
    service_name: str = Field(..., description="Name of the LLM service")
    status: str = Field(..., description="Service health status")
    model_name: str = Field(..., description="Currently configured model")
    api_accessible: bool = Field(..., description="Whether API is accessible")
    response_time_ms: Optional[float] = Field(None, ge=0, description="API response time")
    daily_token_usage: Optional[int] = Field(None, ge=0, description="Tokens used today")
    daily_cost_estimate: Optional[float] = Field(None, ge=0, description="Estimated cost today")
    active_sessions: int = Field(0, ge=0, description="Number of active conversation sessions")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check timestamp")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")


class LLMUsageStats(BaseSchema):
    """Schema for LLM usage statistics."""
    daily_usage: TokenUsageBase = Field(..., description="Today's token usage")
    total_usage: TokenUsageBase = Field(..., description="All-time token usage")
    active_sessions: int = Field(0, ge=0, description="Currently active sessions")
    model_name: str = Field(..., description="LLM model being used")
    reset_date: str = Field(..., description="Date when daily usage was last reset")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class SafetyValidationResult(BaseSchema):
    """Schema for safety validation results."""
    is_safe: bool = Field(..., description="Whether content passed safety checks")
    violations: List[str] = Field(default_factory=list, description="List of safety violations detected")
    filtered_content: Optional[str] = Field(None, description="Content after safety filtering")
    confidence: float = Field(1.0, ge=0, le=1, description="Confidence in safety assessment")