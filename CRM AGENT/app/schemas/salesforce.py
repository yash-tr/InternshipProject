"""
Pydantic schemas for Salesforce CRM data validation.
"""
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from pydantic import Field, validator, EmailStr

from .base import (
    BaseSchema, TimestampMixin, LeadSource, Priority,
    validate_phone_number, validate_salesforce_id, validate_email,
    sanitize_text_input
)


class ContactBase(BaseSchema):
    """Base schema for Salesforce Contact data."""
    phone: str = Field(..., description="Primary phone number")
    first_name: Optional[str] = Field(None, max_length=40, description="First name")
    last_name: Optional[str] = Field(None, max_length=80, description="Last name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    company: Optional[str] = Field(None, max_length=255, description="Company name")
    title: Optional[str] = Field(None, max_length=128, description="Job title")
    lead_source: LeadSource = Field(default=LeadSource.AI_CALLING_AGENT, description="Lead source")
    
    @validator('phone')
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    @validator('first_name', 'last_name', 'company', 'title')
    def validate_text_fields(cls, v):
        if v:
            return sanitize_text_input(v, max_length=255)
        return v


class ContactCreate(ContactBase):
    """Schema for creating a new Salesforce Contact."""
    description: Optional[str] = Field(None, max_length=32000, description="Contact description")
    
    @validator('description')
    def validate_description(cls, v):
        if v:
            return sanitize_text_input(v, max_length=32000)
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+15551234567",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "company": "Acme Corp",
                "title": "Sales Manager",
                "lead_source": "AI_Calling_Agent",
                "description": "Contact created from AI calling agent interaction"
            }
        }
    }


class ContactUpdate(BaseSchema):
    """Schema for updating an existing Salesforce Contact."""
    first_name: Optional[str] = Field(None, max_length=40)
    last_name: Optional[str] = Field(None, max_length=80)
    email: Optional[EmailStr] = None
    company: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=32000)
    
    @validator('first_name', 'last_name', 'company', 'title')
    def validate_text_fields(cls, v):
        if v:
            return sanitize_text_input(v, max_length=255)
        return v
    
    @validator('description')
    def validate_description(cls, v):
        if v:
            return sanitize_text_input(v, max_length=32000)
        return v


class ContactResponse(ContactBase):
    """Schema for Salesforce Contact API responses."""
    id: str = Field(..., description="Salesforce Contact ID")
    created_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None
    
    @validator('id')
    def validate_id(cls, v):
        return validate_salesforce_id(v)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "0031234567890AB",
                "phone": "+15551234567",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "company": "Acme Corp",
                "title": "Sales Manager",
                "lead_source": "AI_Calling_Agent",
                "created_date": "2024-01-01T12:00:00Z"
            }
        }
    }


class LeadBase(BaseSchema):
    """Base schema for Salesforce Lead data."""
    phone: str = Field(..., description="Primary phone number")
    first_name: Optional[str] = Field(None, max_length=40, description="First name")
    last_name: str = Field(..., max_length=80, description="Last name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    company: str = Field(..., max_length=255, description="Company name")
    title: Optional[str] = Field(None, max_length=128, description="Job title")
    lead_source: LeadSource = Field(default=LeadSource.AI_CALLING_AGENT, description="Lead source")
    status: str = Field(default="Open - Not Contacted", description="Lead status")
    rating: Optional[str] = Field(None, description="Lead rating (Hot/Warm/Cold)")
    
    @validator('phone')
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    @validator('first_name', 'last_name', 'company', 'title', 'status', 'rating')
    def validate_text_fields(cls, v):
        if v:
            return sanitize_text_input(v, max_length=255)
        return v


class LeadCreate(LeadBase):
    """Schema for creating a new Salesforce Lead."""
    description: Optional[str] = Field(None, max_length=32000, description="Lead description")
    qualification_score: Optional[int] = Field(None, ge=0, le=100, description="AI qualification score")
    
    @validator('description')
    def validate_description(cls, v):
        if v:
            return sanitize_text_input(v, max_length=32000)
        return v
    
    @validator('rating', pre=True)
    def set_rating_from_score(cls, v, values):
        """Set rating based on qualification score if not provided."""
        if v is None and 'qualification_score' in values:
            score = values['qualification_score']
            if score and score > 80:
                return "Hot"
            elif score and score > 60:
                return "Warm"
            else:
                return "Cold"
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+15551234567",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "company": "Acme Corp",
                "title": "Sales Manager",
                "lead_source": "AI_Calling_Agent",
                "status": "Open - Not Contacted",
                "rating": "Hot",
                "qualification_score": 85,
                "description": "Qualified lead from AI calling agent with high buying intent"
            }
        }
    }


