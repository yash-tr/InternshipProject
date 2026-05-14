"""
Unit tests for the prospect scoring and qualification system.

Tests cover all scoring rules, edge cases, and validation logic
for the rules-based scoring engine and LLM-assisted gray zone classification.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from app.services.prospect_scoring import (
    RulesBasedScoringEngine, CompanySizeScoring, IndustryScoring,
    JobTitleScoring, GeographyScoring, BuyingSignalScoring, RevenueScoring,
    ValueTier, ScoringCategory, ConfidenceLevel, ScoringValidator,
    create_scoring_engine, EnhancedScoringEngine, LLMScoringCache,
    LLMAssistedScoring, ScoringResult
)
from app.schemas.prospect_research import (
    ResearchResultSchema, ContactProfileSchema, CompanyIntelligenceSchema,
    CompanySize, RevenueRange, BuyingSignal, DataSource
)


class TestCompanySizeScoring:
    """Test company size scoring matrix."""
    
    def test_startup_scoring(self):
        """Test startup company scoring."""
        score, rationale = CompanySizeScoring.score_by_employee_count(5)
        assert score == 15
        assert "startup" in rationale.lower()
    
    def test_small_company_scoring(self):
        """Test small company scoring."""
        score, rationale = CompanySizeScoring.score_by_employee_count(25)
        assert score == 25
        assert "small company" in rationale.lower()
    
    def test_medium_company_scoring(self):
        """Test medium company scoring."""
        score, rationale = CompanySizeScoring.score_by_employee_count(100)
        assert score == 35
        assert "medium company" in rationale.lower()
    
    def test_large_company_scoring(self):
        """Test large company scoring."""
        score, rationale = CompanySizeScoring.score_by_employee_count(500)
        assert score == 30
        assert "large company" in rationale.lower()
    
    def test_enterprise_scoring(self):
        """Test enterprise company scoring."""
        score, rationale = CompanySizeScoring.score_by_employee_count(5000)
        assert score == 20
        assert "enterprise" in rationale.lower()
    
    def test_no_employee_count(self):
        """Test scoring with no employee count data."""
        score, rationale = CompanySizeScoring.score_by_employee_count(None)
        assert score == 0
        assert "no employee count" in rationale.lower()


class TestLLMScoringCache:
    """Test LLM scoring cache functionality."""
    
    def test_cache_key_generation(self):
        """Test cache key generation from research data."""
        cache = LLMScoringCache()
        
        contact = ContactProfileSchema(
            job_title="Manager",
            location="Chicago, IL"
        )
        
        company = CompanyIntelligenceSchema(
            company_name="Test Corp",
            industry="Manufacturing",
            employee_count=100
        )
        
        research_data = ResearchResultSchema(
            prospect_id="cache_test",
            contact_profile=contact,
            company_intelligence=company
        )
        
        key1 = cache._generate_cache_key(research_data)
        key2 = cache._generate_cache_key(research_data)
        
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length
    
    def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        cache = LLMScoringCache()
        
        contact = ContactProfileSchema(job_title="Manager")
        company = CompanyIntelligenceSchema(company_name="Test Corp")
        research_data = ResearchResultSchema(
            prospect_id="cache_test",
            contact_profile=contact,
            company_intelligence=company
        )
        
        test_result = {
            "adjusted_score": 52,
            "confidence": 0.8,
            "rationale": "Test rationale"
        }
        
        # Test cache miss
        assert cache.get(research_data) is None
        
        # Test cache set and hit
        cache.set(research_data, test_result)
        cached_result = cache.get(research_data)
        
        assert cached_result is not None
        assert cached_result["adjusted_score"] == 52
        assert cached_result["confidence"] == 0.8
        assert cached_result["rationale"] == "Test rationale"


class TestLLMAssistedScoring:
    """Test LLM-assisted scoring functionality."""
    
    @pytest.fixture
    def llm_scorer(self):
        """Create LLM scorer for testing."""
        return LLMAssistedScoring()
    
    def test_budget_tracking(self, llm_scorer):
        """Test budget tracking functionality."""
        # Test initial budget state
        status = llm_scorer.get_budget_status()
        assert status["daily_budget_cents"] == 500
        assert status["daily_spend_cents"] == 0
        assert status["remaining_budget_cents"] == 500
        assert status["budget_utilization"] == 0.0
    
    def test_cost_estimation(self, llm_scorer):
        """Test cost estimation for LLM calls."""
        short_prompt = "Short prompt"
        long_prompt = "This is a much longer prompt that should cost more to process" * 10
        
        short_cost = llm_scorer._estimate_cost(len(short_prompt))
        long_cost = llm_scorer._estimate_cost(len(long_prompt))
        
        assert short_cost > 0
        assert long_cost > short_cost
        assert isinstance(short_cost, float)
        assert isinstance(long_cost, float)
    
    def test_budget_check(self, llm_scorer):
        """Test budget availability checking."""
        # Should have budget available initially
        assert llm_scorer._check_budget_available(100) == True
        
        # Simulate spending most of the budget
        llm_scorer.daily_spend_cents = 450
        
        # Should still have budget for small amount
        assert llm_scorer._check_budget_available(40) == True
        
        # Should not have budget for large amount
        assert llm_scorer._check_budget_available(100) == False


class TestRulesBasedScoringEngine:
    """Test the complete rules-based scoring engine."""
    
    @pytest.fixture
    def scoring_engine(self):
        """Create a scoring engine for testing."""
        return RulesBasedScoringEngine()
    
    @pytest.fixture
    def sample_research_data(self):
        """Create sample research data for testing."""
        contact = ContactProfileSchema(
            job_title="VP of Engineering",
            location="San Francisco, CA"
        )
        
        company = CompanyIntelligenceSchema(
            company_name="TechCorp Inc",
            industry="Software Technology",
            employee_count=150,
            revenue_range=RevenueRange.RANGE_10M_50M
        )
        
        buying_signals = [
            BuyingSignal(
                signal_type="budget_mentioned",
                description="Budget approved",
                confidence=0.9,
                source=DataSource.MANUAL_RESEARCH
            ),
            BuyingSignal(
                signal_type="timeline_mentioned", 
                description="Need solution this quarter",
                confidence=0.8,
                source=DataSource.MANUAL_RESEARCH
            )
        ]
        
        return ResearchResultSchema(
            prospect_id="test_prospect_001",
            contact_profile=contact,
            company_intelligence=company,
            buying_signals=buying_signals,
            overall_confidence=0.8
        )
    
    @pytest.mark.asyncio
    async def test_complete_scoring(self, scoring_engine, sample_research_data):
        """Test complete prospect scoring."""
        result = await scoring_engine.score_prospect(sample_research_data)
        
        assert isinstance(result.total_score, int)
        assert 0 <= result.total_score <= 100
        assert result.value_tier in [ValueTier.A_TIER, ValueTier.B_TIER, ValueTier.C_TIER, ValueTier.UNQUALIFIED]
        assert result.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]
        assert len(result.applied_rules) > 0
        assert len(result.scoring_rationale) > 0


class TestEnhancedScoringEngine:
    """Test the enhanced scoring engine with LLM assistance."""
    
    @pytest.fixture
    def enhanced_engine(self):
        """Create enhanced scoring engine for testing."""
        return EnhancedScoringEngine()
    
    @pytest.mark.asyncio
    async def test_enhanced_scoring_without_llm_review(self, enhanced_engine):
        """Test enhanced scoring for cases that don't need LLM review."""
        # High-scoring prospect that doesn't need LLM review
        contact = ContactProfileSchema(
            job_title="CEO",
            location="San Francisco, CA"
        )
        
        company = CompanyIntelligenceSchema(
            company_name="TechCorp",
            industry="SaaS",
            employee_count=200,
            revenue_range=RevenueRange.RANGE_50M_100M
        )
        
        buying_signals = [
            BuyingSignal(
                signal_type="budget_mentioned",
                description="Budget approved",
                confidence=0.9,
                source=DataSource.MANUAL_RESEARCH
            )
        ]
        
        research_data = ResearchResultSchema(
            prospect_id="high_score_test",
            contact_profile=contact,
            company_intelligence=company,
            buying_signals=buying_signals,
            overall_confidence=0.9
        )
        
        result = await enhanced_engine.score_prospect(research_data)
        
        # Should be high score without LLM review
        assert result.total_score >= 70
        assert result.requires_llm_review == False
        assert "LLM Enhancement" not in result.scoring_rationale


