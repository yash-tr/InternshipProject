"""
Unit tests for OpenRouter LLM service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from app.services.openrouter_llm import (
    OpenRouterLLMService, ConversationSession, TokenUsage
)
from app.schemas.conversation import ConversationContext, ConversationRole


class TestTokenUsage:
    """Test TokenUsage dataclass functionality."""
    
    def test_token_usage_initialization(self):
        """Test TokenUsage initialization with default values."""
        usage = TokenUsage()
        
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_estimate == 0.0
    
    def test_add_usage(self):
        """Test adding usage data to TokenUsage."""
        usage = TokenUsage()
        
        usage_data = {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150
        }
        
        usage.add_usage(usage_data)
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cost_estimate > 0  # Should calculate some cost
    
    def test_add_usage_accumulates(self):
        """Test that multiple add_usage calls accumulate."""
        usage = TokenUsage()
        
        usage.add_usage({'prompt_tokens': 50, 'completion_tokens': 25, 'total_tokens': 75})
        usage.add_usage({'prompt_tokens': 30, 'completion_tokens': 20, 'total_tokens': 50})
        
        assert usage.prompt_tokens == 80
        assert usage.completion_tokens == 45
        assert usage.total_tokens == 125


class TestConversationSession:
    """Test ConversationSession dataclass functionality."""
    
    def test_conversation_session_initialization(self):
        """Test ConversationSession initialization."""
        call_sid = "CA1234567890abcdef1234567890abcdef"
        session = ConversationSession(call_sid=call_sid)
        
        assert session.call_sid == call_sid
        assert session.contact_context == {}
        assert session.conversation_history == []
        assert session.extracted_information == {}
        assert session.lead_score == 0
        assert session.current_intent is None
        assert session.buying_signals == []
        assert session.objections == []
        assert isinstance(session.token_usage, TokenUsage)
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_updated, datetime)
    
    def test_add_message(self):
        """Test adding messages to conversation history."""
        session = ConversationSession(call_sid="test_call")
        
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]['role'] == "user"
        assert session.conversation_history[0]['content'] == "Hello"
        assert session.conversation_history[1]['role'] == "assistant"
        assert session.conversation_history[1]['content'] == "Hi there!"
        assert 'timestamp' in session.conversation_history[0]
    
    def test_add_message_limits_history(self):
        """Test that conversation history is limited to 20 messages."""
        session = ConversationSession(call_sid="test_call")
        
        # Add 25 messages
        for i in range(25):
            session.add_message("user", f"Message {i}")
        
        # Should only keep the last 20
        assert len(session.conversation_history) == 20
        assert session.conversation_history[0]['content'] == "Message 5"
        assert session.conversation_history[-1]['content'] == "Message 24"
    
    def test_get_context_summary(self):
        """Test conversation context summary generation."""
        session = ConversationSession(call_sid="test_call")
        
        # Test empty conversation
        summary = session.get_context_summary()
        assert "New conversation" in summary
        
        # Add some messages
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi!")
        
        summary = session.get_context_summary()
        assert "2 messages" in summary
        assert "minutes" in summary


class TestOpenRouterLLMService:
    """Test OpenRouter LLM service functionality."""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing."""
        with patch('app.services.openrouter_llm.get_settings') as mock_settings:
            mock_settings.return_value.OPENROUTER_API_KEY = "test_key"
            mock_settings.return_value.OPENROUTER_MODEL = "test_model"
            
            service = OpenRouterLLMService()
            return service
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for testing."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test AI response"
        mock_response.usage.total_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client
    
    def test_service_initialization(self, llm_service):
        """Test LLM service initialization."""
        assert llm_service.model_name == "test_model"
        assert llm_service.max_tokens == 150
        assert llm_service.temperature == 0.7
        assert llm_service.active_sessions == {}
        assert isinstance(llm_service.total_usage, TokenUsage)
        assert isinstance(llm_service.daily_usage, TokenUsage)
    
    @pytest.mark.asyncio
    async def test_generate_response_new_session(self, llm_service, mock_openai_client):
        """Test generating response for new conversation session."""
        llm_service.client = mock_openai_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        user_input = "Hello, I'm interested in your services"
        
        response_text, tokens_used, analysis_data = await llm_service.generate_response(
            call_sid=call_sid,
            user_input=user_input
        )
        
        assert response_text == "Test AI response"
        assert tokens_used == 50
        assert isinstance(analysis_data, dict)
        assert call_sid in llm_service.active_sessions
        
        # Verify session was created
        session = llm_service.active_sessions[call_sid]
        assert len(session.conversation_history) == 2  # User + assistant messages
        assert session.conversation_history[0]['role'] == 'user'
        assert session.conversation_history[0]['content'] == user_input
        assert session.conversation_history[1]['role'] == 'assistant'
        assert session.conversation_history[1]['content'] == "Test AI response"
    
    @pytest.mark.asyncio
    async def test_generate_response_existing_session(self, llm_service, mock_openai_client):
        """Test generating response for existing conversation session."""
        llm_service.client = mock_openai_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create existing session
        session = ConversationSession(call_sid=call_sid)
        session.add_message("user", "Previous message")
        session.add_message("assistant", "Previous response")
        llm_service.active_sessions[call_sid] = session
        
        user_input = "Follow-up question"
        
        response_text, tokens_used, analysis_data = await llm_service.generate_response(
            call_sid=call_sid,
            user_input=user_input
        )
        
        assert response_text == "Test AI response"
        assert tokens_used == 50
        
        # Verify session was updated
        updated_session = llm_service.active_sessions[call_sid]
        assert len(updated_session.conversation_history) == 4  # 2 previous + 2 new
        assert updated_session.conversation_history[-2]['content'] == user_input
        assert updated_session.conversation_history[-1]['content'] == "Test AI response"
    
    @pytest.mark.asyncio
    async def test_generate_response_with_contact_context(self, llm_service, mock_openai_client):
        """Test generating response with Salesforce contact context."""
        llm_service.client = mock_openai_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        user_input = "I need information"
        contact_context = {
            'Name': 'John Doe',
            'Company': 'Acme Corp',
            'Industry': 'Technology'
        }
        
        response_text, tokens_used, analysis_data = await llm_service.generate_response(
            call_sid=call_sid,
            user_input=user_input,
            contact_context=contact_context
        )
        
        assert response_text == "Test AI response"
        
        # Verify contact context was stored in session
        session = llm_service.active_sessions[call_sid]
        assert session.contact_context == contact_context
    
    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, llm_service):
        """Test error handling in response generation."""
        # Mock client to raise exception
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        llm_service.client = mock_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        user_input = "Test input"
        
        response_text, tokens_used, analysis_data = await llm_service.generate_response(
            call_sid=call_sid,
            user_input=user_input
        )
        
        # Should return fallback response
        assert "I apologize" in response_text or "I'm sorry" in response_text
        assert tokens_used == 0
        assert 'error' in analysis_data
    
    @pytest.mark.asyncio
    async def test_analyze_conversation_intent(self, llm_service, mock_openai_client):
        """Test conversation intent analysis."""
        # Mock response for intent analysis
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """Intent: sales_inquiry
Confidence: 0.85
Buying Signals: budget, timeline
Objections: price
Key Topics: services, pricing"""
        mock_openai_client.chat.completions.create.return_value = mock_response
        llm_service.client = mock_openai_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create session with conversation history
        session = ConversationSession(call_sid=call_sid)
        session.add_message("user", "I'm interested in your services")
        session.add_message("assistant", "Great! What's your budget?")
        llm_service.active_sessions[call_sid] = session
        
        conversation_history = [
            {'role': 'user', 'content': 'I need services'},
            {'role': 'assistant', 'content': 'What\'s your budget?'}
        ]
        
        analysis = await llm_service.analyze_conversation_intent(
            call_sid=call_sid,
            conversation_history=conversation_history
        )
        
        assert analysis['intent'] == 'sales_inquiry'
        assert analysis['confidence'] == 0.85
        assert 'budget' in analysis['buying_signals']
        assert 'timeline' in analysis['buying_signals']
        assert 'price' in analysis['objections']
        assert 'services' in analysis['key_topics']
    
    @pytest.mark.asyncio
    async def test_calculate_lead_score(self, llm_service, mock_openai_client):
        """Test lead score calculation."""
        # Mock response for lead scoring
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """Score: 75
Rationale: Strong buying signals detected including budget discussion and timeline urgency"""
        mock_openai_client.chat.completions.create.return_value = mock_response
        llm_service.client = mock_openai_client
        
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create session
        session = ConversationSession(call_sid=call_sid)
        session.buying_signals = ['budget', 'timeline']
        session.extracted_information = {'company': 'Acme Corp'}
        llm_service.active_sessions[call_sid] = session
        
        # Mock conversation context
        mock_context = MagicMock()
        mock_context.extracted_information = {'company': 'Acme Corp'}
        
        lead_score, rationale = await llm_service.calculate_lead_score(
            call_sid=call_sid,
            conversation_context=mock_context
        )
        
        assert lead_score == 75
        assert 'buying signals' in rationale['explanation']
        assert session.lead_score == 75
    
    @pytest.mark.asyncio
    async def test_get_conversation_summary(self, llm_service):
        """Test conversation summary generation."""
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create session with data
        session = ConversationSession(call_sid=call_sid)
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        session.lead_score = 60
        session.current_intent = "information_seeking"
        session.buying_signals = ['budget']
        session.token_usage.total_tokens = 100
        session.token_usage.cost_estimate = 0.05
        llm_service.active_sessions[call_sid] = session
        
        summary = await llm_service.get_conversation_summary(call_sid)
        
        assert summary['call_sid'] == call_sid
        assert summary['message_count'] == 2
        assert summary['lead_score'] == 60
        assert summary['current_intent'] == "information_seeking"
        assert summary['buying_signals'] == ['budget']
        assert summary['token_usage']['total_tokens'] == 100
        assert summary['token_usage']['cost_estimate'] == 0.05
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self, llm_service):
        """Test session cleanup."""
        call_sid = "CA1234567890abcdef1234567890abcdef"
        
        # Create session
        session = ConversationSession(call_sid=call_sid)
        session.token_usage.total_tokens = 100
        llm_service.active_sessions[call_sid] = session
        
        assert call_sid in llm_service.active_sessions
        
        await llm_service.cleanup_session(call_sid)
        
        assert call_sid not in llm_service.active_sessions
    
    @pytest.mark.asyncio
    async def test_get_token_usage_stats(self, llm_service):
        """Test token usage statistics."""
        # Set up usage data
        llm_service.daily_usage.total_tokens = 500
        llm_service.daily_usage.cost_estimate = 0.25
        llm_service.total_usage.total_tokens = 2000
        llm_service.total_usage.cost_estimate = 1.00
        
        # Add active session
        session = ConversationSession(call_sid="test_call")
        llm_service.active_sessions["test_call"] = session
        
        stats = await llm_service.get_token_usage_stats()
        
        assert stats['daily_usage']['total_tokens'] == 500
        assert stats['daily_usage']['cost_estimate'] == 0.25
        assert stats['total_usage']['total_tokens'] == 2000
        assert stats['total_usage']['cost_estimate'] == 1.00
        assert stats['active_sessions'] == 1
        assert stats['model_name'] == "test_model"
    
    def test_build_system_prompt_basic(self, llm_service):
        """Test basic system prompt building."""
        session = ConversationSession(call_sid="test_call")
        
        prompt = llm_service._build_system_prompt(session)
        
        assert "professional AI sales assistant" in prompt
        assert "Keep responses under 150 tokens" in prompt
        assert "Ask one question at a time" in prompt
    
    def test_build_system_prompt_with_context(self, llm_service):
        """Test system prompt building with contact context."""
        session = ConversationSession(call_sid="test_call")
        session.contact_context = {
            'Name': 'John Doe',
            'Company': 'Acme Corp',
            'Industry': 'Technology'
        }
        session.current_intent = 'sales_inquiry'
        session.buying_signals = ['budget', 'timeline']
        session.objections = ['price']
        
        prompt = llm_service._build_system_prompt(session)
        
        assert "John Doe" in prompt
        assert "Acme Corp" in prompt
        assert "Technology" in prompt
        assert "sales_inquiry" in prompt
        assert "budget" in prompt
        assert "timeline" in prompt
        assert "price" in prompt
    
    @pytest.mark.asyncio
    async def test_build_message_history(self, llm_service):
        """Test message history building for LLM context."""
        session = ConversationSession(call_sid="test_call")
        
        # Add messages
        for i in range(15):
            session.add_message("user", f"User message {i}")
            session.add_message("assistant", f"Assistant message {i}")
        
        messages = await llm_service._build_message_history(session)
        
        # Should only include last 10 messages
        assert len(messages) == 10
        assert messages[0]['content'] == "User message 10"
        assert messages[-1]['content'] == "Assistant message 14"
    
    @pytest.mark.asyncio
    async def test_validate_response_safety_filter(self, llm_service):
        """Test response validation with safety filters."""
        # Test response with sensitive content
        unsafe_response = "Please provide your credit card number"
        
        validated = await llm_service._validate_response(unsafe_response)
        
        assert "credit card" not in validated.lower()
        assert "apologize" in validated.lower()
    
    @pytest.mark.asyncio
    async def test_validate_response_length_limit(self, llm_service):
        """Test response validation with length limits."""
        # Create very long response
        long_response = "This is a very long response. " * 20  # Over 500 chars
        
        validated = await llm_service._validate_response(long_response)
        
        # Should be truncated to first 2 sentences
        assert len(validated) < len(long_response)
        assert validated.endswith('.')
    
    def test_get_fallback_response(self, llm_service):
        """Test fallback response generation."""
        # Test different input types
        greeting_response = llm_service._get_fallback_response("hello")
        assert "Hello" in greeting_response or "Hi" in greeting_response
        
        help_response = llm_service._get_fallback_response("I need help")
        assert "information" in help_response.lower()
        
        short_response = llm_service._get_fallback_response("ok")
        assert "technical issue" in short_response.lower()
    
    def test_update_usage_tracking(self, llm_service):
        """Test token usage tracking updates."""
        initial_total = llm_service.total_usage.total_tokens
        initial_daily = llm_service.daily_usage.total_tokens
        
        llm_service._update_usage_tracking(100)
        
        assert llm_service.total_usage.total_tokens == initial_total + 100
        assert llm_service.daily_usage.total_tokens == initial_daily + 100
        assert llm_service.total_usage.cost_estimate > 0
        assert llm_service.daily_usage.cost_estimate > 0


