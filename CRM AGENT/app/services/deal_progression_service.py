"""
Deal Progression and Outcome Tracking Service

This module implements comprehensive deal progression tracking, outcome classification,
Salesforce integration, and analytics for the AI Calling Agent MVP.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json

import structlog

from ..core.config import get_settings
from ..services.salesforce import salesforce_service
from ..services.audit_trail import audit_service, AuditEventType
from ..utils.encryption import encrypt_pii_data, decrypt_pii_data

logger = structlog.get_logger()


class DealStage(str, Enum):
    """Deal progression stages."""
    INITIAL_CONTACT = "initial_contact"           # First contact made
    QUALIFICATION = "qualification"               # Lead qualification in progress
    NEEDS_ANALYSIS = "needs_analysis"            # Understanding prospect needs
    PROPOSAL = "proposal"                        # Proposal/demo stage
    NEGOTIATION = "negotiation"                  # Price/terms negotiation
    CLOSING = "closing"                          # Attempting to close
    CLOSED_WON = "closed_won"                    # Deal won
    CLOSED_LOST = "closed_lost"                  # Deal lost
    NURTURE = "nurture"                          # Long-term nurturing
    TRANSFERRED = "transferred"                  # Handed off to human


class DealOutcome(str, Enum):
    """Final deal outcomes."""
    MEETING_SCHEDULED = "meeting_scheduled"       # Demo/meeting scheduled
    TRIAL_STARTED = "trial_started"              # Trial or pilot started
    PROPOSAL_REQUESTED = "proposal_requested"     # Formal proposal requested
    QUOTE_REQUESTED = "quote_requested"          # Pricing quote requested
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"  # Future follow-up scheduled
    REFERRAL_PROVIDED = "referral_provided"      # Referred to decision maker
    NOT_INTERESTED = "not_interested"            # Not interested
    BUDGET_CONSTRAINTS = "budget_constraints"     # Budget issues
    TIMING_ISSUES = "timing_issues"              # Timing not right
    COMPETITOR_CHOSEN = "competitor_chosen"       # Chose competitor
    NO_DECISION = "no_decision"                  # No decision made
    UNQUALIFIED = "unqualified"                  # Not a qualified prospect


class HandoffReason(str, Enum):
    """Reasons for human handoff."""
    COMPLEX_REQUIREMENTS = "complex_requirements"  # Technical complexity
    HIGH_VALUE_DEAL = "high_value_deal"           # High-value opportunity
    EXECUTIVE_LEVEL = "executive_level"           # C-level prospect
    CUSTOM_PRICING = "custom_pricing"             # Custom pricing needed
    LEGAL_CONCERNS = "legal_concerns"             # Legal/compliance issues
    TECHNICAL_QUESTIONS = "technical_questions"   # Deep technical questions
    RELATIONSHIP_BUILDING = "relationship_building" # Relationship focus
    ESCALATION_REQUEST = "escalation_request"     # Prospect requested escalation


@dataclass
class DealProgressionEvent:
    """Individual event in deal progression."""
    event_id: str
    deal_id: str
    timestamp: datetime
    event_type: str  # stage_change, outcome_recorded, objection_handled, etc.
    from_stage: Optional[DealStage] = None
    to_stage: Optional[DealStage] = None
    outcome: Optional[DealOutcome] = None
    details: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    ai_generated: bool = True


@dataclass
class DealMetrics:
    """Metrics for deal progression analysis."""
    deal_id: str
    
    # Progression metrics
    total_interactions: int = 0
    stage_duration_minutes: Dict[DealStage, float] = field(default_factory=dict)
    objections_handled: int = 0
    objection_types: List[str] = field(default_factory=list)
    
    # Quality metrics
    qualification_score: int = 0
    engagement_score: float = 0.0
    buying_signals_count: int = 0
    buying_signals: List[str] = field(default_factory=list)
    
    # Outcome metrics
    conversion_probability: float = 0.0
    estimated_deal_value: float = 0.0
    expected_close_date: Optional[datetime] = None
    
    # Performance metrics
    response_quality_score: float = 0.0
    conversation_flow_score: float = 0.0
    
    # Timestamps
    first_contact: datetime = field(default_factory=datetime.utcnow)
    last_interaction: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_total_duration_minutes(self) -> float:
        """Calculate total deal duration in minutes."""
        return (self.last_interaction - self.first_contact).total_seconds() / 60
    
    def get_current_stage_duration(self, current_stage: DealStage) -> float:
        """Get duration in current stage."""
        return self.stage_duration_minutes.get(current_stage, 0.0)


@dataclass
class DealProgression:
    """Complete deal progression tracking."""
    deal_id: str
    lead_id: str
    call_sid: str
    
    # Basic info
    prospect_data: Dict[str, Any] = field(default_factory=dict)
    current_stage: DealStage = DealStage.INITIAL_CONTACT
    final_outcome: Optional[DealOutcome] = None
    
    # Progression tracking
    stage_history: List[DealProgressionEvent] = field(default_factory=list)
    stage_entry_time: datetime = field(default_factory=datetime.utcnow)
    
    # Metrics
    metrics: DealMetrics = field(default_factory=lambda: DealMetrics(""))
    
    # Salesforce integration
    salesforce_lead_id: Optional[str] = None
    salesforce_opportunity_id: Optional[str] = None
    salesforce_contact_id: Optional[str] = None
    
    # Handoff tracking
    requires_handoff: bool = False
    handoff_reason: Optional[HandoffReason] = None
    handoff_notes: Optional[str] = None
    assigned_rep: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize metrics with deal_id."""
        if not self.metrics.deal_id:
            self.metrics.deal_id = self.deal_id
    
    def is_active(self) -> bool:
        """Check if deal is still active."""
        return self.current_stage not in [
            DealStage.CLOSED_WON,
            DealStage.CLOSED_LOST,
            DealStage.TRANSFERRED
        ]
    
    def is_qualified(self) -> bool:
        """Check if deal is qualified."""
        return self.metrics.qualification_score >= 60
    
    def needs_human_intervention(self) -> bool:
        """Check if deal needs human intervention."""
        return (
            self.requires_handoff or
            self.metrics.qualification_score >= 80 or
            self.metrics.objections_handled >= 3 or
            self.current_stage == DealStage.NEGOTIATION
        )


