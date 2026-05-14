"""
Prospect Scoring and Qualification System

This module implements a rules-based prospect scoring engine with deterministic
scoring for clear cases and LLM-assisted classification for ambiguous scenarios.
Follows the cost-controlled approach with strict budget limits and caching.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator

from ..schemas.prospect_research import (
    ResearchResultSchema, ContactProfileSchema, CompanyIntelligenceSchema,
    CompanySize, RevenueRange, ConfidenceLevel
)
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ValueTier(str, Enum):
    """Value tier classifications for prospects."""
    A_TIER = "A"  # High value (score 80-100)
    B_TIER = "B"  # Medium value (score 60-79)
    C_TIER = "C"  # Low value (score 40-59)
    UNQUALIFIED = "U"  # Unqualified (score 0-39)


class ScoringCategory(str, Enum):
    """Categories for scoring components."""
    COMPANY_SIZE = "company_size"
    REVENUE = "revenue"
    INDUSTRY = "industry"
    JOB_TITLE = "job_title"
    SENIORITY = "seniority"
    GEOGRAPHY = "geography"
    BUDGET_SIGNALS = "budget_signals"
    TIMELINE_SIGNALS = "timeline_signals"
    TECHNOLOGY_FIT = "technology_fit"
    BUYING_SIGNALS = "buying_signals"


@dataclass
class ScoringRule:
    """Individual scoring rule definition."""
    category: ScoringCategory
    condition: str  # Description of the condition
    score_value: int  # Points awarded (0-100)
    weight: float = 1.0  # Weight multiplier
    required_fields: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not 0 <= self.score_value <= 100:
            raise ValueError("Score value must be between 0 and 100")
        if not 0 <= self.weight <= 2.0:
            raise ValueError("Weight must be between 0 and 2.0")


@dataclass
class ScoringResult:
    """Result of prospect scoring."""
    total_score: int
    category_scores: Dict[ScoringCategory, int]
    applied_rules: List[str]
    confidence_level: ConfidenceLevel
    value_tier: ValueTier
    scoring_rationale: str
    requires_llm_review: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CompanySizeScoring:
    """Company size scoring matrix."""
    
    SCORING_MATRIX = {
        CompanySize.STARTUP: {"score": 15, "rationale": "Startup - limited budget but fast decisions"},
        CompanySize.SMALL: {"score": 25, "rationale": "Small company - good balance of budget and agility"},
        CompanySize.MEDIUM: {"score": 35, "rationale": "Medium company - established budget and processes"},
        CompanySize.LARGE: {"score": 30, "rationale": "Large company - significant budget but complex decisions"},
        CompanySize.ENTERPRISE: {"score": 20, "rationale": "Enterprise - huge budget but very complex sales cycle"}
    }
    
    @classmethod
    def score_by_employee_count(cls, employee_count: Optional[int]) -> Tuple[int, str]:
        """Score based on employee count."""
        if not employee_count:
            return 0, "No employee count data available"
        
        if employee_count <= 10:
            size = CompanySize.STARTUP
        elif employee_count <= 50:
            size = CompanySize.SMALL
        elif employee_count <= 200:
            size = CompanySize.MEDIUM
        elif employee_count <= 1000:
            size = CompanySize.LARGE
        else:
            size = CompanySize.ENTERPRISE
        
        matrix_data = cls.SCORING_MATRIX[size]
        return matrix_data["score"], matrix_data["rationale"]


class IndustryScoring:
    """Industry-based scoring matrix."""
    
    HIGH_VALUE_INDUSTRIES = {
        "technology": 40,
        "software": 40,
        "saas": 45,
        "fintech": 45,
        "healthcare": 35,
        "financial services": 35,
        "consulting": 30,
        "professional services": 30,
        "manufacturing": 25,
        "e-commerce": 35
    }
    
    MEDIUM_VALUE_INDUSTRIES = {
        "retail": 20,
        "education": 15,
        "real estate": 20,
        "marketing": 25,
        "media": 20,
        "telecommunications": 25,
        "automotive": 20,
        "energy": 25
    }
    
    LOW_VALUE_INDUSTRIES = {
        "non-profit": 5,
        "government": 10,
        "agriculture": 10,
        "hospitality": 10,
        "food service": 10
    }
    
    @classmethod
    def score_industry(cls, industry: Optional[str]) -> Tuple[int, str]:
        """Score based on industry."""
        if not industry:
            return 0, "No industry data available"
        
        industry_lower = industry.lower()
        
        # Check high-value industries
        for ind, score in cls.HIGH_VALUE_INDUSTRIES.items():
            if ind in industry_lower:
                return score, f"High-value industry: {industry}"
        
        # Check medium-value industries
        for ind, score in cls.MEDIUM_VALUE_INDUSTRIES.items():
            if ind in industry_lower:
                return score, f"Medium-value industry: {industry}"
        
        # Check low-value industries
        for ind, score in cls.LOW_VALUE_INDUSTRIES.items():
            if ind in industry_lower:
                return score, f"Low-value industry: {industry}"
        
        # Default for unknown industries
        return 15, f"Unknown industry: {industry}"


class JobTitleScoring:
    """Job title and seniority level scoring."""
    
    C_LEVEL_TITLES = [
        "ceo", "cto", "cfo", "coo", "cmo", "chief", "president", "founder"
    ]
    
    VP_DIRECTOR_TITLES = [
        "vp", "vice president", "director", "head of", "senior director"
    ]
    
    MANAGER_TITLES = [
        "manager", "senior manager", "team lead", "lead", "principal"
    ]
    
    INDIVIDUAL_CONTRIBUTOR_TITLES = [
        "analyst", "specialist", "coordinator", "associate", "engineer",
        "developer", "designer", "consultant"
    ]
    
    @classmethod
    def score_job_title(cls, job_title: Optional[str]) -> Tuple[int, str]:
        """Score based on job title and seniority."""
        if not job_title:
            return 0, "No job title data available"
        
        title_lower = job_title.lower()
        
        # C-Level scoring
        for title in cls.C_LEVEL_TITLES:
            if title in title_lower:
                return 45, f"C-Level executive: {job_title}"
        
        # VP/Director scoring
        for title in cls.VP_DIRECTOR_TITLES:
            if title in title_lower:
                return 35, f"VP/Director level: {job_title}"
        
        # Manager scoring
        for title in cls.MANAGER_TITLES:
            if title in title_lower:
                return 25, f"Manager level: {job_title}"
        
        # Individual contributor scoring
        for title in cls.INDIVIDUAL_CONTRIBUTOR_TITLES:
            if title in title_lower:
                return 10, f"Individual contributor: {job_title}"
        
        # Unknown title
        return 15, f"Unknown title level: {job_title}"


class GeographyScoring:
    """Geographic and timezone-based scoring."""
    
    HIGH_VALUE_REGIONS = {
        "united states": 30,
        "canada": 25,
        "united kingdom": 25,
        "australia": 20,
        "germany": 20,
        "france": 20,
        "netherlands": 20,
        "sweden": 20,
        "denmark": 20,
        "norway": 20
    }
    
    MEDIUM_VALUE_REGIONS = {
        "spain": 15,
        "italy": 15,
        "japan": 15,
        "south korea": 15,
        "singapore": 15,
        "new zealand": 15,
        "ireland": 15,
        "belgium": 15
    }
    
    TIMEZONE_PREFERENCES = {
        "EST": 1.2,  # Eastern Standard Time
        "PST": 1.1,  # Pacific Standard Time
        "CST": 1.1,  # Central Standard Time
        "GMT": 1.0,  # Greenwich Mean Time
        "CET": 1.0,  # Central European Time
    }
    
    @classmethod
    def score_geography(cls, location: Optional[str]) -> Tuple[int, str]:
        """Score based on geographic location."""
        if not location:
            return 0, "No location data available"
        
        location_lower = location.lower()
        
        # Check high-value regions
        for region, score in cls.HIGH_VALUE_REGIONS.items():
            if region in location_lower:
                return score, f"High-value region: {location}"
        
        # Check medium-value regions
        for region, score in cls.MEDIUM_VALUE_REGIONS.items():
            if region in location_lower:
                return score, f"Medium-value region: {location}"
        
        # Default for other regions
        return 5, f"Other region: {location}"
    
    @classmethod
    def get_timezone_multiplier(cls, location: Optional[str]) -> float:
        """Get timezone-based scoring multiplier."""
        if not location:
            return 1.0
        
        # Simple timezone detection based on location
        location_lower = location.lower()
        
        if any(term in location_lower for term in ["new york", "boston", "miami", "atlanta"]):
            return cls.TIMEZONE_PREFERENCES.get("EST", 1.0)
        elif any(term in location_lower for term in ["los angeles", "san francisco", "seattle"]):
            return cls.TIMEZONE_PREFERENCES.get("PST", 1.0)
        elif any(term in location_lower for term in ["chicago", "dallas", "houston"]):
            return cls.TIMEZONE_PREFERENCES.get("CST", 1.0)
        elif any(term in location_lower for term in ["london", "dublin"]):
            return cls.TIMEZONE_PREFERENCES.get("GMT", 1.0)
        elif any(term in location_lower for term in ["berlin", "paris", "amsterdam"]):
            return cls.TIMEZONE_PREFERENCES.get("CET", 1.0)
        
        return 1.0


class BuyingSignalScoring:
    """Buying signal and timeline indicator scoring."""
    
    BUDGET_SIGNALS = {
        "budget approved": 25,
        "budget allocated": 25,
        "funding secured": 20,
        "investment received": 20,
        "budget planning": 15,
        "cost evaluation": 10,
        "price comparison": 10
    }
    
    TIMELINE_SIGNALS = {
        "urgent": 25,
        "asap": 25,
        "immediate": 25,
        "this quarter": 20,
        "q1": 15, "q2": 15, "q3": 15, "q4": 15,
        "this year": 10,
        "next year": 5,
        "exploring": 5
    }
    
    PAIN_POINT_SIGNALS = {
        "current solution failing": 20,
        "system down": 25,
        "losing customers": 25,
        "compliance issues": 20,
        "security breach": 25,
        "manual processes": 15,
        "inefficient": 10,
        "outdated": 10
    }
    
    @classmethod
    def score_buying_signals(cls, buying_signals: List[Any]) -> Tuple[int, str]:
        """Score based on buying signals."""
        if not buying_signals:
            return 0, "No buying signals detected"
        
        total_score = 0
        detected_signals = []
        
        for signal in buying_signals:
            # Handle both string and BuyingSignal object formats
            if hasattr(signal, 'description'):
                signal_text = signal.description.lower()
                signal_type = getattr(signal, 'signal_type', '')
            else:
                signal_text = str(signal).lower()
                signal_type = ''
            
            # Check budget signals
            for budget_signal, score in cls.BUDGET_SIGNALS.items():
                if budget_signal in signal_text or budget_signal in signal_type:
                    total_score += score
                    detected_signals.append(f"Budget: {budget_signal}")
                    break
            
            # Check timeline signals
            for timeline_signal, score in cls.TIMELINE_SIGNALS.items():
                if timeline_signal in signal_text or timeline_signal in signal_type:
                    total_score += score
                    detected_signals.append(f"Timeline: {timeline_signal}")
                    break
            
            # Check pain point signals
            for pain_signal, score in cls.PAIN_POINT_SIGNALS.items():
                if pain_signal in signal_text:
                    total_score += score
                    detected_signals.append(f"Pain: {pain_signal}")
                    break
        
        # Cap the total score at 50 for buying signals
        total_score = min(total_score, 50)
        
        rationale = f"Buying signals detected: {', '.join(detected_signals)}" if detected_signals else "No specific buying signals"
        
        return total_score, rationale


class RevenueScoring:
    """Revenue-based scoring matrix."""
    
    REVENUE_SCORING = {
        RevenueRange.UNDER_1M: {"score": 10, "rationale": "Under $1M revenue - limited budget"},
        RevenueRange.RANGE_1M_10M: {"score": 20, "rationale": "$1M-$10M revenue - growing budget"},
        RevenueRange.RANGE_10M_50M: {"score": 35, "rationale": "$10M-$50M revenue - established budget"},
        RevenueRange.RANGE_50M_100M: {"score": 40, "rationale": "$50M-$100M revenue - significant budget"},
        RevenueRange.RANGE_100M_500M: {"score": 35, "rationale": "$100M-$500M revenue - large but complex"},
        RevenueRange.OVER_500M: {"score": 25, "rationale": "Over $500M revenue - enterprise complexity"}
    }
    
    @classmethod
    def score_revenue(cls, revenue_range: Optional[RevenueRange]) -> Tuple[int, str]:
        """Score based on revenue range."""
        if not revenue_range:
            return 0, "No revenue data available"
        
        matrix_data = cls.REVENUE_SCORING.get(revenue_range)
        if matrix_data:
            return matrix_data["score"], matrix_data["rationale"]
        
        return 0, f"Unknown revenue range: {revenue_range}"


class RulesBasedScoringEngine:
    """
    Rules-based prospect scoring engine for deterministic scoring.
    
    Implements scoring matrices for company size, industry, job titles,
    geography, and buying signals with clear business logic.
    """
    
    def __init__(self):
        self.scoring_rules = self._initialize_scoring_rules()
        self.logger = logging.getLogger(__name__)
    
    def _initialize_scoring_rules(self) -> List[ScoringRule]:
        """Initialize all scoring rules."""
        return [
            # Company size rules
            ScoringRule(
                category=ScoringCategory.COMPANY_SIZE,
                condition="Employee count based scoring",
                score_value=35,
                weight=1.0,
                required_fields=["employee_count"]
            ),
            
            # Revenue rules
            ScoringRule(
                category=ScoringCategory.REVENUE,
                condition="Revenue range based scoring",
                score_value=40,
                weight=1.2,
                required_fields=["revenue_range"]
            ),
            
            # Industry rules
            ScoringRule(
                category=ScoringCategory.INDUSTRY,
                condition="Industry vertical scoring",
                score_value=40,
                weight=1.0,
                required_fields=["industry"]
            ),
            
            # Job title rules
            ScoringRule(
                category=ScoringCategory.JOB_TITLE,
                condition="Job title and seniority scoring",
                score_value=45,
                weight=1.1,
                required_fields=["job_title"]
            ),
            
            # Geography rules
            ScoringRule(
                category=ScoringCategory.GEOGRAPHY,
                condition="Geographic location scoring",
                score_value=30,
                weight=0.8,
                required_fields=["location"]
            ),
            
            # Buying signals rules
            ScoringRule(
                category=ScoringCategory.BUYING_SIGNALS,
                condition="Buying signals and timeline indicators",
                score_value=50,
                weight=1.3,
                required_fields=["buying_signals"]
            )
        ]
    
    async def score_prospect(self, research_data: ResearchResultSchema) -> ScoringResult:
        """
        Score a prospect based on research data using deterministic rules.
        
        Args:
            research_data: Complete research result with contact and company data
            
        Returns:
            ScoringResult with total score, category breakdown, and rationale
        """
        start_time = datetime.utcnow()
        
        try:
            category_scores = {}
            applied_rules = []
            rationale_parts = []
            
            # Extract data for scoring
            contact = research_data.contact_profile
            company = research_data.company_intelligence
            
            # Score company size
            size_score, size_rationale = CompanySizeScoring.score_by_employee_count(
                company.employee_count
            )
            category_scores[ScoringCategory.COMPANY_SIZE] = size_score
            if size_score > 0:
                applied_rules.append(f"Company Size: {size_rationale}")
                rationale_parts.append(size_rationale)
            
            # Score revenue
            revenue_score, revenue_rationale = RevenueScoring.score_revenue(
                company.revenue_range
            )
            category_scores[ScoringCategory.REVENUE] = revenue_score
            if revenue_score > 0:
                applied_rules.append(f"Revenue: {revenue_rationale}")
                rationale_parts.append(revenue_rationale)
            
            # Score industry
            industry_score, industry_rationale = IndustryScoring.score_industry(
                company.industry
            )
            category_scores[ScoringCategory.INDUSTRY] = industry_score
            if industry_score > 0:
                applied_rules.append(f"Industry: {industry_rationale}")
                rationale_parts.append(industry_rationale)
            
            # Score job title
            title_score, title_rationale = JobTitleScoring.score_job_title(
                contact.job_title
            )
            category_scores[ScoringCategory.JOB_TITLE] = title_score
            if title_score > 0:
                applied_rules.append(f"Job Title: {title_rationale}")
                rationale_parts.append(title_rationale)
            
            # Score geography
            geo_score, geo_rationale = GeographyScoring.score_geography(
                contact.location
            )
            geo_multiplier = GeographyScoring.get_timezone_multiplier(contact.location)
            geo_score = int(geo_score * geo_multiplier)
            category_scores[ScoringCategory.GEOGRAPHY] = geo_score
            if geo_score > 0:
                applied_rules.append(f"Geography: {geo_rationale}")
                rationale_parts.append(geo_rationale)
            
            # Score buying signals
            signals_score, signals_rationale = BuyingSignalScoring.score_buying_signals(
                research_data.buying_signals
            )
            category_scores[ScoringCategory.BUYING_SIGNALS] = signals_score
            if signals_score > 0:
                applied_rules.append(f"Buying Signals: {signals_rationale}")
                rationale_parts.append(signals_rationale)
            
            # Calculate total score (weighted average)
            total_score = self._calculate_weighted_score(category_scores)
            
            # Determine confidence level
            confidence_level = self._determine_confidence_level(
                category_scores, research_data.overall_confidence
            )
            
            # Determine value tier
            value_tier = self._determine_value_tier(total_score)
            
            # Check if LLM review is needed (gray zone)
            requires_llm_review = self._requires_llm_review(total_score, confidence_level)
            
            # Build rationale
            scoring_rationale = self._build_scoring_rationale(
                total_score, rationale_parts, value_tier
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(
                f"Scored prospect {research_data.prospect_id}: "
                f"Score={total_score}, Tier={value_tier.value}, "
                f"LLM_Review={requires_llm_review}, Time={execution_time:.2f}s"
            )
            
            return ScoringResult(
                total_score=total_score,
                category_scores=category_scores,
                applied_rules=applied_rules,
                confidence_level=confidence_level,
                value_tier=value_tier,
                scoring_rationale=scoring_rationale,
                requires_llm_review=requires_llm_review
            )
            
        except Exception as e:
            self.logger.error(f"Error scoring prospect {research_data.prospect_id}: {e}")
            raise
    
    def _calculate_weighted_score(self, category_scores: Dict[ScoringCategory, int]) -> int:
        """Calculate weighted total score from category scores."""
        # Define weights for each category
        weights = {
            ScoringCategory.COMPANY_SIZE: 0.15,
            ScoringCategory.REVENUE: 0.20,
            ScoringCategory.INDUSTRY: 0.15,
            ScoringCategory.JOB_TITLE: 0.20,
            ScoringCategory.GEOGRAPHY: 0.10,
            ScoringCategory.BUYING_SIGNALS: 0.20
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for category, score in category_scores.items():
            weight = weights.get(category, 0.0)
            weighted_sum += score * weight
            total_weight += weight
        
        # Normalize to 0-100 scale
        if total_weight > 0:
            normalized_score = int(weighted_sum / total_weight)
        else:
            normalized_score = 0
        
        return min(max(normalized_score, 0), 100)
    
    def _determine_confidence_level(self, 
                                  category_scores: Dict[ScoringCategory, int],
                                  research_confidence: float) -> ConfidenceLevel:
        """Determine confidence level based on data availability and quality."""
        # Count non-zero scores (data availability)
        available_data_points = sum(1 for score in category_scores.values() if score > 0)
        total_data_points = len(category_scores)
        
        data_completeness = available_data_points / total_data_points
        
        # Combine data completeness with research confidence
        combined_confidence = (data_completeness + research_confidence) / 2
        
        if combined_confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif combined_confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif combined_confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _determine_value_tier(self, total_score: int) -> ValueTier:
        """Determine value tier based on total score."""
        if total_score >= 80:
            return ValueTier.A_TIER
        elif total_score >= 60:
            return ValueTier.B_TIER
        elif total_score >= 40:
            return ValueTier.C_TIER
        else:
            return ValueTier.UNQUALIFIED
    
    def _requires_llm_review(self, total_score: int, confidence_level: ConfidenceLevel) -> bool:
        """Determine if LLM review is needed for gray zone cases."""
        # Gray zone: scores between 45-55 with medium or low confidence
        is_gray_zone_score = 45 <= total_score <= 55
        is_uncertain_confidence = confidence_level in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]
        
        return is_gray_zone_score and is_uncertain_confidence
    
    def _build_scoring_rationale(self, 
                               total_score: int,
                               rationale_parts: List[str],
                               value_tier: ValueTier) -> str:
        """Build human-readable scoring rationale."""
        tier_descriptions = {
            ValueTier.A_TIER: "High-value prospect with strong buying potential",
            ValueTier.B_TIER: "Medium-value prospect worth pursuing",
            ValueTier.C_TIER: "Lower-value prospect for nurture campaigns",
            ValueTier.UNQUALIFIED: "Unqualified prospect, not recommended for outreach"
        }
        
        rationale = f"Total Score: {total_score}/100 - {tier_descriptions[value_tier]}\n\n"
        rationale += "Scoring Breakdown:\n"
        
        for i, part in enumerate(rationale_parts, 1):
            rationale += f"{i}. {part}\n"
        
        return rationale.strip()


# Validation and testing framework
class ScoringValidator:
    """Validation framework for scoring rules and edge cases."""
    
    @staticmethod
    def validate_scoring_rules(engine: RulesBasedScoringEngine) -> List[str]:
        """Validate all scoring rules for consistency and completeness."""
        issues = []
        
        # Check rule completeness
        required_categories = set(ScoringCategory)
        covered_categories = {rule.category for rule in engine.scoring_rules}
        
        missing_categories = required_categories - covered_categories
        if missing_categories:
            issues.append(f"Missing scoring rules for categories: {missing_categories}")
        
        # Check score ranges
        for rule in engine.scoring_rules:
            if not 0 <= rule.score_value <= 100:
                issues.append(f"Invalid score value for {rule.category}: {rule.score_value}")
            
            if not 0 <= rule.weight <= 2.0:
                issues.append(f"Invalid weight for {rule.category}: {rule.weight}")
        
        return issues
    
    @staticmethod
    def test_edge_cases() -> List[str]:
        """Test edge cases for scoring logic."""
        test_results = []
        
        # Test empty data
        try:
            empty_contact = ContactProfileSchema()
            empty_company = CompanyIntelligenceSchema(company_name="Test")
            empty_research = ResearchResultSchema(
                prospect_id="test",
                contact_profile=empty_contact,
                company_intelligence=empty_company
            )
            
            engine = RulesBasedScoringEngine()
            result = asyncio.run(engine.score_prospect(empty_research))
            
            if result.total_score != 0:
                test_results.append(f"Empty data should score 0, got {result.total_score}")
            
        except Exception as e:
            test_results.append(f"Empty data test failed: {e}")
        
        return test_results


class LLMScoringCache:
    """Cache for LLM scoring results with 24-hour expiration."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.cache_duration = timedelta(hours=24)
    
    def _generate_cache_key(self, research_data: ResearchResultSchema) -> str:
        """Generate cache key from research data."""
        # Create a hash of key prospect data for caching
        key_data = {
            "company_name": research_data.company_intelligence.company_name,
            "industry": research_data.company_intelligence.industry,
            "employee_count": research_data.company_intelligence.employee_count,
            "job_title": research_data.contact_profile.job_title,
            "buying_signals": sorted(research_data.buying_signals) if research_data.buying_signals else []
        }
        
        import hashlib
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, research_data: ResearchResultSchema) -> Optional[Dict[str, Any]]:
        """Get cached LLM scoring result if available and not expired."""
        cache_key = self._generate_cache_key(research_data)
        
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            cached_time = cached_data.get("timestamp")
            
            if cached_time and datetime.utcnow() - cached_time < self.cache_duration:
                logger.info(f"Using cached LLM scoring result for key: {cache_key[:8]}...")
                return cached_data.get("result")
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
        
        return None
    
    def set(self, research_data: ResearchResultSchema, result: Dict[str, Any]):
        """Cache LLM scoring result."""
        cache_key = self._generate_cache_key(research_data)
        
        self._cache[cache_key] = {
            "result": result,
            "timestamp": datetime.utcnow()
        }
        
        logger.info(f"Cached LLM scoring result for key: {cache_key[:8]}...")
    
    def clear_expired(self):
        """Clear expired cache entries."""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, data in self._cache.items():
            if current_time - data.get("timestamp", current_time) >= self.cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")


