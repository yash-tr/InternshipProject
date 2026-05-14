"""
Unit tests for base schema validation and utilities.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.base import (
    BaseSchema, TimestampMixin, CallStatus, CallOutcome, ConversationRole,
    LeadSource, Priority, validate_phone_number, validate_email,
    validate_call_sid, validate_salesforce_id, sanitize_text_input
)


class TestValidationFunctions:
    """Test validation utility functions."""
    
    def test_validate_phone_number_valid(self):
        """Test phone number validation with valid inputs."""
        # Test various valid formats
        assert validate_phone_number("+15551234567") == "+15551234567"
        assert validate_phone_number("5551234567") == "+15551234567"
        assert validate_phone_number("15551234567") == "+15551234567"
        assert validate_phone_number("(555) 123-4567") == "+15551234567"
        assert validate_phone_number("555-123-4567") == "+15551234567"
    
    def test_validate_phone_number_invalid(self):
        """Test phone number validation with invalid inputs."""
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_phone_number("")
        
        with pytest.raises(ValueError, match="Invalid phone number format"):
            validate_phone_number("123")
        
        with pytest.raises(ValueError, match="Invalid phone number format"):
            validate_phone_number("1234567890123")
        
        with pytest.raises(ValueError, match="Invalid phone number format"):
            validate_phone_number("invalid")
    
    def test_validate_email_valid(self):
        """Test email validation with valid inputs."""
        assert validate_email("test@example.com") == "test@example.com"
        assert validate_email("USER@EXAMPLE.COM") == "user@example.com"
        assert validate_email("  test@example.com  ") == "test@example.com"
        assert validate_email("test.email+tag@example.co.uk") == "test.email+tag@example.co.uk"
    
    def test_validate_email_invalid(self):
        """Test email validation with invalid inputs."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            validate_email("")
        
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email("invalid")
        
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email("@example.com")
        
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email("test@")
    
    def test_validate_call_sid_valid(self):
        """Test Call SID validation with valid inputs."""
        valid_sid = "CA1234567890abcdef1234567890abcdef"
        assert validate_call_sid(valid_sid) == valid_sid
    
    def test_validate_call_sid_invalid(self):
        """Test Call SID validation with invalid inputs."""
        with pytest.raises(ValueError, match="Call SID cannot be empty"):
            validate_call_sid("")
        
        with pytest.raises(ValueError, match="Invalid Call SID format"):
            validate_call_sid("invalid")
        
        with pytest.raises(ValueError, match="Invalid Call SID format"):
            validate_call_sid("CA123")  # Too short
    
    def test_validate_salesforce_id_valid(self):
        """Test Salesforce ID validation with valid inputs."""
        valid_15 = "0031234567890AB"
        valid_18 = "0031234567890ABCDE"
        
        assert validate_salesforce_id(valid_15) == valid_15
        assert validate_salesforce_id(valid_18) == valid_18
    
    def test_validate_salesforce_id_invalid(self):
        """Test Salesforce ID validation with invalid inputs."""
        with pytest.raises(ValueError, match="Salesforce ID cannot be empty"):
            validate_salesforce_id("")
        
        with pytest.raises(ValueError, match="Invalid Salesforce ID format"):
            validate_salesforce_id("123")  # Too short
        
        with pytest.raises(ValueError, match="Invalid Salesforce ID format"):
            validate_salesforce_id("0031234567890ABCDEF")  # Too long
    
    def test_sanitize_text_input(self):
        """Test text input sanitization."""
        # Test normal text
        assert sanitize_text_input("Hello World") == "Hello World"
        
        # Test dangerous characters removal
        assert sanitize_text_input("Hello <script>alert('xss')</script>") == "Hello scriptalert('xss')/script"
        assert sanitize_text_input('Hello "World"') == "Hello World"
        assert sanitize_text_input("Hello; DROP TABLE users;") == "Hello DROP TABLE users"
        
        # Test length truncation
        long_text = "a" * 2000
        assert len(sanitize_text_input(long_text, max_length=100)) == 100
        
        # Test empty input
        assert sanitize_text_input("") == ""
        assert sanitize_text_input(None) == ""


