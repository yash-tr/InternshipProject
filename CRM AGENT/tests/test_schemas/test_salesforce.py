"""
Unit tests for Salesforce schema validation.
"""
import pytest
from datetime import datetime, date
from pydantic import ValidationError

from app.schemas.salesforce import (
    ContactBase, ContactCreate, ContactUpdate, ContactResponse,
    LeadBase, LeadCreate, LeadResponse, TaskBase, TaskCreate, TaskResponse,
    SalesforceWebhookData, SalesforceAuthToken
)
from app.schemas.base import LeadSource, Priority


class TestContactBase:
    """Test ContactBase schema."""
    
    def test_valid_contact_base(self):
        """Test creating valid ContactBase."""
        data = {
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "company": "Acme Corp",
            "title": "Sales Manager",
            "lead_source": LeadSource.AI_CALLING_AGENT
        }
        
        contact = ContactBase(**data)
        
        assert contact.phone == data["phone"]
        assert contact.first_name == data["first_name"]
        assert contact.last_name == data["last_name"]
        assert contact.email == data["email"]
        assert contact.company == data["company"]
        assert contact.title == data["title"]
        assert contact.lead_source == LeadSource.AI_CALLING_AGENT
    
    def test_contact_base_phone_normalization(self):
        """Test phone number normalization."""
        data = {
            "phone": "5551234567"  # Will be normalized to +15551234567
        }
        
        contact = ContactBase(**data)
        assert contact.phone == "+15551234567"
    
    def test_contact_base_invalid_phone(self):
        """Test invalid phone number validation."""
        data = {
            "phone": "invalid"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ContactBase(**data)
        
        assert "Invalid phone number format" in str(exc_info.value)
    
    def test_contact_base_text_sanitization(self):
        """Test text field sanitization."""
        data = {
            "phone": "+15551234567",
            "first_name": "John <script>alert('xss')</script>",
            "company": "Acme Corp; DROP TABLE users;"
        }
        
        contact = ContactBase(**data)
        assert "<script>" not in contact.first_name
        assert "alert('xss')" not in contact.first_name
        assert "DROP TABLE users" not in contact.company
        assert ";" not in contact.company
    
    def test_contact_base_default_lead_source(self):
        """Test default lead source."""
        data = {
            "phone": "+15551234567"
        }
        
        contact = ContactBase(**data)
        assert contact.lead_source == LeadSource.AI_CALLING_AGENT


class TestContactCreate:
    """Test ContactCreate schema."""
    
    def test_valid_contact_create(self):
        """Test creating valid ContactCreate."""
        data = {
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "company": "Acme Corp",
            "title": "Sales Manager",
            "description": "Contact created from AI calling agent interaction"
        }
        
        contact = ContactCreate(**data)
        
        assert contact.phone == data["phone"]
        assert contact.first_name == data["first_name"]
        assert contact.description == data["description"]
    
    def test_contact_create_description_sanitization(self):
        """Test description sanitization."""
        data = {
            "phone": "+15551234567",
            "description": "Contact created <script>alert('xss')</script> from AI agent"
        }
        
        contact = ContactCreate(**data)
        assert "<script>" not in contact.description
        assert "alert('xss')" not in contact.description
    
    def test_contact_create_description_length(self):
        """Test description length validation."""
        long_description = "a" * 35000
        data = {
            "phone": "+15551234567",
            "description": long_description
        }
        
        contact = ContactCreate(**data)
        assert len(contact.description) <= 32000


class TestContactUpdate:
    """Test ContactUpdate schema."""
    
    def test_valid_contact_update(self):
        """Test creating valid ContactUpdate."""
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com",
            "company": "New Corp",
            "title": "VP Sales",
            "description": "Updated contact information"
        }
        
        update = ContactUpdate(**data)
        
        assert update.first_name == "Jane"
        assert update.last_name == "Smith"
        assert update.email == "jane.smith@example.com"
        assert update.company == "New Corp"
        assert update.title == "VP Sales"
        assert update.description == "Updated contact information"
    
    def test_contact_update_all_none(self):
        """Test ContactUpdate with all None values."""
        update = ContactUpdate()
        
        assert update.first_name is None
        assert update.last_name is None
        assert update.email is None
        assert update.company is None
        assert update.title is None
        assert update.description is None


