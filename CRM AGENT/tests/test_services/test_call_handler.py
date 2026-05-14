"""
Unit tests for call handler service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.call_handler import CallHandler, call_handler
from app.schemas.call_session import CallSessionResponse
from app.schemas.conversation import ConversationContext, ConversationRole


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch('app.services.call_handler.get_async_session') as mock:
        session = AsyncMock()
        # Mock the async context manager properly
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        mock.return_value = async_context
        yield session


@pytest.fixture
def mock_salesforce_service():
    """Mock Salesforce service."""
    with patch('app.services.call_handler.get_salesforce_service') as mock:
        service_mock = AsyncMock()
        service_mock.find_or_create_contact.return_value = {
            'Id': '0031234567890AB',
            'is_new': True
        }
        service_mock.create_task.return_value = {'Id': '00T1234567890AB'}
        service_mock.create_lead.return_value = {'Id': '00Q1234567890AB'}
        mock.return_value = service_mock
        yield service_mock


@pytest.fixture
def mock_encryption():
    """Mock encryption utilities."""
    with patch('app.services.call_handler.encrypt_pii_data') as encrypt_mock, \
         patch('app.services.call_handler.decrypt_pii_data') as decrypt_mock:
        
        encrypt_mock.return_value = {
            'caller_phone': 'encrypted_phone',
            'contact_id': 'encrypted_contact_id',
            'content': 'encrypted_content'
        }
        decrypt_mock.return_value = {
            'caller_phone': '+15551234567',
            'contact_id': '0031234567890AB',
            'content': 'decrypted_content'
        }
        yield encrypt_mock, decrypt_mock


class TestCallHandler:
    """Test call handler functionality."""
    
    def test_init(self):
        """Test call handler initialization."""
        handler = CallHandler()
        
        assert handler.active_sessions == {}
        assert handler.session_timeouts == {}
    
    @pytest.mark.asyncio
    async def test_initialize_call_session_new(
        self, 
        mock_db_session, 
        mock_salesforce_service, 
        mock_encryption
    ):
        """Test initializing a new call session."""
        # Mock database query for existing session
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Mock database session creation
        mock_call_session = MagicMock()
        mock_call_session.id = 1
        mock_call_session.call_sid = "CA1234567890abcdef1234567890abcdef"
        mock_call_session.caller_phone = "encrypted_phone"
        mock_call_session.contact_id = "encrypted_contact_id"
        mock_call_session.start_time = datetime.utcnow()
        mock_call_session.lead_score = 0
        
        mock_db_session.refresh = AsyncMock()
        mock_db_session.refresh.return_value = None
        
        handler = CallHandler()
        result = await handler.initialize_call_session(
            call_sid="CA1234567890abcdef1234567890abcdef",
            caller_phone="+15551234567",
            call_status="in-progress"
        )
        
        # Verify Salesforce contact creation was called
        mock_salesforce_service.find_or_create_contact.assert_called_once_with(
            phone="+15551234567",
            additional_data={'LeadSource': 'AI_Calling_Agent'}
        )
        
        # Verify session was added to active sessions
        assert "CA1234567890abcdef1234567890abcdef" in handler.active_sessions
        assert "CA1234567890abcdef1234567890abcdef" in handler.session_timeouts
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_call_session_existing(self, mock_db_session):
        """Test initializing an existing call session."""
        # Mock existing session
        existing_session = MagicMock()
        existing_session.id = 1
        existing_session.call_sid = "CA1234567890abcdef1234567890abcdef"
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = existing_session
        
        handler = CallHandler()
        result = await handler.initialize_call_session(
            call_sid="CA1234567890abcdef1234567890abcdef",
            caller_phone="+15551234567"
        )
        
        # Should not create new session
        mock_db_session.add.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_initialize_call_session_salesforce_error(
        self, 
        mock_db_session, 
        mock_salesforce_service, 
        mock_encryption
    ):
        """Test call session initialization with Salesforce error."""
        # Mock database query for existing session
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Mock Salesforce error
        mock_salesforce_service.find_or_create_contact.side_effect = Exception("SF Error")
        
        # Mock database session creation
        mock_call_session = MagicMock()
        mock_call_session.id = 1
        mock_db_session.refresh = AsyncMock()
        
        handler = CallHandler()
        result = await handler.initialize_call_session(
            call_sid="CA1234567890abcdef1234567890abcdef",
            caller_phone="+15551234567"
        )
        
        # Should continue without Salesforce contact
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_conversation_turn_success(self):
        """Test successful conversation turn processing."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Set up active session
        context = ConversationContext(
            call_sid=call_sid,
            turns=[],
            extracted_information={'phone': '+15551234567'}
        )
        handler.active_sessions[call_sid] = context
        
        with patch.object(handler, '_store_conversation_turn') as mock_store, \
             patch.object(handler, '_generate_ai_response') as mock_generate, \
             patch.object(handler, '_generate_response_audio') as mock_audio, \
             patch.object(handler, '_update_lead_information') as mock_update:
            
            mock_generate.return_value = ("Thank you for that information!", False)
            mock_audio.return_value = b"audio_data"
            mock_store.return_value = None
            mock_update.return_value = None
            
            response, should_end, audio_data = await handler.process_conversation_turn(
                call_sid=call_sid,
                user_input="I'm interested in your services",
                confidence=0.95,
                audio_url="https://example.com/audio.mp3"
            )
            
            assert response == "Thank you for that information!"
            assert should_end is False
            assert audio_data == b"audio_data"
            
            # Verify methods were called
            assert mock_store.call_count == 2  # User turn + AI turn
            mock_generate.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_conversation_turn_empty_input(self):
        """Test conversation turn with empty input."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Set up active session
        context = ConversationContext(call_sid=call_sid, turns=[])
        handler.active_sessions[call_sid] = context
        
        with patch.object(handler, '_handle_unclear_input') as mock_handle, \
             patch.object(handler, '_generate_response_audio') as mock_audio:
            
            mock_handle.return_value = ("I didn't catch that.", False)
            mock_audio.return_value = b"audio_data"
            
            response, should_end, audio_data = await handler.process_conversation_turn(
                call_sid=call_sid,
                user_input="",
                confidence=0.3
            )
            
            assert "didn't catch" in response
            assert should_end is False
            assert audio_data == b"audio_data"
            mock_handle.assert_called_once_with(call_sid, 0.3)
    
    @pytest.mark.asyncio
    async def test_process_conversation_turn_no_session(self):
        """Test conversation turn with no active session."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        with patch.object(handler, '_restore_conversation_context') as mock_restore:
            mock_restore.return_value = None
            
            with pytest.raises(HTTPException):  # Should raise HTTPException
                await handler.process_conversation_turn(
                    call_sid=call_sid,
                    user_input="Hello"
                )
    
    @pytest.mark.asyncio
    async def test_end_call_session_success(self, mock_db_session, mock_salesforce_service):
        """Test successful call session ending."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Mock existing session
        mock_session = MagicMock()
        mock_session.start_time = datetime.utcnow() - timedelta(minutes=5)
        mock_session.contact_id = "0031234567890AB"
        mock_session.lead_score = 75
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_session
        
        # Set up active session
        context = ConversationContext(call_sid=call_sid, turns=[])
        handler.active_sessions[call_sid] = context
        handler.session_timeouts[call_sid] = datetime.utcnow() + timedelta(minutes=30)
        
        with patch.object(handler, '_log_salesforce_activity') as mock_log:
            mock_log.return_value = None
            
            await handler.end_call_session(
                call_sid=call_sid,
                call_outcome="completed",
                final_summary="Customer interested in services"
            )
            
            # Verify database update
            mock_db_session.execute.assert_called()
            mock_db_session.commit.assert_called()
            
            # Verify Salesforce logging
            mock_log.assert_called_once()
            
            # Verify cleanup
            assert call_sid not in handler.active_sessions
            assert call_sid not in handler.session_timeouts
    
    @pytest.mark.asyncio
    async def test_handle_unclear_input_first_time(self):
        """Test handling unclear input for the first time."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Set up context with no unclear responses
        from app.schemas.conversation import ConversationTurnResponse
        context = ConversationContext(
            call_sid=call_sid,
            turns=[
                ConversationTurnResponse(
                    id=1,
                    call_sid=call_sid,
                    role=ConversationRole.USER,
                    content="Hello",
                    timestamp=datetime.utcnow()
                ),
                ConversationTurnResponse(
                    id=2,
                    call_sid=call_sid,
                    role=ConversationRole.ASSISTANT,
                    content="How can I help?",
                    timestamp=datetime.utcnow()
                )
            ]
        )
        handler.active_sessions[call_sid] = context
        
        response, should_end = await handler._handle_unclear_input(call_sid, 0.3)
        
        assert "sorry" in response.lower() and ("unclear" in response.lower() or "catch" in response.lower())
        assert should_end is False
    
    @pytest.mark.asyncio
    async def test_handle_unclear_input_repeated(self):
        """Test handling repeated unclear input."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Set up context with multiple unclear responses
        from app.schemas.conversation import ConversationTurnResponse
        context = ConversationContext(
            call_sid=call_sid,
            turns=[
                ConversationTurnResponse(
                    id=1,
                    call_sid=call_sid,
                    role=ConversationRole.ASSISTANT,
                    content="I didn't catch that",
                    timestamp=datetime.utcnow()
                ),
                ConversationTurnResponse(
                    id=2,
                    call_sid=call_sid,
                    role=ConversationRole.ASSISTANT,
                    content="Could you repeat that?",
                    timestamp=datetime.utcnow()
                ),
                ConversationTurnResponse(
                    id=3,
                    call_sid=call_sid,
                    role=ConversationRole.ASSISTANT,
                    content="I'm having trouble",
                    timestamp=datetime.utcnow()
                )
            ]
        )
        handler.active_sessions[call_sid] = context
        
        response, should_end = await handler._handle_unclear_input(call_sid, 0.2)
        
        assert "transfer you to a human" in response.lower()
        assert should_end is False
    
    @pytest.mark.asyncio
    async def test_generate_ai_response_greeting(self):
        """Test AI response generation for greeting."""
        handler = CallHandler()
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef", turns=[])
        
        response, should_end = await handler._generate_ai_response(context, "Hello there")
        
        assert "hello" in response.lower() or "great to hear" in response.lower()
        assert should_end is False
    
    @pytest.mark.asyncio
    async def test_generate_ai_response_goodbye(self):
        """Test AI response generation for goodbye."""
        handler = CallHandler()
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef", turns=[])
        
        response, should_end = await handler._generate_ai_response(context, "Thank you, goodbye")
        
        assert "thank you" in response.lower()
        assert should_end is True
    
    @pytest.mark.asyncio
    async def test_generate_ai_response_information_request(self):
        """Test AI response generation for information request."""
        handler = CallHandler()
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef", turns=[])
        
        response, should_end = await handler._generate_ai_response(context, "Tell me about your services")
        
        assert "information" in response.lower() or "services" in response.lower()
        assert should_end is False
    
    @pytest.mark.asyncio
    async def test_store_conversation_turn(self, mock_db_session, mock_encryption):
        """Test storing conversation turn."""
        handler = CallHandler()
        
        from app.schemas.conversation import ConversationTurnCreate
        turn = ConversationTurnCreate(
            call_sid="CA1234567890abcdef1234567890abcdef",
            role=ConversationRole.USER,
            content="Hello, I need help",
            timestamp=datetime.utcnow()
        )
        
        await handler._store_conversation_turn(turn)
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Verify encryption was called for user content
        mock_encryption[0].assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_lead_information_buying_signals(self, mock_db_session):
        """Test lead information update with buying signals."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create context with buying signals
        from app.schemas.conversation import ConversationTurnResponse
        context = ConversationContext(
            call_sid=call_sid,
            turns=[
                ConversationTurnResponse(
                    id=1,
                    call_sid=call_sid,
                    role=ConversationRole.USER,
                    content="What's your budget for this project? We need it soon.",
                    timestamp=datetime.utcnow()
                ),
                ConversationTurnResponse(
                    id=2,
                    call_sid=call_sid,
                    role=ConversationRole.USER,
                    content="I need to get approval from my manager.",
                    timestamp=datetime.utcnow()
                )
            ]
        )
        
        # Mock the LLM service to avoid actual API calls
        with patch('app.services.call_handler.openrouter_llm_service') as mock_llm:
            mock_llm.calculate_lead_score.side_effect = Exception("LLM Error")
            
            await handler._update_lead_information(call_sid, context)
            
            # Should fall back to simple scoring and update database
            mock_db_session.execute.assert_called_once()
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_salesforce_activity_qualified_lead(self, mock_salesforce_service):
        """Test Salesforce activity logging for qualified lead."""
        handler = CallHandler()
        
        await handler._log_salesforce_activity(
            contact_id="0031234567890AB",
            call_sid="CA1234567890abcdef1234567890abcdef",
            duration_seconds=180,
            summary="Customer very interested in services",
            lead_score=85
        )
        
        # Verify task creation
        mock_salesforce_service.create_task.assert_called_once()
        task_data = mock_salesforce_service.create_task.call_args[0][0]
        assert task_data['WhoId'] == "0031234567890AB"
        assert task_data['Priority'] == 'High'  # High score = High priority
        
        # Verify lead creation for qualified lead
        mock_salesforce_service.create_lead.assert_called_once()
        lead_data = mock_salesforce_service.create_lead.call_args[0][0]
        assert lead_data['Rating'] == 'Hot'  # Score > 80 = Hot
    
    @pytest.mark.asyncio
    async def test_log_salesforce_activity_unqualified_lead(self, mock_salesforce_service):
        """Test Salesforce activity logging for unqualified lead."""
        handler = CallHandler()
        
        await handler._log_salesforce_activity(
            contact_id="0031234567890AB",
            call_sid="CA1234567890abcdef1234567890abcdef",
            duration_seconds=60,
            summary="Brief inquiry",
            lead_score=30
        )
        
        # Verify task creation
        mock_salesforce_service.create_task.assert_called_once()
        task_data = mock_salesforce_service.create_task.call_args[0][0]
        assert task_data['Priority'] == 'Normal'  # Low score = Normal priority
        
        # Should not create lead for unqualified prospect
        mock_salesforce_service.create_lead.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        handler = CallHandler()
        
        # Set up expired and active sessions with valid call SIDs
        expired_call_sid = "CA1234567890abcdef1234567890abcde1"
        active_call_sid = "CA1234567890abcdef1234567890abcde2"
        
        handler.session_timeouts[expired_call_sid] = datetime.utcnow() - timedelta(minutes=1)
        handler.session_timeouts[active_call_sid] = datetime.utcnow() + timedelta(minutes=30)
        
        handler.active_sessions[expired_call_sid] = ConversationContext(call_sid=expired_call_sid, turns=[])
        handler.active_sessions[active_call_sid] = ConversationContext(call_sid=active_call_sid, turns=[])
        
        with patch.object(handler, 'end_call_session') as mock_end:
            mock_end.return_value = None
            
            await handler.cleanup_expired_sessions()
            
            # Should only end expired session
            mock_end.assert_called_once_with(expired_call_sid, "timeout")
            
            # Active session should remain
            assert active_call_sid in handler.active_sessions
            assert active_call_sid in handler.session_timeouts


