"""
Base Pydantic models and utilities for data validation.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum


class TimestampMixin(BaseModel):
    """Mixin for models that need timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class CallStatus(str, Enum):
    """Enumeration for call status values."""
    INITIATED = "initiated"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    BUSY = "busy"


class CallOutcome(str, Enum):
    """Enumeration for call outcome values."""
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CALLBACK_REQUESTED = "callback_requested"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"
    TECHNICAL_ISSUE = "technical_issue"
    HUNG_UP = "hung_up"


class ConversationRole(str, Enum):
    """Enumeration for conversation participant roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class LeadSource(str, Enum):
    """Enumeration for lead source values."""
    AI_CALLING_AGENT = "AI_Calling_Agent"
    INBOUND_CALL = "Inbound_Call"
    OUTBOUND_CALL = "Outbound_Call"
    WEB_FORM = "Web_Form"
    REFERRAL = "Referral"


class Priority(str, Enum):
    """Enumeration for task priority levels."""
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"


# Validation patterns
PHONE_PATTERN = re.compile(r'^\+1\d{10}$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
CALL_SID_PATTERN = re.compile(r'^CA[a-f0-9]{32}$')
SALESFORCE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$')


def validate_phone_number(phone: str) -> str:
    """Validate and normalize phone number format."""
    if not phone:
        raise ValueError("Phone number cannot be empty")
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Add +1 if missing for US numbers
    if not cleaned.startswith('+'):
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
    
    if not PHONE_PATTERN.match(cleaned):
        raise ValueError(f"Invalid phone number format: {phone}")
    
    return cleaned


def validate_email(email: str) -> str:
    """Validate email format."""
    if not email:
        raise ValueError("Email cannot be empty")
    
    email = email.lower().strip()
    if not EMAIL_PATTERN.match(email):
        raise ValueError(f"Invalid email format: {email}")
    
    return email


def validate_call_sid(call_sid: str) -> str:
    """Validate Twilio Call SID format."""
    if not call_sid:
        raise ValueError("Call SID cannot be empty")
    
    if not CALL_SID_PATTERN.match(call_sid):
        raise ValueError(f"Invalid Call SID format: {call_sid}")
    
    return call_sid


def validate_salesforce_id(sf_id: str) -> str:
    """Validate Salesforce ID format."""
    if not sf_id:
        raise ValueError("Salesforce ID cannot be empty")
    
    if not SALESFORCE_ID_PATTERN.match(sf_id):
        raise ValueError(f"Invalid Salesforce ID format: {sf_id}")
    
    return sf_id


def sanitize_text_input(text: str, max_length: int = 1000) -> str:
    """Sanitize text input to prevent injection attacks."""
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';\\]', '', text.strip())
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = {
        # Use enum values instead of enum objects
        "use_enum_values": True,
        # Validate assignment to prevent invalid data
        "validate_assignment": True,
        # Allow population by field name or alias
        "populate_by_name": True,
        # Serialize datetime as ISO format
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }