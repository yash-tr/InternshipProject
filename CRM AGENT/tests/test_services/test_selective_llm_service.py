"""
Tests for Selective LLM Service

Tests budget controls, caching, and fallback mechanisms for the selective LLM service.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from app.services.selective_llm_service import (
    SelectiveLLMService,
    LLMUsageType,
    ProspectTier,
    LLMBudgetLimits,
    LLMUsageTracker
)


@pytest.fixture
def selective_llm_service():
    """Create a selective LLM service instance for testing."""
    service = SelectiveLLMService()
    # Use smaller limits for testing
    service.budget_limits.daily_token_limit = 1000
    service.budget_limits.daily_cost_limit = 5.0
    return service


@pytest.fixture
def sample_prospect_data():
    """Sample prospect data for testing."""
    return {
        'company_name': 'Test Corp',
        'industry': 'Technology',
        'employee_count': '100-500',
        'revenue': '$10M-50M',
        'contact_name': 'John Doe',
        'job_title': 'CTO',
        'pain_points': ['scalability', 'security'],
        'buying_signals': ['budget approved', 'timeline Q1']
    }


@pytest.fixture
def sample_objection_context():
    """Sample objection context for testing."""
    return {
        'prospect_data': {
            'company_name': 'Test Corp',
            'industry': 'Technology'
        },
        'conversation_history': [
            {'role': 'assistant', 'content': 'Hello, how can I help you today?'},
            {'role': 'user', 'content': 'I\'m interested in your solution but concerned about the price.'}
        ],
        'previous_objections': ['timing']
    }


class TestLLMUsageTracker:
    """Test LLM usage tracking functionality."""
    
    def test_usage_tracker_initialization(self):
        """Test usage tracker initialization."""
        tracker = LLMUsageTracker(
            lead_id="test_lead_123",
            prospect_tier=ProspectTier.VIP
        )
        
        assert tracker.lead_id == "test_lead_123"
        assert tracker.prospect_tier == ProspectTier.VIP
        assert tracker.planner_calls == 0
        assert tracker.classifier_calls == 0
        assert tracker.runtime_calls == 0
        assert tracker.total_tokens_used == 0
        assert tracker.estimated_cost == 0.0
    
    def test_can_use_llm_planner(self):
        """Test planner LLM usage limits."""
        budget_limits = LLMBudgetLimits()
        tracker = LLMUsageTracker("test_lead", ProspectTier.NON_VIP)
        
        # Should allow first planner call
        assert tracker.can_use_llm(LLMUsageType.PLANNER, budget_limits) is True
        
        # Record usage
        tracker.record_usage(LLMUsageType.PLANNER, 500, 0.1)
        
        # Should not allow second planner call (limit is 1)
        assert tracker.can_use_llm(LLMUsageType.PLANNER, budget_limits) is False
    
    def test_can_use_llm_runtime_non_vip(self):
        """Test runtime LLM usage limits for non-VIP prospects."""
        budget_limits = LLMBudgetLimits()
        tracker = LLMUsageTracker("test_lead", ProspectTier.NON_VIP)
        
        # Should allow first runtime call
        assert tracker.can_use_llm(LLMUsageType.RUNTIME, budget_limits) is True
        
        # Record usage
        tracker.record_usage(LLMUsageType.RUNTIME, 80, 0.01)
        
        # Should not allow second runtime call for non-VIP (limit is 1)
        assert tracker.can_use_llm(LLMUsageType.RUNTIME, budget_limits) is False
    
    def test_can_use_llm_runtime_vip(self):
        """Test runtime LLM usage limits for VIP prospects."""
        budget_limits = LLMBudgetLimits()
        tracker = LLMUsageTracker("test_lead", ProspectTier.VIP)
        
        # Should allow multiple runtime calls for VIP
        for i in range(3):
            assert tracker.can_use_llm(LLMUsageType.RUNTIME, budget_limits) is True
            tracker.record_usage(LLMUsageType.RUNTIME, 80, 0.01)
        
        # Should not allow fourth runtime call (limit is 3)
        assert tracker.can_use_llm(LLMUsageType.RUNTIME, budget_limits) is False
    
    def test_record_usage(self):
        """Test usage recording."""
        tracker = LLMUsageTracker("test_lead", ProspectTier.NON_VIP)
        
        # Record planner usage
        tracker.record_usage(LLMUsageType.PLANNER, 500, 0.1)
        assert tracker.planner_calls == 1
        assert tracker.total_tokens_used == 500
        assert tracker.estimated_cost == 0.1
        assert tracker.tokens_by_type[LLMUsageType.PLANNER] == 500
        
        # Record runtime usage
        tracker.record_usage(LLMUsageType.RUNTIME, 80, 0.01)
        assert tracker.runtime_calls == 1
        assert tracker.total_tokens_used == 580
        assert tracker.estimated_cost == 0.11


class TestSelectiveLLMService:
    """Test selective LLM service functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_pre_call_plan_success(self, selective_llm_service, sample_prospect_data):
        """Test successful pre-call plan generation."""
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            # Mock LLM response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test pre-call plan with key talking points."
            mock_response.usage.total_tokens = 150
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Generate plan
            plan_text, from_cache, metadata = await selective_llm_service.generate_pre_call_plan(
                lead_id="test_lead_123",
                prospect_data=sample_prospect_data,
                prospect_tier=ProspectTier.NON_VIP
            )
            
            assert plan_text is not None
            assert "Test pre-call plan" in plan_text
            assert from_cache is False
            assert metadata['cached'] is False
            assert metadata['tokens_used'] == 150
            assert 'estimated_cost' in metadata
    
    @pytest.mark.asyncio
    async def test_generate_pre_call_plan_cached(self, selective_llm_service, sample_prospect_data):
        """Test cached pre-call plan retrieval."""
        # First call to populate cache
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Cached pre-call plan."
            mock_response.usage.total_tokens = 150
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # First call
            await selective_llm_service.generate_pre_call_plan(
                lead_id="test_lead_123",
                prospect_data=sample_prospect_data
            )
            
            # Second call should use cache
            plan_text, from_cache, metadata = await selective_llm_service.generate_pre_call_plan(
                lead_id="test_lead_123",
                prospect_data=sample_prospect_data
            )
            
            assert plan_text == "Cached pre-call plan."
            assert from_cache is True
            assert metadata['cached'] is True
            assert selective_llm_service.performance_metrics['cache_hits'] == 1
    
    @pytest.mark.asyncio
    async def test_generate_pre_call_plan_budget_exceeded(self, selective_llm_service, sample_prospect_data):
        """Test pre-call plan generation when budget is exceeded."""
        # Exhaust planner budget
        tracker = selective_llm_service._get_usage_tracker("test_lead_123", ProspectTier.NON_VIP)
        tracker.record_usage(LLMUsageType.PLANNER, 500, 0.1)  # Exhaust limit
        
        # Try to generate plan
        plan_text, from_cache, metadata = await selective_llm_service.generate_pre_call_plan(
            lead_id="test_lead_123",
            prospect_data=sample_prospect_data
        )
        
        assert plan_text is None
        assert from_cache is False
        assert metadata['error'] == 'budget_exceeded'
        assert selective_llm_service.performance_metrics['budget_blocks'] == 1
    
    @pytest.mark.asyncio
    async def test_handle_complex_objection_template_used(self, selective_llm_service, sample_objection_context):
        """Test complex objection handling using templates for simple objections."""
        # Simple price objection should use template
        objection_text = "This is too expensive for our budget."
        
        response_text, should_escalate, metadata = await selective_llm_service.handle_complex_objection(
            lead_id="test_lead_123",
            objection_text=objection_text,
            objection_context=sample_objection_context
        )
        
        assert response_text is not None
        assert "cost is always a consideration" in response_text  # Template response
        assert should_escalate is False
        assert metadata['template_used'] is True
        assert metadata['complexity'] < 0.7
    
    @pytest.mark.asyncio
    async def test_handle_complex_objection_llm_used(self, selective_llm_service, sample_objection_context):
        """Test complex objection handling using LLM for complex objections."""
        # Complex objection with multiple concerns and emotional language
        objection_text = "I'm really frustrated because we've tried similar solutions before and they failed. We're also concerned about the integration complexity and whether your support team can handle our technical requirements."
        
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "I understand your frustration with previous solutions. Let me address your specific concerns about integration and support."
            mock_response.usage.total_tokens = 75
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            response_text, should_escalate, metadata = await selective_llm_service.handle_complex_objection(
                lead_id="test_lead_123",
                objection_text=objection_text,
                objection_context=sample_objection_context,
                prospect_tier=ProspectTier.VIP
            )
            
            assert response_text is not None
            assert "understand your frustration" in response_text
            assert should_escalate is False
            assert metadata['llm_used'] is True
            assert metadata['complexity'] >= 0.7
            assert metadata['tokens_used'] == 75
    
    @pytest.mark.asyncio
    async def test_handle_complex_objection_budget_exceeded(self, selective_llm_service, sample_objection_context):
        """Test complex objection handling when runtime budget is exceeded."""
        # Exhaust runtime budget for non-VIP
        tracker = selective_llm_service._get_usage_tracker("test_lead_123", ProspectTier.NON_VIP)
        tracker.record_usage(LLMUsageType.RUNTIME, 80, 0.01)  # Exhaust limit
        
        # Complex objection should fall back to template
        objection_text = "This is a very complex technical objection with multiple integration concerns and security requirements."
        
        response_text, should_escalate, metadata = await selective_llm_service.handle_complex_objection(
            lead_id="test_lead_123",
            objection_text=objection_text,
            objection_context=sample_objection_context
        )
        
        assert response_text is not None
        assert should_escalate is False
        assert metadata['budget_exceeded'] is True
        assert metadata['template_fallback'] is True
        assert selective_llm_service.performance_metrics['budget_blocks'] == 1
    
    @pytest.mark.asyncio
    async def test_classify_objection_type_success(self, selective_llm_service):
        """Test successful objection classification."""
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"objection_type": "price", "confidence": 0.9}'
            mock_response.usage.total_tokens = 50
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            objection_type, confidence, metadata = await selective_llm_service.classify_objection_type(
                objection_text="This solution is too expensive for our budget."
            )
            
            assert objection_type == "price"
            assert confidence == 0.9
            assert metadata['cached'] is False
            assert metadata['tokens_used'] == 50
    
    @pytest.mark.asyncio
    async def test_classify_objection_type_cached(self, selective_llm_service):
        """Test cached objection classification."""
        objection_text = "This is too expensive."
        
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"objection_type": "price", "confidence": 0.8}'
            mock_response.usage.total_tokens = 45
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # First call
            await selective_llm_service.classify_objection_type(objection_text)
            
            # Second call should use cache
            objection_type, confidence, metadata = await selective_llm_service.classify_objection_type(objection_text)
            
            assert objection_type == "price"
            assert confidence == 0.8
            assert metadata['cached'] is True
            assert selective_llm_service.performance_metrics['cache_hits'] == 1
    
    @pytest.mark.asyncio
    async def test_classify_objection_type_keyword_fallback(self, selective_llm_service):
        """Test objection classification with keyword fallback."""
        # Set daily limits to 0 to force keyword fallback
        selective_llm_service.daily_usage.total_tokens = 1000
        
        objection_type, confidence, metadata = await selective_llm_service.classify_objection_type(
            objection_text="This is too expensive for our budget."
        )
        
        assert objection_type == "price"
        assert confidence > 0.0
        assert metadata['keyword_classification'] is True
        assert metadata['daily_budget_exceeded'] is True
    
    def test_assess_objection_complexity(self, selective_llm_service):
        """Test objection complexity assessment."""
        # Simple objection
        simple_objection = "Too expensive."
        complexity = selective_llm_service._assess_objection_complexity(simple_objection, {})
        assert complexity < 0.5
        
        # Complex objection
        complex_objection = "I'm frustrated because we've tried similar solutions before and they failed. We're also concerned about the integration complexity and security requirements."
        complexity = selective_llm_service._assess_objection_complexity(complex_objection, {
            'conversation_history': [{'role': 'user', 'content': 'test'}] * 15,
            'previous_objections': ['timing', 'authority']
        })
        assert complexity >= 0.7
    
    def test_classify_objection_keywords(self, selective_llm_service):
        """Test keyword-based objection classification."""
        # Price objection
        objection_type, confidence = selective_llm_service._classify_objection_keywords(
            "This is too expensive for our budget."
        )
        assert objection_type == "price"
        assert confidence > 0.0
        
        # Timing objection
        objection_type, confidence = selective_llm_service._classify_objection_keywords(
            "We're too busy right now to implement this."
        )
        assert objection_type == "timing"
        assert confidence > 0.0
        
        # Unknown objection
        objection_type, confidence = selective_llm_service._classify_objection_keywords(
            "This is a completely unrelated concern."
        )
        assert objection_type == "unknown"
        assert confidence == 0.0
    
    def test_get_template_objection_response(self, selective_llm_service, sample_objection_context):
        """Test template objection response retrieval."""
        # Price objection
        response = selective_llm_service._get_template_objection_response(
            "This is too expensive.",
            sample_objection_context
        )
        assert response is not None
        assert "cost is always a consideration" in response
        
        # Unknown objection
        response = selective_llm_service._get_template_objection_response(
            "This is a completely unknown concern.",
            sample_objection_context
        )
        assert response is not None
        assert "appreciate you sharing that concern" in response
    
    def test_get_fallback_plan(self, selective_llm_service, sample_prospect_data):
        """Test fallback plan generation."""
        plan = selective_llm_service._get_fallback_plan(sample_prospect_data)
        
        assert "Test Corp" in plan
        assert "Technology" in plan
        assert "Opening:" in plan
        assert "Qualification:" in plan
        assert "Needs Discovery:" in plan
        assert "Solution Fit:" in plan
        assert "Objection Handling:" in plan
        assert "Next Steps:" in plan
    
    def test_cache_functionality(self, selective_llm_service):
        """Test caching functionality."""
        cache_key = "test_key"
        response_data = {
            'response': 'Test response',
            'tokens_used': 100,
            'created_at': datetime.utcnow().isoformat(),
            'usage_type': 'planner'
        }
        
        # Cache response
        selective_llm_service._cache_response(cache_key, response_data)
        
        # Retrieve cached response
        cached = selective_llm_service._get_cached_response(cache_key, 3600)
        assert cached is not None
        assert cached['response'] == 'Test response'
        assert cached['tokens_used'] == 100
        
        # Test expiration
        expired_data = {
            'response': 'Expired response',
            'tokens_used': 50,
            'created_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            'usage_type': 'planner'
        }
        selective_llm_service._cache_response("expired_key", expired_data)
        
        # Should return None for expired cache
        cached = selective_llm_service._get_cached_response("expired_key", 3600)
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_daily_usage_reset(self, selective_llm_service):
        """Test daily usage reset functionality."""
        # Set usage
        selective_llm_service.daily_usage.total_tokens = 500
        selective_llm_service.daily_usage.cost_estimate = 2.5
        
        # Set last reset to yesterday
        selective_llm_service.last_daily_reset = datetime.utcnow().date() - timedelta(days=1)
        
        # Check daily limits (should trigger reset)
        await selective_llm_service._reset_daily_usage_if_needed()
        
        assert selective_llm_service.daily_usage.total_tokens == 0
        assert selective_llm_service.daily_usage.cost_estimate == 0.0
        assert selective_llm_service.last_daily_reset == datetime.utcnow().date()
    
    def test_estimate_cost(self, selective_llm_service):
        """Test cost estimation."""
        # Test with 1000 tokens
        cost = selective_llm_service._estimate_cost(1000)
        assert cost > 0.0
        assert cost < 0.1  # Should be small for 1000 tokens
        
        # Test with larger token count
        cost_large = selective_llm_service._estimate_cost(10000)
        assert cost_large > cost  # Should be proportionally larger
    
    def test_performance_metrics_tracking(self, selective_llm_service):
        """Test performance metrics tracking."""
        initial_metrics = selective_llm_service.performance_metrics.copy()
        
        # Simulate cache hit
        selective_llm_service.performance_metrics['cache_hits'] += 1
        selective_llm_service.performance_metrics['total_requests'] += 1
        
        # Simulate cache miss
        selective_llm_service.performance_metrics['cache_misses'] += 1
        selective_llm_service.performance_metrics['total_requests'] += 1
        
        # Simulate budget block
        selective_llm_service.performance_metrics['budget_blocks'] += 1
        selective_llm_service.performance_metrics['total_requests'] += 1
        
        # Simulate fallback use
        selective_llm_service.performance_metrics['fallback_uses'] += 1
        selective_llm_service.performance_metrics['total_requests'] += 1
        
        assert selective_llm_service.performance_metrics['cache_hits'] == initial_metrics['cache_hits'] + 1
        assert selective_llm_service.performance_metrics['cache_misses'] == initial_metrics['cache_misses'] + 1
        assert selective_llm_service.performance_metrics['budget_blocks'] == initial_metrics['budget_blocks'] + 1
        assert selective_llm_service.performance_metrics['fallback_uses'] == initial_metrics['fallback_uses'] + 1
        assert selective_llm_service.performance_metrics['total_requests'] == initial_metrics['total_requests'] + 4


