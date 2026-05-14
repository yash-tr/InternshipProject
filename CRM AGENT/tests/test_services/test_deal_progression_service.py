"""
Tests for Deal Progression Service

Tests deal stage management, outcome tracking, Salesforce integration,
and analytics for the deal progression service.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from app.services.deal_progression_service import (
    DealProgressionService,
    DealProgression,
    DealStage,
    DealOutcome,
    HandoffReason,
    DealMetrics
)


@pytest.fixture
def deal_service():
    """Create a deal progression service instance for testing."""
    return DealProgressionService()


@pytest.fixture
def sample_prospect_data():
    """Sample prospect data for testing."""
    return {
        'company_name': 'Test Corp',
        'contact_name': 'John Doe',
        'job_title': 'CTO',
        'industry': 'Technology',
        'employee_count': '100-500',
        'revenue': '$10M-50M',
        'phone': '+1-555-0123',
        'email': 'john.doe@testcorp.com'
    }


@pytest.fixture
def sample_deal_data():
    """Sample deal data for testing."""
    return {
        'deal_id': 'test_deal_123',
        'lead_id': 'test_lead_456',
        'call_sid': 'test_call_789'
    }


class TestDealProgression:
    """Test DealProgression data class functionality."""
    
    def test_deal_progression_initialization(self, sample_deal_data, sample_prospect_data):
        """Test deal progression initialization."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        assert deal.deal_id == sample_deal_data['deal_id']
        assert deal.lead_id == sample_deal_data['lead_id']
        assert deal.call_sid == sample_deal_data['call_sid']
        assert deal.current_stage == DealStage.INITIAL_CONTACT
        assert deal.final_outcome is None
        assert deal.is_active() is True
        assert deal.is_qualified() is False  # Default qualification score is 0
        assert deal.metrics.deal_id == sample_deal_data['deal_id']
    
    def test_deal_qualification_status(self, sample_deal_data, sample_prospect_data):
        """Test deal qualification status."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        # Initially not qualified
        assert deal.is_qualified() is False
        
        # Set qualification score above threshold
        deal.metrics.qualification_score = 70
        assert deal.is_qualified() is True
    
    def test_deal_active_status(self, sample_deal_data, sample_prospect_data):
        """Test deal active status."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        # Initially active
        assert deal.is_active() is True
        
        # Set to closed stage
        deal.current_stage = DealStage.CLOSED_WON
        assert deal.is_active() is False
        
        deal.current_stage = DealStage.CLOSED_LOST
        assert deal.is_active() is False
        
        deal.current_stage = DealStage.TRANSFERRED
        assert deal.is_active() is False
    
    def test_needs_human_intervention(self, sample_deal_data, sample_prospect_data):
        """Test human intervention detection."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        # Initially doesn't need intervention
        assert deal.needs_human_intervention() is False
        
        # High qualification score
        deal.metrics.qualification_score = 85
        assert deal.needs_human_intervention() is True
        
        # Reset and test objections
        deal.metrics.qualification_score = 50
        deal.metrics.objections_handled = 4
        assert deal.needs_human_intervention() is True
        
        # Reset and test handoff flag
        deal.metrics.objections_handled = 1
        deal.requires_handoff = True
        assert deal.needs_human_intervention() is True


class TestDealMetrics:
    """Test DealMetrics functionality."""
    
    def test_deal_metrics_initialization(self):
        """Test deal metrics initialization."""
        metrics = DealMetrics("test_deal_123")
        
        assert metrics.deal_id == "test_deal_123"
        assert metrics.total_interactions == 0
        assert metrics.qualification_score == 0
        assert metrics.engagement_score == 0.0
        assert metrics.buying_signals_count == 0
        assert metrics.conversion_probability == 0.0
        assert metrics.estimated_deal_value == 0.0
    
    def test_calculate_total_duration(self):
        """Test total duration calculation."""
        metrics = DealMetrics("test_deal_123")
        
        # Set times 30 minutes apart
        metrics.first_contact = datetime.utcnow() - timedelta(minutes=30)
        metrics.last_interaction = datetime.utcnow()
        
        duration = metrics.calculate_total_duration_minutes()
        assert 29 <= duration <= 31  # Allow for small timing differences
    
    def test_stage_duration_tracking(self):
        """Test stage duration tracking."""
        metrics = DealMetrics("test_deal_123")
        
        # Add stage durations
        metrics.stage_duration_minutes[DealStage.INITIAL_CONTACT] = 5.0
        metrics.stage_duration_minutes[DealStage.QUALIFICATION] = 10.0
        
        assert metrics.get_current_stage_duration(DealStage.INITIAL_CONTACT) == 5.0
        assert metrics.get_current_stage_duration(DealStage.QUALIFICATION) == 10.0
        assert metrics.get_current_stage_duration(DealStage.NEEDS_ANALYSIS) == 0.0


class TestDealProgressionService:
    """Test deal progression service functionality."""
    
    @pytest.mark.asyncio
    async def test_create_deal(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test deal creation."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            deal = await deal_service.create_deal(
                deal_id=sample_deal_data['deal_id'],
                lead_id=sample_deal_data['lead_id'],
                call_sid=sample_deal_data['call_sid'],
                prospect_data=sample_prospect_data
            )
            
            assert deal.deal_id == sample_deal_data['deal_id']
            assert deal.current_stage == DealStage.INITIAL_CONTACT
            assert len(deal.stage_history) == 1
            assert deal.stage_history[0].event_type == "deal_created"
            
            # Check it's stored in active deals
            assert sample_deal_data['deal_id'] in deal_service.active_deals
            assert deal_service.daily_stats['deals_created'] == 1
    
    @pytest.mark.asyncio
    async def test_update_deal_stage_valid_transition(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test valid deal stage update."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create deal
            deal = await deal_service.create_deal(
                deal_id=sample_deal_data['deal_id'],
                lead_id=sample_deal_data['lead_id'],
                call_sid=sample_deal_data['call_sid'],
                prospect_data=sample_prospect_data
            )
            
            # Update to qualification stage
            success = await deal_service.update_deal_stage(
                deal_id=sample_deal_data['deal_id'],
                new_stage=DealStage.QUALIFICATION,
                reason="Prospect showed interest",
                confidence=0.8
            )
            
            assert success is True
            assert deal.current_stage == DealStage.QUALIFICATION
            assert len(deal.stage_history) == 2
            assert deal.stage_history[1].event_type == "stage_change"
            assert deal.stage_history[1].from_stage == DealStage.INITIAL_CONTACT
            assert deal.stage_history[1].to_stage == DealStage.QUALIFICATION
    
    @pytest.mark.asyncio
    async def test_update_deal_stage_invalid_transition(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test invalid deal stage update."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create deal
            await deal_service.create_deal(
                deal_id=sample_deal_data['deal_id'],
                lead_id=sample_deal_data['lead_id'],
                call_sid=sample_deal_data['call_sid'],
                prospect_data=sample_prospect_data
            )
            
            # Try invalid transition (initial_contact -> closing)
            success = await deal_service.update_deal_stage(
                deal_id=sample_deal_data['deal_id'],
                new_stage=DealStage.CLOSING,
                reason="Invalid transition test"
            )
            
            assert success is False
            deal = deal_service.active_deals[sample_deal_data['deal_id']]
            assert deal.current_stage == DealStage.INITIAL_CONTACT  # Should remain unchanged
    
    @pytest.mark.asyncio
    async def test_record_deal_outcome_positive(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test recording positive deal outcome."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            with patch.object(deal_service, '_sync_outcome_to_salesforce', new_callable=AsyncMock, return_value=True):
                with patch.object(deal_service, '_create_handoff_for_outcome', new_callable=AsyncMock):
                    # Create and progress deal
                    deal = await deal_service.create_deal(
                        deal_id=sample_deal_data['deal_id'],
                        lead_id=sample_deal_data['lead_id'],
                        call_sid=sample_deal_data['call_sid'],
                        prospect_data=sample_prospect_data
                    )
                    
                    # Record positive outcome
                    success = await deal_service.record_deal_outcome(
                        deal_id=sample_deal_data['deal_id'],
                        outcome=DealOutcome.MEETING_SCHEDULED,
                        estimated_value=25000.0,
                        next_steps="Schedule demo for next week"
                    )
                    
                    assert success is True
                    assert deal.final_outcome == DealOutcome.MEETING_SCHEDULED
                    assert deal.metrics.estimated_deal_value == 25000.0
                    assert deal.completed_at is not None
                    assert deal_service.daily_stats['meetings_scheduled'] == 1
    
    @pytest.mark.asyncio
    async def test_record_deal_outcome_negative(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test recording negative deal outcome."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            with patch.object(deal_service, '_sync_outcome_to_salesforce', new_callable=AsyncMock, return_value=True):
                # Create deal
                deal = await deal_service.create_deal(
                    deal_id=sample_deal_data['deal_id'],
                    lead_id=sample_deal_data['lead_id'],
                    call_sid=sample_deal_data['call_sid'],
                    prospect_data=sample_prospect_data
                )
                
                # Record negative outcome
                success = await deal_service.record_deal_outcome(
                    deal_id=sample_deal_data['deal_id'],
                    outcome=DealOutcome.NOT_INTERESTED,
                    details={'reason': 'Already have a solution'}
                )
                
                assert success is True
                assert deal.final_outcome == DealOutcome.NOT_INTERESTED
                assert deal.current_stage == DealStage.CLOSED_LOST
                
                # Should be removed from active deals
                assert sample_deal_data['deal_id'] not in deal_service.active_deals
                assert deal_service.daily_stats['deals_completed'] == 1
    
    @pytest.mark.asyncio
    async def test_create_handoff(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test creating handoff to human rep."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            with patch.object(deal_service, '_create_salesforce_handoff_task', new_callable=AsyncMock, return_value=True):
                # Create deal
                deal = await deal_service.create_deal(
                    deal_id=sample_deal_data['deal_id'],
                    lead_id=sample_deal_data['lead_id'],
                    call_sid=sample_deal_data['call_sid'],
                    prospect_data=sample_prospect_data
                )
                
                # Create handoff
                success = await deal_service.create_handoff(
                    deal_id=sample_deal_data['deal_id'],
                    reason=HandoffReason.HIGH_VALUE_DEAL,
                    notes="High-value prospect needs personal attention",
                    priority="high",
                    assigned_rep="john.smith@company.com"
                )
                
                assert success is True
                assert deal.requires_handoff is True
                assert deal.handoff_reason == HandoffReason.HIGH_VALUE_DEAL
                assert deal.assigned_rep == "john.smith@company.com"
                assert deal.current_stage == DealStage.TRANSFERRED
                assert deal_service.daily_stats['handoffs_created'] == 1
    
    @pytest.mark.asyncio
    async def test_update_deal_metrics(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test updating deal metrics."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create deal
            deal = await deal_service.create_deal(
                deal_id=sample_deal_data['deal_id'],
                lead_id=sample_deal_data['lead_id'],
                call_sid=sample_deal_data['call_sid'],
                prospect_data=sample_prospect_data
            )
            
            # Update metrics
            success = await deal_service.update_deal_metrics(
                deal_id=sample_deal_data['deal_id'],
                qualification_score=75,
                buying_signals=['budget approved', 'timeline Q1'],
                objection_handled='price',
                engagement_score=0.8
            )
            
            assert success is True
            assert deal.metrics.qualification_score == 75
            assert deal.metrics.buying_signals_count == 2
            assert 'budget approved' in deal.metrics.buying_signals
            assert 'timeline Q1' in deal.metrics.buying_signals
            assert deal.metrics.objections_handled == 1
            assert 'price' in deal.metrics.objection_types
            assert deal.metrics.engagement_score == 0.8
            assert deal.metrics.conversion_probability > 0.0  # Should be calculated
    
    @pytest.mark.asyncio
    async def test_get_deal_analytics_individual(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test getting individual deal analytics."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create and update deal
            deal = await deal_service.create_deal(
                deal_id=sample_deal_data['deal_id'],
                lead_id=sample_deal_data['lead_id'],
                call_sid=sample_deal_data['call_sid'],
                prospect_data=sample_prospect_data
            )
            
            await deal_service.update_deal_metrics(
                deal_id=sample_deal_data['deal_id'],
                qualification_score=80,
                buying_signals=['budget approved']
            )
            
            # Get analytics
            analytics = await deal_service.get_deal_analytics(deal_id=sample_deal_data['deal_id'])
            
            assert analytics['deal_id'] == sample_deal_data['deal_id']
            assert analytics['current_stage'] == DealStage.INITIAL_CONTACT.value
            assert analytics['is_active'] is True
            assert analytics['is_qualified'] is True
            assert analytics['metrics']['qualification_score'] == 80
            assert analytics['metrics']['buying_signals_count'] == 1
            assert len(analytics['stage_history']) >= 1
    
    @pytest.mark.asyncio
    async def test_get_deal_analytics_overall(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test getting overall deal analytics."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create multiple deals
            for i in range(3):
                await deal_service.create_deal(
                    deal_id=f"test_deal_{i}",
                    lead_id=f"test_lead_{i}",
                    call_sid=f"test_call_{i}",
                    prospect_data=sample_prospect_data
                )
            
            # Update one deal to qualified
            await deal_service.update_deal_metrics(
                deal_id="test_deal_0",
                qualification_score=70
            )
            
            # Get overall analytics
            analytics = await deal_service.get_deal_analytics()
            
            assert analytics['total_active_deals'] == 3
            assert analytics['qualified_deals'] == 1
            assert analytics['stage_distribution'][DealStage.INITIAL_CONTACT.value] == 3
            assert analytics['performance_metrics']['qualification_rate'] == 1/3
    
    @pytest.mark.asyncio
    async def test_get_pipeline_forecast(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test pipeline forecast generation."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            # Create deals with different values and probabilities
            deals_data = [
                {'deal_id': 'deal_1', 'value': 10000, 'score': 80},
                {'deal_id': 'deal_2', 'value': 25000, 'score': 60},
                {'deal_id': 'deal_3', 'value': 5000, 'score': 40}
            ]
            
            for deal_data in deals_data:
                await deal_service.create_deal(
                    deal_id=deal_data['deal_id'],
                    lead_id=f"lead_{deal_data['deal_id']}",
                    call_sid=f"call_{deal_data['deal_id']}",
                    prospect_data=sample_prospect_data
                )
                
                await deal_service.update_deal_metrics(
                    deal_id=deal_data['deal_id'],
                    qualification_score=deal_data['score']
                )
                
                # Set estimated value
                deal = deal_service.active_deals[deal_data['deal_id']]
                deal.metrics.estimated_deal_value = deal_data['value']
            
            # Get forecast
            forecast = await deal_service.get_pipeline_forecast()
            
            assert forecast['total_deals'] == 3
            assert forecast['pipeline_value'] == 40000  # Sum of all values
            assert forecast['weighted_pipeline'] > 0  # Should have weighted value
            assert DealStage.INITIAL_CONTACT.value in forecast['forecast_by_stage']
            assert 'high_probability' in forecast['conversion_predictions']
            assert 'medium_probability' in forecast['conversion_predictions']
            assert 'low_probability' in forecast['conversion_predictions']
    
    def test_stage_transition_validation(self, deal_service):
        """Test stage transition validation."""
        # Valid transitions
        assert deal_service._is_valid_stage_transition(
            DealStage.INITIAL_CONTACT, 
            DealStage.QUALIFICATION
        ) is True
        
        assert deal_service._is_valid_stage_transition(
            DealStage.QUALIFICATION, 
            DealStage.NEEDS_ANALYSIS
        ) is True
        
        # Invalid transitions
        assert deal_service._is_valid_stage_transition(
            DealStage.INITIAL_CONTACT, 
            DealStage.CLOSING
        ) is False
        
        assert deal_service._is_valid_stage_transition(
            DealStage.CLOSED_WON, 
            DealStage.QUALIFICATION
        ) is False
    
    def test_conversion_probability_calculation(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test conversion probability calculation."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        # Base probability for initial contact
        probability = deal_service._calculate_conversion_probability(deal)
        assert 0.0 <= probability <= 1.0
        assert probability == 0.1  # Base probability for initial contact
        
        # Increase with qualification score
        deal.metrics.qualification_score = 80
        probability = deal_service._calculate_conversion_probability(deal)
        assert probability > 0.1
        
        # Increase with buying signals
        deal.metrics.buying_signals_count = 3
        probability_with_signals = deal_service._calculate_conversion_probability(deal)
        assert probability_with_signals > probability
        
        # Decrease with too many objections
        deal.metrics.objections_handled = 4
        probability_with_objections = deal_service._calculate_conversion_probability(deal)
        assert probability_with_objections < probability_with_signals
    
    def test_outcome_classification(self, deal_service):
        """Test outcome classification and stage mapping."""
        # Positive outcomes should map to closed won
        assert deal_service._get_final_stage_for_outcome(
            DealOutcome.MEETING_SCHEDULED
        ) == DealStage.CLOSED_WON
        
        assert deal_service._get_final_stage_for_outcome(
            DealOutcome.TRIAL_STARTED
        ) == DealStage.CLOSED_WON
        
        # Nurture outcomes
        assert deal_service._get_final_stage_for_outcome(
            DealOutcome.FOLLOW_UP_SCHEDULED
        ) == DealStage.NURTURE
        
        # Negative outcomes should map to closed lost
        assert deal_service._get_final_stage_for_outcome(
            DealOutcome.NOT_INTERESTED
        ) == DealStage.CLOSED_LOST
        
        assert deal_service._get_final_stage_for_outcome(
            DealOutcome.BUDGET_CONSTRAINTS
        ) == DealStage.CLOSED_LOST
    
    def test_handoff_requirements(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test handoff requirement detection."""
        deal = DealProgression(
            deal_id=sample_deal_data['deal_id'],
            lead_id=sample_deal_data['lead_id'],
            call_sid=sample_deal_data['call_sid'],
            prospect_data=sample_prospect_data
        )
        
        # Initially no handoff required
        assert deal_service._requires_handoff_for_stage(DealStage.INITIAL_CONTACT, deal) is False
        
        # High-value deal in proposal stage
        deal.current_stage = DealStage.PROPOSAL
        deal.metrics.estimated_deal_value = 75000
        assert deal_service._requires_handoff_for_stage(DealStage.PROPOSAL, deal) is True
        
        # High qualification score
        deal.metrics.estimated_deal_value = 10000
        deal.metrics.qualification_score = 85
        assert deal_service._requires_handoff_for_stage(DealStage.QUALIFICATION, deal) is True
        
        # Multiple objections
        deal.metrics.qualification_score = 50
        deal.metrics.objections_handled = 4
        assert deal_service._requires_handoff_for_stage(DealStage.NEEDS_ANALYSIS, deal) is True
    
    def test_salesforce_stage_mapping(self, deal_service):
        """Test Salesforce stage mapping."""
        assert deal_service._map_stage_to_salesforce(DealStage.INITIAL_CONTACT) == 'Prospecting'
        assert deal_service._map_stage_to_salesforce(DealStage.QUALIFICATION) == 'Qualification'
        assert deal_service._map_stage_to_salesforce(DealStage.NEEDS_ANALYSIS) == 'Needs Analysis'
        assert deal_service._map_stage_to_salesforce(DealStage.PROPOSAL) == 'Proposal/Price Quote'
        assert deal_service._map_stage_to_salesforce(DealStage.NEGOTIATION) == 'Negotiation/Review'
        assert deal_service._map_stage_to_salesforce(DealStage.CLOSING) == 'Closed Won'
        assert deal_service._map_stage_to_salesforce(DealStage.CLOSED_WON) == 'Closed Won'
        assert deal_service._map_stage_to_salesforce(DealStage.CLOSED_LOST) == 'Closed Lost'


