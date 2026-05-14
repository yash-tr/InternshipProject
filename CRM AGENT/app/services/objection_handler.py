"""
Enhanced Objection Handling System

This module extends the existing dialog manager with comprehensive objection handling
capabilities. It provides sophisticated objection classification, template-based responses
with prospect-specific customization, objection tracking, and escalation logic.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import re
from collections import defaultdict, Counter

from ..core.config import get_settings
from ..services.audit_trail import audit_service, AuditEventType
from ..utils.encryption import encrypt_pii_data

logger = logging.getLogger(__name__)
settings = get_settings()


class ObjectionType(str, Enum):
    """Types of sales objections."""
    PRICE = "price"                    # Budget/cost concerns
    TIMING = "timing"                  # Not the right time
    AUTHORITY = "authority"            # Not the decision maker
    NEED = "need"                      # Don't see the need
    TRUST = "trust"                    # Skeptical of solution/company
    COMPETITION = "competition"        # Already have a solution
    PRIORITY = "priority"              # Other priorities
    FEATURE = "feature"                # Missing specific features
    IMPLEMENTATION = "implementation"   # Concerns about implementation
    SUPPORT = "support"                # Concerns about support/service
    UNKNOWN = "unknown"                # Unclassified objection


class ObjectionSeverity(str, Enum):
    """Severity levels for objections."""
    LOW = "low"           # Minor concern, easy to address
    MEDIUM = "medium"     # Moderate concern, requires explanation
    HIGH = "high"         # Major concern, needs strong response
    CRITICAL = "critical" # Deal-breaking concern, may need escalation


class ResponseStrategy(str, Enum):
    """Response strategies for objections."""
    ACKNOWLEDGE_REDIRECT = "acknowledge_redirect"     # Acknowledge and redirect
    FEEL_FELT_FOUND = "feel_felt_found"              # Empathy-based response
    QUESTION_BACK = "question_back"                   # Answer with a question
    EVIDENCE_BASED = "evidence_based"                 # Provide proof/evidence
    REFRAME = "reframe"                               # Reframe the objection
    TRIAL_CLOSE = "trial_close"                       # Attempt to close after addressing
    ESCALATE = "escalate"                             # Escalate to human


@dataclass
class ObjectionPattern:
    """Pattern for identifying objections."""
    objection_type: ObjectionType
    keywords: List[str]
    phrases: List[str]
    context_clues: List[str]
    severity_indicators: Dict[ObjectionSeverity, List[str]]
    confidence_threshold: float = 0.6


@dataclass
class ObjectionResponse:
    """Response template for objections."""
    objection_type: ObjectionType
    severity: ObjectionSeverity
    strategy: ResponseStrategy
    template: str
    follow_up_questions: List[str]
    success_indicators: List[str]
    escalation_triggers: List[str]
    industry_variations: Dict[str, str] = field(default_factory=dict)
    role_variations: Dict[str, str] = field(default_factory=dict)


@dataclass
class ObjectionInstance:
    """Individual objection occurrence."""
    objection_id: str
    call_sid: str
    timestamp: datetime
    objection_type: ObjectionType
    severity: ObjectionSeverity
    user_input: str
    confidence: float
    response_used: str
    strategy: ResponseStrategy
    resolved: bool = False
    escalated: bool = False
    follow_up_needed: bool = False


@dataclass
class ObjectionAnalytics:
    """Analytics for objection handling."""
    call_sid: str
    total_objections: int
    objections_by_type: Dict[ObjectionType, int]
    objections_by_severity: Dict[ObjectionSeverity, int]
    resolution_rate: float
    escalation_rate: float
    average_resolution_time: float
    most_common_objection: Optional[ObjectionType]
    success_rate_by_strategy: Dict[ResponseStrategy, float]


class ObjectionClassifier:
    """Advanced objection classification system."""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.classification_cache: Dict[str, Tuple[ObjectionType, float]] = {}
    
    def _initialize_patterns(self) -> Dict[ObjectionType, ObjectionPattern]:
        """Initialize objection patterns for classification."""
        return {
            ObjectionType.PRICE: ObjectionPattern(
                objection_type=ObjectionType.PRICE,
                keywords=["price", "cost", "expensive", "budget", "money", "afford", "cheap", "fee", "rate"],
                phrases=[
                    "too expensive", "can't afford", "out of budget", "costs too much",
                    "price is high", "budget constraints", "financial concerns",
                    "looking for cheaper", "price point", "cost-effective"
                ],
                context_clues=["budget", "financial", "economic", "ROI", "investment"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["bit expensive", "slightly over budget"],
                    ObjectionSeverity.MEDIUM: ["expensive", "over budget", "cost concern"],
                    ObjectionSeverity.HIGH: ["too expensive", "can't afford", "way over budget"],
                    ObjectionSeverity.CRITICAL: ["absolutely can't afford", "no budget", "impossible"]
                }
            ),
            
            ObjectionType.TIMING: ObjectionPattern(
                objection_type=ObjectionType.TIMING,
                keywords=["time", "timing", "busy", "later", "now", "when", "schedule", "delay"],
                phrases=[
                    "not the right time", "too busy", "call back later", "bad timing",
                    "maybe next quarter", "not now", "in the future", "timing isn't right",
                    "busy season", "other priorities right now"
                ],
                context_clues=["schedule", "calendar", "deadline", "project", "busy"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["bit busy", "maybe later"],
                    ObjectionSeverity.MEDIUM: ["busy right now", "not the best time"],
                    ObjectionSeverity.HIGH: ["too busy", "terrible timing", "no time"],
                    ObjectionSeverity.CRITICAL: ["absolutely no time", "impossible timing"]
                }
            ),
            
            ObjectionType.AUTHORITY: ObjectionPattern(
                objection_type=ObjectionType.AUTHORITY,
                keywords=["decision", "boss", "manager", "team", "committee", "approval", "authorize"],
                phrases=[
                    "not my decision", "need to ask my boss", "team decision",
                    "need approval", "not the decision maker", "have to check with",
                    "committee decides", "need buy-in", "not authorized"
                ],
                context_clues=["hierarchy", "approval", "permission", "authority"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["should check with", "probably need approval"],
                    ObjectionSeverity.MEDIUM: ["need to ask", "team decision"],
                    ObjectionSeverity.HIGH: ["not my decision", "need approval"],
                    ObjectionSeverity.CRITICAL: ["absolutely not my call", "no authority"]
                }
            ),
            
            ObjectionType.NEED: ObjectionPattern(
                objection_type=ObjectionType.NEED,
                keywords=["need", "necessary", "problem", "issue", "solution", "working", "fine"],
                phrases=[
                    "don't need it", "working fine", "no problem", "not necessary",
                    "current solution works", "don't see the need", "not broken",
                    "satisfied with current", "no issues", "don't have that problem"
                ],
                context_clues=["satisfied", "current", "existing", "status quo"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["mostly satisfied", "working okay"],
                    ObjectionSeverity.MEDIUM: ["working fine", "don't really need"],
                    ObjectionSeverity.HIGH: ["don't need it", "no problem"],
                    ObjectionSeverity.CRITICAL: ["absolutely don't need", "perfect as is"]
                }
            ),
            
            ObjectionType.TRUST: ObjectionPattern(
                objection_type=ObjectionType.TRUST,
                keywords=["trust", "skeptical", "doubt", "unsure", "risky", "proven", "track record"],
                phrases=[
                    "not sure about", "seems risky", "don't trust", "skeptical",
                    "unproven solution", "too good to be true", "heard bad things",
                    "not convinced", "doubtful", "uncertain"
                ],
                context_clues=["reputation", "reviews", "references", "proof"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["bit unsure", "some doubts"],
                    ObjectionSeverity.MEDIUM: ["not convinced", "skeptical"],
                    ObjectionSeverity.HIGH: ["don't trust", "very doubtful"],
                    ObjectionSeverity.CRITICAL: ["absolutely don't trust", "completely skeptical"]
                }
            ),
            
            ObjectionType.COMPETITION: ObjectionPattern(
                objection_type=ObjectionType.COMPETITION,
                keywords=["already", "have", "using", "competitor", "alternative", "current", "existing"],
                phrases=[
                    "already have", "using competitor", "current vendor", "existing solution",
                    "happy with current", "already using", "have something similar",
                    "competitor offers", "current provider", "existing contract"
                ],
                context_clues=["vendor", "provider", "contract", "alternative"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["have something", "using alternative"],
                    ObjectionSeverity.MEDIUM: ["happy with current", "existing solution"],
                    ObjectionSeverity.HIGH: ["already have", "committed to current"],
                    ObjectionSeverity.CRITICAL: ["locked in contract", "completely satisfied"]
                }
            ),
            
            ObjectionType.PRIORITY: ObjectionPattern(
                objection_type=ObjectionType.PRIORITY,
                keywords=["priority", "focus", "important", "urgent", "project", "initiative"],
                phrases=[
                    "other priorities", "not a priority", "focusing on", "more important",
                    "urgent projects", "other initiatives", "different focus",
                    "not important right now", "bigger priorities"
                ],
                context_clues=["focus", "initiative", "project", "urgent"],
                severity_indicators={
                    ObjectionSeverity.LOW: ["lower priority", "not urgent"],
                    ObjectionSeverity.MEDIUM: ["other priorities", "different focus"],
                    ObjectionSeverity.HIGH: ["not a priority", "more important things"],
                    ObjectionSeverity.CRITICAL: ["absolutely not a priority", "no importance"]
                }
            )
        }
    
    def classify_objection(self, user_input: str, context: Dict[str, Any] = None) -> Tuple[ObjectionType, ObjectionSeverity, float]:
        """
        Classify an objection based on user input and context.
        
        Args:
            user_input: User's objection text
            context: Additional context (prospect data, conversation history)
            
        Returns:
            Tuple of (objection_type, severity, confidence)
        """
        if not user_input:
            return ObjectionType.UNKNOWN, ObjectionSeverity.LOW, 0.0
        
        user_input_lower = user_input.lower()
        
        # Check cache first
        cache_key = f"{user_input_lower}:{hash(str(context))}"
        if cache_key in self.classification_cache:
            cached_type, cached_confidence = self.classification_cache[cache_key]
            severity = self._determine_severity(cached_type, user_input_lower)
            return cached_type, severity, cached_confidence
        
        # Score each objection type
        type_scores = {}
        
        for objection_type, pattern in self.patterns.items():
            score = self._calculate_pattern_score(user_input_lower, pattern, context)
            if score > 0:
                type_scores[objection_type] = score
        
        if not type_scores:
            return ObjectionType.UNKNOWN, ObjectionSeverity.LOW, 0.0
        
        # Get best match
        best_type = max(type_scores, key=type_scores.get)
        confidence = type_scores[best_type]
        
        # Determine severity
        severity = self._determine_severity(best_type, user_input_lower)
        
        # Cache result
        self.classification_cache[cache_key] = (best_type, confidence)
        
        return best_type, severity, confidence
    
    def _calculate_pattern_score(self, user_input: str, pattern: ObjectionPattern, context: Dict[str, Any] = None) -> float:
        """Calculate score for a specific pattern."""
        score = 0.0
        
        # Keyword matching
        keyword_matches = sum(1 for keyword in pattern.keywords if keyword in user_input)
        score += keyword_matches * 0.3
        
        # Phrase matching (higher weight)
        phrase_matches = sum(1 for phrase in pattern.phrases if phrase in user_input)
        score += phrase_matches * 0.5
        
        # Context clues
        if context:
            context_str = str(context).lower()
            context_matches = sum(1 for clue in pattern.context_clues if clue in context_str)
            score += context_matches * 0.2
        
        # Normalize score
        max_possible = len(pattern.keywords) * 0.3 + len(pattern.phrases) * 0.5 + len(pattern.context_clues) * 0.2
        if max_possible > 0:
            score = min(score / max_possible, 1.0)
        
        return score
    
    def _determine_severity(self, objection_type: ObjectionType, user_input: str) -> ObjectionSeverity:
        """Determine severity based on objection type and input."""
        if objection_type not in self.patterns:
            return ObjectionSeverity.MEDIUM
        
        pattern = self.patterns[objection_type]
        
        # Check severity indicators
        for severity, indicators in pattern.severity_indicators.items():
            if any(indicator in user_input for indicator in indicators):
                return severity
        
        return ObjectionSeverity.MEDIUM


class ObjectionResponseGenerator:
    """Generates customized responses to objections."""
    
    def __init__(self):
        self.response_templates = self._initialize_response_templates()
        self.industry_customizations = self._initialize_industry_customizations()
        self.role_customizations = self._initialize_role_customizations()
    
    def _initialize_response_templates(self) -> Dict[Tuple[ObjectionType, ObjectionSeverity], List[ObjectionResponse]]:
        """Initialize response templates for different objection types and severities."""
        templates = {}
        
        # Price objection responses
        templates[(ObjectionType.PRICE, ObjectionSeverity.LOW)] = [
            ObjectionResponse(
                objection_type=ObjectionType.PRICE,
                severity=ObjectionSeverity.LOW,
                strategy=ResponseStrategy.ACKNOWLEDGE_REDIRECT,
                template="I understand price is always a consideration. Let me ask you this - what's the cost of not solving {pain_point}? Many of our clients find that the ROI becomes clear when they see the time and money they save.",
                follow_up_questions=["What would solving this problem be worth to your organization?"],
                success_indicators=["interested in ROI", "want to see numbers", "makes sense"],
                escalation_triggers=["absolutely no budget", "impossible"]
            )
        ]
        
        templates[(ObjectionType.PRICE, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.PRICE,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.FEEL_FELT_FOUND,
                template="I completely understand how you feel about the investment. Many of our clients in {industry} felt the same way initially. What they found was that the solution paid for itself within {roi_timeframe} through {specific_benefits}. Would you be interested in seeing how the numbers work for a company like yours?",
                follow_up_questions=["What would a 3-month payback period mean for your business?"],
                success_indicators=["want to see numbers", "interested in payback", "show me how"],
                escalation_triggers=["way too expensive", "no budget at all"]
            )
        ]
        
        templates[(ObjectionType.PRICE, ObjectionSeverity.HIGH)] = [
            ObjectionResponse(
                objection_type=ObjectionType.PRICE,
                severity=ObjectionSeverity.HIGH,
                strategy=ResponseStrategy.QUESTION_BACK,
                template="I hear you on the investment concern. Let me ask you - if I could show you how this solution could save your team {time_savings} hours per week and reduce {cost_area} by {percentage}%, would that change how you think about the investment?",
                follow_up_questions=["What would those savings be worth to your organization?"],
                success_indicators=["that would be significant", "show me the savings", "interested"],
                escalation_triggers=["absolutely can't afford", "no way"]
            )
        ]
        
        # Timing objection responses
        templates[(ObjectionType.TIMING, ObjectionSeverity.LOW)] = [
            ObjectionResponse(
                objection_type=ObjectionType.TIMING,
                severity=ObjectionSeverity.LOW,
                strategy=ResponseStrategy.ACKNOWLEDGE_REDIRECT,
                template="I completely understand timing is important. The good news is we can work with your timeline. What would be the ideal timeframe for you to start seeing results from a solution like this?",
                follow_up_questions=["When would be a good time to revisit this?"],
                success_indicators=["maybe in a few months", "next quarter", "after current project"],
                escalation_triggers=["never", "no time ever"]
            )
        ]
        
        templates[(ObjectionType.TIMING, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.TIMING,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.REFRAME,
                template="I understand you're busy - that's exactly why this solution exists. What if I told you that our clients typically save {time_savings} hours per week once implemented? Would 15 minutes now to potentially save hours later make sense?",
                follow_up_questions=["What's driving the time constraints right now?"],
                success_indicators=["that would help", "save time", "15 minutes okay"],
                escalation_triggers=["absolutely no time", "impossible timing"]
            )
        ]
        
        # Authority objection responses
        templates[(ObjectionType.AUTHORITY, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.AUTHORITY,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.QUESTION_BACK,
                template="That makes perfect sense - decisions like this often involve multiple stakeholders. Help me understand the process - who else would be involved in evaluating a solution like this? And what information would be most helpful for that conversation?",
                follow_up_questions=["What would make you look good when presenting this to your team?"],
                success_indicators=["my boss would need", "team would want to see", "need approval"],
                escalation_triggers=["not my decision at all", "no input"]
            )
        ]
        
        # Need objection responses
        templates[(ObjectionType.NEED, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.NEED,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.QUESTION_BACK,
                template="That's great that things are working well for you. I'm curious - if you could wave a magic wand and improve one thing about {relevant_process}, what would it be?",
                follow_up_questions=["What would perfect look like in this area?"],
                success_indicators=["well, if I could", "one thing would be", "perfect would be"],
                escalation_triggers=["absolutely perfect", "no improvements needed"]
            )
        ]
        
        # Trust objection responses
        templates[(ObjectionType.TRUST, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.TRUST,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.EVIDENCE_BASED,
                template="I completely understand your caution - that's smart business. Let me share what {similar_company} in {industry} said after their first month: '{testimonial}'. Would it be helpful to connect you with a reference who's in a similar situation?",
                follow_up_questions=["What would help you feel confident about moving forward?"],
                success_indicators=["reference would help", "want to talk to someone", "testimonial interesting"],
                escalation_triggers=["don't trust at all", "completely skeptical"]
            )
        ]
        
        # Competition objection responses
        templates[(ObjectionType.COMPETITION, ObjectionSeverity.MEDIUM)] = [
            ObjectionResponse(
                objection_type=ObjectionType.COMPETITION,
                severity=ObjectionSeverity.MEDIUM,
                strategy=ResponseStrategy.ACKNOWLEDGE_REDIRECT,
                template="That's great that you have something in place. I'm curious - what's working well with your current solution, and if you could improve one thing about it, what would that be?",
                follow_up_questions=["What would make your current solution perfect?"],
                success_indicators=["one thing would be", "could be better", "if I could improve"],
                escalation_triggers=["completely satisfied", "perfect solution"]
            )
        ]
        
        return templates
    
    def _initialize_industry_customizations(self) -> Dict[str, Dict[str, str]]:
        """Initialize industry-specific customizations."""
        return {
            "technology": {
                "pain_point": "technical debt and scalability issues",
                "roi_timeframe": "3-6 months",
                "specific_benefits": "reduced development time and improved system performance",
                "time_savings": "15-20",
                "cost_area": "development costs",
                "percentage": "30-40",
                "relevant_process": "your development workflow"
            },
            "healthcare": {
                "pain_point": "patient data management and compliance challenges",
                "roi_timeframe": "6-12 months",
                "specific_benefits": "improved patient outcomes and regulatory compliance",
                "time_savings": "10-15",
                "cost_area": "administrative overhead",
                "percentage": "25-35",
                "relevant_process": "patient care coordination"
            },
            "finance": {
                "pain_point": "manual processes and regulatory reporting",
                "roi_timeframe": "4-8 months",
                "specific_benefits": "automated reporting and risk reduction",
                "time_savings": "20-25",
                "cost_area": "compliance costs",
                "percentage": "40-50",
                "relevant_process": "financial reporting"
            },
            "manufacturing": {
                "pain_point": "production inefficiencies and quality control",
                "roi_timeframe": "6-9 months",
                "specific_benefits": "increased throughput and quality improvements",
                "time_savings": "12-18",
                "cost_area": "production costs",
                "percentage": "20-30",
                "relevant_process": "production planning"
            }
        }
    
    def _initialize_role_customizations(self) -> Dict[str, Dict[str, str]]:
        """Initialize role-specific customizations."""
        return {
            "ceo": {
                "focus": "strategic impact and competitive advantage",
                "language": "executive",
                "concerns": "ROI and market position"
            },
            "cto": {
                "focus": "technical implementation and scalability",
                "language": "technical",
                "concerns": "architecture and integration"
            },
            "cfo": {
                "focus": "financial impact and cost control",
                "language": "financial",
                "concerns": "budget and ROI"
            },
            "vp": {
                "focus": "departmental efficiency and team productivity",
                "language": "operational",
                "concerns": "team performance and results"
            },
            "director": {
                "focus": "process improvement and resource optimization",
                "language": "tactical",
                "concerns": "efficiency and effectiveness"
            },
            "manager": {
                "focus": "day-to-day operations and team management",
                "language": "practical",
                "concerns": "workflow and productivity"
            }
        }
    
    def generate_response(self, 
                         objection_type: ObjectionType,
                         severity: ObjectionSeverity,
                         prospect_data: Dict[str, Any],
                         context: Dict[str, Any] = None) -> Optional[ObjectionResponse]:
        """
        Generate a customized response to an objection.
        
        Args:
            objection_type: Type of objection
            severity: Severity level
            prospect_data: Prospect information for customization
            context: Additional context
            
        Returns:
            Customized ObjectionResponse or None
        """
        # Get base template
        template_key = (objection_type, severity)
        templates = self.response_templates.get(template_key, [])
        
        if not templates:
            # Try with lower severity
            if severity != ObjectionSeverity.LOW:
                lower_severity = ObjectionSeverity.LOW if severity == ObjectionSeverity.MEDIUM else ObjectionSeverity.MEDIUM
                template_key = (objection_type, lower_severity)
                templates = self.response_templates.get(template_key, [])
        
        if not templates:
            return None
        
        # Select best template (for now, just use first)
        base_template = templates[0]
        
        # Customize template
        customized_template = self._customize_template(base_template, prospect_data, context)
        
        return customized_template
    
    def _customize_template(self, 
                           template: ObjectionResponse,
                           prospect_data: Dict[str, Any],
                           context: Dict[str, Any] = None) -> ObjectionResponse:
        """Customize template based on prospect data."""
        # Extract prospect information
        industry = prospect_data.get("industry", "").lower()
        job_title = prospect_data.get("job_title", "").lower()
        company_name = prospect_data.get("company_name", "your company")
        
        # Get industry customizations
        industry_vars = self.industry_customizations.get(industry, self.industry_customizations.get("technology", {}))
        
        # Get role customizations
        role_key = self._extract_role_key(job_title)
        role_vars = self.role_customizations.get(role_key, {})
        
        # Build template variables
        template_vars = {
            "company_name": company_name,
            "industry": industry or "your industry",
            "job_title": job_title or "decision maker",
            "similar_company": f"another {industry} company" if industry else "a similar company",
            "testimonial": "This has transformed how we operate - we're seeing results we never thought possible.",
            **industry_vars
        }
        
        # Format template
        try:
            customized_response = template.template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            customized_response = template.template
        
        # Create customized response
        return ObjectionResponse(
            objection_type=template.objection_type,
            severity=template.severity,
            strategy=template.strategy,
            template=customized_response,
            follow_up_questions=template.follow_up_questions,
            success_indicators=template.success_indicators,
            escalation_triggers=template.escalation_triggers
        )
    
    def _extract_role_key(self, job_title: str) -> str:
        """Extract role key from job title."""
        job_title_lower = job_title.lower()
        
        if any(title in job_title_lower for title in ["ceo", "chief executive", "president"]):
            return "ceo"
        elif any(title in job_title_lower for title in ["cto", "chief technology", "chief technical"]):
            return "cto"
        elif any(title in job_title_lower for title in ["cfo", "chief financial"]):
            return "cfo"
        elif any(title in job_title_lower for title in ["vp", "vice president"]):
            return "vp"
        elif "director" in job_title_lower:
            return "director"
        elif "manager" in job_title_lower:
            return "manager"
        else:
            return "manager"  # Default


class ObjectionTracker:
    """Tracks objections and provides analytics."""
    
    def __init__(self):
        self.objections: Dict[str, List[ObjectionInstance]] = defaultdict(list)
        self.resolution_tracking: Dict[str, bool] = {}
        self.response_effectiveness: Dict[ResponseStrategy, List[bool]] = defaultdict(list)
    
    def record_objection(self, 
                        call_sid: str,
                        objection_type: ObjectionType,
                        severity: ObjectionSeverity,
                        user_input: str,
                        confidence: float,
                        response_used: str,
                        strategy: ResponseStrategy) -> str:
        """Record an objection occurrence."""
        objection_id = f"{call_sid}_{len(self.objections[call_sid])}"
        
        objection = ObjectionInstance(
            objection_id=objection_id,
            call_sid=call_sid,
            timestamp=datetime.utcnow(),
            objection_type=objection_type,
            severity=severity,
            user_input=user_input,
            confidence=confidence,
            response_used=response_used,
            strategy=strategy
        )
        
        self.objections[call_sid].append(objection)
        return objection_id
    
    def update_objection_outcome(self, 
                                objection_id: str,
                                resolved: bool,
                                escalated: bool = False,
                                follow_up_needed: bool = False):
        """Update objection outcome."""
        # Find objection
        for call_objections in self.objections.values():
            for objection in call_objections:
                if objection.objection_id == objection_id:
                    objection.resolved = resolved
                    objection.escalated = escalated
                    objection.follow_up_needed = follow_up_needed
                    
                    # Track response effectiveness
                    self.response_effectiveness[objection.strategy].append(resolved)
                    break
    
    def get_call_analytics(self, call_sid: str) -> Optional[ObjectionAnalytics]:
        """Get analytics for a specific call."""
        if call_sid not in self.objections:
            return None
        
        call_objections = self.objections[call_sid]
        if not call_objections:
            return None
        
        # Calculate metrics
        total_objections = len(call_objections)
        objections_by_type = Counter(obj.objection_type for obj in call_objections)
        objections_by_severity = Counter(obj.severity for obj in call_objections)
        
        resolved_count = sum(1 for obj in call_objections if obj.resolved)
        escalated_count = sum(1 for obj in call_objections if obj.escalated)
        
        resolution_rate = resolved_count / total_objections if total_objections > 0 else 0.0
        escalation_rate = escalated_count / total_objections if total_objections > 0 else 0.0
        
        # Calculate average resolution time (placeholder)
        average_resolution_time = 120.0  # seconds
        
        # Most common objection
        most_common_objection = objections_by_type.most_common(1)[0][0] if objections_by_type else None
        
        # Success rate by strategy
        success_rate_by_strategy = {}
        for strategy in ResponseStrategy:
            strategy_results = self.response_effectiveness.get(strategy, [])
            if strategy_results:
                success_rate_by_strategy[strategy] = sum(strategy_results) / len(strategy_results)
        
        return ObjectionAnalytics(
            call_sid=call_sid,
            total_objections=total_objections,
            objections_by_type=dict(objections_by_type),
            objections_by_severity=dict(objections_by_severity),
            resolution_rate=resolution_rate,
            escalation_rate=escalation_rate,
            average_resolution_time=average_resolution_time,
            most_common_objection=most_common_objection,
            success_rate_by_strategy=success_rate_by_strategy
        )
    
    def should_escalate(self, call_sid: str) -> bool:
        """Determine if call should be escalated based on objection patterns."""
        if call_sid not in self.objections:
            return False
        
        call_objections = self.objections[call_sid]
        
        # Escalation criteria
        total_objections = len(call_objections)
        unresolved_objections = sum(1 for obj in call_objections if not obj.resolved)
        critical_objections = sum(1 for obj in call_objections if obj.severity == ObjectionSeverity.CRITICAL)
        
        # Escalate if:
        # - More than 3 objections total
        # - More than 2 unresolved objections
        # - Any critical objections
        return (total_objections > 3 or 
                unresolved_objections > 2 or 
                critical_objections > 0)


class EnhancedObjectionHandler:
    """
    Enhanced objection handling system that integrates with the existing dialog manager.
    
    Provides comprehensive objection classification, template-based responses with
    prospect-specific customization, objection tracking, and escalation logic.
    """
    
    def __init__(self):
        self.classifier = ObjectionClassifier()
        self.response_generator = ObjectionResponseGenerator()
        self.tracker = ObjectionTracker()
        
        logger.info("Enhanced Objection Handler initialized")
    
    async def handle_objection(self, 
                             call_sid: str,
                             user_input: str,
                             prospect_data: Dict[str, Any],
                             conversation_context: Dict[str, Any] = None) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Handle an objection with classification, response generation, and tracking.
        
        Args:
            call_sid: Call identifier
            user_input: User's objection text
            prospect_data: Prospect information
            conversation_context: Additional conversation context
            
        Returns:
            Tuple of (response_text, should_escalate, objection_info)
        """
        try:
            # Classify objection
            objection_type, severity, confidence = self.classifier.classify_objection(
                user_input, conversation_context
            )
            
            # Generate response
            response_template = self.response_generator.generate_response(
                objection_type, severity, prospect_data, conversation_context
            )
            
            if not response_template:
                # Fallback response
                response_text = "I understand your concern. Let me see how we can address that. What would be most helpful for you to know?"
                strategy = ResponseStrategy.ACKNOWLEDGE_REDIRECT
            else:
                response_text = response_template.template
                strategy = response_template.strategy
            
            # Record objection
            objection_id = self.tracker.record_objection(
                call_sid=call_sid,
                objection_type=objection_type,
                severity=severity,
                user_input=user_input,
                confidence=confidence,
                response_used=response_text,
                strategy=strategy
            )
            
            # Check if escalation is needed
            should_escalate = self.tracker.should_escalate(call_sid)
            
            # Log objection handling
            await audit_service.log_event(
                event_type=AuditEventType.OBJECTION_HANDLED,
                entity_type="objection_handler",
                entity_id=call_sid,
                details={
                    "objection_id": objection_id,
                    "objection_type": objection_type.value,
                    "severity": severity.value,
                    "confidence": confidence,
                    "strategy": strategy.value,
                    "should_escalate": should_escalate
                }
            )
            
            # Objection info for caller
            objection_info = {
                "objection_id": objection_id,
                "objection_type": objection_type.value,
                "severity": severity.value,
                "confidence": confidence,
                "strategy": strategy.value,
                "follow_up_questions": response_template.follow_up_questions if response_template else [],
                "success_indicators": response_template.success_indicators if response_template else [],
                "escalation_triggers": response_template.escalation_triggers if response_template else []
            }
            
            return response_text, should_escalate, objection_info
            
        except Exception as e:
            logger.error(f"Error handling objection for call {call_sid}: {e}")
            
            # Fallback response
            fallback_response = "I understand your concern. Let me connect you with one of our specialists who can address this better."
            return fallback_response, True, {"error": str(e)}
    
    async def update_objection_outcome(self, 
                                     objection_id: str,
                                     user_response: str,
                                     resolved: bool = None) -> bool:
        """
        Update objection outcome based on user response.
        
        Args:
            objection_id: Objection identifier
            user_response: User's response to objection handling
            resolved: Whether objection was resolved (auto-detected if None)
            
        Returns:
            Whether objection was resolved
        """
        try:
            # Auto-detect resolution if not provided
            if resolved is None:
                resolved = self._detect_resolution(user_response)
            
            # Check for escalation triggers
            escalated = self._detect_escalation_needed(user_response)
            
            # Update tracking
            self.tracker.update_objection_outcome(
                objection_id=objection_id,
                resolved=resolved,
                escalated=escalated,
                follow_up_needed=not resolved and not escalated
            )
            
            return resolved
            
        except Exception as e:
            logger.error(f"Error updating objection outcome {objection_id}: {e}")
            return False
    
    def _detect_resolution(self, user_response: str) -> bool:
        """Detect if objection was resolved based on user response."""
        if not user_response:
            return False
        
        user_response_lower = user_response.lower()
        
        # Positive indicators
        positive_indicators = [
            "that makes sense", "i see", "good point", "interesting", "helpful",
            "yes", "okay", "sure", "sounds good", "i understand", "fair enough",
            "let's proceed", "move forward", "next step", "schedule", "demo"
        ]
        
        # Negative indicators
        negative_indicators = [
            "but", "however", "still", "not convinced", "don't think", "disagree",
            "no", "not interested", "won't work", "can't", "impossible"
        ]
        
        positive_score = sum(1 for indicator in positive_indicators if indicator in user_response_lower)
        negative_score = sum(1 for indicator in negative_indicators if indicator in user_response_lower)
        
        return positive_score > negative_score
    
    def _detect_escalation_needed(self, user_response: str) -> bool:
        """Detect if escalation is needed based on user response."""
        if not user_response:
            return False
        
        user_response_lower = user_response.lower()
        
        escalation_triggers = [
            "speak to manager", "talk to someone else", "human", "person",
            "not satisfied", "this isn't working", "waste of time",
            "absolutely not", "never", "impossible", "ridiculous"
        ]
        
        return any(trigger in user_response_lower for trigger in escalation_triggers)
    
    async def get_call_objection_analytics(self, call_sid: str) -> Optional[ObjectionAnalytics]:
        """Get objection analytics for a call."""
        return self.tracker.get_call_analytics(call_sid)
    
    async def get_system_objection_metrics(self) -> Dict[str, Any]:
        """Get system-wide objection handling metrics."""
        try:
            all_objections = []
            for call_objections in self.tracker.objections.values():
                all_objections.extend(call_objections)
            
            if not all_objections:
                return {"total_objections": 0, "message": "No objections recorded"}
            
            # Calculate system metrics
            total_objections = len(all_objections)
            objections_by_type = Counter(obj.objection_type for obj in all_objections)
            objections_by_severity = Counter(obj.severity for obj in all_objections)
            
            resolved_count = sum(1 for obj in all_objections if obj.resolved)
            escalated_count = sum(1 for obj in all_objections if obj.escalated)
            
            overall_resolution_rate = resolved_count / total_objections if total_objections > 0 else 0.0
            overall_escalation_rate = escalated_count / total_objections if total_objections > 0 else 0.0
            
            # Strategy effectiveness
            strategy_effectiveness = {}
            for strategy in ResponseStrategy:
                strategy_results = self.tracker.response_effectiveness.get(strategy, [])
                if strategy_results:
                    strategy_effectiveness[strategy.value] = {
                        "success_rate": sum(strategy_results) / len(strategy_results),
                        "total_uses": len(strategy_results)
                    }
            
            return {
                "total_objections": total_objections,
                "objections_by_type": {k.value: v for k, v in objections_by_type.items()},
                "objections_by_severity": {k.value: v for k, v in objections_by_severity.items()},
                "overall_resolution_rate": overall_resolution_rate,
                "overall_escalation_rate": overall_escalation_rate,
                "strategy_effectiveness": strategy_effectiveness,
                "most_common_objection": objections_by_type.most_common(1)[0][0].value if objections_by_type else None,
                "active_calls_with_objections": len(self.tracker.objections)
            }
            
        except Exception as e:
            logger.error(f"Error getting system objection metrics: {e}")
            return {"error": str(e)}


# Global instance
enhanced_objection_handler = EnhancedObjectionHandler()