class TestEnums:
    """Test enum definitions."""
    
    def test_call_status_enum(self):
        """Test CallStatus enum values."""
        assert CallStatus.INITIATED == "initiated"
        assert CallStatus.IN_PROGRESS == "in-progress"
        assert CallStatus.COMPLETED == "completed"
        assert CallStatus.FAILED == "failed"
        assert CallStatus.NO_ANSWER == "no-answer"
        assert CallStatus.BUSY == "busy"
    
    def test_call_outcome_enum(self):
        """Test CallOutcome enum values."""
        assert CallOutcome.QUALIFIED == "qualified"
        assert CallOutcome.UNQUALIFIED == "unqualified"
        assert CallOutcome.CALLBACK_REQUESTED == "callback_requested"
        assert CallOutcome.TRANSFERRED_TO_HUMAN == "transferred_to_human"
        assert CallOutcome.TECHNICAL_ISSUE == "technical_issue"
        assert CallOutcome.HUNG_UP == "hung_up"
    
    def test_conversation_role_enum(self):
        """Test ConversationRole enum values."""
        assert ConversationRole.USER == "user"
        assert ConversationRole.ASSISTANT == "assistant"
        assert ConversationRole.SYSTEM == "system"
    
    def test_lead_source_enum(self):
        """Test LeadSource enum values."""
        assert LeadSource.AI_CALLING_AGENT == "AI_Calling_Agent"
        assert LeadSource.INBOUND_CALL == "Inbound_Call"
        assert LeadSource.OUTBOUND_CALL == "Outbound_Call"
        assert LeadSource.WEB_FORM == "Web_Form"
        assert LeadSource.REFERRAL == "Referral"
    
    def test_priority_enum(self):
        """Test Priority enum values."""
        assert Priority.LOW == "Low"
        assert Priority.NORMAL == "Normal"
        assert Priority.HIGH == "High"
        assert Priority.URGENT == "Urgent"


class TestTimestampMixin:
    """Test TimestampMixin functionality."""
    
    def test_timestamp_mixin_creation(self):
        """Test TimestampMixin creates timestamps correctly."""
        
        class TestModel(TimestampMixin):
            name: str
        
        model = TestModel(name="test")
        
        assert isinstance(model.created_at, datetime)
        assert model.updated_at is None
    
    def test_timestamp_mixin_with_values(self):
        """Test TimestampMixin with provided values."""
        
        class TestModel(TimestampMixin):
            name: str
        
        created_time = datetime(2024, 1, 1, 12, 0, 0)
        updated_time = datetime(2024, 1, 2, 12, 0, 0)
        
        model = TestModel(
            name="test",
            created_at=created_time,
            updated_at=updated_time
        )
        
        assert model.created_at == created_time
        assert model.updated_at == updated_time


class TestBaseSchema:
    """Test BaseSchema configuration."""
    
    def test_base_schema_config(self):
        """Test BaseSchema configuration settings."""
        
        class TestModel(BaseSchema):
            status: CallStatus
            created_at: datetime
        
        # Test enum value usage
        model = TestModel(
            status=CallStatus.COMPLETED,
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Test serialization
        data = model.dict()
        assert data['status'] == "completed"  # Enum value, not enum object
        
        # Test JSON encoding
        json_str = model.json()
        assert '"status":"completed"' in json_str
        assert '"created_at":"2024-01-01T12:00:00"' in json_str
    
    def test_base_schema_validation_assignment(self):
        """Test BaseSchema validates on assignment."""
        
        class TestModel(BaseSchema):
            phone: str
            
            @validator('phone')
            def validate_phone(cls, v):
                return validate_phone_number(v)
        
        model = TestModel(phone="5551234567")
        assert model.phone == "+15551234567"
        
        # Test validation on assignment
        with pytest.raises(ValidationError):
            model.phone = "invalid"