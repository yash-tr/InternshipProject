"""
Unit tests for call session schema validation.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.call_session import (
    CallSessionBase, CallSessionCreate, CallSessionUpdate, 
    CallSessionResponse, CallMetricsBase, CallMetricsCreate,
    CallMetricsResponse, CallSessionWithMetrics
)
from app.schemas.base import CallOutcome


class TestCallSessionBase:
    """Test CallSessionBase schema."""
    
    def test_valid_call_session_base(self):
        """Test creating valid CallSessionBase."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "contact_id": "0031234567890AB",
            "lead_score": 75,
            "call_outcome": CallOutcome.QUALIFIED
        }
        
        session = CallSessionBase(**data)
        
        assert session.call_sid == data["call_sid"]
        assert session.caller_phone == data["caller_phone"]
        assert session.contact_id == data["contact_id"]
        assert session.lead_score == data["lead_score"]
        assert session.call_outcome == CallOutcome.QUALIFIED
    
    def test_call_session_base_phone_validation(self):
        """Test phone number validation in CallSessionBase."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "5551234567",  # Will be normalized
        }
        
        session = CallSessionBase(**data)
        assert session.caller_phone == "+15551234567"
    
    def test_call_session_base_invalid_call_sid(self):
        """Test invalid Call SID validation."""
        data = {
            "call_sid": "invalid",
            "caller_phone": "+15551234567",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CallSessionBase(**data)
        
        assert "Invalid Call SID format" in str(exc_info.value)
    
    def test_call_session_base_invalid_phone(self):
        """Test invalid phone number validation."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "invalid",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CallSessionBase(**data)
        
        assert "Invalid phone number format" in str(exc_info.value)
    
    def test_call_session_base_invalid_contact_id(self):
        """Test invalid Salesforce Contact ID validation."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "contact_id": "invalid"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CallSessionBase(**data)
        
        assert "Invalid Salesforce ID format" in str(exc_info.value)
    
    def test_call_session_base_lead_score_bounds(self):
        """Test lead score validation bounds."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
        }
        
        # Test valid bounds
        session = CallSessionBase(**data, lead_score=0)
        assert session.lead_score == 0
        
        session = CallSessionBase(**data, lead_score=100)
        assert session.lead_score == 100
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            CallSessionBase(**data, lead_score=-1)
        
        with pytest.raises(ValidationError):
            CallSessionBase(**data, lead_score=101)


class TestCallSessionCreate:
    """Test CallSessionCreate schema."""
    
    def test_valid_call_session_create(self):
        """Test creating valid CallSessionCreate."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "contact_id": "0031234567890AB",
            "lead_score": 75
        }
        
        session = CallSessionCreate(**data)
        
        assert session.call_sid == data["call_sid"]
        assert session.caller_phone == data["caller_phone"]
        assert session.contact_id == data["contact_id"]
        assert session.lead_score == data["lead_score"]
        assert isinstance(session.start_time, datetime)
    
    def test_call_session_create_with_start_time(self):
        """Test CallSessionCreate with provided start_time."""
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "start_time": start_time
        }
        
        session = CallSessionCreate(**data)
        assert session.start_time == start_time


class TestCallSessionUpdate:
    """Test CallSessionUpdate schema."""
    
    def test_valid_call_session_update(self):
        """Test creating valid CallSessionUpdate."""
        end_time = datetime(2024, 1, 1, 12, 30, 0)
        data = {
            "end_time": end_time,
            "duration_seconds": 1800,
            "lead_score": 85,
            "call_outcome": CallOutcome.QUALIFIED,
            "conversation_summary": "Customer interested in our services",
            "extracted_data": {"name": "John Doe", "company": "Acme Corp"}
        }
        
        update = CallSessionUpdate(**data)
        
        assert update.end_time == end_time
        assert update.duration_seconds == 1800
        assert update.lead_score == 85
        assert update.call_outcome == CallOutcome.QUALIFIED
        assert update.conversation_summary == "Customer interested in our services"
        assert update.extracted_data == {"name": "John Doe", "company": "Acme Corp"}
    
    def test_call_session_update_conversation_summary_sanitization(self):
        """Test conversation summary sanitization."""
        data = {
            "conversation_summary": "Customer said <script>alert('xss')</script> hello"
        }
        
        update = CallSessionUpdate(**data)
        assert "<script>" not in update.conversation_summary
        assert "alert('xss')" not in update.conversation_summary
    
    def test_call_session_update_conversation_summary_length(self):
        """Test conversation summary length validation."""
        long_summary = "a" * 3000
        data = {
            "conversation_summary": long_summary
        }
        
        update = CallSessionUpdate(**data)
        assert len(update.conversation_summary) <= 2000
    
    def test_call_session_update_invalid_duration(self):
        """Test invalid duration validation."""
        data = {
            "duration_seconds": -1
        }
        
        with pytest.raises(ValidationError):
            CallSessionUpdate(**data)
    
    def test_call_session_update_invalid_extracted_data(self):
        """Test invalid extracted_data validation."""
        data = {
            "extracted_data": "not a dict"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CallSessionUpdate(**data)
        
        assert "extracted_data must be a dictionary" in str(exc_info.value)


class TestCallSessionResponse:
    """Test CallSessionResponse schema."""
    
    def test_valid_call_session_response(self):
        """Test creating valid CallSessionResponse."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 30, 0)
        
        data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "contact_id": "0031234567890AB",
            "lead_score": 75,
            "call_outcome": CallOutcome.QUALIFIED,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": 1800,
            "conversation_summary": "Customer interested in services",
            "extracted_data": {"name": "John Doe"},
            "created_at": created_at
        }
        
        response = CallSessionResponse(**data)
        
        assert response.id == 1
        assert response.call_sid == data["call_sid"]
        assert response.caller_phone == data["caller_phone"]
        assert response.start_time == start_time
        assert response.end_time == end_time
        assert response.duration_seconds == 1800
        assert response.created_at == created_at


