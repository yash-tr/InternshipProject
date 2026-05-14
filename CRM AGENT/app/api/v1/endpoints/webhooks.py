"""
Webhook endpoints for external service integrations.
"""
from typing import Optional
from fastapi import APIRouter, Form, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
import structlog

from app.services.twilio_service import twilio_service
from app.services.call_handler import call_handler
from app.services.outbound_call_manager import outbound_call_manager

logger = structlog.get_logger()
router = APIRouter()


@router.post("/twilio/incoming-call")
async def handle_incoming_call(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    CallSid: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...)
) -> PlainTextResponse:
    """Handle incoming Twilio voice calls."""
    try:
        # Store form data for signature validation
        form_data = {
            'From': From,
            'CallSid': CallSid,
            'To': To,
            'CallStatus': CallStatus
        }
        request._form_data = form_data
        
        # Validate webhook signature for security
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature",
                call_sid=CallSid,
                from_number=From
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Incoming call received",
            from_number=From,
            call_sid=CallSid,
            to_number=To,
            call_status=CallStatus
        )
        
        # Initialize call session in background
        background_tasks.add_task(
            call_handler.initialize_call_session,
            CallSid,
            From,
            CallStatus
        )
        
        # Generate greeting TwiML response
        twiml_response = twilio_service.create_greeting_response(From)
        
        return PlainTextResponse(content=twiml_response, media_type="application/xml")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error handling incoming call",
            call_sid=CallSid,
            from_number=From,
            error=str(e)
        )
        
        # Return error TwiML response
        error_response = twilio_service.create_error_response(
            "We're experiencing technical difficulties. Please try again later."
        )
        return PlainTextResponse(content=error_response, media_type="application/xml")


@router.post("/twilio/conversation")
async def handle_conversation_turn(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
) -> PlainTextResponse:
    """Handle ongoing conversation turns."""
    try:
        # Extract all webhook data
        form_data = await request.form()
        webhook_data = twilio_service.extract_webhook_data(dict(form_data))
        
        # Store form data for signature validation
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for conversation",
                call_sid=CallSid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Conversation turn received",
            call_sid=CallSid,
            from_number=From,
            speech_result=SpeechResult[:100] if SpeechResult else None,
            confidence=Confidence
        )
        
        # Process conversation turn
        ai_response, should_end_call, audio_data = await call_handler.process_conversation_turn(
            call_sid=CallSid,
            user_input=SpeechResult,
            confidence=Confidence,
            audio_url=RecordingUrl
        )
        
        # Generate TwiML response
        twiml_response = twilio_service.create_conversation_response(
            user_speech=SpeechResult,
            ai_response=ai_response,
            should_end_call=should_end_call
        )
        
        # End call session if needed
        if should_end_call:
            await call_handler.end_call_session(CallSid, "completed")
        
        return PlainTextResponse(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(
            "Error handling conversation turn",
            call_sid=CallSid,
            error=str(e)
        )
        
        # Return error response but continue call
        error_response = twilio_service.create_conversation_response(
            user_speech=SpeechResult,
            ai_response="I'm sorry, I'm having technical difficulties. Could you please repeat that?",
            should_end_call=False
        )
        return PlainTextResponse(content=error_response, media_type="application/xml")


@router.post("/twilio/recording/{call_sid}")
async def handle_call_recording(
    call_sid: str,
    request: Request,
    RecordingUrl: str = Form(...),
    RecordingSid: str = Form(...),
    RecordingDuration: Optional[int] = Form(None)
) -> PlainTextResponse:
    """Handle call recording completion."""
    try:
        # Extract webhook data
        form_data = await request.form()
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for recording",
                call_sid=call_sid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Call recording received",
            call_sid=call_sid,
            recording_sid=RecordingSid,
            recording_url=RecordingUrl,
            duration=RecordingDuration
        )
        
        # TODO: Process recording for transcription and analysis
        # This would integrate with ElevenLabs STT service
        
        # Return simple acknowledgment
        return PlainTextResponse(content="OK", media_type="text/plain")
        
    except Exception as e:
        logger.error(
            "Error handling call recording",
            call_sid=call_sid,
            error=str(e)
        )
        return PlainTextResponse(content="ERROR", media_type="text/plain")


@router.post("/twilio/transcription/{call_sid}")
async def handle_transcription(
    call_sid: str,
    request: Request,
    TranscriptionText: Optional[str] = Form(None),
    TranscriptionStatus: Optional[str] = Form(None),
    TranscriptionSid: Optional[str] = Form(None)
) -> PlainTextResponse:
    """Handle transcription completion."""
    try:
        # Extract webhook data
        form_data = await request.form()
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for transcription",
                call_sid=call_sid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Transcription received",
            call_sid=call_sid,
            transcription_sid=TranscriptionSid,
            status=TranscriptionStatus,
            text_length=len(TranscriptionText) if TranscriptionText else 0
        )
        
        # TODO: Store transcription and update conversation history
        
        return PlainTextResponse(content="OK", media_type="text/plain")
        
    except Exception as e:
        logger.error(
            "Error handling transcription",
            call_sid=call_sid,
            error=str(e)
        )
        return PlainTextResponse(content="ERROR", media_type="text/plain")