class LeadResponse(LeadBase):
    """Schema for Salesforce Lead API responses."""
    id: str = Field(..., description="Salesforce Lead ID")
    created_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None
    qualification_score: Optional[int] = Field(None, ge=0, le=100)
    
    @validator('id')
    def validate_id(cls, v):
        return validate_salesforce_id(v)


class TaskBase(BaseSchema):
    """Base schema for Salesforce Task data."""
    who_id: str = Field(..., description="Contact or Lead ID")
    subject: str = Field(..., max_length=255, description="Task subject")
    description: Optional[str] = Field(None, max_length=32000, description="Task description")
    type: str = Field(default="Call", description="Task type")
    task_subtype: str = Field(default="Call", description="Task subtype")
    call_type: Optional[str] = Field(None, description="Call type (Inbound/Outbound)")
    priority: Priority = Field(default=Priority.NORMAL, description="Task priority")
    status: str = Field(default="Completed", description="Task status")
    activity_date: date = Field(default_factory=date.today, description="Activity date")
    
    @validator('who_id')
    def validate_who_id(cls, v):
        return validate_salesforce_id(v)
    
    @validator('subject')
    def validate_subject(cls, v):
        return sanitize_text_input(v, max_length=255)
    
    @validator('description')
    def validate_description(cls, v):
        if v:
            return sanitize_text_input(v, max_length=32000)
        return v


class TaskCreate(TaskBase):
    """Schema for creating a new Salesforce Task."""
    call_duration_seconds: Optional[int] = Field(None, ge=0, description="Call duration in seconds")
    call_outcome: Optional[str] = Field(None, description="Call outcome")
    lead_qualification_score: Optional[int] = Field(None, ge=0, le=100, description="Lead qualification score")
    
    @validator('priority', pre=True)
    def set_priority_from_score(cls, v, values):
        """Set priority based on lead qualification score if not provided."""
        if v == Priority.NORMAL and 'lead_qualification_score' in values:
            score = values['lead_qualification_score']
            if score and score > 80:
                return Priority.HIGH
            elif score and score > 60:
                return Priority.NORMAL
            else:
                return Priority.LOW
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "who_id": "0031234567890AB",
                "subject": "AI Agent Call - Qualified Lead",
                "description": "Inbound call handled by AI agent. Customer expressed interest in our services and provided contact information.",
                "type": "Call",
                "task_subtype": "Call",
                "call_type": "Inbound",
                "priority": "High",
                "status": "Completed",
                "call_duration_seconds": 300,
                "call_outcome": "qualified",
                "lead_qualification_score": 85
            }
        }
    }


class TaskResponse(TaskBase):
    """Schema for Salesforce Task API responses."""
    id: str = Field(..., description="Salesforce Task ID")
    created_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None
    
    @validator('id')
    def validate_id(cls, v):
        return validate_salesforce_id(v)


class SalesforceWebhookData(BaseSchema):
    """Schema for Salesforce webhook payload validation."""
    object_type: str = Field(..., description="Salesforce object type (Lead, Contact, etc.)")
    object_id: str = Field(..., description="Salesforce object ID")
    event_type: str = Field(..., description="Event type (created, updated, deleted)")
    data: Dict[str, Any] = Field(..., description="Object data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    
    @validator('object_id')
    def validate_object_id(cls, v):
        return validate_salesforce_id(v)
    
    @validator('object_type')
    def validate_object_type(cls, v):
        allowed_types = ['Lead', 'Contact', 'Task', 'Opportunity']
        if v not in allowed_types:
            raise ValueError(f"Object type must be one of: {allowed_types}")
        return v
    
    @validator('event_type')
    def validate_event_type(cls, v):
        allowed_events = ['created', 'updated', 'deleted']
        if v not in allowed_events:
            raise ValueError(f"Event type must be one of: {allowed_events}")
        return v


class SalesforceAuthToken(BaseSchema):
    """Schema for Salesforce authentication token."""
    access_token: str = Field(..., description="OAuth access token")
    instance_url: str = Field(..., description="Salesforce instance URL")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime = Field(..., description="Token expiration time")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.utcnow() >= self.expires_at
    
    def expires_soon(self, minutes: int = 5) -> bool:
        """Check if the token expires within the specified minutes."""
        from datetime import timedelta
        return datetime.utcnow() + timedelta(minutes=minutes) >= self.expires_at