"""
Unit tests for conversation schema validation.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.conversation import (
    ConversationTurnBase, ConversationTurnCreate, ConversationTurnUpdate,
    ConversationTurnResponse, ConversationContext, ConversationAnalysis
)
from app.schemas.base import ConversationRole


class TestConversationTurnBase:
    """Test ConversationTurnBase schema."""
    
    def test_valid_conversation_turn_base(self):
        """Test creating valid ConversationTurnBase."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello, I'm interested in your services",
            "audio_url": "https://example.com/audio.wav",
            "transcription_confidence": 0.95
        }
        
        turn = ConversationTurnBase(**data)
        
        assert turn.call_sid == data["call_sid"]
        assert turn.role == ConversationRole.USER
        assert turn.content == data["content"]
        assert str(turn.audio_url) == data["audio_url"]
        assert turn.transcription_confidence == 0.95
    
    def test_conversation_turn_base_content_sanitization(self):
        """Test content sanitization in ConversationTurnBase."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello <script>alert('xss')</script> world"
        }
        
        turn = ConversationTurnBase(**data)
        assert "<script>" not in turn.content
        assert "alert('xss')" not in turn.content
        assert "Hello" in turn.content
        assert "world" in turn.content
    
    def test_conversation_turn_base_content_length_validation(self):
        """Test content length validation."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "a" * 6000  # Exceeds max length
        }
        
        turn = ConversationTurnBase(**data)
        assert len(turn.content) <= 5000
    
    def test_conversation_turn_base_invalid_call_sid(self):
        """Test invalid Call SID validation."""
        data = {
            "call_sid": "invalid",
            "role": ConversationRole.USER,
            "content": "Hello"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ConversationTurnBase(**data)
        
        assert "Invalid Call SID format" in str(exc_info.value)
    
    def test_conversation_turn_base_empty_content(self):
        """Test empty content validation."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": ""
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ConversationTurnBase(**data)
        
        assert "at least 1 characters" in str(exc_info.value)
    
    def test_conversation_turn_base_transcription_confidence_bounds(self):
        """Test transcription confidence validation bounds."""
        base_data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello"
        }
        
        # Test valid bounds
        turn = ConversationTurnBase(**base_data, transcription_confidence=0.0)
        assert turn.transcription_confidence == 0.0
        
        turn = ConversationTurnBase(**base_data, transcription_confidence=1.0)
        assert turn.transcription_confidence == 1.0
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            ConversationTurnBase(**base_data, transcription_confidence=-0.1)
        
        with pytest.raises(ValidationError):
            ConversationTurnBase(**base_data, transcription_confidence=1.1)


class TestConversationTurnCreate:
    """Test ConversationTurnCreate schema."""
    
    def test_valid_conversation_turn_create(self):
        """Test creating valid ConversationTurnCreate."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello, I'm interested in your services",
            "transcription_confidence": 0.95,
            "processing_time_ms": 150,
            "llm_tokens_used": 25
        }
        
        turn = ConversationTurnCreate(**data)
        
        assert turn.call_sid == data["call_sid"]
        assert turn.role == ConversationRole.USER
        assert turn.content == data["content"]
        assert turn.transcription_confidence == 0.95
        assert turn.processing_time_ms == 150
        assert turn.llm_tokens_used == 25
        assert isinstance(turn.timestamp, datetime)
    
    def test_conversation_turn_create_with_timestamp(self):
        """Test ConversationTurnCreate with provided timestamp."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello",
            "timestamp": timestamp
        }
        
        turn = ConversationTurnCreate(**data)
        assert turn.timestamp == timestamp
    
    def test_conversation_turn_create_negative_values(self):
        """Test validation of negative values."""
        base_data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello"
        }
        
        with pytest.raises(ValidationError):
            ConversationTurnCreate(**base_data, processing_time_ms=-1)
        
        with pytest.raises(ValidationError):
            ConversationTurnCreate(**base_data, llm_tokens_used=-1)


class TestConversationTurnUpdate:
    """Test ConversationTurnUpdate schema."""
    
    def test_valid_conversation_turn_update(self):
        """Test creating valid ConversationTurnUpdate."""
        data = {
            "content": "Updated content",
            "audio_url": "https://example.com/updated-audio.wav",
            "transcription_confidence": 0.98,
            "processing_time_ms": 200,
            "llm_tokens_used": 30
        }
        
        update = ConversationTurnUpdate(**data)
        
        assert update.content == "Updated content"
        assert str(update.audio_url) == data["audio_url"]
        assert update.transcription_confidence == 0.98
        assert update.processing_time_ms == 200
        assert update.llm_tokens_used == 30
    
    def test_conversation_turn_update_content_sanitization(self):
        """Test content sanitization in update."""
        data = {
            "content": "Updated <script>alert('xss')</script> content"
        }
        
        update = ConversationTurnUpdate(**data)
        assert "<script>" not in update.content
        assert "alert('xss')" not in update.content
    
    def test_conversation_turn_update_all_none(self):
        """Test ConversationTurnUpdate with all None values."""
        update = ConversationTurnUpdate()
        
        assert update.content is None
        assert update.audio_url is None
        assert update.transcription_confidence is None
        assert update.processing_time_ms is None
        assert update.llm_tokens_used is None


class TestConversationTurnResponse:
    """Test ConversationTurnResponse schema."""
    
    def test_valid_conversation_turn_response(self):
        """Test creating valid ConversationTurnResponse."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.ASSISTANT,
            "content": "Thank you for your interest. How can I help you today?",
            "timestamp": timestamp,
            "processing_time_ms": 150,
            "llm_tokens_used": 25
        }
        
        response = ConversationTurnResponse(**data)
        
        assert response.id == 1
        assert response.call_sid == data["call_sid"]
        assert response.role == ConversationRole.ASSISTANT
        assert response.content == data["content"]
        assert response.timestamp == timestamp
        assert response.processing_time_ms == 150
        assert response.llm_tokens_used == 25


