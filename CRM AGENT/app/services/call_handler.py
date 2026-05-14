"""
Call handler service for managing conversation sessions and processing turns.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException

from app.core.database import get_async_session
from app.models.call_session import CallSession, ConversationTurn, CallMetrics
from app.schemas.call_session import CallSessionCreate, CallSessionUpdate, CallSessionResponse
from app.schemas.conversation import (
    ConversationTurnCreate, ConversationContext, ConversationRole,
    ConversationAnalysis
)
from app.services.salesforce import get_salesforce_service
from app.services.twilio_service import twilio_service
from app.services.elevenlabs_service import elevenlabs_service
from app.services.openrouter_llm import openrouter_llm_service
from app.services.dialog_manager import dialog_manager
from app.services.call_quality_monitor import call_quality_monitor
from app.utils.encryption import encrypt_pii_data, decrypt_pii_data


logger = structlog.get_logger()


class CallHandler:
    """Service for handling call sessions and conversation management."""
    
    def __init__(self):
        """Initialize call handler service."""
        self.active_sessions: Dict[str, ConversationContext] = {}
        self.session_timeouts: Dict[str, datetime] = {}
        
    async def initialize_call_session(
        self,
        call_sid: str,
        caller_phone: str,
        call_status: str = "in-progress"
    ) -> CallSessionResponse:
        """
        Initialize a new call session and find/create Salesforce contact.
        
        Args:
            call_sid: Twilio Call SID
            caller_phone: Caller's phone number
            call_status: Current call status
            
        Returns:
            CallSessionResponse: Created call session
        """
        try:
            async with get_async_session() as db:
                # Check if session already exists
                existing_session = await db.execute(
                    select(CallSession).where(CallSession.call_sid == call_sid)
                )
                existing = existing_session.scalar_one_or_none()
                
                if existing:
                    logger.info(
                        "Call session already exists",
                        call_sid=call_sid,
                        session_id=existing.id
                    )
                    return CallSessionResponse.model_validate(existing)
                
                # Find or create Salesforce contact
                contact_id = None
                try:
                    salesforce_service = await get_salesforce_service()
                    contact_data = await salesforce_service.find_or_create_contact(
                        phone=caller_phone,
                        additional_data={'LeadSource': 'AI_Calling_Agent'}
                    )
                    contact_id = contact_data.get('Id')
                    logger.info(
                        "Salesforce contact processed",
                        call_sid=call_sid,
                        contact_id=contact_id,
                        is_new=contact_data.get('is_new', False)
                    )
                except Exception as sf_error:
                    logger.warning(
                        "Salesforce contact creation failed, continuing without CRM",
                        call_sid=call_sid,
                        error=str(sf_error)
                    )
                
                # Create new call session
                session_data = CallSessionCreate(
                    call_sid=call_sid,
                    caller_phone=caller_phone,
                    contact_id=contact_id,
                    start_time=datetime.utcnow()
                )
                
                # Encrypt PII data
                encrypted_data = await encrypt_pii_data({
                    'caller_phone': caller_phone,
                    'contact_id': contact_id
                })
                
                db_session = CallSession(
                    call_sid=call_sid,
                    caller_phone=encrypted_data['caller_phone'],
                    contact_id=encrypted_data.get('contact_id'),
                    start_time=session_data.start_time,
                    lead_score=0
                )
                
                db.add(db_session)
                await db.commit()
                await db.refresh(db_session)
                
                # Initialize conversation context
                context = ConversationContext(
                    call_sid=call_sid,
                    turns=[],
                    extracted_information={
                        'phone': caller_phone,
                        'contact_id': contact_id
                    }
                )
                
                self.active_sessions[call_sid] = context
                self.session_timeouts[call_sid] = datetime.utcnow() + timedelta(minutes=30)
                
                # Start call quality monitoring
                try:
                    await call_quality_monitor.start_monitoring(call_sid)
                    logger.info(
                        "Call quality monitoring started",
                        call_sid=call_sid
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to start call quality monitoring",
                        call_sid=call_sid,
                        error=str(e)
                    )
                
                logger.info(
                    "Call session initialized",
                    call_sid=call_sid,
                    session_id=db_session.id,
                    contact_id=contact_id
                )
                
                return CallSessionResponse.model_validate(db_session)
                
        except Exception as e:
            logger.error(
                "Failed to initialize call session",
                call_sid=call_sid,
                caller_phone=caller_phone,
                error=str(e)
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize call session: {str(e)}"
            )
    
    async def process_conversation_turn(
        self,
        call_sid: str,
        user_input: Optional[str],
        confidence: Optional[float] = None,
        audio_url: Optional[str] = None,
        audio_data: Optional[bytes] = None
    ) -> Tuple[str, bool, Optional[bytes]]:
        """
        Process a conversation turn and generate AI response with audio.
        
        Args:
            call_sid: Twilio Call SID
            user_input: User's speech input
            confidence: Speech recognition confidence
            audio_url: URL to audio recording
            audio_data: Raw audio data for quality analysis
            
        Returns:
            Tuple of (AI response text, should_end_call, audio_data)
        """
        start_time = datetime.utcnow()
        stt_start_time = start_time
        response_generation_start = None
        tts_start_time = None
        
        try:
            # Get or create conversation context
            context = self.active_sessions.get(call_sid)
            if not context:
                # Try to restore from database
                context = await self._restore_conversation_context(call_sid)
                if not context:
                    raise HTTPException(
                        status_code=404,
                        detail="Call session not found"
                    )
            
            # Record audio metrics if audio data provided
            if audio_data:
                try:
                    await call_quality_monitor.record_audio_metrics(
                        call_sid=call_sid,
                        audio_data=audio_data,
                        sample_rate=8000
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to record audio metrics",
                        call_sid=call_sid,
                        error=str(e)
                    )
            
            # Enhanced transcription using ElevenLabs if audio_url provided
            enhanced_user_input = user_input
            if audio_url and not user_input:
                try:
                    enhanced_user_input = await elevenlabs_service.transcribe_audio(
                        audio_url=audio_url,
                        language="en",
                        fallback_enabled=True
                    )
                    stt_latency = (datetime.utcnow() - stt_start_time).total_seconds() * 1000
                    
                    if enhanced_user_input:
                        logger.info(
                            "Enhanced transcription successful",
                            call_sid=call_sid,
                            original_length=len(user_input) if user_input else 0,
                            enhanced_length=len(enhanced_user_input),
                            stt_latency_ms=stt_latency
                        )
                    else:
                        enhanced_user_input = user_input
                except Exception as e:
                    logger.warning(
                        "ElevenLabs transcription failed, using original",
                        call_sid=call_sid,
                        error=str(e)
                    )
                    enhanced_user_input = user_input
                    stt_latency = (datetime.utcnow() - stt_start_time).total_seconds() * 1000
            else:
                stt_latency = 0.0  # No STT processing needed
            
            # Handle empty or unclear input
            if not enhanced_user_input or len(enhanced_user_input.strip()) < 2:
                response_text, should_end = await self._handle_unclear_input(call_sid, confidence)
                audio_data = await self._generate_response_audio(response_text)
                return response_text, should_end, audio_data
            
            # Store user turn
            user_turn = ConversationTurnCreate(
                call_sid=call_sid,
                role=ConversationRole.USER,
                content=enhanced_user_input,
                audio_url=audio_url,
                transcription_confidence=confidence,
                timestamp=datetime.utcnow()
            )
            
            await self._store_conversation_turn(user_turn)
            context.add_turn(user_turn)
            
            # Generate AI response (placeholder for now)
            response_generation_start = datetime.utcnow()
            ai_response, should_end = await self._generate_ai_response(
                context, enhanced_user_input
            )
            response_generation_time = (datetime.utcnow() - response_generation_start).total_seconds() * 1000
            
            # Generate audio for AI response
            tts_start_time = datetime.utcnow()
            response_audio_data = await self._generate_response_audio(ai_response)
            tts_latency = (datetime.utcnow() - tts_start_time).total_seconds() * 1000
            
            # Store AI turn
            ai_turn = ConversationTurnCreate(
                call_sid=call_sid,
                role=ConversationRole.ASSISTANT,
                content=ai_response,
                timestamp=datetime.utcnow(),
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
            
            await self._store_conversation_turn(ai_turn)
            context.add_turn(ai_turn)
            
            # Record performance metrics
            try:
                await call_quality_monitor.record_performance_metrics(
                    call_sid=call_sid,
                    stt_latency_ms=stt_latency,
                    tts_latency_ms=tts_latency,
                    response_generation_ms=response_generation_time,
                    stt_confidence=confidence or 1.0,
                    connection_quality=1.0  # Default, could be enhanced with Twilio metrics
                )
                
                # Analyze call quality and apply optimizations
                await call_quality_monitor.analyze_call_quality(call_sid)
                
            except Exception as e:
                logger.warning(
                    "Failed to record performance metrics",
                    call_sid=call_sid,
                    error=str(e)
                )
            
            # Update session timeout
            self.session_timeouts[call_sid] = datetime.utcnow() + timedelta(minutes=30)
            
            # Extract information and update lead score
            await self._update_lead_information(call_sid, context)
            
            logger.info(
                "Processed conversation turn",
                call_sid=call_sid,
                user_input_length=len(enhanced_user_input) if enhanced_user_input else 0,
                ai_response_length=len(ai_response),
                confidence=confidence,
                should_end=should_end,
                has_audio=audio_data is not None,
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
            
            return ai_response, should_end, response_audio_data
            
        except Exception as e:
            logger.error(
                "Failed to process conversation turn",
                call_sid=call_sid,
                user_input=user_input[:100] if user_input else None,
                error=str(e)
            )
            
            # Return error response but don't end call
            error_response = (
                "I'm sorry, I didn't quite catch that. Could you please repeat what you said?"
            )
            error_audio = await self._generate_response_audio(error_response)
            return error_response, False, error_audio
    
    async def end_call_session(
        self,
        call_sid: str,
        call_outcome: str = "completed",
        final_summary: Optional[str] = None
    ) -> None:
        """
        End a call session and perform cleanup.
        
        Args:
            call_sid: Twilio Call SID
            call_outcome: Final call outcome
            final_summary: Optional final conversation summary
        """
        try:
            async with get_async_session() as db:
                # Update call session
                end_time = datetime.utcnow()
                
                # Get session to calculate duration
                session_result = await db.execute(
                    select(CallSession).where(CallSession.call_sid == call_sid)
                )
                session = session_result.scalar_one_or_none()
                
                if session:
                    duration_seconds = int((end_time - session.start_time).total_seconds())
                    
                    # Get conversation context for summary
                    context = self.active_sessions.get(call_sid)
                    if context and not final_summary:
                        final_summary = context.get_conversation_summary()
                    
                    # Update session
                    await db.execute(
                        update(CallSession)
                        .where(CallSession.call_sid == call_sid)
                        .values(
                            end_time=end_time,
                            duration_seconds=duration_seconds,
                            call_outcome=call_outcome,
                            conversation_summary=final_summary
                        )
                    )
                    
                    await db.commit()
                    
                    # Log call activity in Salesforce
                    if session.contact_id:
                        try:
                            await self._log_salesforce_activity(
                                session.contact_id,
                                call_sid,
                                duration_seconds,
                                final_summary or "Call completed",
                                session.lead_score
                            )
                        except Exception as sf_error:
                            logger.warning(
                                "Failed to log Salesforce activity",
                                call_sid=call_sid,
                                error=str(sf_error)
                            )
                
                # Stop call quality monitoring and get final report
                try:
                    quality_report = await call_quality_monitor.stop_monitoring(call_sid)
                    if quality_report:
                        logger.info(
                            "Call quality monitoring completed",
                            call_sid=call_sid,
                            average_quality_score=quality_report.get("average_overall_score", 0.0),
                            total_issues=quality_report.get("total_issues_detected", 0),
                            total_optimizations=quality_report.get("total_optimizations_applied", 0)
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to stop call quality monitoring",
                        call_sid=call_sid,
                        error=str(e)
                    )
                
                # Cleanup active session
                self.active_sessions.pop(call_sid, None)
                self.session_timeouts.pop(call_sid, None)
                
                # Cleanup dialog manager conversation
                dialog_summary = await dialog_manager.end_conversation(call_sid, call_outcome)
                
                # Cleanup LLM session
                await openrouter_llm_service.cleanup_session(call_sid)
                
                logger.info(
                    "Call session ended",
                    call_sid=call_sid,
                    outcome=call_outcome,
                    duration_seconds=duration_seconds if session else None
                )
                
        except Exception as e:
            logger.error(
                "Failed to end call session",
                call_sid=call_sid,
                error=str(e)
            )
    
    async def _handle_unclear_input(
        self,
        call_sid: str,
        confidence: Optional[float]
    ) -> Tuple[str, bool]:
        """Handle unclear or empty user input."""
        context = self.active_sessions.get(call_sid)
        if not context:
            return "I'm sorry, I'm having trouble hearing you. Could you please speak clearly?", False
        
        # Count consecutive unclear inputs
        recent_turns = context.get_recent_turns(5)
        unclear_count = sum(
            1 for turn in recent_turns 
            if turn.role == ConversationRole.ASSISTANT and 
            "didn't catch" in turn.content.lower() or "repeat" in turn.content.lower()
        )
        
        if unclear_count >= 2:
            return (
                "I'm having trouble understanding you. Would you like me to transfer you to a human representative?",
                False
            )
        
        if confidence and confidence < 0.5:
            return (
                "I'm sorry, the connection seems unclear. Could you please speak a bit louder and slower?",
                False
            )
        
        return (
            "I didn't quite catch that. Could you please repeat what you said?",
            False
        )
    
    async def _generate_ai_response(
        self,
        context: ConversationContext,
        user_input: str
    ) -> Tuple[str, bool]:
        """
        Generate AI response using FSM-based Dialog Manager with template-first approach.
        """
        try:
            # Check if this is the first turn (start conversation)
            if len(context.turns) <= 1:  # Only user input, no assistant response yet
                # Get prospect data from Salesforce if available
                prospect_data = {}
                if context.extracted_information.get('contact_id'):
                    try:
                        salesforce_service = await get_salesforce_service()
                        contact_data = await salesforce_service.get_contact(
                            context.extracted_information['contact_id']
                        )
                        if contact_data:
                            prospect_data = {
                                'name': contact_data.get('Name'),
                                'company': contact_data.get('Account', {}).get('Name'),
                                'industry': contact_data.get('Account', {}).get('Industry'),
                                'phone': contact_data.get('Phone'),
                                'email': contact_data.get('Email'),
                                'lead_score': 70  # Default score, could be enhanced
                            }
                    except Exception as sf_error:
                        logger.warning(
                            "Failed to get contact context from Salesforce",
                            call_sid=context.call_sid,
                            error=str(sf_error)
                        )
                
                # Start conversation with dialog manager
                response_text = await dialog_manager.start_conversation(
                    call_sid=context.call_sid,
                    prospect_data=prospect_data
                )
                
                # For initial greeting, don't end call
                should_end = False
                
                logger.info(
                    "Started FSM-based conversation",
                    call_sid=context.call_sid,
                    response_length=len(response_text)
                )
                
                return response_text, should_end
            
            else:
                # Process conversation turn through dialog manager
                response_text, should_end = await dialog_manager.process_turn(
                    call_sid=context.call_sid,
                    user_input=user_input
                )
                
                logger.info(
                    "Processed FSM conversation turn",
                    call_sid=context.call_sid,
                    response_length=len(response_text),
                    should_end=should_end
                )
                
                return response_text, should_end
            
        except Exception as e:
            logger.error(
                "FSM dialog generation failed, using fallback",
                call_sid=context.call_sid,
                error=str(e)
            )
            
            # Fallback to simple rule-based response
            return await self._generate_fallback_response(user_input)
    
    async def _generate_fallback_response(self, user_input: str) -> Tuple[str, bool]:
        """Generate fallback response when LLM fails."""
        user_input_lower = user_input.lower()
        
        # Greeting responses
        if any(word in user_input_lower for word in ['hello', 'hi', 'hey']):
            return (
                "Hello! It's great to hear from you. How can I help you today?",
                False
            )
        
        # Information requests
        if any(word in user_input_lower for word in ['information', 'info', 'tell me about']):
            return (
                "I'd be happy to provide you with information. What specifically would you like to know about our services?",
                False
            )
        
        # Contact information
        if any(word in user_input_lower for word in ['contact', 'reach', 'call back']):
            return (
                "I can help you with contact information. May I get your name and the best number to reach you?",
                False
            )
        
        # Ending conversation
        if any(word in user_input_lower for word in ['goodbye', 'bye', 'thanks', 'thank you']):
            return (
                "Thank you for calling! We'll follow up with you soon. Have a great day!",
                True
            )
        
        # Default response
        return (
            "That's interesting. Can you tell me more about what you're looking for so I can better assist you?",
            False
        )
    
    def _should_end_call(self, analysis_data: Dict[str, Any], response_text: str) -> bool:
        """Determine if call should end based on analysis and response."""
        # End call if response contains goodbye indicators
        goodbye_indicators = ['goodbye', 'bye', 'thank you for calling', 'have a great day']
        response_lower = response_text.lower()
        
        if any(indicator in response_lower for indicator in goodbye_indicators):
            return True
        
        # End call if analysis indicates conversation completion
        if analysis_data.get('intent') == 'conversation_end':
            return True
        
        return False
    
    async def _store_conversation_turn(self, turn: ConversationTurnCreate) -> None:
        """Store conversation turn in database."""
        try:
            async with get_async_session() as db:
                # Encrypt content if it contains PII
                encrypted_content = turn.content
                if turn.role == ConversationRole.USER:
                    # Basic PII detection and encryption
                    encrypted_data = await encrypt_pii_data({'content': turn.content})
                    encrypted_content = encrypted_data['content']
                
                db_turn = ConversationTurn(
                    call_sid=turn.call_sid,
                    role=turn.role.value,
                    content=encrypted_content,
                    timestamp=turn.timestamp,
                    audio_url=str(turn.audio_url) if turn.audio_url else None,
                    transcription_confidence=turn.transcription_confidence,
                    processing_time_ms=turn.processing_time_ms,
                    llm_tokens_used=turn.llm_tokens_used
                )
                
                db.add(db_turn)
                await db.commit()
                
        except Exception as e:
            logger.error(
                "Failed to store conversation turn",
                call_sid=turn.call_sid,
                role=turn.role,
                error=str(e)
            )
    
    async def _restore_conversation_context(self, call_sid: str) -> Optional[ConversationContext]:
        """Restore conversation context from database."""
        try:
            async with get_async_session() as db:
                # Get call session
                session_result = await db.execute(
                    select(CallSession).where(CallSession.call_sid == call_sid)
                )
                session = session_result.scalar_one_or_none()
                
                if not session:
                    return None
                
                # Get conversation turns
                turns_result = await db.execute(
                    select(ConversationTurn)
                    .where(ConversationTurn.call_sid == call_sid)
                    .order_by(ConversationTurn.timestamp)
                )
                turns = turns_result.scalars().all()
                
                # Decrypt and build context
                context = ConversationContext(
                    call_sid=call_sid,
                    turns=[],
                    extracted_information=session.extracted_data or {}
                )
                
                for turn in turns:
                    # Decrypt content if needed
                    content = turn.content
                    if turn.role == 'user':
                        try:
                            decrypted_data = await decrypt_pii_data({'content': turn.content})
                            content = decrypted_data['content']
                        except:
                            pass  # Use original content if decryption fails
                    
                    context.turns.append({
                        'role': turn.role,
                        'content': content,
                        'timestamp': turn.timestamp
                    })
                
                self.active_sessions[call_sid] = context
                return context
                
        except Exception as e:
            logger.error(
                "Failed to restore conversation context",
                call_sid=call_sid,
                error=str(e)
            )
            return None
    
    async def _update_lead_information(
        self,
        call_sid: str,
        context: ConversationContext
    ) -> None:
        """Update lead information and scoring using LLM analysis."""
        try:
            # Use LLM service for advanced lead scoring
            lead_score, scoring_rationale = await openrouter_llm_service.calculate_lead_score(
                call_sid=call_sid,
                conversation_context=context
            )
            
            # Update database with new score
            if lead_score > 0:
                async with get_async_session() as db:
                    await db.execute(
                        update(CallSession)
                        .where(CallSession.call_sid == call_sid)
                        .values(
                            lead_score=lead_score,
                            extracted_data=context.extracted_information
                        )
                    )
                    await db.commit()
                    
                logger.info(
                    "Updated lead score using LLM analysis",
                    call_sid=call_sid,
                    lead_score=lead_score,
                    rationale_factors=len(scoring_rationale)
                )
            
            # Analyze conversation intent for additional insights
            try:
                intent_analysis = await openrouter_llm_service.analyze_conversation_intent(
                    call_sid=call_sid,
                    conversation_history=[
                        {'role': turn.role.value, 'content': turn.content}
                        for turn in context.get_recent_turns(10)
                    ]
                )
                
                logger.info(
                    "Analyzed conversation intent",
                    call_sid=call_sid,
                    intent=intent_analysis.get('intent'),
                    confidence=intent_analysis.get('confidence'),
                    buying_signals=len(intent_analysis.get('buying_signals', []))
                )
                
            except Exception as intent_error:
                logger.warning(
                    "Intent analysis failed",
                    call_sid=call_sid,
                    error=str(intent_error)
                )
                
        except Exception as e:
            logger.error(
                "Failed to update lead information with LLM",
                call_sid=call_sid,
                error=str(e)
            )
            
            # Fallback to simple keyword-based scoring
            await self._fallback_lead_scoring(call_sid, context)
    
    async def _fallback_lead_scoring(
        self,
        call_sid: str,
        context: ConversationContext
    ) -> None:
        """Fallback lead scoring when LLM analysis fails."""
        try:
            score_increase = 0
            recent_content = " ".join([
                turn.content for turn in context.get_recent_turns(3)
                if turn.role == ConversationRole.USER
            ]).lower()
            
            # Buying signals
            if any(word in recent_content for word in ['budget', 'price', 'cost', 'buy', 'purchase']):
                score_increase += 20
            
            if any(word in recent_content for word in ['timeline', 'when', 'soon', 'urgent']):
                score_increase += 15
            
            if any(word in recent_content for word in ['decision', 'approve', 'manager', 'team']):
                score_increase += 10
            
            # Update database if score changed
            if score_increase > 0:
                async with get_async_session() as db:
                    await db.execute(
                        update(CallSession)
                        .where(CallSession.call_sid == call_sid)
                        .values(lead_score=CallSession.lead_score + score_increase)
                    )
                    await db.commit()
                    
                logger.info(
                    "Updated lead score using fallback method",
                    call_sid=call_sid,
                    score_increase=score_increase
                )
                
        except Exception as e:
            logger.error(
                "Fallback lead scoring failed",
                call_sid=call_sid,
                error=str(e)
            )
    
    async def _log_salesforce_activity(
        self,
        contact_id: str,
        call_sid: str,
        duration_seconds: int,
        summary: str,
        lead_score: int
    ) -> None:
        """Log call activity in Salesforce."""
        try:
            task_data = {
                'WhoId': contact_id,
                'Subject': f'AI Agent Call - {call_sid}',
                'Description': f'{summary}\n\nCall Duration: {duration_seconds}s\nLead Score: {lead_score}',
                'Type': 'Call',
                'TaskSubtype': 'Call',
                'CallType': 'Inbound',
                'Priority': 'High' if lead_score > 60 else 'Normal',
                'Status': 'Completed'
            }
            
            salesforce_service = await get_salesforce_service()
            await salesforce_service.create_task(task_data)
            
            # Create lead if qualified
            if lead_score > 60:
                lead_data = {
                    'LastName': 'AI Qualified Lead',
                    'Phone': contact_id,  # Will be resolved by Salesforce service
                    'LeadSource': 'AI_Agent_Qualification',
                    'Status': 'Open - Not Contacted',
                    'Rating': 'Hot' if lead_score > 80 else 'Warm',
                    'Description': f'AI qualified lead from call {call_sid}. Score: {lead_score}'
                }
                
                await salesforce_service.create_lead(lead_data)
                
        except Exception as e:
            logger.error(
                "Failed to log Salesforce activity",
                contact_id=contact_id,
                call_sid=call_sid,
                error=str(e)
            )
    
    async def _generate_response_audio(self, text: str) -> Optional[bytes]:
        """
        Generate audio for AI response using ElevenLabs TTS.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data as bytes or None if generation fails
        """
        try:
            audio_data = await elevenlabs_service.synthesize_speech(
                text=text,
                optimize_for_phone=True,
                streaming=False  # Use standard generation for reliability
            )
            
            if audio_data:
                logger.debug(
                    "Generated response audio",
                    text_length=len(text),
                    audio_size=len(audio_data)
                )
                return audio_data
            else:
                logger.warning("Failed to generate audio for response", text_length=len(text))
                return None
                
        except Exception as e:
            logger.error(
                "Error generating response audio",
                text_length=len(text),
                error=str(e)
            )
            return None
    
    async def get_speech_service_health(self) -> Dict[str, Any]:
        """
        Get health status of speech services.
        
        Returns:
            Dictionary with health information
        """
        try:
            # Check ElevenLabs API usage and health
            usage_info = await elevenlabs_service.check_api_usage()
            
            # Determine health status
            if 'error' in usage_info:
                status = "unhealthy"
                api_accessible = False
            else:
                characters_remaining = usage_info.get('characters_remaining', 0)
                if characters_remaining < 1000:  # Low on characters
                    status = "degraded"
                else:
                    status = "healthy"
                api_accessible = True
            
            return {
                'service_name': 'ElevenLabs',
                'status': status,
                'api_accessible': api_accessible,
                'usage_info': usage_info,
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error checking speech service health", error=str(e))
            return {
                'service_name': 'ElevenLabs',
                'status': 'unhealthy',
                'api_accessible': False,
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def cleanup_expired_sessions(self) -> None:
        """Clean up expired conversation sessions."""
        current_time = datetime.utcnow()
        expired_sessions = [
            call_sid for call_sid, timeout in self.session_timeouts.items()
            if timeout < current_time
        ]
        
        for call_sid in expired_sessions:
            logger.info("Cleaning up expired session", call_sid=call_sid)
            await self.end_call_session(call_sid, "timeout")


# Global instance
call_handler = CallHandler()