@pytest.mark.integration
class TestDealProgressionServiceIntegration:
    """Integration tests for deal progression service."""
    
    @pytest.mark.asyncio
    async def test_complete_deal_lifecycle(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test complete deal lifecycle from creation to outcome."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            with patch.object(deal_service, '_sync_deal_to_salesforce', new_callable=AsyncMock, return_value=True):
                with patch.object(deal_service, '_sync_outcome_to_salesforce', new_callable=AsyncMock, return_value=True):
                    with patch.object(deal_service, '_create_handoff_for_outcome', new_callable=AsyncMock):
                        
                        # Step 1: Create deal
                        deal = await deal_service.create_deal(
                            deal_id=sample_deal_data['deal_id'],
                            lead_id=sample_deal_data['lead_id'],
                            call_sid=sample_deal_data['call_sid'],
                            prospect_data=sample_prospect_data
                        )
                        
                        assert deal.current_stage == DealStage.INITIAL_CONTACT
                        assert len(deal.stage_history) == 1
                        
                        # Step 2: Progress through qualification
                        await deal_service.update_deal_stage(
                            deal_id=sample_deal_data['deal_id'],
                            new_stage=DealStage.QUALIFICATION,
                            reason="Prospect engaged in conversation"
                        )
                        
                        await deal_service.update_deal_metrics(
                            deal_id=sample_deal_data['deal_id'],
                            qualification_score=70,
                            buying_signals=['budget approved', 'decision authority'],
                            engagement_score=0.8
                        )
                        
                        assert deal.current_stage == DealStage.QUALIFICATION
                        assert deal.is_qualified() is True
                        
                        # Step 3: Move to needs analysis
                        await deal_service.update_deal_stage(
                            deal_id=sample_deal_data['deal_id'],
                            new_stage=DealStage.NEEDS_ANALYSIS,
                            reason="Understanding specific requirements"
                        )
                        
                        # Handle an objection
                        await deal_service.update_deal_metrics(
                            deal_id=sample_deal_data['deal_id'],
                            objection_handled='price'
                        )
                        
                        assert deal.metrics.objections_handled == 1
                        assert 'price' in deal.metrics.objection_types
                        
                        # Step 4: Record positive outcome
                        success = await deal_service.record_deal_outcome(
                            deal_id=sample_deal_data['deal_id'],
                            outcome=DealOutcome.MEETING_SCHEDULED,
                            estimated_value=30000.0,
                            next_steps="Demo scheduled for next Tuesday"
                        )
                        
                        assert success is True
                        assert deal.final_outcome == DealOutcome.MEETING_SCHEDULED
                        assert deal.current_stage == DealStage.CLOSED_WON
                        assert deal.metrics.estimated_deal_value == 30000.0
                        assert deal.completed_at is not None
                        
                        # Verify analytics
                        analytics = await deal_service.get_deal_analytics(deal_id=sample_deal_data['deal_id'])
                        assert analytics['is_qualified'] is True
                        assert analytics['metrics']['qualification_score'] == 70
                        assert analytics['metrics']['buying_signals_count'] == 2
                        assert analytics['metrics']['objections_handled'] == 1
                        assert len(analytics['stage_history']) >= 4  # Created + 2 stage changes + outcome
                        
                        # Verify daily stats
                        assert deal_service.daily_stats['deals_created'] == 1
                        assert deal_service.daily_stats['meetings_scheduled'] == 1
    
    @pytest.mark.asyncio
    async def test_high_value_deal_handoff_workflow(self, deal_service, sample_deal_data, sample_prospect_data):
        """Test high-value deal handoff workflow."""
        with patch('app.services.deal_progression_service.audit_service.log_event', new_callable=AsyncMock):
            with patch.object(deal_service, '_create_salesforce_handoff_task', new_callable=AsyncMock, return_value=True):
                
                # Create high-value deal
                deal = await deal_service.create_deal(
                    deal_id=sample_deal_data['deal_id'],
                    lead_id=sample_deal_data['lead_id'],
                    call_sid=sample_deal_data['call_sid'],
                    prospect_data=sample_prospect_data
                )
                
                # Set high qualification score and value
                await deal_service.update_deal_metrics(
                    deal_id=sample_deal_data['deal_id'],
                    qualification_score=85,
                    buying_signals=['large budget', 'urgent timeline', 'executive sponsor']
                )
                
                deal.metrics.estimated_deal_value = 100000.0
                
                # Progress to proposal stage (should trigger handoff)
                await deal_service.update_deal_stage(
                    deal_id=sample_deal_data['deal_id'],
                    new_stage=DealStage.QUALIFICATION
                )
                
                await deal_service.update_deal_stage(
                    deal_id=sample_deal_data['deal_id'],
                    new_stage=DealStage.NEEDS_ANALYSIS
                )
                
                await deal_service.update_deal_stage(
                    deal_id=sample_deal_data['deal_id'],
                    new_stage=DealStage.PROPOSAL
                )
                
                # Should automatically flag for handoff
                assert deal.requires_handoff is True
                assert deal.handoff_reason == HandoffReason.HIGH_VALUE_DEAL
                
                # Create explicit handoff
                success = await deal_service.create_handoff(
                    deal_id=sample_deal_data['deal_id'],
                    reason=HandoffReason.HIGH_VALUE_DEAL,
                    notes="High-value enterprise deal requiring senior rep attention",
                    priority="urgent",
                    assigned_rep="senior.rep@company.com"
                )
                
                assert success is True
                assert deal.current_stage == DealStage.TRANSFERRED
                assert deal.assigned_rep == "senior.rep@company.com"
                assert deal_service.daily_stats['handoffs_created'] == 1
                
                # Verify handoff event in history
                handoff_events = [event for event in deal.stage_history if event.event_type == "handoff_created"]
                assert len(handoff_events) == 1
                assert handoff_events[0].details['reason'] == HandoffReason.HIGH_VALUE_DEAL.value
                assert handoff_events[0].details['priority'] == "urgent"