class TestScoringEngineFactory:
    """Test the enhanced scoring engine factory."""
    
    def test_create_rules_based_engine(self):
        """Test creating rules-based engine."""
        engine = create_scoring_engine(use_llm_enhancement=False)
        
        assert isinstance(engine, RulesBasedScoringEngine)
        assert not isinstance(engine, EnhancedScoringEngine)
    
    def test_create_enhanced_engine(self):
        """Test creating enhanced engine."""
        engine = create_scoring_engine(use_llm_enhancement=True)
        
        assert isinstance(engine, EnhancedScoringEngine)
        assert hasattr(engine, 'llm_scorer')
    
    def test_default_enhanced_engine(self):
        """Test default engine creation (should be enhanced)."""
        engine = create_scoring_engine()
        
        assert isinstance(engine, EnhancedScoringEngine)


# Integration test fixtures
@pytest.fixture
def high_value_research_data():
    """High-value prospect research data."""
    contact = ContactProfileSchema(
        job_title="Chief Technology Officer",
        location="San Francisco, CA",
        experience_years=15
    )
    
    company = CompanyIntelligenceSchema(
        company_name="TechUnicorn Inc",
        industry="SaaS",
        employee_count=250,
        revenue_range=RevenueRange.RANGE_50M_100M
    )
    
    buying_signals = [
        BuyingSignal(
            signal_type="budget_mentioned",
            description="Budget approved for new platform",
            confidence=0.9,
            source=DataSource.MANUAL_RESEARCH
        ),
        BuyingSignal(
            signal_type="timeline_mentioned",
            description="Need implementation this quarter",
            confidence=0.8,
            source=DataSource.MANUAL_RESEARCH
        ),
        BuyingSignal(
            signal_type="pain_point_expressed",
            description="Current solution causing customer churn",
            confidence=0.9,
            source=DataSource.MANUAL_RESEARCH
        )
    ]
    
    return ResearchResultSchema(
        prospect_id="high_value_test",
        contact_profile=contact,
        company_intelligence=company,
        buying_signals=buying_signals,
        overall_confidence=0.9
    )


