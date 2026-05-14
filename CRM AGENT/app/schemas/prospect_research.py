"""
Pydantic schemas for prospect research data validation and serialization.

This module defines the data structures used for prospect research,
company intelligence, and research result validation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator, HttpUrl, EmailStr
from pydantic.types import constr


class DataSource(str, Enum):
    """Enumeration of data sources for research."""
    LINKEDIN = "linkedin"
    COMPANY_WEBSITE = "company_website"
    CLEARBIT = "clearbit"
    APOLLO = "apollo"
    ZOOMINFO = "zoominfo"
    BUILTWITH = "builtwith"
    WEB_SCRAPING = "web_scraping"
    SOCIAL_MEDIA = "social_media"
    NEWS_ARTICLES = "news_articles"
    JOB_POSTINGS = "job_postings"
    MANUAL_RESEARCH = "manual_research"


class ConfidenceLevel(str, Enum):
    """Confidence levels for research data."""
    HIGH = "high"      # 0.8 - 1.0
    MEDIUM = "medium"  # 0.6 - 0.8
    LOW = "low"        # 0.4 - 0.6
    VERY_LOW = "very_low"  # 0.0 - 0.4


class CompanySize(str, Enum):
    """Company size categories."""
    STARTUP = "startup"          # 1-10 employees
    SMALL = "small"              # 11-50 employees
    MEDIUM = "medium"            # 51-200 employees
    LARGE = "large"              # 201-1000 employees
    ENTERPRISE = "enterprise"    # 1000+ employees


class RevenueRange(str, Enum):
    """Revenue range categories."""
    UNDER_1M = "under_1m"        # < $1M
    RANGE_1M_10M = "1m_10m"      # $1M - $10M
    RANGE_10M_50M = "10m_50m"    # $10M - $50M
    RANGE_50M_100M = "50m_100m"  # $50M - $100M
    RANGE_100M_500M = "100m_500m"  # $100M - $500M
    OVER_500M = "over_500m"      # > $500M


class BuyingSignal(BaseModel):
    """Individual buying signal data."""
    
    signal_type: str = Field(..., description="Type of buying signal")
    description: str = Field(..., description="Description of the signal")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: DataSource = Field(..., description="Source of the signal")
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('signal_type')
    def validate_signal_type(cls, v):
        """Validate signal type."""
        valid_types = [
            "budget_mentioned", "timeline_mentioned", "pain_point_expressed",
            "competitor_mentioned", "expansion_plans", "hiring_activity",
            "technology_adoption", "funding_raised", "leadership_change"
        ]
        if v not in valid_types:
            raise ValueError(f"Invalid signal type: {v}")
        return v


class ContactEducation(BaseModel):
    """Contact education information."""
    
    institution: str = Field(..., description="Educational institution")
    degree: Optional[str] = Field(None, description="Degree obtained")
    field_of_study: Optional[str] = Field(None, description="Field of study")
    start_year: Optional[int] = Field(None, ge=1950, le=2030)
    end_year: Optional[int] = Field(None, ge=1950, le=2030)
    
    @validator('end_year')
    def validate_end_year(cls, v, values):
        """Validate end year is after start year."""
        if v and values.get('start_year') and v < values['start_year']:
            raise ValueError("End year must be after start year")
        return v


class ContactExperience(BaseModel):
    """Contact work experience information."""
    
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    description: Optional[str] = Field(None, description="Role description")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    is_current: bool = Field(False, description="Is current position")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Validate end date is after start date."""
        if v and values.get('start_date') and v < values['start_date']:
            raise ValueError("End date must be after start date")
        return v


