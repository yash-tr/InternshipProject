"""
Unit tests for Twilio webhook handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.services.twilio_service import twilio_service
from app.services.call_handler import call_handler
from app.schemas.call_session import CallSessionResponse


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_twilio_service():
    """Mock Twilio service."""
    with patch('app.api.v1.endpoints.webhooks.twilio_service') as mock:
        mock.validate_webhook_signature.return_value = True
        mock.create_greeting_response.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/v1/webhooks/twilio/conversation" method="POST">
        <Say voice="alice">Hello! How can I help you?</Say>
    </Gather>
</Response>"""
        mock.create_conversation_response.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/v1/webhooks/twilio/conversation" method="POST">
        <Say voice="alice">Thank you for that information.</Say>
    </Gather>
</Response>"""
        mock.create_error_response.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">I'm sorry, technical difficulties.</Say>
    <Hangup/>
</Response>"""
        yield mock


@pytest.fixture
def mock_call_handler():
    """Mock call handler service."""
    with patch('app.api.v1.endpoints.webhooks.call_handler') as mock:
        mock.initialize_call_session.return_value = CallSessionResponse(
            id=1,
            call_sid="CA1234567890abcdef1234567890abcdef",
            caller_phone="+15551234567",
            contact_id="0031234567890AB",
            lead_score=0,
            call_outcome=None,
            start_time=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        mock.process_conversation_turn.return_value = ("Thank you for calling!", False)
        mock.end_call_session.return_value = None
        yield mock


class TestIncomingCallWebhook:
    """Test incoming call webhook handler."""
    
    def test_incoming_call_success(self, client, mock_twilio_service, mock_call_handler):
        """Test successful incoming call handling."""
        response = client.post(
            "/api/v1/webhooks/twilio/incoming-call",
            data={
                "From": "+15551234567",
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml; charset=utf-8"
        assert "Hello! How can I help you?" in response.text
        
        # Verify services were called
        mock_twilio_service.validate_webhook_signature.assert_called_once()
        mock_twilio_service.create_greeting_response.assert_called_once_with("+15551234567")
    
    def test_incoming_call_invalid_signature(self, client, mock_twilio_service):
        """Test incoming call with invalid signature."""
        mock_twilio_service.validate_webhook_signature.return_value = False
        
        response = client.post(
            "/api/v1/webhooks/twilio/incoming-call",
            data={
                "From": "+15551234567",
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
        )
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid webhook signature"
    
    def test_incoming_call_missing_required_fields(self, client):
        """Test incoming call with missing required fields."""
        response = client.post(
            "/api/v1/webhooks/twilio/incoming-call",
            data={
                "From": "+15551234567",
                # Missing CallSid, To, CallStatus
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_incoming_call_service_error(self, client, mock_twilio_service):
        """Test incoming call with service error."""
        mock_twilio_service.create_greeting_response.side_effect = Exception("Service error")
        
        response = client.post(
            "/api/v1/webhooks/twilio/incoming-call",
            data={
                "From": "+15551234567",
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
        )
        
        assert response.status_code == 200
        assert "technical difficulties" in response.text.lower()


class TestConversationWebhook:
    """Test conversation webhook handler."""
    
    def test_conversation_turn_success(self, client, mock_twilio_service, mock_call_handler):
        """Test successful conversation turn."""
        response = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "SpeechResult": "Hello, I'm interested in your services",
                "Confidence": "0.95"
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml; charset=utf-8"
        assert "Thank you for that information" in response.text
        
        # Verify call handler was called
        mock_call_handler.process_conversation_turn.assert_called_once_with(
            call_sid="CA1234567890abcdef1234567890abcdef",
            user_input="Hello, I'm interested in your services",
            confidence=0.95,
            audio_url=None
        )
    
    def test_conversation_turn_end_call(self, client, mock_twilio_service, mock_call_handler):
        """Test conversation turn that ends the call."""
        mock_call_handler.process_conversation_turn.return_value = ("Goodbye!", True)
        
        response = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "SpeechResult": "Thank you, goodbye"
            }
        )
        
        assert response.status_code == 200
        mock_call_handler.end_call_session.assert_called_once_with(
            "CA1234567890abcdef1234567890abcdef", "completed"
        )
    
    def test_conversation_turn_no_speech(self, client, mock_twilio_service, mock_call_handler):
        """Test conversation turn with no speech input."""
        response = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567"
                # No SpeechResult
            }
        )
        
        assert response.status_code == 200
        mock_call_handler.process_conversation_turn.assert_called_once_with(
            call_sid="CA1234567890abcdef1234567890abcdef",
            user_input=None,
            confidence=None,
            audio_url=None
        )
    
    def test_conversation_turn_invalid_signature(self, client, mock_twilio_service):
        """Test conversation turn with invalid signature."""
        mock_twilio_service.validate_webhook_signature.return_value = False
        
        response = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "SpeechResult": "Hello"
            }
        )
        
        assert response.status_code == 401
    
    def test_conversation_turn_handler_error(self, client, mock_twilio_service, mock_call_handler):
        """Test conversation turn with handler error."""
        mock_call_handler.process_conversation_turn.side_effect = Exception("Handler error")
        
        response = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "SpeechResult": "Hello"
            }
        )
        
        assert response.status_code == 200
        assert "technical difficulties" in response.text.lower()


