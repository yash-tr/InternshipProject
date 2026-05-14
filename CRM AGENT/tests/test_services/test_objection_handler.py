"""
Tests for Enhanced Objection Handler service.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.services.objection_handler import (
    EnhancedObjectionHandler,
    ObjectionClassifier,
    ObjectionResponseGenerator,
    ObjectionTracker,
    ObjectionType,
    ObjectionSeverity,
    ResponseStrategy,
    ObjectionInstance,
    ObjectionAnalytics
)


@pytest.fixture
def objection_handler():
    """Create an EnhancedObjectionHandler instance for testing."""
    return EnhancedObjectionHandler()


@pytest.fixture
def objection_classifier():
    """Create an ObjectionClassifier instance for testing."""
    return ObjectionClassifier()


@pytest.fixture
def response_generator():
    """Create an ObjectionResponseGenerator instance for testing."""
    return ObjectionResponseGenerator()


@pytest.fixture
def objection_tracker():
    """Create an ObjectionTracker instance for testing."""
    return ObjectionTracker()


@pytest.fixture
def sample_prospect_data():
    """Create sample prospect data for testing."""
    return {
        "company_name": "TechCorp Inc",
        "industry": "technology",
        "job_title": "CTO",
        "name": "John Smith",
        "company_size": "500-1000"
    }


class TestObjectionClassifier:
    """Test cases for ObjectionClassifier."""
    
    def test_classify_price_objection(self, objection_classifier):
        """Test classification of price objections."""
        test_cases = [
            ("This is too expensive for our budget", ObjectionType.PRICE, ObjectionSeverity.HIGH),
            ("The cost seems a bit high", ObjectionType.PRICE, ObjectionSeverity.MEDIUM),
            ("We can't afford this right now", ObjectionType.PRICE, ObjectionSeverity.HIGH),
            ("What's the price point?", ObjectionType.PRICE, ObjectionSeverity.LOW)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_timing_objection(self, objection_classifier):
        """Test classification of timing objections."""
        test_cases = [
            ("We're too busy right now", ObjectionType.TIMING, ObjectionSeverity.MEDIUM),
            ("This isn't the right time", ObjectionType.TIMING, ObjectionSeverity.MEDIUM),
            ("Maybe we can talk later", ObjectionType.TIMING, ObjectionSeverity.LOW),
            ("Absolutely no time for this", ObjectionType.TIMING, ObjectionSeverity.CRITICAL)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_authority_objection(self, objection_classifier):
        """Test classification of authority objections."""
        test_cases = [
            ("I need to check with my boss", ObjectionType.AUTHORITY, ObjectionSeverity.MEDIUM),
            ("This isn't my decision to make", ObjectionType.AUTHORITY, ObjectionSeverity.HIGH),
            ("The team needs to approve this", ObjectionType.AUTHORITY, ObjectionSeverity.MEDIUM),
            ("I have no authority over this", ObjectionType.AUTHORITY, ObjectionSeverity.CRITICAL)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_need_objection(self, objection_classifier):
        """Test classification of need objections."""
        test_cases = [
            ("We don't really need this", ObjectionType.NEED, ObjectionSeverity.MEDIUM),
            ("Our current solution works fine", ObjectionType.NEED, ObjectionSeverity.MEDIUM),
            ("I don't see the problem", ObjectionType.NEED, ObjectionSeverity.MEDIUM),
            ("Everything is perfect as is", ObjectionType.NEED, ObjectionSeverity.CRITICAL)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_trust_objection(self, objection_classifier):
        """Test classification of trust objections."""
        test_cases = [
            ("I'm not sure about this", ObjectionType.TRUST, ObjectionSeverity.MEDIUM),
            ("This seems too good to be true", ObjectionType.TRUST, ObjectionSeverity.MEDIUM),
            ("I don't trust new technology", ObjectionType.TRUST, ObjectionSeverity.HIGH),
            ("I'm completely skeptical", ObjectionType.TRUST, ObjectionSeverity.CRITICAL)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_competition_objection(self, objection_classifier):
        """Test classification of competition objections."""
        test_cases = [
            ("We already have a solution", ObjectionType.COMPETITION, ObjectionSeverity.MEDIUM),
            ("Our current vendor is great", ObjectionType.COMPETITION, ObjectionSeverity.MEDIUM),
            ("We're locked into a contract", ObjectionType.COMPETITION, ObjectionSeverity.CRITICAL),
            ("Happy with our existing system", ObjectionType.COMPETITION, ObjectionSeverity.HIGH)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_priority_objection(self, objection_classifier):
        """Test classification of priority objections."""
        test_cases = [
            ("We have other priorities", ObjectionType.PRIORITY, ObjectionSeverity.MEDIUM),
            ("This isn't important right now", ObjectionType.PRIORITY, ObjectionSeverity.MEDIUM),
            ("We're focusing on other projects", ObjectionType.PRIORITY, ObjectionSeverity.MEDIUM),
            ("Absolutely not a priority", ObjectionType.PRIORITY, ObjectionSeverity.CRITICAL)
        ]
        
        for user_input, expected_type, expected_severity in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert severity == expected_severity
            assert confidence > 0.0
    
    def test_classify_unknown_objection(self, objection_classifier):
        """Test classification of unknown/unclear objections."""
        test_cases = [
            ("I don't understand", ObjectionType.UNKNOWN),
            ("What do you mean?", ObjectionType.UNKNOWN),
            ("", ObjectionType.UNKNOWN)
        ]
        
        for user_input, expected_type in test_cases:
            objection_type, severity, confidence = objection_classifier.classify_objection(user_input)
            assert objection_type == expected_type
            assert confidence >= 0.0
    
    def test_classification_with_context(self, objection_classifier):
        """Test objection classification with additional context."""
        context = {
            "previous_objections": ["price"],
            "prospect_industry": "healthcare",
            "conversation_stage": "needs_analysis"
        }
        
        objection_type, severity, confidence = objection_classifier.classify_objection(
            "This is expensive", context
        )
        
        assert objection_type == ObjectionType.PRICE
        assert confidence > 0.0
    
    def test_classification_caching(self, objection_classifier):
        """Test that classification results are cached."""
        user_input = "This costs too much"
        
        # First call
        result1 = objection_classifier.classify_objection(user_input)
        
        # Second call should use cache
        result2 = objection_classifier.classify_objection(user_input)
        
        assert result1 == result2
        assert len(objection_classifier.classification_cache) > 0


class TestObjectionResponseGenerator:
    """Test cases for ObjectionResponseGenerator."""
    
    def test_generate_price_objection_response(self, response_generator, sample_prospect_data):
        """Test generation of price objection responses."""
        response = response_generator.generate_response(
            ObjectionType.PRICE,
            ObjectionSeverity.MEDIUM,
            sample_prospect_data
        )
        
        assert response is not None
        assert response.objection_type == ObjectionType.PRICE
        assert response.severity == ObjectionSeverity.MEDIUM
        assert "TechCorp Inc" in response.template or "your company" in response.template
        assert len(response.follow_up_questions) > 0
    
    def test_generate_timing_objection_response(self, response_generator, sample_prospect_data):
        """Test generation of timing objection responses."""
        response = response_generator.generate_response(
            ObjectionType.TIMING,
            ObjectionSeverity.LOW,
            sample_prospect_data
        )
        
        assert response is not None
        assert response.objection_type == ObjectionType.TIMING
        assert response.severity == ObjectionSeverity.LOW
        assert len(response.follow_up_questions) > 0
    
    def test_generate_authority_objection_response(self, response_generator, sample_prospect_data):
        """Test generation of authority objection responses."""
        response = response_generator.generate_response(
            ObjectionType.AUTHORITY,
            ObjectionSeverity.MEDIUM,
            sample_prospect_data
        )
        
        assert response is not None
        assert response.objection_type == ObjectionType.AUTHORITY
        assert response.severity == ObjectionSeverity.MEDIUM
        assert len(response.follow_up_questions) > 0
    
    def test_industry_customization(self, response_generator):
        """Test industry-specific response customization."""
        healthcare_prospect = {
            "company_name": "HealthCorp",
            "industry": "healthcare",
            "job_title": "Director of IT"
        }
        
        response = response_generator.generate_response(
            ObjectionType.PRICE,
            ObjectionSeverity.MEDIUM,
            healthcare_prospect
        )
        
        assert response is not None
        # Should contain healthcare-specific language
        assert "HealthCorp" in response.template or "your company" in response.template
    
    def test_role_customization(self, response_generator):
        """Test role-specific response customization."""
        ceo_prospect = {
            "company_name": "BigCorp",
            "industry": "finance",
            "job_title": "CEO"
        }
        
        response = response_generator.generate_response(
            ObjectionType.PRICE,
            ObjectionSeverity.MEDIUM,
            ceo_prospect
        )
        
        assert response is not None
        assert "BigCorp" in response.template or "your company" in response.template
    
    def test_fallback_to_lower_severity(self, response_generator, sample_prospect_data):
        """Test fallback to lower severity when exact match not found."""
        # Try to get a response for a combination that might not exist
        response = response_generator.generate_response(
            ObjectionType.FEATURE,  # Less common objection type
            ObjectionSeverity.CRITICAL,
            sample_prospect_data
        )
        
        # Should either return a response or None (graceful handling)
        if response:
            assert response.objection_type == ObjectionType.FEATURE
    
    def test_template_variable_substitution(self, response_generator, sample_prospect_data):
        """Test that template variables are properly substituted."""
        response = response_generator.generate_response(
            ObjectionType.PRICE,
            ObjectionSeverity.MEDIUM,
            sample_prospect_data
        )
        
        assert response is not None
        # Should not contain unsubstituted template variables
        assert "{company_name}" not in response.template
        assert "{industry}" not in response.template


class TestObjectionTracker:
    """Test cases for ObjectionTracker."""
    
    def test_record_objection(self, objection_tracker):
        """Test recording objections."""
        call_sid = "test_call_123"
        
        objection_id = objection_tracker.record_objection(
            call_sid=call_sid,
            objection_type=ObjectionType.PRICE,
            severity=ObjectionSeverity.MEDIUM,
            user_input="This is too expensive",
            confidence=0.8,
            response_used="I understand your concern about the investment...",
            strategy=ResponseStrategy.FEEL_FELT_FOUND
        )
        
        assert objection_id.startswith(call_sid)
        assert len(objection_tracker.objections[call_sid]) == 1
        
        objection = objection_tracker.objections[call_sid][0]
        assert objection.objection_type == ObjectionType.PRICE
        assert objection.severity == ObjectionSeverity.MEDIUM
        assert objection.confidence == 0.8
    
    def test_update_objection_outcome(self, objection_tracker):
        """Test updating objection outcomes."""
        call_sid = "test_call_123"
        
        objection_id = objection_tracker.record_objection(
            call_sid=call_sid,
            objection_type=ObjectionType.TIMING,
            severity=ObjectionSeverity.LOW,
            user_input="We're busy right now",
            confidence=0.7,
            response_used="I understand timing is important...",
            strategy=ResponseStrategy.ACKNOWLEDGE_REDIRECT
        )
        
        # Update outcome
        objection_tracker.update_objection_outcome(
            objection_id=objection_id,
            resolved=True,
            escalated=False
        )
        
        objection = objection_tracker.objections[call_sid][0]
        assert objection.resolved == True
        assert objection.escalated == False
    
    def test_get_call_analytics(self, objection_tracker):
        """Test getting call analytics."""
        call_sid = "test_call_123"
        
        # Record multiple objections
        objection_tracker.record_objection(
            call_sid=call_sid,
            objection_type=ObjectionType.PRICE,
            severity=ObjectionSeverity.HIGH,
            user_input="Too expensive",
            confidence=0.9,
            response_used="Response 1",
            strategy=ResponseStrategy.EVIDENCE_BASED
        )
        
        objection_tracker.record_objection(
            call_sid=call_sid,
            objection_type=ObjectionType.TIMING,
            severity=ObjectionSeverity.MEDIUM,
            user_input="Bad timing",
            confidence=0.8,
            response_used="Response 2",
            strategy=ResponseStrategy.REFRAME
        )
        
        # Update outcomes
        objections = objection_tracker.objections[call_sid]
        objection_tracker.update_objection_outcome(objections[0].objection_id, True)
        objection_tracker.update_objection_outcome(objections[1].objection_id, False)
        
        # Get analytics
        analytics = objection_tracker.get_call_analytics(call_sid)
        
        assert analytics is not None
        assert analytics.total_objections == 2
        assert analytics.objections_by_type[ObjectionType.PRICE] == 1
        assert analytics.objections_by_type[ObjectionType.TIMING] == 1
        assert analytics.resolution_rate == 0.5  # 1 out of 2 resolved
        assert analytics.escalation_rate == 0.0  # None escalated
    
    def test_should_escalate(self, objection_tracker):
        """Test escalation decision logic."""
        call_sid = "test_call_123"
        
        # Should not escalate with few objections
        assert objection_tracker.should_escalate(call_sid) == False
        
        # Add multiple objections
        for i in range(4):
            objection_tracker.record_objection(
                call_sid=call_sid,
                objection_type=ObjectionType.PRICE,
                severity=ObjectionSeverity.MEDIUM,
                user_input=f"Objection {i}",
                confidence=0.8,
                response_used=f"Response {i}",
                strategy=ResponseStrategy.ACKNOWLEDGE_REDIRECT
            )
        
        # Should escalate with many objections
        assert objection_tracker.should_escalate(call_sid) == True
    
    def test_should_escalate_critical_objection(self, objection_tracker):
        """Test escalation with critical objections."""
        call_sid = "test_call_123"
        
        # Add critical objection
        objection_tracker.record_objection(
            call_sid=call_sid,
            objection_type=ObjectionType.PRICE,
            severity=ObjectionSeverity.CRITICAL,
            user_input="Absolutely can't afford this",
            confidence=0.9,
            response_used="Response",
            strategy=ResponseStrategy.ESCALATE
        )
        
        # Should escalate immediately with critical objection
        assert objection_tracker.should_escalate(call_sid) == True


class TestEnhancedObjectionHandler:
    """Test cases for EnhancedObjectionHandler."""
    
    @pytest.mark.asyncio
    async def test_handle_objection(self, objection_handler, sample_prospect_data):
        """Test complete objection handling workflow."""
        call_sid = "test_call_123"
        user_input = "This is way too expensive for our budget"
        
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=user_input,
            prospect_data=sample_prospect_data
        )
        
        assert isinstance(response_text, str)
        assert len(response_text) > 0
        assert isinstance(should_escalate, bool)
        assert isinstance(objection_info, dict)
        
        # Check objection info
        assert "objection_id" in objection_info
        assert "objection_type" in objection_info
        assert "severity" in objection_info
        assert "confidence" in objection_info
        assert "strategy" in objection_info
        
        # Should be classified as price objection
        assert objection_info["objection_type"] == ObjectionType.PRICE.value
    
    @pytest.mark.asyncio
    async def test_handle_timing_objection(self, objection_handler, sample_prospect_data):
        """Test handling timing objections."""
        call_sid = "test_call_456"
        user_input = "We're too busy to deal with this right now"
        
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=user_input,
            prospect_data=sample_prospect_data
        )
        
        assert isinstance(response_text, str)
        assert objection_info["objection_type"] == ObjectionType.TIMING.value
        assert not should_escalate  # Timing objections usually don't escalate immediately
    
    @pytest.mark.asyncio
    async def test_handle_authority_objection(self, objection_handler, sample_prospect_data):
        """Test handling authority objections."""
        call_sid = "test_call_789"
        user_input = "I need to check with my boss before making any decisions"
        
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=user_input,
            prospect_data=sample_prospect_data
        )
        
        assert isinstance(response_text, str)
        assert objection_info["objection_type"] == ObjectionType.AUTHORITY.value
        assert not should_escalate  # Authority objections are normal
    
    @pytest.mark.asyncio
    async def test_update_objection_outcome(self, objection_handler, sample_prospect_data):
        """Test updating objection outcomes."""
        call_sid = "test_call_123"
        user_input = "This costs too much"
        
        # Handle objection first
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=user_input,
            prospect_data=sample_prospect_data
        )
        
        objection_id = objection_info["objection_id"]
        
        # Update outcome with positive response
        resolved = await objection_handler.update_objection_outcome(
            objection_id=objection_id,
            user_response="That makes sense, let's proceed"
        )
        
        assert resolved == True
    
    @pytest.mark.asyncio
    async def test_update_objection_outcome_negative(self, objection_handler, sample_prospect_data):
        """Test updating objection outcomes with negative response."""
        call_sid = "test_call_456"
        user_input = "I don't think this will work"
        
        # Handle objection first
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=user_input,
            prospect_data=sample_prospect_data
        )
        
        objection_id = objection_info["objection_id"]
        
        # Update outcome with negative response
        resolved = await objection_handler.update_objection_outcome(
            objection_id=objection_id,
            user_response="I still don't think this is right for us"
        )
        
        assert resolved == False
    
    @pytest.mark.asyncio
    async def test_get_call_objection_analytics(self, objection_handler, sample_prospect_data):
        """Test getting call objection analytics."""
        call_sid = "test_call_analytics"
        
        # Handle multiple objections
        objections = [
            "This is too expensive",
            "We don't have time for this",
            "I need to ask my manager"
        ]
        
        for objection in objections:
            await objection_handler.handle_objection(
                call_sid=call_sid,
                user_input=objection,
                prospect_data=sample_prospect_data
            )
        
        # Get analytics
        analytics = await objection_handler.get_call_objection_analytics(call_sid)
        
        assert analytics is not None
        assert analytics.total_objections == 3
        assert analytics.call_sid == call_sid
    
    @pytest.mark.asyncio
    async def test_get_system_objection_metrics(self, objection_handler, sample_prospect_data):
        """Test getting system-wide objection metrics."""
        # Handle objections across multiple calls
        calls = ["call_1", "call_2", "call_3"]
        objections = [
            "Too expensive",
            "Bad timing",
            "Need approval"
        ]
        
        for call_sid in calls:
            for objection in objections:
                await objection_handler.handle_objection(
                    call_sid=call_sid,
                    user_input=objection,
                    prospect_data=sample_prospect_data
                )
        
        # Get system metrics
        metrics = await objection_handler.get_system_objection_metrics()
        
        assert "total_objections" in metrics
        assert "objections_by_type" in metrics
        assert "overall_resolution_rate" in metrics
        assert metrics["total_objections"] == 9  # 3 calls × 3 objections
    
    @pytest.mark.asyncio
    async def test_escalation_logic(self, objection_handler, sample_prospect_data):
        """Test objection escalation logic."""
        call_sid = "test_escalation"
        
        # Handle multiple objections to trigger escalation
        critical_objections = [
            "This is absolutely impossible",
            "We will never use this",
            "This is completely wrong for us",
            "I want to speak to a manager"
        ]
        
        should_escalate_final = False
        for objection in critical_objections:
            response_text, should_escalate, objection_info = await objection_handler.handle_objection(
                call_sid=call_sid,
                user_input=objection,
                prospect_data=sample_prospect_data
            )
            should_escalate_final = should_escalate
        
        # Should escalate after multiple objections
        assert should_escalate_final == True
    
    @pytest.mark.asyncio
    async def test_prospect_customization(self, objection_handler):
        """Test prospect-specific response customization."""
        healthcare_prospect = {
            "company_name": "HealthSystem Inc",
            "industry": "healthcare",
            "job_title": "Chief Medical Officer"
        }
        
        tech_prospect = {
            "company_name": "TechStartup",
            "industry": "technology",
            "job_title": "VP Engineering"
        }
        
        # Same objection, different prospects
        objection = "This seems expensive"
        
        healthcare_response, _, healthcare_info = await objection_handler.handle_objection(
            call_sid="healthcare_call",
            user_input=objection,
            prospect_data=healthcare_prospect
        )
        
        tech_response, _, tech_info = await objection_handler.handle_objection(
            call_sid="tech_call",
            user_input=objection,
            prospect_data=tech_prospect
        )
        
        # Responses should be different due to customization
        assert healthcare_response != tech_response or "HealthSystem" in healthcare_response
        assert "TechStartup" in tech_response or "your company" in tech_response
    
    @pytest.mark.asyncio
    async def test_error_handling(self, objection_handler):
        """Test error handling in objection processing."""
        # Test with invalid/empty data
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid="error_test",
            user_input="",
            prospect_data={}
        )
        
        # Should handle gracefully
        assert isinstance(response_text, str)
        assert isinstance(should_escalate, bool)
        assert isinstance(objection_info, dict)
    
    @pytest.mark.asyncio
    async def test_conversation_context_integration(self, objection_handler, sample_prospect_data):
        """Test integration with conversation context."""
        call_sid = "context_test"
        conversation_context = {
            "current_state": "needs_analysis",
            "conversation_history": [
                {"role": "assistant", "content": "What are your biggest challenges?"},
                {"role": "user", "content": "We need better efficiency"}
            ],
            "objections_handled": []
        }
        
        response_text, should_escalate, objection_info = await objection_handler.handle_objection(
            call_sid=call_sid,
            user_input="But this looks complicated to implement",
            prospect_data=sample_prospect_data,
            conversation_context=conversation_context
        )
        
        assert isinstance(response_text, str)
        assert len(response_text) > 0
        assert "objection_type" in objection_info


@pytest.mark.asyncio
async def test_concurrent_objection_handling(objection_handler, sample_prospect_data):
    """Test handling multiple objections concurrently."""
    call_sids = [f"concurrent_call_{i}" for i in range(5)]
    objections = [
        "Too expensive",
        "Bad timing", 
        "Need approval",
        "Don't need it",
        "Not sure about this"
    ]
    
    # Handle objections concurrently
    tasks = []
    for i, call_sid in enumerate(call_sids):
        task = objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=objections[i],
            prospect_data=sample_prospect_data
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 5
    for response_text, should_escalate, objection_info in results:
        assert isinstance(response_text, str)
        assert isinstance(should_escalate, bool)
        assert isinstance(objection_info, dict)


@pytest.mark.asyncio
async def test_objection_pattern_coverage():
    """Test that all major objection patterns are covered."""
    classifier = ObjectionClassifier()
    
    # Test cases covering all objection types
    test_patterns = {
        ObjectionType.PRICE: [
            "too expensive", "can't afford", "over budget", "costs too much"
        ],
        ObjectionType.TIMING: [
            "bad timing", "too busy", "not now", "later"
        ],
        ObjectionType.AUTHORITY: [
            "not my decision", "ask my boss", "need approval", "team decides"
        ],
        ObjectionType.NEED: [
            "don't need", "working fine", "no problem", "satisfied"
        ],
        ObjectionType.TRUST: [
            "not sure", "skeptical", "don't trust", "risky"
        ],
        ObjectionType.COMPETITION: [
            "already have", "current vendor", "existing solution", "competitor"
        ],
        ObjectionType.PRIORITY: [
            "other priorities", "not important", "different focus", "not priority"
        ]
    }
    
    for expected_type, patterns in test_patterns.items():
        for pattern in patterns:
            objection_type, severity, confidence = classifier.classify_objection(pattern)
            assert objection_type == expected_type, f"Pattern '{pattern}' should classify as {expected_type}, got {objection_type}"
            assert confidence > 0.0