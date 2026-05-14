"""
Unit tests for Twilio service.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request, HTTPException

from app.services.twilio_service import TwilioService, twilio_service


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client."""
    with patch('app.services.twilio_service.Client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_request():
    """Mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.url = "https://example.com/webhook"
    request.headers = {'X-Twilio-Signature': 'valid_signature'}
    request._form_data = {
        'From': '+15551234567',
        'CallSid': 'CA1234567890abcdef1234567890abcdef'
    }
    return request


class TestTwilioService:
    """Test Twilio service functionality."""
    
    def test_init(self, mock_twilio_client):
        """Test service initialization."""
        service = TwilioService()
        
        assert service.client is not None
        assert service.validator is not None
        assert service.settings is not None
    
    @patch('app.services.twilio_service.RequestValidator')
    def test_validate_webhook_signature_valid(self, mock_validator, mock_request):
        """Test valid webhook signature validation."""
        mock_validator.return_value.validate.return_value = True
        
        service = TwilioService()
        result = service.validate_webhook_signature(mock_request)
        
        assert result is True
        mock_validator.return_value.validate.assert_called_once()
    
    @patch('app.services.twilio_service.RequestValidator')
    def test_validate_webhook_signature_invalid(self, mock_validator, mock_request):
        """Test invalid webhook signature validation."""
        mock_validator.return_value.validate.return_value = False
        
        service = TwilioService()
        result = service.validate_webhook_signature(mock_request)
        
        assert result is False
    
    @patch('app.services.twilio_service.RequestValidator')
    def test_validate_webhook_signature_missing_header(self, mock_validator):
        """Test webhook validation with missing signature header."""
        request = MagicMock(spec=Request)
        request.headers = {}  # No signature header
        
        service = TwilioService()
        result = service.validate_webhook_signature(request)
        
        assert result is False
    
    @patch('app.services.twilio_service.RequestValidator')
    def test_validate_webhook_signature_exception(self, mock_validator, mock_request):
        """Test webhook validation with exception."""
        mock_validator.return_value.validate.side_effect = Exception("Validation error")
        
        service = TwilioService()
        result = service.validate_webhook_signature(mock_request)
        
        assert result is False
    
    def test_create_greeting_response(self):
        """Test greeting TwiML response generation."""
        service = TwilioService()
        response = service.create_greeting_response("+15551234567")
        
        assert "<?xml version=" in response
        assert "<Response>" in response
        assert "<Gather" in response
        assert 'input="speech"' in response
        assert 'action="/api/v1/webhooks/twilio/conversation"' in response
        assert "Hello!" in response or "Thank you" in response
        assert "<Hangup" in response  # Fallback hangup
    
    def test_create_conversation_response_continue(self):
        """Test conversation TwiML for continuing conversation."""
        service = TwilioService()
        response = service.create_conversation_response(
            user_speech="Hello there",
            ai_response="How can I help you today?",
            should_end_call=False,
            gather_timeout=15
        )
        
        assert "<Response>" in response
        assert "<Gather" in response
        assert "How can I help you today?" in response
        assert "timeout=15" in response
        assert response.count("<Hangup/>") >= 1  # At least fallback hangup
    
    def test_create_conversation_response_end_call(self):
        """Test conversation TwiML for ending call."""
        service = TwilioService()
        response = service.create_conversation_response(
            user_speech="Goodbye",
            ai_response="Thank you for calling!",
            should_end_call=True
        )
        
        assert "<Response>" in response
        assert "Thank you for calling!" in response
        assert "Have a great day!" in response
        assert "<Hangup/>" in response
        assert "<Gather" not in response  # No gather when ending call
    
    def test_create_recording_response(self):
        """Test recording TwiML response generation."""
        service = TwilioService()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        response = service.create_recording_response(call_sid)
        
        assert "<Response>" in response
        assert "<Record" in response
        assert f"action='/api/v1/webhooks/twilio/recording/{call_sid}'" in response
        assert "transcribe=True" in response
        assert "max_length=60" in response
        assert "<Hangup/>" in response
    
    def test_create_error_response_with_message(self):
        """Test error TwiML with custom message."""
        service = TwilioService()
        response = service.create_error_response("Custom error occurred")
        
        assert "<Response>" in response
        assert "<Say" in response
        assert "Custom error occurred" in response
        assert "technical difficulties" in response
        assert "<Hangup/>" in response
    
    def test_create_error_response_default(self):
        """Test error TwiML with default message."""
        service = TwilioService()
        response = service.create_error_response()
        
        assert "<Response>" in response
        assert "<Say" in response
        assert "technical difficulties" in response
        assert "try calling back" in response
        assert "<Hangup/>" in response
    
    def test_create_transfer_response(self):
        """Test transfer TwiML response generation."""
        service = TwilioService()
        response = service.create_transfer_response(
            transfer_number="+15559876543",
            reason="speak with a specialist"
        )
        
        assert "<Response>" in response
        assert "<Say" in response
        assert "speak with a specialist" in response
        assert "transfer you" in response
        assert "<Dial" in response
        assert "+15559876543" in response
        assert "timeout=30" in response
        assert "<Hangup/>" in response  # Fallback hangup
    
    def test_create_transfer_response_no_reason(self):
        """Test transfer TwiML without reason."""
        service = TwilioService()
        response = service.create_transfer_response("+15559876543")
        
        assert "<Response>" in response
        assert "transfer you" in response
        assert "+15559876543" in response
    
    @pytest.mark.asyncio
    async def test_initiate_outbound_call_success(self, mock_twilio_client):
        """Test successful outbound call initiation."""
        # Mock call object
        mock_call = MagicMock()
        mock_call.sid = "CA1234567890abcdef1234567890abcdef"
        mock_call.status = "queued"
        
        mock_twilio_client.return_value.calls.create.return_value = mock_call
        
        service = TwilioService()
        result = await service.initiate_outbound_call(
            to_number="+15551234567",
            webhook_url="https://example.com/webhook"
        )
        
        assert result['call_sid'] == "CA1234567890abcdef1234567890abcdef"
        assert result['to_number'] == "+15551234567"
        assert result['status'] == "queued"
        assert result['direction'] == "outbound"
        
        mock_twilio_client.return_value.calls.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initiate_outbound_call_with_caller_id(self, mock_twilio_client):
        """Test outbound call with custom caller ID."""
        mock_call = MagicMock()
        mock_call.sid = "CA1234567890abcdef1234567890abcdef"
        mock_call.status = "queued"
        
        mock_twilio_client.return_value.calls.create.return_value = mock_call
        
        service = TwilioService()
        await service.initiate_outbound_call(
            to_number="+15551234567",
            webhook_url="https://example.com/webhook",
            caller_id="+15559876543"
        )
        
        call_args = mock_twilio_client.return_value.calls.create.call_args[1]
        assert call_args['from_'] == "+15559876543"
    
    @pytest.mark.asyncio
    async def test_initiate_outbound_call_failure(self, mock_twilio_client):
        """Test outbound call initiation failure."""
        mock_twilio_client.return_value.calls.create.side_effect = Exception("API Error")
        
        service = TwilioService()
        
        with pytest.raises(HTTPException) as exc_info:
            await service.initiate_outbound_call(
                to_number="+15551234567",
                webhook_url="https://example.com/webhook"
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to initiate call" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_call_details_success(self, mock_twilio_client):
        """Test successful call details retrieval."""
        # Mock call object
        mock_call = MagicMock()
        mock_call.sid = "CA1234567890abcdef1234567890abcdef"
        mock_call.from_ = "+15551234567"
        mock_call.to = "+15559876543"
        mock_call.status = "completed"
        mock_call.direction = "inbound"
        mock_call.duration = 120
        mock_call.start_time = "2024-01-01T12:00:00Z"
        mock_call.end_time = "2024-01-01T12:02:00Z"
        mock_call.price = "-0.015"
        mock_call.price_unit = "USD"
        
        mock_twilio_client.return_value.calls.return_value.fetch.return_value = mock_call
        
        service = TwilioService()
        result = await service.get_call_details("CA1234567890abcdef1234567890abcdef")
        
        assert result['call_sid'] == "CA1234567890abcdef1234567890abcdef"
        assert result['from_number'] == "+15551234567"
        assert result['to_number'] == "+15559876543"
        assert result['status'] == "completed"
        assert result['duration'] == 120
    
    @pytest.mark.asyncio
    async def test_get_call_details_failure(self, mock_twilio_client):
        """Test call details retrieval failure."""
        mock_twilio_client.return_value.calls.return_value.fetch.side_effect = Exception("API Error")
        
        service = TwilioService()
        result = await service.get_call_details("CA1234567890abcdef1234567890abcdef")
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_get_call_recordings_success(self, mock_twilio_client):
        """Test successful call recordings retrieval."""
        # Mock recording objects
        mock_recording1 = MagicMock()
        mock_recording1.sid = "RE1234567890abcdef1234567890abcdef"
        mock_recording1.call_sid = "CA1234567890abcdef1234567890abcdef"
        mock_recording1.duration = 120
        mock_recording1.date_created = "2024-01-01T12:00:00Z"
        mock_recording1.uri = "/2010-04-01/Accounts/AC123/Recordings/RE123.json"
        
        mock_twilio_client.return_value.recordings.list.return_value = [mock_recording1]
        
        service = TwilioService()
        result = await service.get_call_recordings("CA1234567890abcdef1234567890abcdef")
        
        assert len(result) == 1
        assert result[0]['recording_sid'] == "RE1234567890abcdef1234567890abcdef"
        assert result[0]['call_sid'] == "CA1234567890abcdef1234567890abcdef"
        assert result[0]['duration'] == 120
        assert "RE123.mp3" in result[0]['media_url']
    
    @pytest.mark.asyncio
    async def test_get_call_recordings_failure(self, mock_twilio_client):
        """Test call recordings retrieval failure."""
        mock_twilio_client.return_value.recordings.list.side_effect = Exception("API Error")
        
        service = TwilioService()
        result = await service.get_call_recordings("CA1234567890abcdef1234567890abcdef")
        
        assert result == []
    
    def test_extract_webhook_data_complete(self):
        """Test webhook data extraction with all fields."""
        form_data = {
            'CallSid': 'CA1234567890abcdef1234567890abcdef',
            'From': '+15551234567',
            'To': '+15559876543',
            'CallStatus': 'in-progress',
            'Direction': 'inbound',
            'SpeechResult': 'Hello world',
            'Confidence': '0.95',
            'RecordingUrl': 'https://api.twilio.com/recordings/RE123.mp3',
            'RecordingSid': 'RE1234567890abcdef1234567890abcdef',
            'TranscriptionText': 'Hello world transcription',
            'TranscriptionStatus': 'completed',
            'Digits': '1',
            'CallerName': 'John Doe',
            'CallerCity': 'San Francisco',
            'CallerState': 'CA',
            'CallerZip': '94105',
            'CallerCountry': 'US'
        }
        
        service = TwilioService()
        result = service.extract_webhook_data(form_data)
        
        assert result['call_sid'] == 'CA1234567890abcdef1234567890abcdef'
        assert result['from_number'] == '+15551234567'
        assert result['to_number'] == '+15559876543'
        assert result['call_status'] == 'in-progress'
        assert result['direction'] == 'inbound'
        assert result['speech_result'] == 'Hello world'
        assert result['confidence'] == '0.95'
        assert result['recording_url'] == 'https://api.twilio.com/recordings/RE123.mp3'
        assert result['recording_sid'] == 'RE1234567890abcdef1234567890abcdef'
        assert result['transcription_text'] == 'Hello world transcription'
        assert result['transcription_status'] == 'completed'
        assert result['digits'] == '1'
        assert result['caller_name'] == 'John Doe'
        assert result['caller_city'] == 'San Francisco'
        assert result['caller_state'] == 'CA'
        assert result['caller_zip'] == '94105'
        assert result['caller_country'] == 'US'
    
    def test_extract_webhook_data_minimal(self):
        """Test webhook data extraction with minimal fields."""
        form_data = {
            'CallSid': 'CA1234567890abcdef1234567890abcdef',
            'From': '+15551234567'
        }
        
        service = TwilioService()
        result = service.extract_webhook_data(form_data)
        
        assert result['call_sid'] == 'CA1234567890abcdef1234567890abcdef'
        assert result['from_number'] == '+15551234567'
        assert result['to_number'] is None
        assert result['call_status'] is None
        assert result['speech_result'] is None
    
    def test_extract_webhook_data_empty(self):
        """Test webhook data extraction with empty form data."""
        form_data = {}
        
        service = TwilioService()
        result = service.extract_webhook_data(form_data)
        
        assert all(value is None for value in result.values())


class TestTwilioServiceGlobalInstance:
    """Test the global Twilio service instance."""
    
    def test_global_instance_exists(self):
        """Test that global instance is properly initialized."""
        assert twilio_service is not None
        assert isinstance(twilio_service, TwilioService)
        assert hasattr(twilio_service, 'client')
        assert hasattr(twilio_service, 'validator')
    
    def test_global_instance_methods(self):
        """Test that global instance has all required methods."""
        required_methods = [
            'validate_webhook_signature',
            'create_greeting_response',
            'create_conversation_response',
            'create_recording_response',
            'create_error_response',
            'create_transfer_response',
            'initiate_outbound_call',
            'get_call_details',
            'get_call_recordings',
            'extract_webhook_data'
        ]
        
        for method_name in required_methods:
            assert hasattr(twilio_service, method_name)
            assert callable(getattr(twilio_service, method_name))


@pytest.mark.integration
class TestTwilioServiceIntegration:
    """Integration tests for Twilio service (require real credentials)."""
    
    @pytest.mark.skip(reason="Requires real Twilio credentials")
    async def test_real_call_initiation(self):
        """Test real call initiation (skipped by default)."""
        # This test would require real Twilio credentials
        # and should only be run in integration test environment
        pass
    
    @pytest.mark.skip(reason="Requires real Twilio credentials")
    async def test_real_webhook_validation(self):
        """Test real webhook signature validation (skipped by default)."""
        # This test would require real webhook requests from Twilio
        pass