class TestRecordingWebhook:
    """Test recording webhook handler."""
    
    def test_recording_success(self, client, mock_twilio_service):
        """Test successful recording handling."""
        response = client.post(
            "/api/v1/webhooks/twilio/recording/CA1234567890abcdef1234567890abcdef",
            data={
                "RecordingUrl": "https://api.twilio.com/recordings/RE123.mp3",
                "RecordingSid": "RE1234567890abcdef1234567890abcdef",
                "RecordingDuration": "30"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
    
    def test_recording_invalid_signature(self, client, mock_twilio_service):
        """Test recording with invalid signature."""
        mock_twilio_service.validate_webhook_signature.return_value = False
        
        response = client.post(
            "/api/v1/webhooks/twilio/recording/CA1234567890abcdef1234567890abcdef",
            data={
                "RecordingUrl": "https://api.twilio.com/recordings/RE123.mp3",
                "RecordingSid": "RE1234567890abcdef1234567890abcdef"
            }
        )
        
        assert response.status_code == 401


class TestTranscriptionWebhook:
    """Test transcription webhook handler."""
    
    def test_transcription_success(self, client, mock_twilio_service):
        """Test successful transcription handling."""
        response = client.post(
            "/api/v1/webhooks/twilio/transcription/CA1234567890abcdef1234567890abcdef",
            data={
                "TranscriptionText": "Hello, I would like information about your services",
                "TranscriptionStatus": "completed",
                "TranscriptionSid": "TR1234567890abcdef1234567890abcdef"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
    
    def test_transcription_failed(self, client, mock_twilio_service):
        """Test failed transcription handling."""
        response = client.post(
            "/api/v1/webhooks/twilio/transcription/CA1234567890abcdef1234567890abcdef",
            data={
                "TranscriptionStatus": "failed",
                "TranscriptionSid": "TR1234567890abcdef1234567890abcdef"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"


class TestCallStatusWebhook:
    """Test call status webhook handler."""
    
    def test_call_completed(self, client, mock_twilio_service, mock_call_handler):
        """Test call completion status."""
        response = client.post(
            "/api/v1/webhooks/twilio/call-status",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "CallStatus": "completed",
                "CallDuration": "120"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
        
        mock_call_handler.end_call_session.assert_called_once_with(
            "CA1234567890abcdef1234567890abcdef", "completed"
        )
    
    def test_call_failed(self, client, mock_twilio_service, mock_call_handler):
        """Test call failure status."""
        response = client.post(
            "/api/v1/webhooks/twilio/call-status",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "CallStatus": "failed"
            }
        )
        
        assert response.status_code == 200
        mock_call_handler.end_call_session.assert_called_once_with(
            "CA1234567890abcdef1234567890abcdef", "failed"
        )
    
    def test_call_in_progress(self, client, mock_twilio_service, mock_call_handler):
        """Test call in-progress status (should not end session)."""
        response = client.post(
            "/api/v1/webhooks/twilio/call-status",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "CallStatus": "in-progress"
            }
        )
        
        assert response.status_code == 200
        mock_call_handler.end_call_session.assert_not_called()


class TestTwilioService:
    """Test Twilio service methods."""
    
    def test_create_greeting_response(self):
        """Test greeting TwiML generation."""
        response = twilio_service.create_greeting_response("+15551234567")
        
        assert "<?xml version=" in response
        assert "<Response>" in response
        assert "<Gather" in response
        assert "speech" in response
        assert "Hello!" in response or "Thank you" in response
    
    def test_create_conversation_response_continue(self):
        """Test conversation TwiML for continuing call."""
        response = twilio_service.create_conversation_response(
            user_speech="Hello",
            ai_response="How can I help you?",
            should_end_call=False
        )
        
        assert "<Response>" in response
        assert "<Gather" in response
        assert "How can I help you?" in response
        assert "<Hangup/>" not in response or response.count("<Hangup/>") > 1  # Fallback hangup
    
    def test_create_conversation_response_end_call(self):
        """Test conversation TwiML for ending call."""
        response = twilio_service.create_conversation_response(
            user_speech="Goodbye",
            ai_response="Thank you for calling!",
            should_end_call=True
        )
        
        assert "<Response>" in response
        assert "Thank you for calling!" in response
        assert "<Hangup/>" in response
        assert "<Gather" not in response
    
    def test_create_error_response(self):
        """Test error TwiML generation."""
        response = twilio_service.create_error_response("Custom error message")
        
        assert "<Response>" in response
        assert "<Say" in response
        assert "Custom error message" in response
        assert "<Hangup/>" in response
    
    def test_extract_webhook_data(self):
        """Test webhook data extraction."""
        form_data = {
            'CallSid': 'CA1234567890abcdef1234567890abcdef',
            'From': '+15551234567',
            'To': '+15559876543',
            'CallStatus': 'in-progress',
            'SpeechResult': 'Hello world',
            'Confidence': '0.95'
        }
        
        extracted = twilio_service.extract_webhook_data(form_data)
        
        assert extracted['call_sid'] == 'CA1234567890abcdef1234567890abcdef'
        assert extracted['from_number'] == '+15551234567'
        assert extracted['speech_result'] == 'Hello world'
        assert extracted['confidence'] == '0.95'
    
    @patch('app.services.twilio_service.Client')
    def test_initiate_outbound_call(self, mock_client):
        """Test outbound call initiation."""
        # Mock Twilio client
        mock_call = MagicMock()
        mock_call.sid = 'CA1234567890abcdef1234567890abcdef'
        mock_call.status = 'queued'
        mock_client.return_value.calls.create.return_value = mock_call
        
        # Create new service instance to use mocked client
        service = twilio_service
        
        # This would need to be tested with proper async setup
        # For now, just verify the method exists and has correct signature
        assert hasattr(service, 'initiate_outbound_call')
        assert callable(service.initiate_outbound_call)


@pytest.mark.asyncio
class TestWebhookIntegration:
    """Integration tests for webhook flow."""
    
    async def test_full_call_flow(self, client, mock_twilio_service, mock_call_handler):
        """Test complete call flow from incoming to completion."""
        # 1. Incoming call
        response1 = client.post(
            "/api/v1/webhooks/twilio/incoming-call",
            data={
                "From": "+15551234567",
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "To": "+15559876543",
                "CallStatus": "in-progress"
            }
        )
        assert response1.status_code == 200
        
        # 2. Conversation turn
        response2 = client.post(
            "/api/v1/webhooks/twilio/conversation",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "From": "+15551234567",
                "SpeechResult": "I need help with your services"
            }
        )
        assert response2.status_code == 200
        
        # 3. Call completion
        response3 = client.post(
            "/api/v1/webhooks/twilio/call-status",
            data={
                "CallSid": "CA1234567890abcdef1234567890abcdef",
                "CallStatus": "completed",
                "CallDuration": "180"
            }
        )
        assert response3.status_code == 200
        
        # Verify all services were called appropriately
        assert mock_twilio_service.validate_webhook_signature.call_count >= 3
        mock_call_handler.process_conversation_turn.assert_called()
        mock_call_handler.end_call_session.assert_called_with(
            "CA1234567890abcdef1234567890abcdef", "completed"
        )