class TestIntegrationScenarios:
    """Integration tests for complete scoring scenarios."""
    
    @pytest.mark.asyncio
    async def test_high_value_scenario(self, high_value_research_data):
        """Test complete high-value prospect scoring scenario."""
        engine = create_scoring_engine(use_llm_enhancement=False)  # Use rules-based for predictable results
        result = await engine.score_prospect(high_value_research_data)
        
        assert result.total_score >= 75
        assert result.value_tier == ValueTier.A_TIER
        assert result.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]
        assert "CTO" in result.scoring_rationale or "Chief Technology Officer" in result.scoring_rationale
        assert "SaaS" in result.scoring_rationale
        assert len(result.applied_rules) >= 4
    
    @pytest.mark.asyncio
    async def test_cost_controlled_llm_usage(self):
        """Test that LLM usage is properly cost-controlled."""
        llm_scorer = LLMAssistedScoring()
        
        # Set very low budget
        llm_scorer.daily_budget_cents = 1  # $0.01
        
        contact = ContactProfileSchema(job_title="Manager")
        company = CompanyIntelligenceSchema(company_name="Test Corp")
        research_data = ResearchResultSchema(
            prospect_id="budget_test",
            contact_profile=contact,
            company_intelligence=company
        )
        
        # Should return None due to budget constraints
        result = await llm_scorer.score_gray_zone_prospect(research_data, 50)
        assert result is None
        
        # Budget status should show budget exceeded
        status = llm_scorer.get_budget_status()
        assert status["remaining_budget_cents"] <= 1