class ContactProfileSchema(BaseModel):
    """Contact profile data schema with validation."""
    
    # Basic information
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]+$')
    
    # Professional information
    job_title: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=100)
    linkedin_url: Optional[HttpUrl] = None
    location: Optional[str] = Field(None, max_length=100)
    
    # Experience and skills
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    education: List[ContactEducation] = Field(default_factory=list)
    experience: List[ContactExperience] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    
    # Social proof
    linkedin_connections: Optional[int] = Field(None, ge=0)
    profile_summary: Optional[str] = Field(None, max_length=1000)
    
    # Metadata
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    data_sources: List[DataSource] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('skills')
    def validate_skills_limit(cls, v):
        """Limit number of skills."""
        if len(v) > 20:
            raise ValueError("Maximum 20 skills allowed")
        return v
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level based on score."""
        if self.confidence_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif self.confidence_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif self.confidence_score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


class TechnologyStack(BaseModel):
    """Technology stack information."""
    
    category: str = Field(..., description="Technology category")
    technology: str = Field(..., description="Technology name")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: DataSource = Field(..., description="Detection source")
    
    @validator('category')
    def validate_category(cls, v):
        """Validate technology category."""
        valid_categories = [
            "web_framework", "database", "analytics", "marketing",
            "crm", "payment", "hosting", "cdn", "security", "other"
        ]
        if v not in valid_categories:
            raise ValueError(f"Invalid technology category: {v}")
        return v


class FundingRound(BaseModel):
    """Company funding round information."""
    
    round_type: str = Field(..., description="Type of funding round")
    amount: Optional[int] = Field(None, description="Funding amount in USD")
    date: Optional[datetime] = Field(None, description="Funding date")
    investors: List[str] = Field(default_factory=list)
    source: DataSource = Field(..., description="Information source")


class KeyPersonnel(BaseModel):
    """Key personnel information."""
    
    name: str = Field(..., description="Person's name")
    title: str = Field(..., description="Job title")
    linkedin_url: Optional[HttpUrl] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    start_date: Optional[datetime] = None


class NewsArticle(BaseModel):
    """News article information."""
    
    title: str = Field(..., description="Article title")
    url: HttpUrl = Field(..., description="Article URL")
    published_date: Optional[datetime] = None
    source: str = Field(..., description="News source")
    summary: Optional[str] = Field(None, max_length=500)
    sentiment: Optional[str] = Field(None, pattern=r'^(positive|negative|neutral)$')


class CompanyIntelligenceSchema(BaseModel):
    """Company intelligence data schema with validation."""
    
    # Basic information
    company_name: str = Field(..., min_length=1, max_length=100, description="Company name")
    domain: Optional[str] = Field(None, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$')
    website_url: Optional[HttpUrl] = None
    
    # Company details
    industry: Optional[str] = Field(None, max_length=100)
    employee_count: Optional[int] = Field(None, ge=1)
    company_size: Optional[CompanySize] = None
    revenue_range: Optional[RevenueRange] = None
    founded_year: Optional[int] = Field(None, ge=1800, le=2030)
    headquarters: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    
    # Technology and operations
    technology_stack: List[TechnologyStack] = Field(default_factory=list)
    
    # Social media presence
    social_media: Dict[str, HttpUrl] = Field(default_factory=dict)
    
    # Financial information
    funding_info: List[FundingRound] = Field(default_factory=list)
    total_funding: Optional[int] = Field(None, ge=0, description="Total funding in USD")
    
    # Personnel
    key_personnel: List[KeyPersonnel] = Field(default_factory=list)
    
    # News and updates
    recent_news: List[NewsArticle] = Field(default_factory=list)
    
    # Metadata
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    data_sources: List[DataSource] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('social_media')
    def validate_social_media(cls, v):
        """Validate social media platforms."""
        valid_platforms = [
            'linkedin', 'twitter', 'facebook', 'instagram', 
            'youtube', 'github', 'crunchbase'
        ]
        for platform in v.keys():
            if platform not in valid_platforms:
                raise ValueError(f"Invalid social media platform: {platform}")
        return v
    
    @validator('employee_count')
    def set_company_size(cls, v, values):
        """Automatically set company size based on employee count."""
        if v:
            if v <= 10:
                values['company_size'] = CompanySize.STARTUP
            elif v <= 50:
                values['company_size'] = CompanySize.SMALL
            elif v <= 200:
                values['company_size'] = CompanySize.MEDIUM
            elif v <= 1000:
                values['company_size'] = CompanySize.LARGE
            else:
                values['company_size'] = CompanySize.ENTERPRISE
        return v
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level based on score."""
        if self.confidence_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif self.confidence_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif self.confidence_score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