@pytest.mark.integration
class TestSelectiveLLMServiceIntegration:
    """Integration tests for selective LLM service."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, selective_llm_service, sample_prospect_data, sample_objection_context):
        """Test end-to-end workflow with budget controls."""
        lead_id = "integration_test_lead"
        
        with patch.object(selective_llm_service.base_llm_service, 'client') as mock_client:
            # Mock responses for different calls
            def mock_create(**kwargs):
                messages = kwargs.get('messages', [])
                max_tokens = kwargs.get('max_tokens', 100)
                
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.usage = Mock()
                
                if 'pre-call plan' in str(messages).lower():
                    mock_response.choices[0].message.content = "Comprehensive pre-call plan with talking points."
                    mock_response.usage.total_tokens = min(max_tokens, 200)
                elif 'classify' in str(messages).lower():
                    mock_response.choices[0].message.content = '{"objection_type": "price", "confidence": 0.85}'
                    mock_response.usage.total_tokens = min(max_tokens, 50)
                else:  # Complex objection response
                    mock_response.choices[0].message.content = "I understand your concern about pricing. Let me explain the value proposition."
                    mock_response.usage.total_tokens = min(max_tokens, 75)
                
                return mock_response
            
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
            
            # Step 1: Generate pre-call plan
            plan_text, from_cache, plan_metadata = await selective_llm_service.generate_pre_call_plan(
                lead_id=lead_id,
                prospect_data=sample_prospect_data,
                prospect_tier=ProspectTier.VIP
            )
            
            assert plan_text is not None
            assert "pre-call plan" in plan_text.lower()
            assert from_cache is False
            
            # Step 2: Classify objection
            objection_type, confidence, class_metadata = await selective_llm_service.classify_objection_type(
                objection_text="This solution is too expensive for our current budget."
            )
            
            assert objection_type == "price"
            assert confidence > 0.8
            
            # Step 3: Handle complex objection (should use LLM for VIP)
            complex_objection = "I'm concerned about the pricing and also worried about the implementation timeline and whether your support team can handle our specific technical requirements."
            
            response_text, should_escalate, obj_metadata = await selective_llm_service.handle_complex_objection(
                lead_id=lead_id,
                objection_text=complex_objection,
                objection_context=sample_objection_context,
                prospect_tier=ProspectTier.VIP
            )
            
            assert response_text is not None
            assert "understand your concern" in response_text.lower()
            assert should_escalate is False
            assert obj_metadata['llm_used'] is True
            
            # Verify usage tracking
            tracker = selective_llm_service.usage_trackers[lead_id]
            assert tracker.planner_calls == 1
            assert tracker.runtime_calls == 1
            assert tracker.total_tokens_used > 0
            assert tracker.estimated_cost > 0.0
            
            # Step 4: Test caching - second plan request should use cache
            plan_text_2, from_cache_2, plan_metadata_2 = await selective_llm_service.generate_pre_call_plan(
                lead_id=lead_id,
                prospect_data=sample_prospect_data,
                prospect_tier=ProspectTier.VIP
            )
            
            assert plan_text_2 == plan_text
            assert from_cache_2 is True
            assert plan_metadata_2['cached'] is True
            
            # Verify performance metrics
            assert selective_llm_service.performance_metrics['total_requests'] >= 4
            assert selective_llm_service.performance_metrics['cache_hits'] >= 1
            assert selective_llm_service.performance_metrics['cache_misses'] >= 3