class TestValueTierRouter:
    """Test value tier assignment and routing functionality."""
    
    @pytest.fixture
    def tier_router(self):
        """Create tier router for testing."""
        from app.services.prospect_scoring import ValueTierRouter
        return ValueTierRouter()
    
    @pytest.fixture
    def a_tier_scoring_result(self):
        """Create A-tier scoring result for testing."""
        return ScoringResult(
            total_score=85,
            category_scores={
                ScoringCategory.COMPANY_SIZE: 35,
                ScoringCategory.REVENUE: 40,
                ScoringCategory.INDUSTRY: 40,
                ScoringCategory.JOB_TITLE: 45,
                ScoringCategory.GEOGRAPHY: 25,
                ScoringCategory.BUYING_SIGNALS: 45
            },
            applied_rules=["High-value prospect rules applied"],
            confidence_level=ConfidenceLevel.HIGH,
            value_tier=ValueTier.A_TIER,
            scoring_rationale="High-value prospect with strong buying potential",
            requires_llm_review=False
        )
    
    @pytest.fixture
    def b_tier_scoring_result(self):
        """Create B-tier scoring result for testing."""
        return ScoringResult(
            total_score=65,
            category_scores={
                ScoringCategory.COMPANY_SIZE: 25,
                ScoringCategory.REVENUE: 30,
                ScoringCategory.INDUSTRY: 25,
                ScoringCategory.JOB_TITLE: 35,
                ScoringCategory.GEOGRAPHY: 20,
                ScoringCategory.BUYING_SIGNALS: 25
            },
            applied_rules=["Medium-value prospect rules applied"],
            confidence_level=ConfidenceLevel.MEDIUM,
            value_tier=ValueTier.B_TIER,
            scoring_rationale="Medium-value prospect worth pursuing",
            requires_llm_review=False
        )
    
    @pytest.fixture
    def c_tier_scoring_result(self):
        """Create C-tier scoring result for testing."""
        return ScoringResult(
            total_score=45,
            category_scores={
                ScoringCategory.COMPANY_SIZE: 15,
                ScoringCategory.REVENUE: 20,
                ScoringCategory.INDUSTRY: 15,
                ScoringCategory.JOB_TITLE: 25,
                ScoringCategory.GEOGRAPHY: 15,
                ScoringCategory.BUYING_SIGNALS: 10
            },
            applied_rules=["Lower-value prospect rules applied"],
            confidence_level=ConfidenceLevel.LOW,
            value_tier=ValueTier.C_TIER,
            scoring_rationale="Lower-value prospect for nurture campaigns",
            requires_llm_review=False
        )
    
    def test_tier_routing_rules_initialization(self, tier_router):
        """Test that routing rules are properly initialized."""
        assert len(tier_router.routing_rules) == 4
        assert ValueTier.A_TIER in tier_router.routing_rules
        assert ValueTier.B_TIER in tier_router.routing_rules
        assert ValueTier.C_TIER in tier_router.routing_rules
        assert ValueTier.UNQUALIFIED in tier_router.routing_rules
        
        # Test A-tier rule
        a_rule = tier_router.routing_rules[ValueTier.A_TIER]
        assert a_rule.priority_weight == 1.0
        assert a_rule.max_staleness_hours == 2
        assert a_rule.routing_destination == "high_value_queue"
        assert a_rule.workflow_config["immediate_notification"] == True
        assert a_rule.workflow_config["sales_rep_assignment"] == "senior"
    
    def test_a_tier_assignment_and_routing(self, tier_router, a_tier_scoring_result):
        """Test A-tier prospect assignment and routing."""
        prospect_id = "a_tier_test_001"
        
        queue_item = tier_router.assign_tier_and_route(prospect_id, a_tier_scoring_result)
        
        assert queue_item.prospect_id == prospect_id
        assert queue_item.tier == ValueTier.A_TIER
        assert queue_item.score == 85
        assert queue_item.confidence == ConfidenceLevel.HIGH
        assert queue_item.routing_destination == "high_value_queue"
        assert queue_item.priority_score > 0.8  # Should be high priority
        assert queue_item.workflow_config["immediate_notification"] == True
        assert queue_item.workflow_config["sales_rep_assignment"] == "senior"
    
    def test_b_tier_assignment_and_routing(self, tier_router, b_tier_scoring_result):
        """Test B-tier prospect assignment and routing."""
        prospect_id = "b_tier_test_001"
        
        queue_item = tier_router.assign_tier_and_route(prospect_id, b_tier_scoring_result)
        
        assert queue_item.prospect_id == prospect_id
        assert queue_item.tier == ValueTier.B_TIER
        assert queue_item.score == 65
        assert queue_item.confidence == ConfidenceLevel.MEDIUM
        assert queue_item.routing_destination == "standard_queue"
        assert 0.4 < queue_item.priority_score < 0.8  # Medium priority
        assert queue_item.workflow_config["immediate_notification"] == False
        assert queue_item.workflow_config["sales_rep_assignment"] == "standard"
    
    def test_c_tier_assignment_and_routing(self, tier_router, c_tier_scoring_result):
        """Test C-tier prospect assignment and routing."""
        prospect_id = "c_tier_test_001"
        
        queue_item = tier_router.assign_tier_and_route(prospect_id, c_tier_scoring_result)
        
        assert queue_item.prospect_id == prospect_id
        assert queue_item.tier == ValueTier.C_TIER
        assert queue_item.score == 45
        assert queue_item.confidence == ConfidenceLevel.LOW
        assert queue_item.routing_destination == "nurture_queue"
        assert queue_item.priority_score < 0.5  # Lower priority
        assert queue_item.workflow_config["follow_up_cadence"] == "nurture"
        assert queue_item.workflow_config["sales_rep_assignment"] == "junior"
    
    def test_priority_queue_ordering(self, tier_router, a_tier_scoring_result, b_tier_scoring_result, c_tier_scoring_result):
        """Test that prospects are properly ordered in priority queue."""
        # Add prospects in reverse priority order
        c_item = tier_router.assign_tier_and_route("c_prospect", c_tier_scoring_result)
        b_item = tier_router.assign_tier_and_route("b_prospect", b_tier_scoring_result)
        a_item = tier_router.assign_tier_and_route("a_prospect", a_tier_scoring_result)
        
        # Queue should be ordered by priority (A, B, C)
        queue = tier_router.get_next_prospects(limit=3)
        
        assert len(queue) == 3
        assert queue[0].prospect_id == "a_prospect"  # Highest priority
        assert queue[1].prospect_id == "b_prospect"  # Medium priority
        assert queue[2].prospect_id == "c_prospect"  # Lowest priority
        
        # Priority scores should be in descending order
        assert queue[0].priority_score > queue[1].priority_score
        assert queue[1].priority_score > queue[2].priority_score
    
    def test_tier_filtering(self, tier_router, a_tier_scoring_result, b_tier_scoring_result):
        """Test filtering prospects by tier."""
        tier_router.assign_tier_and_route("a_prospect", a_tier_scoring_result)
        tier_router.assign_tier_and_route("b_prospect", b_tier_scoring_result)
        
        # Filter for A-tier only
        a_prospects = tier_router.get_next_prospects(tier_filter=ValueTier.A_TIER, limit=10)
        assert len(a_prospects) == 1
        assert a_prospects[0].tier == ValueTier.A_TIER
        
        # Filter for B-tier only
        b_prospects = tier_router.get_next_prospects(tier_filter=ValueTier.B_TIER, limit=10)
        assert len(b_prospects) == 1
        assert b_prospects[0].tier == ValueTier.B_TIER
        
        # Filter for non-existent tier
        c_prospects = tier_router.get_next_prospects(tier_filter=ValueTier.C_TIER, limit=10)
        assert len(c_prospects) == 0
    
    def test_tier_update(self, tier_router, b_tier_scoring_result, a_tier_scoring_result):
        """Test updating prospect tier assignment."""
        prospect_id = "tier_update_test"
        
        # Initially assign as B-tier
        initial_item = tier_router.assign_tier_and_route(prospect_id, b_tier_scoring_result)
        assert initial_item.tier == ValueTier.B_TIER
        
        # Update to A-tier
        updated_item = tier_router.update_tier_assignment(prospect_id, a_tier_scoring_result)
        assert updated_item is not None
        assert updated_item.tier == ValueTier.A_TIER
        assert updated_item.score == 85
        assert updated_item.routing_destination == "high_value_queue"
        
        # Check that tier adjustment was tracked
        analytics = tier_router.get_tier_analytics()
        assert "B_to_A" in analytics["tier_adjustments"]
        assert analytics["tier_adjustments"]["B_to_A"] == 1
    
    def test_prospect_removal(self, tier_router, a_tier_scoring_result):
        """Test removing prospect from queue."""
        prospect_id = "removal_test"
        
        # Add prospect
        tier_router.assign_tier_and_route(prospect_id, a_tier_scoring_result)
        initial_queue_size = len(tier_router.prospect_queue)
        assert initial_queue_size == 1
        
        # Remove prospect
        removed = tier_router.remove_prospect_from_queue(prospect_id)
        assert removed == True
        assert len(tier_router.prospect_queue) == 0
        
        # Try to remove non-existent prospect
        removed_again = tier_router.remove_prospect_from_queue(prospect_id)
        assert removed_again == False
    
    def test_conversion_tracking(self, tier_router, a_tier_scoring_result):
        """Test conversion tracking for analytics."""
        prospect_id = "conversion_test"
        
        # Add A-tier prospect
        tier_router.assign_tier_and_route(prospect_id, a_tier_scoring_result)
        
        # Record conversion
        tier_router.record_conversion(prospect_id, "meeting_booked")
        
        # Check analytics
        analytics = tier_router.get_tier_analytics()
        a_tier_performance = analytics["tier_performance"]["A"]
        assert a_tier_performance["conversion_count"] == 1
        assert a_tier_performance["total_prospects"] == 1
        assert a_tier_performance["conversion_rate"] == 1.0
    
    def test_tier_analytics(self, tier_router, a_tier_scoring_result, b_tier_scoring_result, c_tier_scoring_result):
        """Test comprehensive tier analytics."""
        # Add multiple prospects
        tier_router.assign_tier_and_route("a1", a_tier_scoring_result)
        tier_router.assign_tier_and_route("a2", a_tier_scoring_result)
        tier_router.assign_tier_and_route("b1", b_tier_scoring_result)
        tier_router.assign_tier_and_route("c1", c_tier_scoring_result)
        
        # Record some conversions
        tier_router.record_conversion("a1", "meeting_booked")
        tier_router.record_conversion("b1", "meeting_booked")
        
        analytics = tier_router.get_tier_analytics()
        
        # Check tier performance
        assert analytics["tier_performance"]["A"]["total_prospects"] == 2
        assert analytics["tier_performance"]["A"]["conversion_count"] == 1
        assert analytics["tier_performance"]["A"]["conversion_rate"] == 0.5
        assert analytics["tier_performance"]["A"]["average_score"] == 85
        
        assert analytics["tier_performance"]["B"]["total_prospects"] == 1
        assert analytics["tier_performance"]["B"]["conversion_count"] == 1
        assert analytics["tier_performance"]["B"]["conversion_rate"] == 1.0
        
        assert analytics["tier_performance"]["C"]["total_prospects"] == 1
        assert analytics["tier_performance"]["C"]["conversion_count"] == 0
        assert analytics["tier_performance"]["C"]["conversion_rate"] == 0.0
        
        # Check queue health
        queue_health = analytics["queue_health"]
        assert queue_health["status"] in ["healthy", "warning", "unhealthy"]
        assert "tier_distribution" in queue_health
        assert queue_health["tier_distribution"]["A"] == 2
        assert queue_health["tier_distribution"]["B"] == 1
        assert queue_health["tier_distribution"]["C"] == 1
    
    def test_workflow_config_retrieval(self, tier_router):
        """Test retrieving workflow configuration for tiers."""
        a_config = tier_router.get_workflow_config_for_tier(ValueTier.A_TIER)
        assert a_config["immediate_notification"] == True
        assert a_config["sales_rep_assignment"] == "senior"
        assert a_config["follow_up_cadence"] == "aggressive"
        
        c_config = tier_router.get_workflow_config_for_tier(ValueTier.C_TIER)
        assert c_config["immediate_notification"] == False
        assert c_config["sales_rep_assignment"] == "junior"
        assert c_config["follow_up_cadence"] == "nurture"
    
    def test_routing_destination_retrieval(self, tier_router):
        """Test retrieving routing destinations for tiers."""
        assert tier_router.get_routing_destination_for_tier(ValueTier.A_TIER) == "high_value_queue"
        assert tier_router.get_routing_destination_for_tier(ValueTier.B_TIER) == "standard_queue"
        assert tier_router.get_routing_destination_for_tier(ValueTier.C_TIER) == "nurture_queue"
        assert tier_router.get_routing_destination_for_tier(ValueTier.UNQUALIFIED) == "unqualified_queue"
    
    def test_optimization_recommendations(self, tier_router):
        """Test tier threshold optimization recommendations."""
        # Add prospects with various performance patterns
        for i in range(15):  # Enough data for meaningful analysis
            if i < 5:  # A-tier prospects with low conversion
                scoring_result = ScoringResult(
                    total_score=85, category_scores={}, applied_rules=[],
                    confidence_level=ConfidenceLevel.HIGH, value_tier=ValueTier.A_TIER,
                    scoring_rationale="", requires_llm_review=False
                )
                tier_router.assign_tier_and_route(f"a_{i}", scoring_result)
                # Only convert 1 out of 5 (20% conversion rate)
                if i == 0:
                    tier_router.record_conversion(f"a_{i}")
            elif i < 10:  # B-tier prospects with good conversion
                scoring_result = ScoringResult(
                    total_score=65, category_scores={}, applied_rules=[],
                    confidence_level=ConfidenceLevel.MEDIUM, value_tier=ValueTier.B_TIER,
                    scoring_rationale="", requires_llm_review=False
                )
                tier_router.assign_tier_and_route(f"b_{i}", scoring_result)
                # Convert 3 out of 5 (60% conversion rate)
                if i < 8:
                    tier_router.record_conversion(f"b_{i}")
            else:  # C-tier prospects
                scoring_result = ScoringResult(
                    total_score=45, category_scores={}, applied_rules=[],
                    confidence_level=ConfidenceLevel.LOW, value_tier=ValueTier.C_TIER,
                    scoring_rationale="", requires_llm_review=False
                )
                tier_router.assign_tier_and_route(f"c_{i}", scoring_result)
        
        recommendations = tier_router.optimize_tier_thresholds()
        
        assert "threshold_recommendations" in recommendations
        assert "adjustment_patterns" in recommendations
        assert "optimization_priority" in recommendations
        assert "data_confidence" in recommendations
        
        # Should recommend raising A-tier threshold due to low conversion
        a_tier_recs = [r for r in recommendations["threshold_recommendations"] if r["tier"] == "A"]
        assert len(a_tier_recs) > 0
        assert "Low A-tier conversion rate" in a_tier_recs[0]["issue"]