class TestCallHandlerGlobalInstance:
    """Test the global call handler instance."""
    
    def test_global_instance_exists(self):
        """Test that global instance is properly initialized."""
        assert call_handler is not None
        assert isinstance(call_handler, CallHandler)
        assert hasattr(call_handler, 'active_sessions')
        assert hasattr(call_handler, 'session_timeouts')
    
    def test_global_instance_methods(self):
        """Test that global instance has all required methods."""
        required_methods = [
            'initialize_call_session',
            'process_conversation_turn',
            'end_call_session',
            'cleanup_expired_sessions'
        ]
        
        for method_name in required_methods:
            assert hasattr(call_handler, method_name)
            assert callable(getattr(call_handler, method_name))


@pytest.mark.integration
class TestCallHandlerIntegration:
    """Integration tests for call handler."""
    
    @pytest.mark.asyncio
    async def test_full_call_session_lifecycle(
        self, 
        mock_db_session, 
        mock_salesforce_service, 
        mock_encryption
    ):
        """Test complete call session lifecycle."""
        handler = CallHandler()
        call_sid = "CA1234567890abcdef1234567890abcdef"
        caller_phone = "+15551234567"
        
        # Mock database responses
        mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
            None,  # No existing session
            MagicMock(  # Session for ending
                start_time=datetime.utcnow() - timedelta(minutes=5),
                contact_id="0031234567890AB",
                lead_score=75
            )
        ]
        
        mock_call_session = MagicMock()
        mock_call_session.id = 1
        mock_db_session.refresh = AsyncMock()
        
        with patch.object(handler, '_store_conversation_turn') as mock_store, \
             patch.object(handler, '_log_salesforce_activity') as mock_log:
            
            mock_store.return_value = None
            mock_log.return_value = None
            
            # 1. Initialize session
            session = await handler.initialize_call_session(call_sid, caller_phone)
            assert call_sid in handler.active_sessions
            
            # 2. Process conversation turns
            response1, end1, audio1 = await handler.process_conversation_turn(
                call_sid, "Hello, I'm interested in your services"
            )
            assert not end1
            
            response2, end2, audio2 = await handler.process_conversation_turn(
                call_sid, "What's your pricing? I have budget approved."
            )
            assert not end2
            
            response3, end3, audio3 = await handler.process_conversation_turn(
                call_sid, "Thank you, goodbye"
            )
            assert end3
            
            # 3. End session
            await handler.end_call_session(call_sid, "completed")
            assert call_sid not in handler.active_sessions
            
            # Verify all interactions
            mock_salesforce_service.find_or_create_contact.assert_called_once()
            assert mock_store.call_count >= 6  # At least 3 user + 3 AI turns
            mock_log.assert_called_once()