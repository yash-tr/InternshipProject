"""
Pydantic schemas for conversation data validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import Field, validator, HttpUrl

from .base import (
    BaseSchema, TimestampMixin, ConversationRole,
    validate_call_sid, sanitize_text_input
)


class ConversationTurnBase(BaseSchema):
    """Base schema for conversation turn data."""
    call_sid: str = Field(..., description="Twilio Call SID")
    role: ConversationRole = Field(..., description="Speaker role in conversation")
    content: str = Field(..., min_length=1, max_length=5000, description="Conversation content")
    audio_url: Optional[HttpUrl] = Field(None, description="URL to audio recording")
    transcription_confidence: Optional[float] = Field(None, ge=0, le=1, description="Transcription confidence score")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('content')
    def validate_content(cls, v):
        return sanitize_text_input(v, max_length=5000)


class ConversationTurnCreate(ConversationTurnBase):
    """Schema for creating a new conversation turn."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time in milliseconds")
    llm_tokens_used: Optional[int] = Field(None, ge=0, description="LLM tokens consumed for this turn")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "role": "user",
                "content": "Hi, I'm interested in your services",
                "timestamp": "2024-01-01T12:00:00Z",
                "transcription_confidence": 0.95
            }
        }
    }


class ConversationTurnUpdate(BaseSchema):
    """Schema for updating a conversation turn."""
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    audio_url: Optional[HttpUrl] = None
    transcription_confidence: Optional[float] = Field(None, ge=0, le=1)
    processing_time_ms: Optional[int] = Field(None, ge=0)
    llm_tokens_used: Optional[int] = Field(None, ge=0)
    
    @validator('content')
    def validate_content(cls, v):
        if v:
            return sanitize_text_input(v, max_length=5000)
        return v


class ConversationTurnResponse(ConversationTurnBase):
    """Schema for conversation turn API responses."""
    id: int
    timestamp: datetime
    processing_time_ms: Optional[int] = None
    llm_tokens_used: Optional[int] = None
    
    model_config = {"from_attributes": True}


class ConversationContext(BaseSchema):
    """Schema for conversation context and history."""
    call_sid: str = Field(..., description="Twilio Call SID")
    turns: list[ConversationTurnResponse] = Field(default_factory=list, description="Conversation history")
    current_topic: Optional[str] = Field(None, description="Current conversation topic")
    extracted_information: dict = Field(default_factory=dict, description="Information extracted from conversation")
    lead_indicators: list[str] = Field(default_factory=list, description="Buying signals detected")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('current_topic')
    def validate_current_topic(cls, v):
        if v:
            return sanitize_text_input(v, max_length=100)
        return v
    
    def get_recent_turns(self, limit: int = 10) -> list[ConversationTurnResponse]:
        """Get the most recent conversation turns."""
        return self.turns[-limit:] if self.turns else []
    
    def get_conversation_summary(self) -> str:
        """Generate a summary of the conversation."""
        if not self.turns:
            return "No conversation yet"
        
        user_messages = [turn.content for turn in self.turns if turn.role == ConversationRole.USER]
        assistant_messages = [turn.content for turn in self.turns if turn.role == ConversationRole.ASSISTANT]
        
        return f"User messages: {len(user_messages)}, Assistant messages: {len(assistant_messages)}"
    
    def add_turn(self, turn: ConversationTurnResponse) -> None:
        """Add a new turn to the conversation."""
        self.turns.append(turn)
        
        # Keep only the last 50 turns to manage memory
        if len(self.turns) > 50:
            self.turns = self.turns[-50:]


class ConversationAnalysis(BaseSchema):
    """Schema for conversation analysis results."""
    call_sid: str = Field(..., description="Twilio Call SID")
    sentiment_score: float = Field(..., ge=-1, le=1, description="Overall sentiment score")
    intent_classification: str = Field(..., description="Primary intent detected")
    key_topics: list[str] = Field(default_factory=list, description="Main topics discussed")
    buying_signals: list[str] = Field(default_factory=list, description="Buying signals detected")
    objections_raised: list[str] = Field(default_factory=list, description="Objections mentioned")
    information_completeness: float = Field(..., ge=0, le=1, description="How complete is the gathered information")
    next_best_action: str = Field(..., description="Recommended next action")
    
    @validator('call_sid')
    def validate_call_sid(cls, v):
        return validate_call_sid(v)
    
    @validator('intent_classification')
    def validate_intent_classification(cls, v):
        return sanitize_text_input(v, max_length=100)
    
    @validator('next_best_action')
    def validate_next_best_action(cls, v):
        return sanitize_text_input(v, max_length=500)