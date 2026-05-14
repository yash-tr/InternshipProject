"""
Tests for the Dialog Manager service.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.dialog_manager import (
    DialogManager, ConversationStateMachine, DialogTemplateLibrary,
    DialogState, DialogEvent, DialogContext, DialogTemplate, LLMBudgetTracker,
    dialog_manager
)


class TestLLMBudgetTracker:
    """Test LLM budget tracking functionality."""
    
    def test_budget_tracker_initialization(self):
        """Test budget tracker initialization."""
        # Non-VIP tracker
        tracker = LLMBudgetTracker(is_vip=False)
        assert tracker.max_llm_calls_non_vip == 1
        assert tracker.max_llm_calls_vip == 3
        assert tracker.current_llm_calls == 0
        assert not tracker.is_vip
        
        # VIP tracker
        vip_tracker = LLMBudgetTracker(is_vip=True)
        assert vip_tracker.is_vip
    
    def test_can_use_llm_non_vip(self):
        """Test LLM usage checking for non-VIP."""
        tracker = LLMBudgetTracker(is_vip=False)
        
        # Should allow first call
        assert tracker.can_use_llm() is True
        
        # Record usage
        tracker.record_llm_usage(50)
        assert tracker.current_llm_calls == 1
        assert tracker.current_tokens_used == 50
        
        # Should not allow second call for non-VIP
        assert tracker.can_use_llm() is False
    
    def test_can_use_llm_vip(self):
        """Test LLM usage checking for VIP."""
        tracker = LLMBudgetTracker(is_vip=True)
        
        # Should allow up to 3 calls for VIP
        for i in range(3):
            assert tracker.can_use_llm() is True
            tracker.record_llm_usage(30)
        
        assert tracker.current_llm_calls == 3
        assert tracker.current_tokens_used == 90
        
        # Should not allow 4th call
        assert tracker.can_use_llm() is False


class TestDialogTemplateLibrary:
    """Test dialog template library functionality."""
    
    @pytest.fixture
    def template_library(self):
        """Create a template library for testing."""
        return DialogTemplateLibrary()
    
    def test_template_library_initialization(self, template_library):
        """Test that template library initializes with templates."""
        assert len(template_library.templates) > 0
        
        # Check that all dialog states have templates
        expected_states = [
            DialogState.GREETING.value,
            DialogState.QUALIFICATION.value,
            DialogState.NEEDS_ANALYSIS.value,
            DialogState.OBJECTION_HANDLING.value,
            DialogState.CLOSING.value,
            DialogState.COMPLETED.value,
            DialogState.ABANDONED.value
        ]
        
        for state in expected_states:
            assert state in template_library.templates
            assert len(template_library.templates[state]) > 0
    
    def test_get_templates_by_state(self, template_library):
        """Test getting templates by state."""
        greeting_templates = template_library.get_templates(DialogState.GREETING)
        assert len(greeting_templates) > 0
        
        for template in greeting_templates:
            assert template.state == DialogState.GREETING
    
    def test_get_templates_by_trigger(self, template_library):
        """Test getting templates by trigger."""
        price_objection_templates = template_library.get_templates(
            DialogState.OBJECTION_HANDLING, 
            "price_objection"
        )
        assert len(price_objection_templates) > 0
        
        for template in price_objection_templates:
            assert template.trigger == "price_objection"
    
    def test_find_best_template_price_objection(self, template_library):
        """Test finding best template for price objections."""
        context = DialogContext(
            call_sid="test_call",
            prospect_data={},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.OBJECTION_HANDLING,
            state_entry_time=datetime.utcnow()
        )
        
        user_input = "That's too expensive for our budget"
        template = template_library.find_best_template(
            DialogState.OBJECTION_HANDLING, 
            context, 
            user_input
        )
        
        assert template is not None
        assert template.trigger == "price_objection"
    
    def test_find_best_template_timing_objection(self, template_library):
        """Test finding best template for timing objections."""
        context = DialogContext(
            call_sid="test_call",
            prospect_data={},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.OBJECTION_HANDLING,
            state_entry_time=datetime.utcnow()
        )
        
        user_input = "We don't have time for this right now"
        template = template_library.find_best_template(
            DialogState.OBJECTION_HANDLING, 
            context, 
            user_input
        )
        
        assert template is not None
        assert template.trigger == "timing_objection"
    
    def test_add_custom_template(self, template_library):
        """Test adding custom templates."""
        custom_template = DialogTemplate(
            template_id="custom_test",
            state=DialogState.GREETING,
            trigger="test_trigger",
            response="This is a test response",
            priority=10
        )
        
        template_library.add_template(custom_template)
        
        templates = template_library.get_templates(DialogState.GREETING, "test_trigger")
        assert len(templates) == 1
        assert templates[0].template_id == "custom_test"


class TestDialogContext:
    """Test dialog context functionality."""
    
    def test_dialog_context_initialization(self):
        """Test dialog context initialization."""
        context = DialogContext(
            call_sid="test_call",
            prospect_data={"name": "John Doe"},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.GREETING,
            state_entry_time=datetime.utcnow()
        )
        
        assert context.call_sid == "test_call"
        assert context.prospect_data["name"] == "John Doe"
        assert context.current_state == DialogState.GREETING
        assert not context.is_timeout()
    
    def test_timeout_detection(self):
        """Test timeout detection."""
        # Create context with past entry time
        past_time = datetime.utcnow() - timedelta(minutes=5)
        context = DialogContext(
            call_sid="test_call",
            prospect_data={},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.GREETING,
            state_entry_time=past_time,
            timeout_duration=timedelta(minutes=2)
        )
        
        assert context.is_timeout() is True
    
    def test_reset_state_timer(self):
        """Test resetting state timer."""
        past_time = datetime.utcnow() - timedelta(minutes=5)
        context = DialogContext(
            call_sid="test_call",
            prospect_data={},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.GREETING,
            state_entry_time=past_time
        )
        
        assert context.is_timeout() is True
        
        context.reset_state_timer()
        assert context.is_timeout() is False


class TestConversationStateMachine:
    """Test conversation state machine functionality."""
    
    @pytest.fixture
    def dialog_context(self):
        """Create a dialog context for testing."""
        return DialogContext(
            call_sid="test_call",
            prospect_data={"name": "John Doe", "company": "Test Corp", "lead_score": 75},
            conversation_history=[],
            extracted_information={},
            current_state=DialogState.GREETING,
            state_entry_time=datetime.utcnow()
        )
    
    @pytest.fixture
    def template_library(self):
        """Create a template library for testing."""
        return DialogTemplateLibrary()
    
    @pytest.fixture
    def state_machine(self, dialog_context, template_library):
        """Create a conversation state machine for testing."""
        return ConversationStateMachine(dialog_context, template_library)
    
    @pytest.mark.asyncio
    async def test_state_machine_initialization(self, state_machine):
        """Test state machine initialization."""
        assert state_machine.current_state.id == DialogState.GREETING.value
        assert state_machine.context.call_sid == "test_call"
    
    @pytest.mark.asyncio
    async def test_process_user_input_template_response(self, state_machine):
        """Test processing user input with template response."""
        user_input = "Hello, how are you?"
        
        response, should_end = await state_machine.process_user_input(user_input)
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert should_end is False
        assert len(state_machine.context.conversation_history) == 2  # User + Assistant
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, state_machine):
        """Test timeout handling."""
        # Set context to timeout state
        state_machine.context.state_entry_time = datetime.utcnow() - timedelta(minutes=5)
        state_machine.context.timeout_duration = timedelta(minutes=2)
        
        response, should_end = await state_machine.process_user_input("Hello")
        
        assert should_end is True
        assert "timeout" in response.lower() or "quiet" in response.lower()
    
    @pytest.mark.asyncio
    @patch('app.services.dialog_manager.openrouter_llm_service')
    async def test_llm_fallback(self, mock_llm_service, state_machine):
        """Test LLM fallback when templates don't match."""
        # Mock LLM service
        mock_llm_service.generate_response = AsyncMock(return_value=(
            "This is an LLM response", 50, {}
        ))
        
        # Use input that doesn't match any templates
        user_input = "Tell me about quantum physics"
        
        response, should_end = await state_machine.process_user_input(user_input)
        
        # Should use LLM fallback
        assert isinstance(response, str)
        assert len(response) > 0
        assert state_machine.context.llm_budget.current_llm_calls > 0
    
    @pytest.mark.asyncio
    async def test_budget_exhaustion_fallback(self, state_machine):
        """Test fallback when LLM budget is exhausted."""
        # Exhaust LLM budget
        state_machine.context.llm_budget.current_llm_calls = 5
        
        user_input = "Tell me about quantum physics"
        
        response, should_end = await state_machine.process_user_input(user_input)
        
        # Should use generic fallback
        assert isinstance(response, str)
        assert len(response) > 0
        assert should_end is False


class TestDialogManager:
    """Test the main dialog manager."""
    
    @pytest.fixture
    def dialog_manager_instance(self):
        """Create a dialog manager instance for testing."""
        return DialogManager()
    
    @pytest.mark.asyncio
    async def test_start_conversation(self, dialog_manager_instance):
        """Test starting a conversation."""
        call_sid = "test_call_123"
        prospect_data = {
            "name": "John Doe",
            "company": "Test Corp",
            "lead_score": 75
        }
        
        response = await dialog_manager_instance.start_conversation(call_sid, prospect_data)
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert call_sid in dialog_manager_instance.active_conversations
        assert call_sid in dialog_manager_instance.conversation_contexts
    
    @pytest.mark.asyncio
    async def test_process_turn(self, dialog_manager_instance):
        """Test processing a conversation turn."""
        call_sid = "test_call_123"
        prospect_data = {"name": "John Doe", "lead_score": 75}
        
        # Start conversation first
        await dialog_manager_instance.start_conversation(call_sid, prospect_data)
        
        # Process a turn
        user_input = "I'm doing well, thank you"
        response, should_end = await dialog_manager_instance.process_turn(call_sid, user_input)
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert isinstance(should_end, bool)
    
    @pytest.mark.asyncio
    async def test_end_conversation(self, dialog_manager_instance):
        """Test ending a conversation."""
        call_sid = "test_call_123"
        prospect_data = {"name": "John Doe", "lead_score": 75}
        
        # Start conversation
        await dialog_manager_instance.start_conversation(call_sid, prospect_data)
        
        # Process a few turns
        await dialog_manager_instance.process_turn(call_sid, "Hello")
        await dialog_manager_instance.process_turn(call_sid, "I'm interested")
        
        # End conversation
        summary = await dialog_manager_instance.end_conversation(call_sid, "completed")
        
        assert isinstance(summary, dict)
        assert summary.get('call_sid') == call_sid
        assert summary.get('final_state') is not None
        assert summary.get('total_turns') > 0
        assert call_sid not in dialog_manager_instance.active_conversations
    
    @pytest.mark.asyncio
    async def test_get_conversation_status(self, dialog_manager_instance):
        """Test getting conversation status."""
        call_sid = "test_call_123"
        prospect_data = {"name": "John Doe", "lead_score": 85}  # VIP prospect
        
        # Start conversation
        await dialog_manager_instance.start_conversation(call_sid, prospect_data)
        
        # Get status
        status = await dialog_manager_instance.get_conversation_status(call_sid)
        
        assert status is not None
        assert status['call_sid'] == call_sid
        assert status['current_state'] == DialogState.GREETING.value
        assert 'llm_budget_used' in status
        assert status['llm_budget_used']['calls_remaining'] == 3  # VIP gets 3 calls
    
    @pytest.mark.asyncio
    async def test_conversation_not_found(self, dialog_manager_instance):
        """Test handling non-existent conversations."""
        call_sid = "nonexistent_call"
        
        # Try to process turn for non-existent conversation
        response, should_end = await dialog_manager_instance.process_turn(call_sid, "Hello")
        
        assert "lost our conversation context" in response
        assert should_end is False
        
        # Try to get status for non-existent conversation
        status = await dialog_manager_instance.get_conversation_status(call_sid)
        assert status is None
    
    @pytest.mark.asyncio
    async def test_vip_vs_non_vip_budget(self, dialog_manager_instance):
        """Test different budget limits for VIP vs non-VIP prospects."""
        # Non-VIP prospect
        non_vip_call = "non_vip_call"
        non_vip_data = {"name": "Regular User", "lead_score": 50}
        
        await dialog_manager_instance.start_conversation(non_vip_call, non_vip_data)
        non_vip_status = await dialog_manager_instance.get_conversation_status(non_vip_call)
        
        # VIP prospect
        vip_call = "vip_call"
        vip_data = {"name": "VIP User", "lead_score": 90}
        
        await dialog_manager_instance.start_conversation(vip_call, vip_data)
        vip_status = await dialog_manager_instance.get_conversation_status(vip_call)
        
        # VIP should have more LLM calls available
        assert non_vip_status['llm_budget_used']['calls_remaining'] == 1
        assert vip_status['llm_budget_used']['calls_remaining'] == 3


@pytest.mark.integration
class TestDialogManagerIntegration:
    """Integration tests for dialog manager."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete conversation flow."""
        call_sid = "integration_test_call"
        prospect_data = {
            "name": "Integration Test User",
            "company": "Test Integration Corp",
            "lead_score": 75
        }
        
        # Start conversation
        response = await dialog_manager.start_conversation(call_sid, prospect_data)
        assert "Hello" in response or "Thank you" in response
        
        # Simulate conversation turns
        turns = [
            "Hi, I'm doing well",
            "I'm the CTO at my company",
            "We have about 100 employees",
            "Our biggest challenge is data management",
            "That sounds interesting, but what's the cost?",
            "Yes, I'd like to see a demo"
        ]
        
        for turn in turns:
            response, should_end = await dialog_manager.process_turn(call_sid, turn)
            assert isinstance(response, str)
            assert len(response) > 0
            
            if should_end:
                break
        
        # Get final status
        status = await dialog_manager.get_conversation_status(call_sid)
        assert status is not None
        assert status['total_turns'] > 0
        
        # End conversation
        summary = await dialog_manager.end_conversation(call_sid, "completed")
        assert summary['call_sid'] == call_sid
        assert summary['total_turns'] > 0
    
    @pytest.mark.asyncio
    async def test_objection_handling_flow(self):
        """Test objection handling in conversation flow."""
        call_sid = "objection_test_call"
        prospect_data = {"name": "Objection User", "lead_score": 70}
        
        # Start conversation
        await dialog_manager.start_conversation(call_sid, prospect_data)
        
        # Simulate objections
        objections = [
            "That's too expensive for us",
            "We don't have time for this right now",
            "I need to think about it"
        ]
        
        for objection in objections:
            response, should_end = await dialog_manager.process_turn(call_sid, objection)
            
            # Response should address the objection
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Should not end call on objections
            assert should_end is False
        
        # End conversation
        await dialog_manager.end_conversation(call_sid, "objection_handling")
    
    @pytest.mark.asyncio
    async def test_timeout_scenario(self):
        """Test conversation timeout handling."""
        call_sid = "timeout_test_call"
        prospect_data = {"name": "Timeout User", "lead_score": 60}
        
        # Start conversation
        await dialog_manager.start_conversation(call_sid, prospect_data)
        
        # Get the context and manually set timeout
        context = dialog_manager.conversation_contexts[call_sid]
        context.state_entry_time = datetime.utcnow() - timedelta(minutes=5)
        context.timeout_duration = timedelta(minutes=2)
        
        # Process turn - should trigger timeout
        response, should_end = await dialog_manager.process_turn(call_sid, "Hello")
        
        assert should_end is True
        assert "timeout" in response.lower() or "quiet" in response.lower()
        
        # End conversation
        await dialog_manager.end_conversation(call_sid, "timeout")