class TestCompleteScoringSystem:
    """Test the complete scoring system with tier assignment and routing."""
    
    @pytest.fixture
    def complete_system(self):
        """Create complete scoring system for testing."""
        from app.services.prospect_scoring import CompleteScoringSystem
        return CompleteScoringSystem()
    
    @pytest.mark.asyncio
    async def test_complete_scoring_and_routing_workflow(self, complete_system, high_value_research_data):
        """Test the complete end-to-end scoring and routing workflow."""
        prospect_id = "complete_workflow_test"
        
        # Execute complete workflow
        scoring_result, queue_item = await complete_system.score_and_route_prospect(
            prospect_id, high_value_research_data
        )
        
        # Verify scoring result
        assert isinstance(scoring_result, ScoringResult)
        assert scoring_result.total_score > 0
        assert scoring_result.value_tier in [ValueTier.A_TIER, ValueTier.B_TIER, ValueTier.C_TIER, ValueTier.UNQUALIFIED]
        
        # Verify queue item
        assert queue_item.prospect_id == prospect_id
        assert queue_item.tier == scoring_result.value_tier
        assert queue_item.score == scoring_result.total_score
        assert queue_item.priority_score > 0
        assert queue_item.routing_destination in ["high_value_queue", "standard_queue", "nurture_queue", "unqualified_queue"]
        
        # Verify workflow configuration is appropriate for tier
        if queue_item.tier == ValueTier.A_TIER:
            assert queue_item.workflow_config["immediate_notification"] == True
            assert queue_item.workflow_config["sales_rep_assignment"] == "senior"
        elif queue_item.tier == ValueTier.B_TIER:
            assert queue_item.workflow_config["sales_rep_assignment"] == "standard"
        elif queue_item.tier == ValueTier.C_TIER:
            assert queue_item.workflow_config["follow_up_cadence"] == "nurture"
    
    def test_get_next_prospects_for_processing(self, complete_system):
        """Test getting next prospects for processing."""
        # Initially should be empty
        prospects = complete_system.get_next_prospects_for_processing()
        assert len(prospects) == 0
        
        # Add some prospects through the tier router directly for testing
        from app.services.prospect_scoring import ScoringResult, ValueTier, ConfidenceLevel
        
        scoring_result = ScoringResult(
            total_score=85, category_scores={}, applied_rules=[],
            confidence_level=ConfidenceLevel.HIGH, value_tier=ValueTier.A_TIER,
            scoring_rationale="", requires_llm_review=False
        )
        
        complete_system.tier_router.assign_tier_and_route("test_prospect", scoring_result)
        
        # Should now return the prospect
        prospects = complete_system.get_next_prospects_for_processing(limit=5)
        assert len(prospects) == 1
        assert prospects[0].prospect_id == "test_prospect"
    
    def test_system_analytics(self, complete_system):
        """Test comprehensive system analytics."""
        analytics = complete_system.get_system_analytics()
        
        assert "tier_analytics" in analytics
        assert "llm_budget_status" in analytics
        assert "system_health" in analytics
        
        # Check system health structure
        system_health = analytics["system_health"]
        assert "queue_health" in system_health
        assert "llm_budget_utilization" in system_health
        assert "total_prospects_processed" in system_health
    
    def test_system_optimization(self, complete_system):
        """Test system optimization recommendations."""
        optimization = complete_system.optimize_system_performance()
        
        assert "threshold_recommendations" in optimization
        assert "adjustment_patterns" in optimization
        assert "optimization_priority" in optimization
        assert "data_confidence" in optimization