class TestContactResponse:
    """Test ContactResponse schema."""
    
    def test_valid_contact_response(self):
        """Test creating valid ContactResponse."""
        created_date = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "id": "0031234567890AB",
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "company": "Acme Corp",
            "title": "Sales Manager",
            "lead_source": LeadSource.AI_CALLING_AGENT,
            "created_date": created_date
        }
        
        response = ContactResponse(**data)
        
        assert response.id == "0031234567890AB"
        assert response.phone == data["phone"]
        assert response.created_date == created_date
    
    def test_contact_response_invalid_id(self):
        """Test invalid Salesforce ID validation."""
        data = {
            "id": "invalid",
            "phone": "+15551234567"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ContactResponse(**data)
        
        assert "Invalid Salesforce ID format" in str(exc_info.value)


class TestLeadBase:
    """Test LeadBase schema."""
    
    def test_valid_lead_base(self):
        """Test creating valid LeadBase."""
        data = {
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "company": "Acme Corp",
            "title": "Sales Manager",
            "lead_source": LeadSource.AI_CALLING_AGENT,
            "status": "Open - Not Contacted",
            "rating": "Hot"
        }
        
        lead = LeadBase(**data)
        
        assert lead.phone == data["phone"]
        assert lead.first_name == data["first_name"]
        assert lead.last_name == data["last_name"]
        assert lead.company == data["company"]
        assert lead.status == "Open - Not Contacted"
        assert lead.rating == "Hot"
    
    def test_lead_base_required_fields(self):
        """Test required fields validation."""
        # Missing last_name
        with pytest.raises(ValidationError):
            LeadBase(phone="+15551234567", company="Acme Corp")
        
        # Missing company
        with pytest.raises(ValidationError):
            LeadBase(phone="+15551234567", last_name="Doe")
    
    def test_lead_base_default_values(self):
        """Test default values."""
        data = {
            "phone": "+15551234567",
            "last_name": "Doe",
            "company": "Acme Corp"
        }
        
        lead = LeadBase(**data)
        assert lead.lead_source == LeadSource.AI_CALLING_AGENT
        assert lead.status == "Open - Not Contacted"


class TestLeadCreate:
    """Test LeadCreate schema."""
    
    def test_valid_lead_create(self):
        """Test creating valid LeadCreate."""
        data = {
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "company": "Acme Corp",
            "title": "Sales Manager",
            "description": "Qualified lead from AI calling agent",
            "qualification_score": 85
        }
        
        lead = LeadCreate(**data)
        
        assert lead.phone == data["phone"]
        assert lead.description == data["description"]
        assert lead.qualification_score == 85
    
    def test_lead_create_rating_from_score(self):
        """Test automatic rating assignment from qualification score."""
        # High score -> Hot rating
        data = {
            "phone": "+15551234567",
            "last_name": "Doe",
            "company": "Acme Corp",
            "qualification_score": 85
        }
        
        lead = LeadCreate(**data)
        assert lead.rating == "Hot"
        
        # Medium score -> Warm rating
        data["qualification_score"] = 70
        lead = LeadCreate(**data)
        assert lead.rating == "Warm"
        
        # Low score -> Cold rating
        data["qualification_score"] = 50
        lead = LeadCreate(**data)
        assert lead.rating == "Cold"
    
    def test_lead_create_explicit_rating_override(self):
        """Test explicit rating overrides score-based rating."""
        data = {
            "phone": "+15551234567",
            "last_name": "Doe",
            "company": "Acme Corp",
            "qualification_score": 85,
            "rating": "Warm"  # Explicit override
        }
        
        lead = LeadCreate(**data)
        assert lead.rating == "Warm"  # Should use explicit value
    
    def test_lead_create_qualification_score_bounds(self):
        """Test qualification score validation bounds."""
        base_data = {
            "phone": "+15551234567",
            "last_name": "Doe",
            "company": "Acme Corp"
        }
        
        # Test valid bounds
        lead = LeadCreate(**base_data, qualification_score=0)
        assert lead.qualification_score == 0
        
        lead = LeadCreate(**base_data, qualification_score=100)
        assert lead.qualification_score == 100
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            LeadCreate(**base_data, qualification_score=-1)
        
        with pytest.raises(ValidationError):
            LeadCreate(**base_data, qualification_score=101)


class TestLeadResponse:
    """Test LeadResponse schema."""
    
    def test_valid_lead_response(self):
        """Test creating valid LeadResponse."""
        created_date = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "id": "00Q1234567890AB",
            "phone": "+15551234567",
            "first_name": "John",
            "last_name": "Doe",
            "company": "Acme Corp",
            "lead_source": LeadSource.AI_CALLING_AGENT,
            "status": "Open - Not Contacted",
            "rating": "Hot",
            "qualification_score": 85,
            "created_date": created_date
        }
        
        response = LeadResponse(**data)
        
        assert response.id == "00Q1234567890AB"
        assert response.qualification_score == 85
        assert response.created_date == created_date