class TestLLMServiceIntegration:
    """Integration tests for LLM service with other components."""
    
    @pytest.mark.asyncio
    async def test_conversation_flow_integration(self):
        """Test complete conversation flow with LLM service."""
        with patch('app.services.openrouter_llm.get_settings') as mock_settings:
            mock_settings.return_value.OPENROUTER_API_KEY = "test_key"
            mock_settings.return_value.OPENROUTER_MODEL = "test_model"
            
            service = OpenRouterLLMService()
            
            # Mock OpenAI client
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Thank you for your interest! What specific services are you looking for?"
            mock_response.usage.total_tokens = 45
            mock_client.chat.completions.create.return_value = mock_response
            service.client = mock_client
            
            call_sid = "CA1234567890abcdef1234567890abcdef"
            
            # First interaction
            response1, tokens1, analysis1 = await service.generate_response(
                call_sid=call_sid,
                user_input="Hi, I'm interested in your services"
            )
            
            assert "Thank you for your interest" in response1
            assert tokens1 == 45
            assert call_sid in service.active_sessions
            
            # Second interaction
            mock_response.choices[0].message.content = "Great! Can you tell me about your budget and timeline?"
            response2, tokens2, analysis2 = await service.generate_response(
                call_sid=call_sid,
                user_input="I need a solution for my company"
            )
            
            assert "budget and timeline" in response2
            
            # Verify session continuity
            session = service.active_sessions[call_sid]
            assert len(session.conversation_history) == 4  # 2 user + 2 assistant
            assert session.token_usage.total_tokens == tokens1 + tokens2
            
            # Cleanup
            await service.cleanup_session(call_sid)
            assert call_sid not in service.active_sessions