class ResearchResultSchema(BaseModel):
    """Complete research result schema with validation."""
    
    # Identifiers
    prospect_id: str = Field(..., min_length=1, description="Unique prospect identifier")
    research_id: str = Field(default_factory=lambda: f"research_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
    
    # Research data
    contact_profile: ContactProfileSchema = Field(..., description="Contact profile data")
    company_intelligence: CompanyIntelligenceSchema = Field(..., description="Company intelligence data")
    
    # Analysis results
    buying_signals: List[BuyingSignal] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    decision_maker_score: float = Field(0.0, ge=0.0, le=1.0, description="Decision maker likelihood")
    
    # Quality metrics
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall research confidence")
    research_duration: float = Field(0.0, ge=0.0, description="Research duration in seconds")
    sources_used: List[DataSource] = Field(default_factory=list)
    
    # Timestamps
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Compliance and audit
    compliance_flags: List[str] = Field(default_factory=list)
    data_retention_date: Optional[datetime] = None
    
    @validator('buying_signals')
    def validate_buying_signals_limit(cls, v):
        """Limit number of buying signals."""
        if len(v) > 10:
            raise ValueError("Maximum 10 buying signals allowed")
        return v
    
    @validator('pain_points')
    def validate_pain_points_limit(cls, v):
        """Limit number of pain points."""
        if len(v) > 10:
            raise ValueError("Maximum 10 pain points allowed")
        return v
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get overall confidence level."""
        if self.overall_confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif self.overall_confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif self.overall_confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    @property
    def is_high_quality(self) -> bool:
        """Check if research meets high quality standards."""
        return (
            self.overall_confidence >= 0.7 and
            len(self.sources_used) >= 2 and
            self.contact_profile.confidence_score >= 0.6 and
            self.company_intelligence.confidence_score >= 0.6
        )


class ResearchRequest(BaseModel):
    """Request schema for prospect research."""
    
    prospect_id: str = Field(..., min_length=1, description="Unique prospect identifier")
    phone_number: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]+$')
    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(None, min_length=1, max_length=100)
    linkedin_url: Optional[HttpUrl] = None
    
    # Research parameters
    research_depth: str = Field("standard", pattern=r'^(basic|standard|deep)$')
    max_duration: int = Field(300, ge=60, le=600, description="Max research time in seconds")
    required_sources: List[DataSource] = Field(default_factory=list)
    
    # Compliance settings
    respect_robots_txt: bool = Field(True, description="Respect robots.txt for web scraping")
    gdpr_compliant: bool = Field(True, description="Ensure GDPR compliance")
    
    @validator('required_sources')
    def validate_required_sources(cls, v):
        """Validate required sources."""
        if len(v) > 5:
            raise ValueError("Maximum 5 required sources allowed")
        return v


class ResearchStatus(BaseModel):
    """Research status response schema."""
    
    prospect_id: str = Field(..., description="Prospect identifier")
    status: str = Field(..., pattern=r'^(pending|in_progress|completed|failed|cancelled)$')
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress percentage")
    current_source: Optional[DataSource] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Results preview
    preliminary_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    sources_completed: List[DataSource] = Field(default_factory=list)
    
    class Config:
        schema_extra = {
            "example": {
                "prospect_id": "prospect_123",
                "status": "in_progress",
                "progress": 0.6,
                "current_source": "linkedin",
                "estimated_completion": "2024-01-15T10:30:00Z",
                "preliminary_confidence": 0.75,
                "sources_completed": ["company_website", "clearbit"]
            }
        }