@dataclass
class LLMScoringResult:
    """Result from LLM-assisted scoring."""
    adjusted_score: int
    confidence: float
    rationale: str
    cost_cents: float
    tokens_used: int
    processing_time: float


class LLMAssistedScoring:
    """
    LLM-assisted scoring for gray zone prospects (45-55 score range).
    
    Uses a small, cost-effective LLM to provide nuanced scoring for ambiguous cases
    with strict budget controls and caching to minimize costs.
    """
    
    def __init__(self):
        self.cache = LLMScoringCache()
        self.daily_budget_cents = 500  # $5.00 daily budget
        self.daily_spend_cents = 0
        self.last_reset_date = datetime.utcnow().date()
        self.cost_per_1k_tokens = 0.02  # $0.02 per 1K tokens for mistral-nemo:free
        self.max_tokens = 64  # Strict token limit for cost control
        self.confidence_threshold = 0.7  # Minimum confidence for LLM results
        
        # Initialize OpenRouter client
        from ..services.openrouter_llm import OpenRouterLLMService
        self.llm_service = OpenRouterLLMService()
    
    def _reset_daily_budget_if_needed(self):
        """Reset daily budget if it's a new day."""
        current_date = datetime.utcnow().date()
        if current_date > self.last_reset_date:
            self.daily_spend_cents = 0
            self.last_reset_date = current_date
            logger.info("Reset daily LLM scoring budget")
    
    def _check_budget_available(self, estimated_cost_cents: float) -> bool:
        """Check if budget is available for LLM call."""
        self._reset_daily_budget_if_needed()
        return (self.daily_spend_cents + estimated_cost_cents) <= self.daily_budget_cents
    
    def _estimate_cost(self, prompt_length: int) -> float:
        """Estimate cost for LLM call based on prompt length."""
        # Estimate tokens (rough approximation: 4 chars per token)
        estimated_tokens = (prompt_length + self.max_tokens) / 4
        return (estimated_tokens / 1000) * self.cost_per_1k_tokens * 100  # Convert to cents
    
    async def score_gray_zone_prospect(self, 
                                     research_data: ResearchResultSchema,
                                     initial_score: int) -> Optional[LLMScoringResult]:
        """
        Use LLM to provide nuanced scoring for gray zone prospects.
        
        Args:
            research_data: Complete research data
            initial_score: Initial rules-based score (should be 45-55)
            
        Returns:
            LLMScoringResult with adjusted score and rationale, or None if budget exceeded
        """
        start_time = datetime.utcnow()
        
        try:
            # Check cache first
            cached_result = self.cache.get(research_data)
            if cached_result:
                return LLMScoringResult(
                    adjusted_score=cached_result["adjusted_score"],
                    confidence=cached_result["confidence"],
                    rationale=cached_result["rationale"],
                    cost_cents=0.0,  # No cost for cached results
                    tokens_used=0,
                    processing_time=0.1
                )
            
            # Create scoring prompt
            prompt = self._create_scoring_prompt(research_data, initial_score)
            
            # Check budget
            estimated_cost = self._estimate_cost(len(prompt))
            if not self._check_budget_available(estimated_cost):
                logger.warning(f"LLM scoring budget exceeded. Daily spend: ${self.daily_spend_cents/100:.2f}")
                return None
            
            # Call LLM with strict parameters
            llm_response = await self._call_llm_for_scoring(prompt)
            
            if not llm_response:
                return None
            
            # Parse and validate response
            scoring_result = self._parse_llm_response(llm_response, initial_score)
            
            if scoring_result and scoring_result.confidence >= self.confidence_threshold:
                # Update budget tracking
                self.daily_spend_cents += scoring_result.cost_cents
                
                # Cache the result
                cache_data = {
                    "adjusted_score": scoring_result.adjusted_score,
                    "confidence": scoring_result.confidence,
                    "rationale": scoring_result.rationale
                }
                self.cache.set(research_data, cache_data)
                
                logger.info(
                    f"LLM scoring completed: {initial_score} -> {scoring_result.adjusted_score} "
                    f"(confidence: {scoring_result.confidence:.2f}, cost: ${scoring_result.cost_cents/100:.3f})"
                )
                
                return scoring_result
            else:
                logger.warning("LLM scoring result below confidence threshold or invalid")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM-assisted scoring: {e}")
            return None
        finally:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
    
    def _create_scoring_prompt(self, research_data: ResearchResultSchema, initial_score: int) -> str:
        """Create a concise prompt for LLM scoring."""
        contact = research_data.contact_profile
        company = research_data.company_intelligence
        
        prompt = f"""Score this prospect (45-55 range needs refinement):

PROSPECT DATA:
- Title: {contact.job_title or 'Unknown'}
- Company: {company.company_name}
- Industry: {company.industry or 'Unknown'}
- Size: {company.employee_count or 'Unknown'} employees
- Revenue: {company.revenue_range or 'Unknown'}
- Location: {contact.location or 'Unknown'}
- Buying Signals: {', '.join(research_data.buying_signals) if research_data.buying_signals else 'None'}

INITIAL SCORE: {initial_score}/100

Provide JSON response (max 64 tokens):
{{"score": <40-60>, "confidence": <0.0-1.0>, "reason": "<brief explanation>"}}

Focus on decision-making authority, budget likelihood, and buying intent."""
        
        return prompt
    
    async def _call_llm_for_scoring(self, prompt: str) -> Optional[str]:
        """Call LLM service for scoring with strict parameters."""
        try:
            # Use the existing OpenRouter service with cost-effective model
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=0.1,  # Low temperature for consistent scoring
                model="mistralai/mistral-nemo:free"  # Cost-effective model
            )
            
            return response.response_text if response else None
            
        except Exception as e:
            logger.error(f"LLM service call failed: {e}")
            return None
    
    def _parse_llm_response(self, response: str, initial_score: int) -> Optional[LLMScoringResult]:
        """Parse and validate LLM response."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', response)
            if not json_match:
                logger.warning("No JSON found in LLM response")
                return None
            
            data = json.loads(json_match.group())
            
            # Validate required fields
            if not all(key in data for key in ["score", "confidence", "reason"]):
                logger.warning("Missing required fields in LLM response")
                return None
            
            adjusted_score = int(data["score"])
            confidence = float(data["confidence"])
            rationale = str(data["reason"])
            
            # Validate score range (should be close to initial score)
            if not (40 <= adjusted_score <= 60):
                logger.warning(f"LLM score {adjusted_score} outside valid range")
                return None
            
            # Validate confidence
            if not (0.0 <= confidence <= 1.0):
                logger.warning(f"LLM confidence {confidence} outside valid range")
                return None
            
            # Calculate actual cost (rough estimate)
            tokens_used = len(response.split()) + len(response) // 4  # Rough token estimate
            actual_cost_cents = (tokens_used / 1000) * self.cost_per_1k_tokens * 100
            
            return LLMScoringResult(
                adjusted_score=adjusted_score,
                confidence=confidence,
                rationale=rationale,
                cost_cents=actual_cost_cents,
                tokens_used=tokens_used,
                processing_time=0.0  # Will be set by caller
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return None
    
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        self._reset_daily_budget_if_needed()
        
        return {
            "daily_budget_cents": self.daily_budget_cents,
            "daily_spend_cents": self.daily_spend_cents,
            "remaining_budget_cents": self.daily_budget_cents - self.daily_spend_cents,
            "budget_utilization": self.daily_spend_cents / self.daily_budget_cents,
            "last_reset_date": self.last_reset_date.isoformat()
        }


class EnhancedScoringEngine(RulesBasedScoringEngine):
    """
    Enhanced scoring engine with LLM-assisted gray zone classification.
    
    Combines rules-based scoring with LLM assistance for ambiguous cases
    while maintaining strict cost controls.
    """
    
    def __init__(self):
        super().__init__()
        self.llm_scorer = LLMAssistedScoring()
    
    async def score_prospect(self, research_data: ResearchResultSchema) -> ScoringResult:
        """
        Score prospect with optional LLM assistance for gray zone cases.
        
        Args:
            research_data: Complete research result with contact and company data
            
        Returns:
            ScoringResult with potentially LLM-adjusted score and rationale
        """
        # Get initial rules-based score
        initial_result = await super().score_prospect(research_data)
        
        # Check if LLM review is needed and budget is available
        if initial_result.requires_llm_review:
            llm_result = await self.llm_scorer.score_gray_zone_prospect(
                research_data, initial_result.total_score
            )
            
            if llm_result:
                # Update result with LLM-adjusted score
                adjusted_result = ScoringResult(
                    total_score=llm_result.adjusted_score,
                    category_scores=initial_result.category_scores,
                    applied_rules=initial_result.applied_rules + [f"LLM Adjustment: {llm_result.rationale}"],
                    confidence_level=self._adjust_confidence_with_llm(
                        initial_result.confidence_level, llm_result.confidence
                    ),
                    value_tier=self._determine_value_tier(llm_result.adjusted_score),
                    scoring_rationale=self._build_enhanced_rationale(
                        initial_result, llm_result
                    ),
                    requires_llm_review=False,  # LLM review completed
                    timestamp=datetime.utcnow()
                )
                
                self.logger.info(
                    f"LLM-enhanced scoring: {initial_result.total_score} -> {llm_result.adjusted_score} "
                    f"for prospect {research_data.prospect_id}"
                )
                
                return adjusted_result
            else:
                # LLM scoring failed or budget exceeded, return original result
                self.logger.info(
                    f"LLM scoring unavailable, using rules-based score for prospect {research_data.prospect_id}"
                )
        
        return initial_result
    
    def _adjust_confidence_with_llm(self, 
                                  initial_confidence: ConfidenceLevel,
                                  llm_confidence: float) -> ConfidenceLevel:
        """Adjust confidence level based on LLM input."""
        # Combine initial confidence with LLM confidence
        confidence_values = {
            ConfidenceLevel.VERY_LOW: 0.2,
            ConfidenceLevel.LOW: 0.4,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.HIGH: 0.8
        }
        
        initial_value = confidence_values[initial_confidence]
        combined_confidence = (initial_value + llm_confidence) / 2
        
        if combined_confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif combined_confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif combined_confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _build_enhanced_rationale(self, 
                                initial_result: ScoringResult,
                                llm_result: LLMScoringResult) -> str:
        """Build enhanced rationale combining rules-based and LLM insights."""
        rationale = initial_result.scoring_rationale
        rationale += f"\n\nLLM Enhancement:\n"
        rationale += f"- Adjusted Score: {initial_result.total_score} → {llm_result.adjusted_score}\n"
        rationale += f"- LLM Confidence: {llm_result.confidence:.2f}\n"
        rationale += f"- LLM Rationale: {llm_result.rationale}\n"
        rationale += f"- Processing Cost: ${llm_result.cost_cents/100:.3f}"
        
        return rationale
    
    def get_llm_budget_status(self) -> Dict[str, Any]:
        """Get LLM budget status."""
        return self.llm_scorer.get_budget_status()


@dataclass
class TierRoutingRule:
    """Routing rule for different value tiers."""
    tier: ValueTier
    priority_weight: float
    max_staleness_hours: int
    workflow_config: Dict[str, Any]
    routing_destination: str


@dataclass
class ProspectQueueItem:
    """Item in the prospect priority queue."""
    prospect_id: str
    tier: ValueTier
    score: int
    confidence: ConfidenceLevel
    created_at: datetime
    last_updated: datetime
    priority_score: float
    routing_destination: str
    workflow_config: Dict[str, Any]


class ValueTierRouter:
    """
    Value tier assignment and routing system.
    
    Manages A/B/C tier assignment, priority queue management,
    and tier-based workflow customization with analytics tracking.
    """
    
    def __init__(self):
        self.routing_rules = self._initialize_routing_rules()
        self.prospect_queue: List[ProspectQueueItem] = []
        self.tier_analytics = {
            ValueTier.A_TIER: {"count": 0, "total_score": 0, "conversions": 0},
            ValueTier.B_TIER: {"count": 0, "total_score": 0, "conversions": 0},
            ValueTier.C_TIER: {"count": 0, "total_score": 0, "conversions": 0},
            ValueTier.UNQUALIFIED: {"count": 0, "total_score": 0, "conversions": 0}
        }
        self.tier_adjustments = {}  # For optimization tracking
    
    def _initialize_routing_rules(self) -> Dict[ValueTier, TierRoutingRule]:
        """Initialize routing rules for each value tier."""
        return {
            ValueTier.A_TIER: TierRoutingRule(
                tier=ValueTier.A_TIER,
                priority_weight=1.0,
                max_staleness_hours=2,  # High priority, process quickly
                workflow_config={
                    "immediate_notification": True,
                    "sales_rep_assignment": "senior",
                    "follow_up_cadence": "aggressive",
                    "personalization_level": "high",
                    "research_depth": "deep",
                    "approval_required": False
                },
                routing_destination="high_value_queue"
            ),
            
            ValueTier.B_TIER: TierRoutingRule(
                tier=ValueTier.B_TIER,
                priority_weight=0.7,
                max_staleness_hours=8,  # Medium priority
                workflow_config={
                    "immediate_notification": False,
                    "sales_rep_assignment": "standard",
                    "follow_up_cadence": "standard",
                    "personalization_level": "medium",
                    "research_depth": "standard",
                    "approval_required": False
                },
                routing_destination="standard_queue"
            ),
            
            ValueTier.C_TIER: TierRoutingRule(
                tier=ValueTier.C_TIER,
                priority_weight=0.4,
                max_staleness_hours=24,  # Lower priority
                workflow_config={
                    "immediate_notification": False,
                    "sales_rep_assignment": "junior",
                    "follow_up_cadence": "nurture",
                    "personalization_level": "low",
                    "research_depth": "basic",
                    "approval_required": False
                },
                routing_destination="nurture_queue"
            ),
            
            ValueTier.UNQUALIFIED: TierRoutingRule(
                tier=ValueTier.UNQUALIFIED,
                priority_weight=0.1,
                max_staleness_hours=72,  # Very low priority
                workflow_config={
                    "immediate_notification": False,
                    "sales_rep_assignment": "none",
                    "follow_up_cadence": "none",
                    "personalization_level": "none",
                    "research_depth": "none",
                    "approval_required": True  # Require approval before outreach
                },
                routing_destination="unqualified_queue"
            )
        }
    
    def assign_tier_and_route(self, 
                             prospect_id: str,
                             scoring_result: ScoringResult) -> ProspectQueueItem:
        """
        Assign value tier and create routing for a prospect.
        
        Args:
            prospect_id: Unique prospect identifier
            scoring_result: Complete scoring result
            
        Returns:
            ProspectQueueItem with tier assignment and routing
        """
        try:
            # Get routing rule for the tier
            routing_rule = self.routing_rules[scoring_result.value_tier]
            
            # Calculate priority score based on tier, score, and staleness
            priority_score = self._calculate_priority_score(
                scoring_result.value_tier,
                scoring_result.total_score,
                scoring_result.confidence_level,
                datetime.utcnow()
            )
            
            # Create queue item
            queue_item = ProspectQueueItem(
                prospect_id=prospect_id,
                tier=scoring_result.value_tier,
                score=scoring_result.total_score,
                confidence=scoring_result.confidence_level,
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                priority_score=priority_score,
                routing_destination=routing_rule.routing_destination,
                workflow_config=routing_rule.workflow_config.copy()
            )
            
            # Add to queue and update analytics
            self._add_to_queue(queue_item)
            self._update_tier_analytics(scoring_result.value_tier, scoring_result.total_score)
            
            logger.info(
                f"Assigned tier {scoring_result.value_tier.value} to prospect {prospect_id} "
                f"with priority {priority_score:.2f}, routing to {routing_rule.routing_destination}"
            )
            
            return queue_item
            
        except Exception as e:
            logger.error(f"Error in tier assignment and routing for {prospect_id}: {e}")
            raise
    
    def _calculate_priority_score(self,
                                tier: ValueTier,
                                score: int,
                                confidence: ConfidenceLevel,
                                created_at: datetime) -> float:
        """
        Calculate priority score for queue ordering.
        
        Combines tier weight, prospect score, confidence, and staleness.
        """
        # Base priority from tier
        routing_rule = self.routing_rules[tier]
        base_priority = routing_rule.priority_weight
        
        # Score factor (normalized to 0-1)
        score_factor = score / 100.0
        
        # Confidence factor
        confidence_factors = {
            ConfidenceLevel.HIGH: 1.0,
            ConfidenceLevel.MEDIUM: 0.8,
            ConfidenceLevel.LOW: 0.6,
            ConfidenceLevel.VERY_LOW: 0.4
        }
        confidence_factor = confidence_factors[confidence]
        
        # Staleness factor (increases priority for older items)
        hours_old = (datetime.utcnow() - created_at).total_seconds() / 3600
        max_staleness = routing_rule.max_staleness_hours
        staleness_factor = min(hours_old / max_staleness, 2.0)  # Cap at 2x
        
        # Combined priority score
        priority_score = (
            base_priority * 
            score_factor * 
            confidence_factor * 
            (1.0 + staleness_factor)
        )
        
        return round(priority_score, 3)
    
    def _add_to_queue(self, queue_item: ProspectQueueItem):
        """Add prospect to priority queue with proper ordering."""
        # Remove existing item if present (for updates)
        self.prospect_queue = [
            item for item in self.prospect_queue 
            if item.prospect_id != queue_item.prospect_id
        ]
        
        # Add new item
        self.prospect_queue.append(queue_item)
        
        # Sort by priority score (descending)
        self.prospect_queue.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Limit queue size to prevent memory issues
        max_queue_size = 10000
        if len(self.prospect_queue) > max_queue_size:
            self.prospect_queue = self.prospect_queue[:max_queue_size]
            logger.warning(f"Prospect queue truncated to {max_queue_size} items")
    
    def _update_tier_analytics(self, tier: ValueTier, score: int):
        """Update analytics for tier performance tracking."""
        if tier in self.tier_analytics:
            self.tier_analytics[tier]["count"] += 1
            self.tier_analytics[tier]["total_score"] += score
    
    def get_next_prospects(self, 
                          tier_filter: Optional[ValueTier] = None,
                          limit: int = 10) -> List[ProspectQueueItem]:
        """
        Get next prospects from priority queue for processing.
        
        Args:
            tier_filter: Optional filter by specific tier
            limit: Maximum number of prospects to return
            
        Returns:
            List of ProspectQueueItem ordered by priority
        """
        # Update priority scores for staleness
        self._update_queue_priorities()
        
        # Filter by tier if specified
        if tier_filter:
            filtered_queue = [
                item for item in self.prospect_queue 
                if item.tier == tier_filter
            ]
        else:
            filtered_queue = self.prospect_queue
        
        # Return top prospects up to limit
        return filtered_queue[:limit]
    
    def _update_queue_priorities(self):
        """Update priority scores for all items in queue based on staleness."""
        current_time = datetime.utcnow()
        
        for item in self.prospect_queue:
            # Recalculate priority with current staleness
            item.priority_score = self._calculate_priority_score(
                item.tier,
                item.score,
                item.confidence,
                item.created_at
            )
            item.last_updated = current_time
        
        # Re-sort queue
        self.prospect_queue.sort(key=lambda x: x.priority_score, reverse=True)
    
    def update_tier_assignment(self, 
                             prospect_id: str,
                             scoring_result: ScoringResult) -> Optional[ProspectQueueItem]:
        """
        Update tier assignment for existing prospect.
        
        Args:
            prospect_id: Prospect to update
            scoring_result: New scoring result
            
        Returns:
            Updated ProspectQueueItem or None if not found
        """
        # Find existing item
        existing_item = None
        for item in self.prospect_queue:
            if item.prospect_id == prospect_id:
                existing_item = item
                break
        
        if not existing_item:
            logger.warning(f"Prospect {prospect_id} not found in queue for tier update")
            return None
        
        # Check if tier changed
        old_tier = existing_item.tier
        new_tier = scoring_result.value_tier
        
        if old_tier != new_tier:
            logger.info(
                f"Tier change for {prospect_id}: {old_tier.value} -> {new_tier.value}"
            )
            
            # Track tier adjustment
            adjustment_key = f"{old_tier.value}_to_{new_tier.value}"
            self.tier_adjustments[adjustment_key] = self.tier_adjustments.get(adjustment_key, 0) + 1
        
        # Create updated queue item
        updated_item = self.assign_tier_and_route(prospect_id, scoring_result)
        
        return updated_item
    
    def remove_prospect_from_queue(self, prospect_id: str) -> bool:
        """
        Remove prospect from queue (e.g., after processing).
        
        Args:
            prospect_id: Prospect to remove
            
        Returns:
            True if removed, False if not found
        """
        initial_length = len(self.prospect_queue)
        self.prospect_queue = [
            item for item in self.prospect_queue 
            if item.prospect_id != prospect_id
        ]
        
        removed = len(self.prospect_queue) < initial_length
        if removed:
            logger.info(f"Removed prospect {prospect_id} from queue")
        
        return removed
    
    def get_tier_analytics(self) -> Dict[str, Any]:
        """Get comprehensive tier analytics and performance metrics."""
        # Calculate tier performance metrics
        tier_performance = {}
        
        for tier, analytics in self.tier_analytics.items():
            count = analytics["count"]
            total_score = analytics["total_score"]
            conversions = analytics["conversions"]
            
            tier_performance[tier.value] = {
                "total_prospects": count,
                "average_score": round(total_score / count, 1) if count > 0 else 0,
                "conversion_rate": round(conversions / count, 3) if count > 0 else 0,
                "conversion_count": conversions
            }
        
        # Queue health metrics
        queue_health = self._calculate_queue_health()
        
        # Tier adjustment tracking
        tier_adjustments = dict(self.tier_adjustments)
        
        return {
            "tier_performance": tier_performance,
            "queue_health": queue_health,
            "tier_adjustments": tier_adjustments,
            "total_queue_size": len(self.prospect_queue)
        }
    
    def _calculate_queue_health(self) -> Dict[str, Any]:
        """Calculate queue health metrics."""
        if not self.prospect_queue:
            return {
                "status": "empty",
                "staleness_distribution": {},
                "tier_distribution": {},
                "priority_distribution": {}
            }
        
        current_time = datetime.utcnow()
        
        # Staleness distribution
        staleness_buckets = {"fresh": 0, "aging": 0, "stale": 0}
        tier_distribution = {tier.value: 0 for tier in ValueTier}
        priority_scores = []
        
        for item in self.prospect_queue:
            hours_old = (current_time - item.created_at).total_seconds() / 3600
            
            # Staleness categorization
            if hours_old < 2:
                staleness_buckets["fresh"] += 1
            elif hours_old < 24:
                staleness_buckets["aging"] += 1
            else:
                staleness_buckets["stale"] += 1
            
            # Tier distribution
            tier_distribution[item.tier.value] += 1
            
            # Priority scores
            priority_scores.append(item.priority_score)
        
        # Priority distribution
        priority_distribution = {
            "min": min(priority_scores),
            "max": max(priority_scores),
            "avg": sum(priority_scores) / len(priority_scores),
            "median": sorted(priority_scores)[len(priority_scores) // 2]
        }
        
        # Overall health status
        stale_percentage = staleness_buckets["stale"] / len(self.prospect_queue)
        if stale_percentage > 0.3:
            status = "unhealthy"
        elif stale_percentage > 0.1:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "staleness_distribution": staleness_buckets,
            "tier_distribution": tier_distribution,
            "priority_distribution": priority_distribution
        }
    
    def optimize_tier_thresholds(self) -> Dict[str, Any]:
        """
        Analyze tier performance and suggest threshold optimizations.
        
        Returns:
            Dictionary with optimization recommendations
        """
        analytics = self.get_tier_analytics()
        tier_performance = analytics["tier_performance"]
        
        recommendations = []
        
        # Analyze conversion rates by tier
        for tier_name, performance in tier_performance.items():
            conversion_rate = performance["conversion_rate"]
            total_prospects = performance["total_prospects"]
            
            if total_prospects < 10:
                continue  # Not enough data
            
            # Tier-specific recommendations
            if tier_name == "A" and conversion_rate < 0.3:
                recommendations.append({
                    "tier": tier_name,
                    "issue": "Low A-tier conversion rate",
                    "current_rate": conversion_rate,
                    "recommendation": "Consider raising A-tier threshold from 80 to 85",
                    "impact": "Reduce false positives in high-value tier"
                })
            
            elif tier_name == "B" and conversion_rate < 0.15:
                recommendations.append({
                    "tier": tier_name,
                    "issue": "Low B-tier conversion rate",
                    "current_rate": conversion_rate,
                    "recommendation": "Consider raising B-tier threshold from 60 to 65",
                    "impact": "Improve medium-value tier quality"
                })
            
            elif tier_name == "C" and conversion_rate > 0.2:
                recommendations.append({
                    "tier": tier_name,
                    "issue": "High C-tier conversion rate",
                    "current_rate": conversion_rate,
                    "recommendation": "Consider lowering C-tier threshold from 40 to 35",
                    "impact": "Capture more prospects in nurture tier"
                })
        
        # Analyze tier adjustments
        adjustment_patterns = []
        for adjustment, count in self.tier_adjustments.items():
            if count > 5:  # Significant pattern
                adjustment_patterns.append({
                    "pattern": adjustment,
                    "frequency": count,
                    "recommendation": f"Review scoring rules causing {adjustment} transitions"
                })
        
        return {
            "threshold_recommendations": recommendations,
            "adjustment_patterns": adjustment_patterns,
            "optimization_priority": "high" if len(recommendations) > 2 else "medium",
            "data_confidence": "high" if sum(p["total_prospects"] for p in tier_performance.values()) > 100 else "low"
        }
    
    def record_conversion(self, prospect_id: str, conversion_type: str = "meeting_booked"):
        """
        Record a conversion for analytics tracking.
        
        Args:
            prospect_id: Prospect who converted
            conversion_type: Type of conversion (meeting_booked, deal_closed, etc.)
        """
        # Find prospect in queue to get tier
        prospect_tier = None
        for item in self.prospect_queue:
            if item.prospect_id == prospect_id:
                prospect_tier = item.tier
                break
        
        if prospect_tier and prospect_tier in self.tier_analytics:
            self.tier_analytics[prospect_tier]["conversions"] += 1
            logger.info(f"Recorded {conversion_type} conversion for {prospect_id} in tier {prospect_tier.value}")
        else:
            logger.warning(f"Could not find tier for prospect {prospect_id} to record conversion")
    
    def get_workflow_config_for_tier(self, tier: ValueTier) -> Dict[str, Any]:
        """Get workflow configuration for a specific tier."""
        routing_rule = self.routing_rules.get(tier)
        return routing_rule.workflow_config.copy() if routing_rule else {}
    
    def get_routing_destination_for_tier(self, tier: ValueTier) -> str:
        """Get routing destination for a specific tier."""
        routing_rule = self.routing_rules.get(tier)
        return routing_rule.routing_destination if routing_rule else "default_queue"



class CompleteScoringSystem(EnhancedScoringEngine):
    """
    Complete scoring system with tier assignment and routing.
    
    Combines rules-based scoring, LLM assistance, and value tier routing
    into a comprehensive prospect qualification system.
    """
    
    def __init__(self):
        super().__init__()
        self.tier_router = ValueTierRouter()
    
    async def score_and_route_prospect(self, 
                                     prospect_id: str,
                                     research_data: ResearchResultSchema) -> Tuple[ScoringResult, ProspectQueueItem]:
        """
        Complete prospect scoring and routing workflow.
        
        Args:
            prospect_id: Unique prospect identifier
            research_data: Complete research data
            
        Returns:
            Tuple of (ScoringResult, ProspectQueueItem)
        """
        try:
            # Score the prospect
            scoring_result = await self.score_prospect(research_data)
            
            # Assign tier and route
            queue_item = self.tier_router.assign_tier_and_route(prospect_id, scoring_result)
            
            logger.info(
                f"Complete scoring and routing for {prospect_id}: "
                f"Score={scoring_result.total_score}, Tier={scoring_result.value_tier.value}, "
                f"Priority={queue_item.priority_score}, Destination={queue_item.routing_destination}"
            )
            
            return scoring_result, queue_item
            
        except Exception as e:
            logger.error(f"Error in complete scoring and routing for {prospect_id}: {e}")
            raise
    
    def get_next_prospects_for_processing(self, 
                                        tier_filter: Optional[ValueTier] = None,
                                        limit: int = 10) -> List[ProspectQueueItem]:
        """Get next prospects from the priority queue for processing."""
        return self.tier_router.get_next_prospects(tier_filter, limit)
    
    def update_prospect_tier(self,
                           prospect_id: str,
                           research_data: ResearchResultSchema) -> Optional[ProspectQueueItem]:
        """Update prospect tier based on new research data."""
        # Re-score the prospect
        scoring_result = asyncio.run(self.score_prospect(research_data))
        
        # Update tier assignment
        return self.tier_router.update_tier_assignment(prospect_id, scoring_result)
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get comprehensive system analytics."""
        tier_analytics = self.tier_router.get_tier_analytics()
        llm_budget_status = self.get_llm_budget_status()
        
        return {
            "tier_analytics": tier_analytics,
            "llm_budget_status": llm_budget_status,
            "system_health": {
                "queue_health": tier_analytics["queue_health"],
                "llm_budget_utilization": llm_budget_status["budget_utilization"],
                "total_prospects_processed": sum(
                    data["total_prospects"] 
                    for data in tier_analytics["tier_performance"].values()
                )
            }
        }
    
    def optimize_system_performance(self) -> Dict[str, Any]:
        """Get system optimization recommendations."""
        return self.tier_router.optimize_tier_thresholds()


# Factory function
def create_scoring_engine(use_llm_enhancement: bool = True) -> Union[RulesBasedScoringEngine, EnhancedScoringEngine]:
    """Create and validate a scoring engine."""
    if use_llm_enhancement:
        engine = EnhancedScoringEngine()
    else:
        engine = RulesBasedScoringEngine()
    
    # Validate the engine
    validator = ScoringValidator()
    issues = validator.validate_scoring_rules(engine)
    
    if issues:
        logger.warning(f"Scoring engine validation issues: {issues}")
    
    return engine


def create_complete_scoring_system() -> CompleteScoringSystem:
    """Create a complete scoring system with tier assignment and routing."""
    system = CompleteScoringSystem()
    
    # Validate the system
    validator = ScoringValidator()
    issues = validator.validate_scoring_rules(system)
    
    if issues:
        logger.warning(f"Complete scoring system validation issues: {issues}")
    
    return system