class DealProgressionService:
    """
    Service for tracking deal progression and outcomes.
    
    Manages deal stages, outcomes, Salesforce integration,
    and provides analytics for deal performance.
    """
    
    def __init__(self):
        """Initialize deal progression service."""
        self.settings = get_settings()
        
        # Active deals tracking
        self.active_deals: Dict[str, DealProgression] = {}
        
        # Stage transition rules
        self.stage_transitions = self._initialize_stage_transitions()
        
        # Outcome classification rules
        self.outcome_classifiers = self._initialize_outcome_classifiers()
        
        # Analytics tracking
        self.daily_stats = {
            'deals_created': 0,
            'deals_completed': 0,
            'meetings_scheduled': 0,
            'trials_started': 0,
            'handoffs_created': 0
        }
        
        logger.info("Deal Progression Service initialized")
    
    async def create_deal(
        self,
        deal_id: str,
        lead_id: str,
        call_sid: str,
        prospect_data: Dict[str, Any]
    ) -> DealProgression:
        """
        Create a new deal progression tracker.
        
        Args:
            deal_id: Unique deal identifier
            lead_id: Lead identifier
            call_sid: Call session identifier
            prospect_data: Prospect information
            
        Returns:
            DealProgression instance
        """
        try:
            # Create deal progression
            deal = DealProgression(
                deal_id=deal_id,
                lead_id=lead_id,
                call_sid=call_sid,
                prospect_data=encrypt_pii_data(prospect_data)
            )
            
            # Initialize metrics
            deal.metrics.first_contact = datetime.utcnow()
            deal.metrics.last_interaction = datetime.utcnow()
            
            # Record initial event
            initial_event = DealProgressionEvent(
                event_id=f"{deal_id}_initial",
                deal_id=deal_id,
                timestamp=datetime.utcnow(),
                event_type="deal_created",
                to_stage=DealStage.INITIAL_CONTACT,
                details={'prospect_data': prospect_data}
            )
            deal.stage_history.append(initial_event)
            
            # Store active deal
            self.active_deals[deal_id] = deal
            
            # Update stats
            self.daily_stats['deals_created'] += 1
            
            # Audit log
            await audit_service.log_event(
                event_type=AuditEventType.DEAL_CREATED,
                user_id="ai_agent",
                resource_type="deal",
                resource_id=deal_id,
                details={
                    'lead_id': lead_id,
                    'call_sid': call_sid,
                    'prospect_company': prospect_data.get('company_name', 'Unknown')
                }
            )
            
            logger.info(
                "Created deal progression tracker",
                deal_id=deal_id,
                lead_id=lead_id,
                prospect_company=prospect_data.get('company_name', 'Unknown')
            )
            
            return deal
            
        except Exception as e:
            logger.error("Failed to create deal", deal_id=deal_id, error=str(e))
            raise
    
    async def update_deal_stage(
        self,
        deal_id: str,
        new_stage: DealStage,
        reason: str = "",
        confidence: float = 0.0,
        details: Dict[str, Any] = None
    ) -> bool:
        """
        Update deal stage with validation and tracking.
        
        Args:
            deal_id: Deal identifier
            new_stage: New stage to transition to
            reason: Reason for stage change
            confidence: Confidence in stage classification
            details: Additional details
            
        Returns:
            True if stage updated successfully
        """
        try:
            if deal_id not in self.active_deals:
                logger.warning("Deal not found for stage update", deal_id=deal_id)
                return False
            
            deal = self.active_deals[deal_id]
            old_stage = deal.current_stage
            
            # Validate stage transition
            if not self._is_valid_stage_transition(old_stage, new_stage):
                logger.warning(
                    "Invalid stage transition",
                    deal_id=deal_id,
                    from_stage=old_stage.value,
                    to_stage=new_stage.value
                )
                return False
            
            # Calculate time in previous stage
            stage_duration = (datetime.utcnow() - deal.stage_entry_time).total_seconds() / 60
            deal.metrics.stage_duration_minutes[old_stage] = (
                deal.metrics.stage_duration_minutes.get(old_stage, 0.0) + stage_duration
            )
            
            # Update stage
            deal.current_stage = new_stage
            deal.stage_entry_time = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
            
            # Record stage change event
            stage_event = DealProgressionEvent(
                event_id=f"{deal_id}_stage_{datetime.utcnow().timestamp()}",
                deal_id=deal_id,
                timestamp=datetime.utcnow(),
                event_type="stage_change",
                from_stage=old_stage,
                to_stage=new_stage,
                details={
                    'reason': reason,
                    'stage_duration_minutes': stage_duration,
                    **(details or {})
                },
                confidence_score=confidence
            )
            deal.stage_history.append(stage_event)
            
            # Update metrics
            deal.metrics.last_interaction = datetime.utcnow()
            deal.metrics.total_interactions += 1
            
            # Check for handoff requirements
            if self._requires_handoff_for_stage(new_stage, deal):
                await self._flag_for_handoff(deal, self._get_handoff_reason_for_stage(new_stage))
            
            # Sync with Salesforce if needed
            if new_stage in [DealStage.PROPOSAL, DealStage.NEGOTIATION, DealStage.CLOSING]:
                await self._sync_deal_to_salesforce(deal)
            
            # Audit log
            await audit_service.log_event(
                event_type=AuditEventType.DEAL_STAGE_UPDATED,
                user_id="ai_agent",
                resource_type="deal",
                resource_id=deal_id,
                details={
                    'from_stage': old_stage.value,
                    'to_stage': new_stage.value,
                    'reason': reason,
                    'confidence': confidence,
                    'stage_duration_minutes': stage_duration
                }
            )
            
            logger.info(
                "Updated deal stage",
                deal_id=deal_id,
                from_stage=old_stage.value,
                to_stage=new_stage.value,
                reason=reason,
                confidence=confidence
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to update deal stage", deal_id=deal_id, error=str(e))
            return False
    
    async def record_deal_outcome(
        self,
        deal_id: str,
        outcome: DealOutcome,
        details: Dict[str, Any] = None,
        estimated_value: float = 0.0,
        next_steps: str = ""
    ) -> bool:
        """
        Record final deal outcome.
        
        Args:
            deal_id: Deal identifier
            outcome: Final outcome
            details: Additional outcome details
            estimated_value: Estimated deal value
            next_steps: Next steps or follow-up actions
            
        Returns:
            True if outcome recorded successfully
        """
        try:
            if deal_id not in self.active_deals:
                logger.warning("Deal not found for outcome recording", deal_id=deal_id)
                return False
            
            deal = self.active_deals[deal_id]
            
            # Set final outcome
            deal.final_outcome = outcome
            deal.completed_at = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
            
            # Update metrics
            deal.metrics.estimated_deal_value = estimated_value
            deal.metrics.last_interaction = datetime.utcnow()
            
            # Determine final stage based on outcome
            final_stage = self._get_final_stage_for_outcome(outcome)
            if final_stage != deal.current_stage:
                await self.update_deal_stage(
                    deal_id,
                    final_stage,
                    f"Outcome recorded: {outcome.value}",
                    confidence=0.9
                )
            
            # Record outcome event
            outcome_event = DealProgressionEvent(
                event_id=f"{deal_id}_outcome_{datetime.utcnow().timestamp()}",
                deal_id=deal_id,
                timestamp=datetime.utcnow(),
                event_type="outcome_recorded",
                outcome=outcome,
                details={
                    'estimated_value': estimated_value,
                    'next_steps': next_steps,
                    **(details or {})
                }
            )
            deal.stage_history.append(outcome_event)
            
            # Update daily stats
            self._update_outcome_stats(outcome)
            
            # Sync final outcome to Salesforce
            await self._sync_outcome_to_salesforce(deal, outcome, estimated_value, next_steps)
            
            # Create handoff if needed
            if self._outcome_requires_handoff(outcome):
                await self._create_handoff_for_outcome(deal, outcome, next_steps)
            
            # Remove from active deals if completed
            if final_stage in [DealStage.CLOSED_WON, DealStage.CLOSED_LOST, DealStage.TRANSFERRED]:
                self.active_deals.pop(deal_id, None)
                self.daily_stats['deals_completed'] += 1
            
            # Audit log
            await audit_service.log_event(
                event_type=AuditEventType.DEAL_OUTCOME_RECORDED,
                user_id="ai_agent",
                resource_type="deal",
                resource_id=deal_id,
                details={
                    'outcome': outcome.value,
                    'estimated_value': estimated_value,
                    'next_steps': next_steps,
                    'total_duration_minutes': deal.metrics.calculate_total_duration_minutes()
                }
            )
            
            logger.info(
                "Recorded deal outcome",
                deal_id=deal_id,
                outcome=outcome.value,
                estimated_value=estimated_value,
                total_duration=deal.metrics.calculate_total_duration_minutes()
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to record deal outcome", deal_id=deal_id, error=str(e))
            return False
    
    async def create_handoff(
        self,
        deal_id: str,
        reason: HandoffReason,
        notes: str = "",
        priority: str = "normal",
        assigned_rep: str = ""
    ) -> bool:
        """
        Create handoff to human sales representative.
        
        Args:
            deal_id: Deal identifier
            reason: Reason for handoff
            notes: Additional notes for rep
            priority: Handoff priority (low, normal, high, urgent)
            assigned_rep: Specific rep to assign to
            
        Returns:
            True if handoff created successfully
        """
        try:
            if deal_id not in self.active_deals:
                logger.warning("Deal not found for handoff creation", deal_id=deal_id)
                return False
            
            deal = self.active_deals[deal_id]
            
            # Update deal with handoff info
            deal.requires_handoff = True
            deal.handoff_reason = reason
            deal.handoff_notes = notes
            deal.assigned_rep = assigned_rep
            deal.updated_at = datetime.utcnow()
            
            # Update stage to transferred
            await self.update_deal_stage(
                deal_id,
                DealStage.TRANSFERRED,
                f"Handoff created: {reason.value}",
                confidence=1.0
            )
            
            # Create handoff task in Salesforce
            handoff_success = await self._create_salesforce_handoff_task(
                deal, reason, notes, priority, assigned_rep
            )
            
            if handoff_success:
                # Record handoff event
                handoff_event = DealProgressionEvent(
                    event_id=f"{deal_id}_handoff_{datetime.utcnow().timestamp()}",
                    deal_id=deal_id,
                    timestamp=datetime.utcnow(),
                    event_type="handoff_created",
                    details={
                        'reason': reason.value,
                        'notes': notes,
                        'priority': priority,
                        'assigned_rep': assigned_rep
                    }
                )
                deal.stage_history.append(handoff_event)
                
                # Update stats
                self.daily_stats['handoffs_created'] += 1
                
                # Audit log
                await audit_service.log_event(
                    event_type=AuditEventType.DEAL_HANDOFF_CREATED,
                    user_id="ai_agent",
                    resource_type="deal",
                    resource_id=deal_id,
                    details={
                        'reason': reason.value,
                        'notes': notes,
                        'priority': priority,
                        'assigned_rep': assigned_rep,
                        'qualification_score': deal.metrics.qualification_score
                    }
                )
                
                logger.info(
                    "Created deal handoff",
                    deal_id=deal_id,
                    reason=reason.value,
                    priority=priority,
                    assigned_rep=assigned_rep
                )
                
                return True
            else:
                logger.error("Failed to create Salesforce handoff task", deal_id=deal_id)
                return False
            
        except Exception as e:
            logger.error("Failed to create handoff", deal_id=deal_id, error=str(e))
            return False  
  
    async def update_deal_metrics(
        self,
        deal_id: str,
        qualification_score: int = None,
        buying_signals: List[str] = None,
        objection_handled: str = None,
        engagement_score: float = None
    ) -> bool:
        """
        Update deal metrics and analytics.
        
        Args:
            deal_id: Deal identifier
            qualification_score: Updated qualification score
            buying_signals: New buying signals detected
            objection_handled: Type of objection handled
            engagement_score: Conversation engagement score
            
        Returns:
            True if metrics updated successfully
        """
        try:
            if deal_id not in self.active_deals:
                logger.warning("Deal not found for metrics update", deal_id=deal_id)
                return False
            
            deal = self.active_deals[deal_id]
            
            # Update qualification score
            if qualification_score is not None:
                deal.metrics.qualification_score = qualification_score
            
            # Add buying signals
            if buying_signals:
                for signal in buying_signals:
                    if signal not in deal.metrics.buying_signals:
                        deal.metrics.buying_signals.append(signal)
                        deal.metrics.buying_signals_count += 1
            
            # Track objection handling
            if objection_handled:
                deal.metrics.objections_handled += 1
                if objection_handled not in deal.metrics.objection_types:
                    deal.metrics.objection_types.append(objection_handled)
            
            # Update engagement score
            if engagement_score is not None:
                deal.metrics.engagement_score = engagement_score
            
            # Update conversion probability based on metrics
            deal.metrics.conversion_probability = self._calculate_conversion_probability(deal)
            
            # Update timestamps
            deal.metrics.last_interaction = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
            
            logger.debug(
                "Updated deal metrics",
                deal_id=deal_id,
                qualification_score=deal.metrics.qualification_score,
                buying_signals_count=deal.metrics.buying_signals_count,
                objections_handled=deal.metrics.objections_handled,
                conversion_probability=deal.metrics.conversion_probability
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to update deal metrics", deal_id=deal_id, error=str(e))
            return False
    
    async def get_deal_analytics(self, deal_id: str = None) -> Dict[str, Any]:
        """
        Get deal analytics and performance metrics.
        
        Args:
            deal_id: Optional specific deal ID for individual analytics
            
        Returns:
            Dictionary with analytics data
        """
        try:
            if deal_id:
                # Individual deal analytics
                if deal_id not in self.active_deals:
                    return {'error': 'Deal not found'}
                
                deal = self.active_deals[deal_id]
                return self._get_individual_deal_analytics(deal)
            
            else:
                # Overall analytics
                return self._get_overall_analytics()
            
        except Exception as e:
            logger.error("Failed to get deal analytics", deal_id=deal_id, error=str(e))
            return {'error': str(e)}
    
    async def get_pipeline_forecast(self) -> Dict[str, Any]:
        """
        Generate pipeline forecast and conversion predictions.
        
        Returns:
            Dictionary with pipeline forecast data
        """
        try:
            active_deals = list(self.active_deals.values())
            
            if not active_deals:
                return {
                    'total_deals': 0,
                    'pipeline_value': 0.0,
                    'weighted_pipeline': 0.0,
                    'forecast_by_stage': {},
                    'conversion_predictions': {}
                }
            
            # Calculate pipeline metrics
            total_deals = len(active_deals)
            pipeline_value = sum(deal.metrics.estimated_deal_value for deal in active_deals)
            weighted_pipeline = sum(
                deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
                for deal in active_deals
            )
            
            # Forecast by stage
            forecast_by_stage = {}
            for stage in DealStage:
                stage_deals = [deal for deal in active_deals if deal.current_stage == stage]
                if stage_deals:
                    forecast_by_stage[stage.value] = {
                        'count': len(stage_deals),
                        'total_value': sum(deal.metrics.estimated_deal_value for deal in stage_deals),
                        'weighted_value': sum(
                            deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
                            for deal in stage_deals
                        ),
                        'avg_qualification_score': sum(deal.metrics.qualification_score for deal in stage_deals) / len(stage_deals),
                        'avg_conversion_probability': sum(deal.metrics.conversion_probability for deal in stage_deals) / len(stage_deals)
                    }
            
            # Conversion predictions
            high_probability_deals = [deal for deal in active_deals if deal.metrics.conversion_probability > 0.7]
            medium_probability_deals = [deal for deal in active_deals if 0.3 <= deal.metrics.conversion_probability <= 0.7]
            low_probability_deals = [deal for deal in active_deals if deal.metrics.conversion_probability < 0.3]
            
            conversion_predictions = {
                'high_probability': {
                    'count': len(high_probability_deals),
                    'total_value': sum(deal.metrics.estimated_deal_value for deal in high_probability_deals),
                    'expected_value': sum(
                        deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
                        for deal in high_probability_deals
                    )
                },
                'medium_probability': {
                    'count': len(medium_probability_deals),
                    'total_value': sum(deal.metrics.estimated_deal_value for deal in medium_probability_deals),
                    'expected_value': sum(
                        deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
                        for deal in medium_probability_deals
                    )
                },
                'low_probability': {
                    'count': len(low_probability_deals),
                    'total_value': sum(deal.metrics.estimated_deal_value for deal in low_probability_deals),
                    'expected_value': sum(
                        deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
                        for deal in low_probability_deals
                    )
                }
            }
            
            return {
                'total_deals': total_deals,
                'pipeline_value': pipeline_value,
                'weighted_pipeline': weighted_pipeline,
                'forecast_by_stage': forecast_by_stage,
                'conversion_predictions': conversion_predictions,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to generate pipeline forecast", error=str(e))
            return {'error': str(e)}
    
    # Private helper methods
    
    def _initialize_stage_transitions(self) -> Dict[DealStage, List[DealStage]]:
        """Initialize valid stage transitions."""
        return {
            DealStage.INITIAL_CONTACT: [
                DealStage.QUALIFICATION,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.QUALIFICATION: [
                DealStage.NEEDS_ANALYSIS,
                DealStage.NURTURE,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.NEEDS_ANALYSIS: [
                DealStage.PROPOSAL,
                DealStage.NURTURE,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.PROPOSAL: [
                DealStage.NEGOTIATION,
                DealStage.CLOSING,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.NEGOTIATION: [
                DealStage.CLOSING,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.CLOSING: [
                DealStage.CLOSED_WON,
                DealStage.CLOSED_LOST,
                DealStage.TRANSFERRED
            ],
            DealStage.NURTURE: [
                DealStage.QUALIFICATION,
                DealStage.CLOSED_LOST
            ]
        }
    
    def _initialize_outcome_classifiers(self) -> Dict[str, DealOutcome]:
        """Initialize outcome classification patterns."""
        return {
            'meeting': DealOutcome.MEETING_SCHEDULED,
            'demo': DealOutcome.MEETING_SCHEDULED,
            'trial': DealOutcome.TRIAL_STARTED,
            'pilot': DealOutcome.TRIAL_STARTED,
            'proposal': DealOutcome.PROPOSAL_REQUESTED,
            'quote': DealOutcome.QUOTE_REQUESTED,
            'pricing': DealOutcome.QUOTE_REQUESTED,
            'follow up': DealOutcome.FOLLOW_UP_SCHEDULED,
            'callback': DealOutcome.FOLLOW_UP_SCHEDULED,
            'referral': DealOutcome.REFERRAL_PROVIDED,
            'decision maker': DealOutcome.REFERRAL_PROVIDED,
            'not interested': DealOutcome.NOT_INTERESTED,
            'no interest': DealOutcome.NOT_INTERESTED,
            'budget': DealOutcome.BUDGET_CONSTRAINTS,
            'cost': DealOutcome.BUDGET_CONSTRAINTS,
            'timing': DealOutcome.TIMING_ISSUES,
            'time': DealOutcome.TIMING_ISSUES,
            'competitor': DealOutcome.COMPETITOR_CHOSEN,
            'alternative': DealOutcome.COMPETITOR_CHOSEN
        }
    
    def _is_valid_stage_transition(self, from_stage: DealStage, to_stage: DealStage) -> bool:
        """Check if stage transition is valid."""
        valid_transitions = self.stage_transitions.get(from_stage, [])
        return to_stage in valid_transitions
    
    def _requires_handoff_for_stage(self, stage: DealStage, deal: DealProgression) -> bool:
        """Check if stage requires human handoff."""
        # High-value deals in proposal/negotiation stage
        if stage in [DealStage.PROPOSAL, DealStage.NEGOTIATION] and deal.metrics.estimated_deal_value > 50000:
            return True
        
        # High qualification score deals
        if deal.metrics.qualification_score >= 80:
            return True
        
        # Multiple objections handled
        if deal.metrics.objections_handled >= 3:
            return True
        
        return False
    
    def _get_handoff_reason_for_stage(self, stage: DealStage) -> HandoffReason:
        """Get appropriate handoff reason for stage."""
        stage_reasons = {
            DealStage.PROPOSAL: HandoffReason.HIGH_VALUE_DEAL,
            DealStage.NEGOTIATION: HandoffReason.CUSTOM_PRICING,
            DealStage.CLOSING: HandoffReason.RELATIONSHIP_BUILDING
        }
        return stage_reasons.get(stage, HandoffReason.COMPLEX_REQUIREMENTS)
    
    def _get_final_stage_for_outcome(self, outcome: DealOutcome) -> DealStage:
        """Get final stage based on outcome."""
        positive_outcomes = [
            DealOutcome.MEETING_SCHEDULED,
            DealOutcome.TRIAL_STARTED,
            DealOutcome.PROPOSAL_REQUESTED,
            DealOutcome.QUOTE_REQUESTED
        ]
        
        if outcome in positive_outcomes:
            return DealStage.CLOSED_WON
        elif outcome in [DealOutcome.FOLLOW_UP_SCHEDULED, DealOutcome.REFERRAL_PROVIDED]:
            return DealStage.NURTURE
        else:
            return DealStage.CLOSED_LOST
    
    def _update_outcome_stats(self, outcome: DealOutcome) -> None:
        """Update daily stats based on outcome."""
        if outcome == DealOutcome.MEETING_SCHEDULED:
            self.daily_stats['meetings_scheduled'] += 1
        elif outcome == DealOutcome.TRIAL_STARTED:
            self.daily_stats['trials_started'] += 1
    
    def _outcome_requires_handoff(self, outcome: DealOutcome) -> bool:
        """Check if outcome requires handoff."""
        handoff_outcomes = [
            DealOutcome.MEETING_SCHEDULED,
            DealOutcome.TRIAL_STARTED,
            DealOutcome.PROPOSAL_REQUESTED,
            DealOutcome.QUOTE_REQUESTED
        ]
        return outcome in handoff_outcomes
    
    def _calculate_conversion_probability(self, deal: DealProgression) -> float:
        """Calculate conversion probability based on deal metrics."""
        probability = 0.0
        
        # Base probability by stage
        stage_probabilities = {
            DealStage.INITIAL_CONTACT: 0.1,
            DealStage.QUALIFICATION: 0.2,
            DealStage.NEEDS_ANALYSIS: 0.4,
            DealStage.PROPOSAL: 0.6,
            DealStage.NEGOTIATION: 0.8,
            DealStage.CLOSING: 0.9
        }
        probability = stage_probabilities.get(deal.current_stage, 0.1)
        
        # Adjust for qualification score
        if deal.metrics.qualification_score >= 80:
            probability += 0.2
        elif deal.metrics.qualification_score >= 60:
            probability += 0.1
        
        # Adjust for buying signals
        if deal.metrics.buying_signals_count >= 3:
            probability += 0.15
        elif deal.metrics.buying_signals_count >= 1:
            probability += 0.05
        
        # Adjust for engagement
        if deal.metrics.engagement_score >= 0.8:
            probability += 0.1
        elif deal.metrics.engagement_score >= 0.6:
            probability += 0.05
        
        # Penalize for too many objections
        if deal.metrics.objections_handled >= 3:
            probability -= 0.1
        
        return min(1.0, max(0.0, probability))
    
    async def _sync_deal_to_salesforce(self, deal: DealProgression) -> bool:
        """Sync deal to Salesforce as Opportunity."""
        try:
            # Create or update Opportunity
            opportunity_data = {
                'Name': f"AI Generated Opportunity - {deal.prospect_data.get('company_name', 'Unknown')}",
                'StageName': self._map_stage_to_salesforce(deal.current_stage),
                'CloseDate': (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d'),
                'Amount': deal.metrics.estimated_deal_value if deal.metrics.estimated_deal_value > 0 else None,
                'Probability': int(deal.metrics.conversion_probability * 100),
                'LeadSource': 'AI_Calling_Agent',
                'Description': f"AI-generated opportunity from call {deal.call_sid}. Qualification score: {deal.metrics.qualification_score}"
            }
            
            if deal.salesforce_opportunity_id:
                # Update existing opportunity
                result = await salesforce_service.update_record(
                    'Opportunity',
                    deal.salesforce_opportunity_id,
                    opportunity_data
                )
            else:
                # Create new opportunity
                result = await salesforce_service.create_record('Opportunity', opportunity_data)
                if result and 'id' in result:
                    deal.salesforce_opportunity_id = result['id']
            
            return result is not None
            
        except Exception as e:
            logger.error("Failed to sync deal to Salesforce", deal_id=deal.deal_id, error=str(e))
            return False
    
    async def _sync_outcome_to_salesforce(
        self,
        deal: DealProgression,
        outcome: DealOutcome,
        estimated_value: float,
        next_steps: str
    ) -> bool:
        """Sync deal outcome to Salesforce."""
        try:
            # Update opportunity with final outcome
            if deal.salesforce_opportunity_id:
                outcome_data = {
                    'StageName': 'Closed Won' if outcome in [
                        DealOutcome.MEETING_SCHEDULED,
                        DealOutcome.TRIAL_STARTED,
                        DealOutcome.PROPOSAL_REQUESTED
                    ] else 'Closed Lost',
                    'Amount': estimated_value if estimated_value > 0 else None,
                    'Description': f"Final outcome: {outcome.value}. Next steps: {next_steps}"
                }
                
                await salesforce_service.update_record(
                    'Opportunity',
                    deal.salesforce_opportunity_id,
                    outcome_data
                )
            
            # Create follow-up task if needed
            if next_steps:
                task_data = {
                    'Subject': f'Follow up on AI conversation - {outcome.value}',
                    'Description': next_steps,
                    'Status': 'Not Started',
                    'Priority': 'Normal',
                    'ActivityDate': (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
                }
                
                if deal.salesforce_contact_id:
                    task_data['WhoId'] = deal.salesforce_contact_id
                
                await salesforce_service.create_record('Task', task_data)
            
            return True
            
        except Exception as e:
            logger.error("Failed to sync outcome to Salesforce", deal_id=deal.deal_id, error=str(e))
            return False
    
    async def _create_salesforce_handoff_task(
        self,
        deal: DealProgression,
        reason: HandoffReason,
        notes: str,
        priority: str,
        assigned_rep: str
    ) -> bool:
        """Create handoff task in Salesforce."""
        try:
            task_data = {
                'Subject': f'AI Agent Handoff - {reason.value.replace("_", " ").title()}',
                'Description': f"""
AI Agent Handoff Details:

Reason: {reason.value.replace("_", " ").title()}
Qualification Score: {deal.metrics.qualification_score}
Buying Signals: {', '.join(deal.metrics.buying_signals)}
Objections Handled: {deal.metrics.objections_handled}
Estimated Value: ${deal.metrics.estimated_deal_value:,.2f}
Conversion Probability: {deal.metrics.conversion_probability:.1%}

Notes: {notes}

Conversation Summary:
- Total Interactions: {deal.metrics.total_interactions}
- Duration: {deal.metrics.calculate_total_duration_minutes():.1f} minutes
- Current Stage: {deal.current_stage.value.replace("_", " ").title()}
                """.strip(),
                'Status': 'Not Started',
                'Priority': priority.title(),
                'ActivityDate': datetime.utcnow().strftime('%Y-%m-%d')
            }
            
            if deal.salesforce_contact_id:
                task_data['WhoId'] = deal.salesforce_contact_id
            
            if deal.salesforce_opportunity_id:
                task_data['WhatId'] = deal.salesforce_opportunity_id
            
            result = await salesforce_service.create_record('Task', task_data)
            return result is not None
            
        except Exception as e:
            logger.error("Failed to create Salesforce handoff task", deal_id=deal.deal_id, error=str(e))
            return False
    
    async def _flag_for_handoff(self, deal: DealProgression, reason: HandoffReason) -> None:
        """Flag deal for handoff."""
        deal.requires_handoff = True
        deal.handoff_reason = reason
        deal.handoff_notes = f"Auto-flagged for handoff: {reason.value}"
    
    async def _create_handoff_for_outcome(
        self,
        deal: DealProgression,
        outcome: DealOutcome,
        next_steps: str
    ) -> None:
        """Create handoff for positive outcomes."""
        reason_map = {
            DealOutcome.MEETING_SCHEDULED: HandoffReason.RELATIONSHIP_BUILDING,
            DealOutcome.TRIAL_STARTED: HandoffReason.HIGH_VALUE_DEAL,
            DealOutcome.PROPOSAL_REQUESTED: HandoffReason.CUSTOM_PRICING,
            DealOutcome.QUOTE_REQUESTED: HandoffReason.CUSTOM_PRICING
        }
        
        reason = reason_map.get(outcome, HandoffReason.RELATIONSHIP_BUILDING)
        await self.create_handoff(deal.deal_id, reason, next_steps, "high")
    
    def _map_stage_to_salesforce(self, stage: DealStage) -> str:
        """Map internal stage to Salesforce stage."""
        stage_mapping = {
            DealStage.INITIAL_CONTACT: 'Prospecting',
            DealStage.QUALIFICATION: 'Qualification',
            DealStage.NEEDS_ANALYSIS: 'Needs Analysis',
            DealStage.PROPOSAL: 'Proposal/Price Quote',
            DealStage.NEGOTIATION: 'Negotiation/Review',
            DealStage.CLOSING: 'Closed Won',
            DealStage.CLOSED_WON: 'Closed Won',
            DealStage.CLOSED_LOST: 'Closed Lost',
            DealStage.NURTURE: 'Prospecting',
            DealStage.TRANSFERRED: 'Qualification'
        }
        return stage_mapping.get(stage, 'Prospecting')
    
    def _get_individual_deal_analytics(self, deal: DealProgression) -> Dict[str, Any]:
        """Get analytics for individual deal."""
        return {
            'deal_id': deal.deal_id,
            'current_stage': deal.current_stage.value,
            'final_outcome': deal.final_outcome.value if deal.final_outcome else None,
            'is_active': deal.is_active(),
            'is_qualified': deal.is_qualified(),
            'needs_handoff': deal.needs_human_intervention(),
            'metrics': {
                'qualification_score': deal.metrics.qualification_score,
                'conversion_probability': deal.metrics.conversion_probability,
                'estimated_deal_value': deal.metrics.estimated_deal_value,
                'total_interactions': deal.metrics.total_interactions,
                'objections_handled': deal.metrics.objections_handled,
                'buying_signals_count': deal.metrics.buying_signals_count,
                'engagement_score': deal.metrics.engagement_score,
                'total_duration_minutes': deal.metrics.calculate_total_duration_minutes()
            },
            'stage_history': [
                {
                    'event_type': event.event_type,
                    'from_stage': event.from_stage.value if event.from_stage else None,
                    'to_stage': event.to_stage.value if event.to_stage else None,
                    'outcome': event.outcome.value if event.outcome else None,
                    'timestamp': event.timestamp.isoformat(),
                    'confidence_score': event.confidence_score
                }
                for event in deal.stage_history
            ],
            'salesforce_integration': {
                'lead_id': deal.salesforce_lead_id,
                'opportunity_id': deal.salesforce_opportunity_id,
                'contact_id': deal.salesforce_contact_id
            },
            'handoff_info': {
                'requires_handoff': deal.requires_handoff,
                'handoff_reason': deal.handoff_reason.value if deal.handoff_reason else None,
                'assigned_rep': deal.assigned_rep
            } if deal.requires_handoff else None
        }
    
    def _get_overall_analytics(self) -> Dict[str, Any]:
        """Get overall deal analytics."""
        active_deals = list(self.active_deals.values())
        
        if not active_deals:
            return {
                'total_active_deals': 0,
                'daily_stats': self.daily_stats,
                'stage_distribution': {},
                'outcome_distribution': {},
                'performance_metrics': {}
            }
        
        # Stage distribution
        stage_distribution = {}
        for stage in DealStage:
            count = sum(1 for deal in active_deals if deal.current_stage == stage)
            if count > 0:
                stage_distribution[stage.value] = count
        
        # Performance metrics
        qualified_deals = [deal for deal in active_deals if deal.is_qualified()]
        high_value_deals = [deal for deal in active_deals if deal.metrics.estimated_deal_value > 10000]
        
        avg_qualification_score = (
            sum(deal.metrics.qualification_score for deal in active_deals) / len(active_deals)
            if active_deals else 0
        )
        
        avg_conversion_probability = (
            sum(deal.metrics.conversion_probability for deal in active_deals) / len(active_deals)
            if active_deals else 0
        )
        
        total_pipeline_value = sum(deal.metrics.estimated_deal_value for deal in active_deals)
        weighted_pipeline_value = sum(
            deal.metrics.estimated_deal_value * deal.metrics.conversion_probability
            for deal in active_deals
        )
        
        return {
            'total_active_deals': len(active_deals),
            'qualified_deals': len(qualified_deals),
            'high_value_deals': len(high_value_deals),
            'daily_stats': self.daily_stats,
            'stage_distribution': stage_distribution,
            'performance_metrics': {
                'avg_qualification_score': avg_qualification_score,
                'avg_conversion_probability': avg_conversion_probability,
                'total_pipeline_value': total_pipeline_value,
                'weighted_pipeline_value': weighted_pipeline_value,
                'qualification_rate': len(qualified_deals) / len(active_deals) if active_deals else 0
            },
            'generated_at': datetime.utcnow().isoformat()
        }


# Global service instance
deal_progression_service = DealProgressionService()