class TestConversationContext:
    """Test ConversationContext schema."""
    
    def test_valid_conversation_context(self):
        """Test creating valid ConversationContext."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        turn_data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello",
            "timestamp": timestamp
        }
        turn = ConversationTurnResponse(**turn_data)
        
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "turns": [turn],
            "current_topic": "product_inquiry",
            "extracted_information": {"name": "John Doe", "company": "Acme Corp"},
            "lead_indicators": ["budget_mentioned", "timeline_discussed"]
        }
        
        context = ConversationContext(**data)
        
        assert context.call_sid == data["call_sid"]
        assert len(context.turns) == 1
        assert context.turns[0].content == "Hello"
        assert context.current_topic == "product_inquiry"
        assert context.extracted_information == {"name": "John Doe", "company": "Acme Corp"}
        assert context.lead_indicators == ["budget_mentioned", "timeline_discussed"]
    
    def test_conversation_context_current_topic_sanitization(self):
        """Test current topic sanitization."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "current_topic": "product <script>alert('xss')</script> inquiry"
        }
        
        context = ConversationContext(**data)
        assert "<script>" not in context.current_topic
        assert "alert('xss')" not in context.current_topic
    
    def test_conversation_context_get_recent_turns(self):
        """Test get_recent_turns method."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        turns = []
        for i in range(15):
            turn_data = {
                "id": i + 1,
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "role": ConversationRole.USER if i % 2 == 0 else ConversationRole.ASSISTANT,
                "content": f"Message {i + 1}",
                "timestamp": timestamp
            }
            turns.append(ConversationTurnResponse(**turn_data))
        
        context = ConversationContext(
            call_sid="CA1234567890abcdef1234567890abcdef",
            turns=turns
        )
        
        # Test default limit (10)
        recent_turns = context.get_recent_turns()
        assert len(recent_turns) == 10
        assert recent_turns[0].content == "Message 6"  # Last 10 messages
        assert recent_turns[-1].content == "Message 15"
        
        # Test custom limit
        recent_turns = context.get_recent_turns(limit=5)
        assert len(recent_turns) == 5
        assert recent_turns[0].content == "Message 11"
        assert recent_turns[-1].content == "Message 15"
    
    def test_conversation_context_get_conversation_summary(self):
        """Test get_conversation_summary method."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        # Test empty conversation
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef")
        assert context.get_conversation_summary() == "No conversation yet"
        
        # Test with turns
        turns = []
        for i in range(4):
            turn_data = {
                "id": i + 1,
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "role": ConversationRole.USER if i % 2 == 0 else ConversationRole.ASSISTANT,
                "content": f"Message {i + 1}",
                "timestamp": timestamp
            }
            turns.append(ConversationTurnResponse(**turn_data))
        
        context = ConversationContext(
            call_sid="CA1234567890abcdef1234567890abcdef",
            turns=turns
        )
        
        summary = context.get_conversation_summary()
        assert "User messages: 2" in summary
        assert "Assistant messages: 2" in summary
    
    def test_conversation_context_add_turn(self):
        """Test add_turn method."""
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef")
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        turn_data = {
            "id": 1,
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "role": ConversationRole.USER,
            "content": "Hello",
            "timestamp": timestamp
        }
        turn = ConversationTurnResponse(**turn_data)
        
        context.add_turn(turn)
        assert len(context.turns) == 1
        assert context.turns[0].content == "Hello"
    
    def test_conversation_context_add_turn_limit(self):
        """Test add_turn method with turn limit."""
        context = ConversationContext(call_sid="CA1234567890abcdef1234567890abcdef")
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        # Add 55 turns (exceeds limit of 50)
        for i in range(55):
            turn_data = {
                "id": i + 1,
                "call_sid": "CA1234567890abcdef1234567890abcdef",
                "role": ConversationRole.USER,
                "content": f"Message {i + 1}",
                "timestamp": timestamp
            }
            turn = ConversationTurnResponse(**turn_data)
            context.add_turn(turn)
        
        # Should keep only the last 50 turns
        assert len(context.turns) == 50
        assert context.turns[0].content == "Message 6"  # First of the last 50
        assert context.turns[-1].content == "Message 55"  # Last turn