class TestTaskBase:
    """Test TaskBase schema."""
    
    def test_valid_task_base(self):
        """Test creating valid TaskBase."""
        activity_date = date(2024, 1, 1)
        data = {
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call - Qualified Lead",
            "description": "Inbound call handled by AI agent",
            "type": "Call",
            "task_subtype": "Call",
            "call_type": "Inbound",
            "priority": Priority.HIGH,
            "status": "Completed",
            "activity_date": activity_date
        }
        
        task = TaskBase(**data)
        
        assert task.who_id == data["who_id"]
        assert task.subject == data["subject"]
        assert task.description == data["description"]
        assert task.type == "Call"
        assert task.task_subtype == "Call"
        assert task.call_type == "Inbound"
        assert task.priority == Priority.HIGH
        assert task.status == "Completed"
        assert task.activity_date == activity_date
    
    def test_task_base_invalid_who_id(self):
        """Test invalid who_id validation."""
        data = {
            "who_id": "invalid",
            "subject": "Test Task"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            TaskBase(**data)
        
        assert "Invalid Salesforce ID format" in str(exc_info.value)
    
    def test_task_base_subject_sanitization(self):
        """Test subject sanitization."""
        data = {
            "who_id": "0031234567890AB",
            "subject": "AI Call <script>alert('xss')</script> Result"
        }
        
        task = TaskBase(**data)
        assert "<script>" not in task.subject
        assert "alert('xss')" not in task.subject
    
    def test_task_base_default_values(self):
        """Test default values."""
        data = {
            "who_id": "0031234567890AB",
            "subject": "Test Task"
        }
        
        task = TaskBase(**data)
        assert task.type == "Call"
        assert task.task_subtype == "Call"
        assert task.priority == Priority.NORMAL
        assert task.status == "Completed"
        assert task.activity_date == date.today()


class TestTaskCreate:
    """Test TaskCreate schema."""
    
    def test_valid_task_create(self):
        """Test creating valid TaskCreate."""
        data = {
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call - Qualified Lead",
            "description": "Customer expressed interest in our services",
            "call_duration_seconds": 300,
            "call_outcome": "qualified",
            "lead_qualification_score": 85
        }
        
        task = TaskCreate(**data)
        
        assert task.who_id == data["who_id"]
        assert task.subject == data["subject"]
        assert task.call_duration_seconds == 300
        assert task.call_outcome == "qualified"
        assert task.lead_qualification_score == 85
    
    def test_task_create_priority_from_score(self):
        """Test automatic priority assignment from lead qualification score."""
        base_data = {
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call"
        }
        
        # High score -> High priority
        task = TaskCreate(**base_data, lead_qualification_score=85)
        assert task.priority == Priority.HIGH
        
        # Medium score -> Normal priority
        task = TaskCreate(**base_data, lead_qualification_score=70)
        assert task.priority == Priority.NORMAL
        
        # Low score -> Low priority
        task = TaskCreate(**base_data, lead_qualification_score=50)
        assert task.priority == Priority.LOW
    
    def test_task_create_explicit_priority_override(self):
        """Test explicit priority overrides score-based priority."""
        data = {
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call",
            "lead_qualification_score": 85,
            "priority": Priority.LOW  # Explicit override
        }
        
        task = TaskCreate(**data)
        assert task.priority == Priority.LOW  # Should use explicit value
    
    def test_task_create_negative_duration(self):
        """Test negative duration validation."""
        data = {
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call",
            "call_duration_seconds": -1
        }
        
        with pytest.raises(ValidationError):
            TaskCreate(**data)


class TestTaskResponse:
    """Test TaskResponse schema."""
    
    def test_valid_task_response(self):
        """Test creating valid TaskResponse."""
        created_date = datetime(2024, 1, 1, 12, 0, 0)
        activity_date = date(2024, 1, 1)
        data = {
            "id": "00T1234567890AB",
            "who_id": "0031234567890AB",
            "subject": "AI Agent Call - Qualified Lead",
            "description": "Customer expressed interest",
            "type": "Call",
            "priority": Priority.HIGH,
            "status": "Completed",
            "activity_date": activity_date,
            "created_date": created_date
        }
        
        response = TaskResponse(**data)
        
        assert response.id == "00T1234567890AB"
        assert response.who_id == data["who_id"]
        assert response.created_date == created_date


class TestSalesforceWebhookData:
    """Test SalesforceWebhookData schema."""
    
    def test_valid_webhook_data(self):
        """Test creating valid SalesforceWebhookData."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "object_type": "Lead",
            "object_id": "00Q1234567890AB",
            "event_type": "created",
            "data": {
                "Id": "00Q1234567890AB",
                "FirstName": "John",
                "LastName": "Doe",
                "Company": "Acme Corp"
            },
            "timestamp": timestamp
        }
        
        webhook = SalesforceWebhookData(**data)
        
        assert webhook.object_type == "Lead"
        assert webhook.object_id == "00Q1234567890AB"
        assert webhook.event_type == "created"
        assert webhook.data["Id"] == "00Q1234567890AB"
        assert webhook.timestamp == timestamp
    
    def test_webhook_data_invalid_object_type(self):
        """Test invalid object type validation."""
        data = {
            "object_type": "InvalidObject",
            "object_id": "00Q1234567890AB",
            "event_type": "created",
            "data": {}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SalesforceWebhookData(**data)
        
        assert "Object type must be one of" in str(exc_info.value)
    
    def test_webhook_data_invalid_event_type(self):
        """Test invalid event type validation."""
        data = {
            "object_type": "Lead",
            "object_id": "00Q1234567890AB",
            "event_type": "invalid_event",
            "data": {}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SalesforceWebhookData(**data)
        
        assert "Event type must be one of" in str(exc_info.value)


class TestSalesforceAuthToken:
    """Test SalesforceAuthToken schema."""
    
    def test_valid_auth_token(self):
        """Test creating valid SalesforceAuthToken."""
        expires_at = datetime(2024, 1, 1, 13, 0, 0)
        data = {
            "access_token": "00D1234567890AB!token",
            "instance_url": "https://example.salesforce.com",
            "token_type": "Bearer",
            "expires_at": expires_at,
            "refresh_token": "refresh_token_value"
        }
        
        token = SalesforceAuthToken(**data)
        
        assert token.access_token == data["access_token"]
        assert token.instance_url == data["instance_url"]
        assert token.token_type == "Bearer"
        assert token.expires_at == expires_at
        assert token.refresh_token == data["refresh_token"]
    
    def test_auth_token_is_expired(self):
        """Test is_expired method."""
        # Token expired 1 hour ago
        past_time = datetime(2024, 1, 1, 11, 0, 0)
        token = SalesforceAuthToken(
            access_token="token",
            instance_url="https://example.salesforce.com",
            expires_at=past_time
        )
        
        # Mock current time to be after expiration
        import unittest.mock
        with unittest.mock.patch('app.schemas.salesforce.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
            assert token.is_expired() is True
    
    def test_auth_token_expires_soon(self):
        """Test expires_soon method."""
        # Token expires in 3 minutes
        future_time = datetime(2024, 1, 1, 12, 3, 0)
        token = SalesforceAuthToken(
            access_token="token",
            instance_url="https://example.salesforce.com",
            expires_at=future_time
        )
        
        # Mock current time
        import unittest.mock
        with unittest.mock.patch('app.schemas.salesforce.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
            # Should expire soon (within 5 minutes)
            assert token.expires_soon() is True
            # Should not expire soon (within 2 minutes)
            assert token.expires_soon(minutes=2) is False