@router.post("/twilio/call-status")
async def handle_call_status_update(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[int] = Form(None)
) -> PlainTextResponse:
    """Handle call status updates (completed, failed, etc.)."""
    try:
        # Extract webhook data
        form_data = await request.form()
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for call status",
                call_sid=CallSid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Call status update received",
            call_sid=CallSid,
            status=CallStatus,
            duration=CallDuration
        )
        
        # End call session if call is completed
        if CallStatus in ['completed', 'failed', 'no-answer', 'busy']:
            await call_handler.end_call_session(CallSid, CallStatus)
        
        return PlainTextResponse(content="OK", media_type="text/plain")
        
    except Exception as e:
        logger.error(
            "Error handling call status update",
            call_sid=CallSid,
            error=str(e)
        )
        return PlainTextResponse(content="ERROR", media_type="text/plain")


@router.post("/twilio/outbound/{task_id}")
async def handle_outbound_call_webhook(
    task_id: str,
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
) -> PlainTextResponse:
    """Handle outbound call webhooks from Twilio."""
    try:
        # Extract webhook data
        form_data = await request.form()
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for outbound call",
                task_id=task_id,
                call_sid=CallSid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Outbound call webhook received",
            task_id=task_id,
            call_sid=CallSid,
            status=CallStatus,
            duration=CallDuration
        )
        
        # Parse duration
        duration = None
        if CallDuration:
            try:
                duration = int(CallDuration)
            except ValueError:
                pass
        
        # Handle status update
        await outbound_call_manager.handle_call_status_update(
            task_id=task_id,
            call_sid=CallSid,
            status=CallStatus,
            duration=duration
        )
        
        # Generate appropriate TwiML response based on call status
        if CallStatus == "ringing":
            # Call is ringing, wait for answer
            twiml_response = twilio_service.create_greeting_response(To)
        elif CallStatus == "in-progress":
            # Call answered, start conversation
            twiml_response = twilio_service.create_greeting_response(To)
        else:
            # Call completed, no response needed
            twiml_response = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"
        
        return PlainTextResponse(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(
            "Error handling outbound call webhook",
            task_id=task_id,
            call_sid=CallSid,
            error=str(e)
        )
        
        # Return empty response to avoid Twilio retries
        return PlainTextResponse(
            content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
            media_type="application/xml"
        )


@router.post("/twilio/outbound-conversation/{task_id}")
async def handle_outbound_conversation(
    task_id: str,
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
) -> PlainTextResponse:
    """Handle outbound call conversation turns."""
    try:
        # Extract webhook data
        form_data = await request.form()
        request._form_data = dict(form_data)
        
        # Validate webhook signature
        if not twilio_service.validate_webhook_signature(request):
            logger.warning(
                "Invalid webhook signature for outbound conversation",
                task_id=task_id,
                call_sid=CallSid
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(
            "Outbound conversation turn received",
            task_id=task_id,
            call_sid=CallSid,
            speech_result=SpeechResult[:100] if SpeechResult else None,
            confidence=Confidence
        )
        
        # Process conversation turn using existing call handler
        # The call handler will manage the conversation flow
        ai_response, should_end_call, audio_data = await call_handler.process_conversation_turn(
            call_sid=CallSid,
            user_input=SpeechResult,
            confidence=Confidence,
            audio_url=RecordingUrl
        )
        
        # Generate TwiML response
        twiml_response = twilio_service.create_conversation_response(
            user_speech=SpeechResult,
            ai_response=ai_response,
            should_end_call=should_end_call
        )
        
        # Update outbound call manager if call should end
        if should_end_call:
            await outbound_call_manager.handle_call_status_update(
                task_id=task_id,
                call_sid=CallSid,
                status="completed",
                duration=None  # Duration will be provided by final status webhook
            )
        
        return PlainTextResponse(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(
            "Error handling outbound conversation",
            task_id=task_id,
            call_sid=CallSid,
            error=str(e)
        )
        
        # Return error response but continue call
        error_response = twilio_service.create_conversation_response(
            user_speech=SpeechResult,
            ai_response="I'm sorry, I'm having technical difficulties. Let me transfer you to a human representative.",
            should_end_call=True
        )
        return PlainTextResponse(content=error_response, media_type="application/xml")


@router.post("/salesforce/lead-created")
async def handle_salesforce_lead_trigger(request: Request):
    """Handle Salesforce lead creation webhook."""
    logger.info("Salesforce webhook received")
    
    # TODO: Implement Salesforce webhook processing
    return {"status": "accepted", "message": "Webhook received"}


@router.get("/test")
async def test_webhook():
    """Test endpoint for webhook functionality."""
    return {"message": "Webhook system is operational", "version": "0.1.0"}