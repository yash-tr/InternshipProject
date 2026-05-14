"""
End-to-end tests for call handler functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.call_handler import CallHandler
from app.schemas.conversation import ConversationContext, ConversationRole


@pytest.mark.asyncio
async def test_basic_call_flow_end_to_end():
    """Test basic call flow from initialization to completion."""
    handler = CallHandler()
    call_sid = "CA1234567890abcdef1234567890abcdef"
    caller_phone = "+15551234567"
    
    # Mock all external dependencies
    with patch('app.services.call_handler.get_async_session') as mock_db, \
         patch('app.services.call_handler.get_salesforce_service') as mock_sf, \
         patch('app.services.call_handler.encrypt_pii_data') as mock_encrypt, \
         patch('app.services.call_handler.elevenlabs_service') as mock_elevenlabs, \
         patch('app.services.call_handler.openrouter_llm_service') as mock_llm:
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session
        
        # Mock the database query result properly
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result
        
        mock_sf_service = AsyncMock()
        mock_sf_service.find_or_create_contact.return_value = {'Id': '0031234567890AB', 'is_new': True}
        mock_sf_service.create_task.return_value = {'Id': '00T1234567890AB'}
        mock_sf.return_value = mock_sf_service
        
        mock_encrypt.return_value = {
            'caller_phone': 'encrypted_phone',
            'contact_id': 'encrypted_contact_id'
        }
        
        mock_elevenlabs.synthesize_speech.return_value = b"audio_data"
        
        mock_llm.generate_response.return_value = ("Hello! How can I help you today?", 50, {})
        mock_llm.calculate_lead_score.return_value = (25, {"engagement": "initial"})
        
        # Mock database session object
        mock_call_session = MagicMock()
        mock_call_session.id = 1
        mock_call_session.call_sid = call_sid
        mock_call_session.caller_phone = "encrypted_phone"
        mock_call_session.contact_id = "encrypted_contact_id"
        mock_call_session.start_time = datetime.utcnow()
        mock_call_session.lead_score = 0
        mock_session.refresh = AsyncMock()
        
        # 1. Initialize call session
        session_response = await handler.initialize_call_session(call_sid, caller_phone)
        
        # Verify session was created
        assert call_sid in handler.active_sessions
        assert call_sid in handler.session_timeouts
        mock_sf_service.find_or_create_contact.assert_called_once()
        
        # 2. Process first conversation turn
        response1, should_end1, audio1 = await handler.process_conversation_turn(
            call_sid=call_sid,
            user_input="Hello, I'm interested in your services",
            confidence=0.95
        )
        
        assert response1 == "Hello! How can I help you today?"
        assert should_end1 is False
        assert audio1 == b"audio_data"
        
        # 3. Process second conversation turn with buying signals
        mock_llm.generate_response.return_value = ("That's great! Let me get some details.", False, {})
        mock_llm.calculate_lead_score.return_value = (65, {"budget_mentioned": True})
        
        response2, should_end2, audio2 = await handler.process_conversation_turn(
            call_sid=call_sid,
            user_input="What's your pricing? I have a budget of $10,000",
            confidence=0.92
        )
        
        assert response2 == "That's great! Let me get some details."
        assert should_end2 is False
        
        # 4. End conversation
        mock_llm.generate_response.return_value = ("Thank you for calling! Have a great day!", True, {})
        
        response3, should_end3, audio3 = await handler.process_conversation_turn(
            call_sid=call_sid,
            user_input="Thank you, goodbye",
            confidence=0.88
        )
        
        assert response3 == "Thank you for calling! Have a great day!"
        assert should_end3 is True
        
        # 5. End call session
        mock_result_end = AsyncMock()
        mock_result_end.scalar_one_or_none = MagicMock(return_value=mock_call_session)
        mock_session.execute.return_value = mock_result_end
        
        await handler.end_call_session(call_sid, "completed")
        
        # Verify cleanup
        assert call_sid not in handler.active_sessions
        assert call_sid not in handler.session_timeouts
        
        # Verify Salesforce integration was called
        mock_sf_service.create_task.assert_called()


@pytest.mark.asyncio
async def test_call_handler_error_handling():
    """Test call handler error handling scenarios."""
    handler = CallHandler()
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    # Test processing turn without active session
    with patch.object(handler, '_restore_conversation_context') as mock_restore:
        mock_restore.return_value = None
        
        with pytest.raises(Exception):
            await handler.process_conversation_turn(call_sid, "Hello")
    
    # Test unclear input handling
    context = ConversationContext(call_sid=call_sid, turns=[])
    handler.active_sessions[call_sid] = context
    
    with patch.object(handler, '_generate_response_audio') as mock_audio:
        mock_audio.return_value = b"audio_data"
        
        response, should_end, audio = await handler.process_conversation_turn(
            call_sid=call_sid,
            user_input="",  # Empty input
            confidence=0.2
        )
        
        assert "sorry" in response.lower()
        assert should_end is False
        assert audio == b"audio_data"


@pytest.mark.asyncio
async def test_lead_scoring_functionality():
    """Test lead scoring with buying signals."""
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
    
    with patch('app.services.call_handler.get_async_session') as mock_db, \
         patch('app.services.call_handler.openrouter_llm_service') as mock_llm:
        
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session
        
        # Mock LLM service failure to test fallback scoring
        mock_llm.calculate_lead_score.side_effect = Exception("LLM Error")
        
        await handler._update_lead_information(call_sid, context)
        
        # Should fall back to simple keyword-based scoring
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])