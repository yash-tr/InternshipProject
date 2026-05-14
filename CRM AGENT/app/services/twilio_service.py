"""
Twilio Voice API integration service for call handling and TwiML generation.
"""
import hashlib
import hmac
import base64
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, urlparse

import structlog
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Record, Hangup
from twilio.request_validator import RequestValidator
from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.schemas.call_session import CallSessionCreate
from app.schemas.conversation import ConversationTurnCreate, ConversationRole


logger = structlog.get_logger()


class TwilioService:
    """Service for Twilio Voice API integration and webhook handling."""
    
    def __init__(self):
        """Initialize Twilio service with configuration."""
        self.settings = get_settings()
        self.client = Client(
            self.settings.TWILIO_ACCOUNT_SID,
            self.settings.TWILIO_AUTH_TOKEN
        )
        self.validator = RequestValidator(self.settings.TWILIO_AUTH_TOKEN)
        
    def validate_webhook_signature(self, request: Request) -> bool:
        """
        Validate Twilio webhook signature for security.
        
        Args:
            request: FastAPI request object
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Get the signature from headers
            signature = request.headers.get('X-Twilio-Signature', '')
            if not signature:
                logger.warning("Missing Twilio signature header")
                return False
            
            # Get the full URL
            url = str(request.url)
            
            # Get form data as dict
            form_data = {}
            if hasattr(request, '_form_data'):
                form_data = request._form_data
            
            # Validate the signature
            is_valid = self.validator.validate(url, form_data, signature)
            
            if not is_valid:
                logger.warning(
                    "Invalid Twilio webhook signature",
                    url=url,
                    signature=signature[:10] + "..."
                )
            
            return is_valid
            
        except Exception as e:
            logger.error("Error validating Twilio webhook signature", error=str(e))
            return False
    
    def create_greeting_response(self, caller_phone: str) -> str:
        """
        Create initial greeting TwiML response for incoming calls.
        
        Args:
            caller_phone: Caller's phone number
            
        Returns:
            str: TwiML XML response
        """
        response = VoiceResponse()
        
        # Professional greeting
        greeting_text = (
            "Hello! Thank you for calling. You've reached our AI assistant. "
            "I'm here to help answer your questions and connect you with the right information. "
            "How can I assist you today?"
        )
        
        # Use Gather to collect speech input
        gather = Gather(
            input='speech',
            action='/api/v1/webhooks/twilio/conversation',
            method='POST',
            speech_timeout='3',
            timeout=10,
            language='en-US',
            enhanced=True
        )
        
        gather.say(greeting_text, voice='alice', language='en-US')
        response.append(gather)
        
        # Fallback if no input received
        response.say(
            "I didn't hear anything. Please call back when you're ready to speak. Goodbye!",
            voice='alice',
            language='en-US'
        )
        response.hangup()
        
        logger.info(
            "Generated greeting TwiML response",
            caller_phone=caller_phone,
            response_length=len(str(response))
        )
        
        return str(response)
    
    def create_conversation_response(
        self,
        user_speech: Optional[str],
        ai_response: str,
        should_end_call: bool = False,
        gather_timeout: int = 10
    ) -> str:
        """
        Create TwiML response for ongoing conversation.
        
        Args:
            user_speech: User's speech input (if any)
            ai_response: AI assistant's response
            should_end_call: Whether to end the call
            gather_timeout: Timeout for gathering next input
            
        Returns:
            str: TwiML XML response
        """
        response = VoiceResponse()
        
        if should_end_call:
            # End call with final message
            response.say(ai_response, voice='alice', language='en-US')
            response.say(
                "Thank you for calling. Have a great day!",
                voice='alice',
                language='en-US'
            )
            response.hangup()
        else:
            # Continue conversation
            gather = Gather(
                input='speech',
                action='/api/v1/webhooks/twilio/conversation',
                method='POST',
                speech_timeout='3',
                timeout=gather_timeout,
                language='en-US',
                enhanced=True
            )
            
            gather.say(ai_response, voice='alice', language='en-US')
            response.append(gather)
            
            # Fallback for no input
            response.say(
                "I didn't hear a response. Are you still there? Please speak up or I'll end the call.",
                voice='alice',
                language='en-US'
            )
            
            # Give one more chance
            final_gather = Gather(
                input='speech',
                action='/api/v1/webhooks/twilio/conversation',
                method='POST',
                speech_timeout='2',
                timeout=5,
                language='en-US',
                enhanced=True
            )
            final_gather.say("Hello?", voice='alice', language='en-US')
            response.append(final_gather)
            
            # Final hangup
            response.say("Goodbye!", voice='alice', language='en-US')
            response.hangup()
        
        logger.info(
            "Generated conversation TwiML response",
            user_speech_length=len(user_speech) if user_speech else 0,
            ai_response_length=len(ai_response),
            should_end_call=should_end_call
        )
        
        return str(response)
    
    def create_recording_response(self, call_sid: str) -> str:
        """
        Create TwiML response to record caller's message.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            str: TwiML XML response
        """
        response = VoiceResponse()
        
        response.say(
            "Please leave your message after the beep, and I'll get back to you shortly.",
            voice='alice',
            language='en-US'
        )
        
        # Record the message
        response.record(
            action=f'/api/v1/webhooks/twilio/recording/{call_sid}',
            method='POST',
            max_length=60,
            finish_on_key='#',
            transcribe=True,
            transcribe_callback=f'/api/v1/webhooks/twilio/transcription/{call_sid}'
        )
        
        response.say("Thank you for your message. Goodbye!", voice='alice', language='en-US')
        response.hangup()
        
        logger.info("Generated recording TwiML response", call_sid=call_sid)
        
        return str(response)
    
    def create_error_response(self, error_message: str = None) -> str:
        """
        Create TwiML response for error scenarios.
        
        Args:
            error_message: Optional custom error message
            
        Returns:
            str: TwiML XML response
        """
        response = VoiceResponse()
        
        if error_message:
            response.say(
                f"I'm sorry, but I'm experiencing technical difficulties. {error_message}",
                voice='alice',
                language='en-US'
            )
        else:
            response.say(
                "I'm sorry, but I'm experiencing technical difficulties. Please try calling back in a few minutes.",
                voice='alice',
                language='en-US'
            )
        
        response.hangup()
        
        logger.warning("Generated error TwiML response", error_message=error_message)
        
        return str(response)
    
    def create_transfer_response(self, transfer_number: str, reason: str = None) -> str:
        """
        Create TwiML response to transfer call to human agent.
        
        Args:
            transfer_number: Phone number to transfer to
            reason: Optional reason for transfer
            
        Returns:
            str: TwiML XML response
        """
        response = VoiceResponse()
        
        if reason:
            response.say(
                f"I understand you'd like to {reason}. Let me transfer you to one of our team members who can help you better.",
                voice='alice',
                language='en-US'
            )
        else:
            response.say(
                "Let me transfer you to one of our team members who can help you.",
                voice='alice',
                language='en-US'
            )
        
        # Dial the transfer number
        response.dial(transfer_number, timeout=30)
        
        # Fallback if transfer fails
        response.say(
            "I'm sorry, but I wasn't able to connect you right now. Please try calling back later.",
            voice='alice',
            language='en-US'
        )
        response.hangup()
        
        logger.info(
            "Generated transfer TwiML response",
            transfer_number=transfer_number,
            reason=reason
        )
        
        return str(response)
    
    async def initiate_outbound_call(
        self,
        to_number: str,
        webhook_url: str,
        caller_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call using Twilio API.
        
        Args:
            to_number: Phone number to call
            webhook_url: Webhook URL for call handling
            caller_id: Optional caller ID to display
            
        Returns:
            Dict containing call information
        """
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=caller_id or self.settings.TWILIO_PHONE_NUMBER,
                url=webhook_url,
                method='POST',
                timeout=30,
                record=True
            )
            
            logger.info(
                "Initiated outbound call",
                call_sid=call.sid,
                to_number=to_number,
                status=call.status
            )
            
            return {
                'call_sid': call.sid,
                'to_number': to_number,
                'status': call.status,
                'direction': 'outbound'
            }
            
        except Exception as e:
            logger.error(
                "Failed to initiate outbound call",
                to_number=to_number,
                error=str(e)
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initiate call: {str(e)}"
            )
    
    async def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """
        Get call details from Twilio API.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            Dict containing call details
        """
        try:
            call = self.client.calls(call_sid).fetch()
            
            return {
                'call_sid': call.sid,
                'from_number': call.from_,
                'to_number': call.to,
                'status': call.status,
                'direction': call.direction,
                'duration': call.duration,
                'start_time': call.start_time,
                'end_time': call.end_time,
                'price': call.price,
                'price_unit': call.price_unit
            }
            
        except Exception as e:
            logger.error(
                "Failed to fetch call details",
                call_sid=call_sid,
                error=str(e)
            )
            return {}
    
    async def get_call_recordings(self, call_sid: str) -> List[Dict[str, Any]]:
        """
        Get recordings for a specific call.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            List of recording details
        """
        try:
            recordings = self.client.recordings.list(call_sid=call_sid)
            
            return [
                {
                    'recording_sid': recording.sid,
                    'call_sid': recording.call_sid,
                    'duration': recording.duration,
                    'date_created': recording.date_created,
                    'uri': recording.uri,
                    'media_url': f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                }
                for recording in recordings
            ]
            
        except Exception as e:
            logger.error(
                "Failed to fetch call recordings",
                call_sid=call_sid,
                error=str(e)
            )
            return []
    
    def extract_webhook_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and validate webhook data from Twilio request.
        
        Args:
            form_data: Form data from webhook request
            
        Returns:
            Dict containing extracted webhook data
        """
        return {
            'call_sid': form_data.get('CallSid'),
            'from_number': form_data.get('From'),
            'to_number': form_data.get('To'),
            'call_status': form_data.get('CallStatus'),
            'direction': form_data.get('Direction'),
            'speech_result': form_data.get('SpeechResult'),
            'confidence': form_data.get('Confidence'),
            'recording_url': form_data.get('RecordingUrl'),
            'recording_sid': form_data.get('RecordingSid'),
            'transcription_text': form_data.get('TranscriptionText'),
            'transcription_status': form_data.get('TranscriptionStatus'),
            'digits': form_data.get('Digits'),
            'caller_name': form_data.get('CallerName'),
            'caller_city': form_data.get('CallerCity'),
            'caller_state': form_data.get('CallerState'),
            'caller_zip': form_data.get('CallerZip'),
            'caller_country': form_data.get('CallerCountry')
        }


# Global instance
twilio_service = TwilioService()