class TestConversationAnalysis:
    """Test ConversationAnalysis schema."""
    
    def test_valid_conversation_analysis(self):
        """Test creating valid ConversationAnalysis."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "sentiment_score": 0.7,
            "intent_classification": "product_inquiry",
            "key_topics": ["pricing", "features", "implementation"],
            "buying_signals": ["budget_mentioned", "timeline_discussed"],
            "objections_raised": ["price_concern", "feature_gap"],
            "information_completeness": 0.8,
            "next_best_action": "Schedule demo call with technical team"
        }
        
        analysis = ConversationAnalysis(**data)
        
        assert analysis.call_sid == data["call_sid"]
        assert analysis.sentiment_score == 0.7
        assert analysis.intent_classification == "product_inquiry"
        assert analysis.key_topics == ["pricing", "features", "implementation"]
        assert analysis.buying_signals == ["budget_mentioned", "timeline_discussed"]
        assert analysis.objections_raised == ["price_concern", "feature_gap"]
        assert analysis.information_completeness == 0.8
        assert analysis.next_best_action == "Schedule demo call with technical team"
    
    def test_conversation_analysis_sentiment_bounds(self):
        """Test sentiment score validation bounds."""
        base_data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "intent_classification": "inquiry",
            "information_completeness": 0.5,
            "next_best_action": "follow up"
        }
        
        # Test valid bounds
        analysis = ConversationAnalysis(**base_data, sentiment_score=-1.0)
        assert analysis.sentiment_score == -1.0
        
        analysis = ConversationAnalysis(**base_data, sentiment_score=1.0)
        assert analysis.sentiment_score == 1.0
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            ConversationAnalysis(**base_data, sentiment_score=-1.1)
        
        with pytest.raises(ValidationError):
            ConversationAnalysis(**base_data, sentiment_score=1.1)
    
    def test_conversation_analysis_information_completeness_bounds(self):
        """Test information completeness validation bounds."""
        base_data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "sentiment_score": 0.0,
            "intent_classification": "inquiry",
            "next_best_action": "follow up"
        }
        
        # Test valid bounds
        analysis = ConversationAnalysis(**base_data, information_completeness=0.0)
        assert analysis.information_completeness == 0.0
        
        analysis = ConversationAnalysis(**base_data, information_completeness=1.0)
        assert analysis.information_completeness == 1.0
        
        # Test invalid bounds
        with pytest.raises(ValidationError):
            ConversationAnalysis(**base_data, information_completeness=-0.1)
        
        with pytest.raises(ValidationError):
            ConversationAnalysis(**base_data, information_completeness=1.1)
    
    def test_conversation_analysis_text_sanitization(self):
        """Test text field sanitization."""
        data = {
            "call_sid": "CA1234567890abcdef1234567890abcdef",
            "sentiment_score": 0.0,
            "intent_classification": "inquiry <script>alert('xss')</script>",
            "information_completeness": 0.5,
            "next_best_action": "follow up <script>alert('xss')</script>"
        }
        
        analysis = ConversationAnalysis(**data)
        assert "<script>" not in analysis.intent_classification
        assert "<script>" not in analysis.next_best_action
        assert "alert('xss')" not in analysis.intent_classification
        assert "alert('xss')" not in analysis.next_best_action