class TestCallMetrics:
    """Test CallMetrics schemas."""
    
    def test_valid_call_metrics_base(self):
        """Test creating valid CallMetricsBase."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "avg_response_time_ms": 1500.5,
            "total_tokens_used": 250,
            "transcription_accuracy": 0.95,
            "audio_quality_score": 0.8,
            "conversation_flow_score": 0.9,
            "lead_qualification_confidence": 0.85,
            "information_extraction_completeness": 0.7
        }
        
        metrics = CallMetricsBase(**data)
        
        assert metrics.call_sid == data["call_sid"]
        assert metrics.avg_response_time_ms == 1500.5
        assert metrics.total_tokens_used == 250
        assert metrics.transcription_accuracy == 0.95
        assert metrics.audio_quality_score == 0.8
        assert metrics.conversation_flow_score == 0.9
        assert metrics.lead_qualification_confidence == 0.85
        assert metrics.information_extraction_completeness == 0.7
    
    def test_call_metrics_validation_bounds(self):
        """Test CallMetrics validation bounds."""
        base_data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef"
        }
        
        # Test valid bounds
        metrics = CallMetricsBase(**base_data, transcription_accuracy=0.0)
        assert metrics.transcription_accuracy == 0.0
        
        metrics = CallMetricsBase(**base_data, transcription_accuracy=1.0)
        assert metrics.transcription_accuracy == 1.0
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            CallMetricsBase(**base_data, transcription_accuracy=-0.1)
        
        with pytest.raises(ValidationError):
            CallMetricsBase(**base_data, transcription_accuracy=1.1)
        
        with pytest.raises(ValidationError):
            CallMetricsBase(**base_data, avg_response_time_ms=-1)
        
        with pytest.raises(ValidationError):
            CallMetricsBase(**base_data, total_tokens_used=-1)
    
    def test_call_metrics_create(self):
        """Test CallMetricsCreate schema."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "avg_response_time_ms": 1500.5,
            "total_tokens_used": 250
        }
        
        metrics = CallMetricsCreate(**data)
        assert metrics.call_sid == data["call_sid"]
        assert metrics.avg_response_time_ms == 1500.5
        assert metrics.total_tokens_used == 250
    
    def test_call_metrics_response(self):
        """Test CallMetricsResponse schema."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "avg_response_time_ms": 1500.5,
            "total_tokens_used": 250,
            "created_at": created_at
        }
        
        response = CallMetricsResponse(**data)
        assert response.id == 1
        assert response.call_sid == data["call_sid"]
        assert response.created_at == created_at


class TestCallSessionWithMetrics:
    """Test CallSessionWithMetrics schema."""
    
    def test_call_session_with_metrics(self):
        """Test CallSessionWithMetrics schema."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        
        session_data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "caller_phone": "+15551234567",
            "lead_score": 75,
            "start_time": start_time,
            "created_at": created_at
        }
        
        metrics_data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "avg_response_time_ms": 1500.5,
            "created_at": created_at
        }
        
        from app.schemas.call_session import CallMetricsResponse
        metrics = CallMetricsResponse(**metrics_data)
        
        session_with_metrics = CallSessionWithMetrics(
            **session_data,
            metrics=metrics,
            conversation_turns=[]
        )
        
        assert session_with_metrics.id == 1
        assert session_with_metrics.metrics is not None
        assert session_with_metrics.metrics.avg_response_time_ms == 1500.5
        assert session_with_metrics.conversation_turns == []