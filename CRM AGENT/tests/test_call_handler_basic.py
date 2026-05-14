"""
Basic functionality tests for call handler core features.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.call_handler import CallHandler
from app.schemas.conversation import ConversationContext, ConversationRole


@pytest.mark.asyncio
async def test_call_handler_conversation_flow():
    """Test basic conversation flow without database dependencies."""
    handler = CallHandler()
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    # Set up a conversation context manually
    context = ConversationContext(
        call_sid=call_sid,
        turns=[],
        extracted_information={'phone': '+15551234567'}
    )
    handler.active_sessions[call_sid] = context
    
    # Mock external services
    with patch.object(handler, '_generate_ai_response') as mock_ai, \
         patch.object(handler, '_generate_response_audio') as mock_audio, \
         patch.object(handler, '_store_conversation_turn') as mock_store, \
         patch.object(handler, '_update_lead_information') as mock_update:
        
        mock_ai.return_value = ("Hello! How can I help you today?", False)
        mock_audio.return_value = b"audio_data"
        mock_store.return_value = None
        mock_update.return_value = None
        
        # Test conversation turn processing
        response, should_end, audio = await handler.process_conversation_turn(
            call_sid=call_sid,
            user_input="I'm interested in your services",
            confidence=0.95
        )
        
        # Verify response
        assert response == "Hello! How can I help you today?"
        assert should_end is False
        assert audio == b"audio_data"
        
        # Verify methods were called
        mock_ai.assert_called_once()
        mock_audio.assert_called_once()
        assert mock_store.call_count == 2  # User turn + AI turn
        mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_call_handler_lead_scoring():
    """Test lead scoring functionality."""
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
                content="I have a budget of $50,000 and need this done by next month",
                timestamp=datetime.utcnow()
            )
        ]
    )
    
    # Test fallback lead scoring (when LLM fails)
    with patch('app.services.call_handler.get_async_session') as mock_db:
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session
        
        await handler._fallback_lead_scoring(call_sid, context)
        
        # Should update database with increased score due to buying signals
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_call_handler_unclear_input():
    """Test handling of unclear input."""
    handler = CallHandler()
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    # Test first unclear input
    context = ConversationContext(call_sid=call_sid, turns=[])
    handler.active_sessions[call_sid] = context
    
    response, should_end = await handler._handle_unclear_input(call_sid, 0.3)
    
    assert "sorry" in response.lower()
    assert should_end is False


@pytest.mark.asyncio
async def test_call_handler_ai_response_generation():
    """Test AI response generation with fallback."""
    handler = CallHandler()
    context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef", turns=[])
    
    # Test greeting response
    response, should_end = await handler._generate_fallback_response("Hello there")
    assert "hello" in response.lower() or "great to hear" in response.lower()
    assert should_end is False
    
    # Test goodbye response
    response, should_end = await handler._generate_fallback_response("Thank you, goodbye")
    assert "thank you" in response.lower()
    assert should_end is True
    
    # Test information request
    response, should_end = await handler._generate_fallback_response("Tell me about your services")
    assert "information" in response.lower() or "services" in response.lower()
    assert should_end is False


@pytest.mark.asyncio
async def test_call_handler_session_management():
    """Test session management functionality."""
    handler = CallHandler()
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    # Test session creation
    context = ConversationContext(call_sid=call_sid, turns=[])
    handler.active_sessions[call_sid] = context
    handler.session_timeouts[call_sid] = datetime.utcnow()
    
    assert call_sid in handler.active_sessions
    assert call_sid in handler.session_timeouts
    
    # Test session cleanup
    with patch.object(handler, 'end_call_session') as mock_end:
        mock_end.return_value = None
        
        await handler.cleanup_expired_sessions()
        
        # Should clean up expired session
        mock_end.assert_called_once_with(call_sid, "timeout")


def test_call_handler_initialization():
    """Test call handler initialization."""
    handler = CallHandler()
    
    assert handler.active_sessions == {}
    assert handler.session_timeouts == {}
    assert hasattr(handler, 'initialize_call_session')
    assert hasattr(handler, 'process_conversation_turn')
    assert hasattr(handler, 'end_call_session')


@pytest.mark.asyncio
async def test_call_outcome_determination():
    """Test call outcome determination logic."""
    handler = CallHandler()
    
    # Test should_end_call logic
    analysis_data = {'intent': 'conversation_end'}
    response_text = "Thank you for calling! Have a great day!"
    
    should_end = handler._should_end_call(analysis_data, response_text)
    assert should_end is True
    
    # Test normal conversation
    analysis_data = {'intent': 'information_seeking'}
    response_text = "I can help you with that information."
    
    should_end = handler._should_end_call(analysis_data, response_text)
    assert should_end is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])