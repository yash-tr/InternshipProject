"""
Prospect Research Agent for autonomous data enrichment and intelligence gathering.

This agent handles LinkedIn API integration, web scraping, company intelligence
gathering, and data enrichment with confidence scoring for lead qualification.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import re
from urllib.parse import urlparse, urljoin
import random

import httpx
import aiohttp
from pydantic import BaseModel, Field, validator
from bs4 import BeautifulSoup

from .base import BaseAgent, AgentConfig, AgentResult, AgentStatus, AgentType, AgentState
from ..utils.encryption import encrypt_pii_data, decrypt_pii_data

logger = logging.getLogger(__name__)


class ProspectResearchConfig(BaseModel):
    """Configuration for prospect research operations."""
    
    # LinkedIn API settings
    linkedin_api_key: Optional[str] = None
    linkedin_api_secret: Optional[str] = None
    linkedin_access_token: Optional[str] = None
    
    # Web scraping settings
    max_concurrent_requests: int = 5
    request_timeout: int = 30
    retry_attempts: int = 3
    proxy_rotation: bool = True
    
    # Company intelligence settings
    company_db_apis: List[str] = Field(default_factory=lambda: [
        "clearbit", "apollo", "zoominfo", "builtwith"
    ])
    
    # Data enrichment settings
    min_confidence_score: float = 0.6
    max_research_time: int = 300  # seconds
    parallel_source_limit: int = 3


class CompanyIntelligence(BaseModel):
    """Company intelligence data structure."""
    
    company_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_range: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters: Optional[str] = None
    description: Optional[str] = None
    technology_stack: List[str] = Field(default_factory=list)
    social_media: Dict[str, str] = Field(default_factory=dict)
    funding_info: Dict[str, Any] = Field(default_factory=dict)
    key_personnel: List[Dict[str, str]] = Field(default_factory=list)
    recent_news: List[Dict[str, str]] = Field(default_factory=list)
    confidence_score: float = 0.0
    data_sources: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ContactProfile(BaseModel):
    """Contact profile data structure."""
    
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    experience_years: Optional[int] = None
    education: List[Dict[str, str]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    connections: Optional[int] = None
    profile_summary: Optional[str] = None
    confidence_score: float = 0.0
    data_sources: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ResearchResult(BaseModel):
    """Complete research result for a prospect."""
    
    prospect_id: str
    contact_profile: ContactProfile
    company_intelligence: CompanyIntelligence
    buying_signals: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    decision_maker_score: float = 0.0
    overall_confidence: float = 0.0
    research_duration: float = 0.0
    sources_used: List[str] = Field(default_factory=list)
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)
    compliance_flags: List[str] = Field(default_factory=list)


class ProspectResearchAgent(BaseAgent):
    """
    Agent responsible for autonomous prospect research and data enrichment.
    
    Handles LinkedIn API integration, web scraping, company intelligence
    gathering, and parallel data source processing with confidence scoring.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if not config:
            config = AgentConfig(
                agent_type=AgentType.RESEARCH,
                timeout_seconds=300,
                retry_attempts=3,
                parallel_execution=True
            )
        
        super().__init__(config)
        self.research_config = ProspectResearchConfig()
        
        # Initialize HTTP clients
        self.http_client = None
        self.session_pool = []
        
        # Proxy rotation setup
        self.proxy_list = self._load_proxy_list()
        self.current_proxy_index = 0
        
        # Rate limiting
        self.request_semaphore = asyncio.Semaphore(
            self.research_config.max_concurrent_requests
        )
        self.last_request_times = {}
    
    async def execute(self, state: AgentState) -> AgentResult:
        """
        Execute prospect research for the given state.
        
        Args:
            state: Current workflow state
            
        Returns:
            AgentResult with research data and confidence scores
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate input
            if not await self.validate_input(state):
                return AgentResult(
                    agent_type=self.config.agent_type,
                    status=AgentStatus.FAILED,
                    errors=["Invalid input state for research agent"]
                )
            
            # Extract prospect information
            prospect_id = state.get("prospect_id")
            phone_number = state.get("phone_number")
            salesforce_lead_id = state.get("salesforce_lead_id")
            
            self.logger.info(f"Starting research for prospect {prospect_id}")
            
            # Initialize HTTP client
            await self._initialize_http_client()
            
            # Perform parallel research
            research_tasks = [
                self._research_linkedin_profile(phone_number, prospect_id),
                self._research_company_intelligence(state),
                self._scrape_web_data(state),
                self._gather_social_signals(state)
            ]
            
            # Execute research tasks with timeout
            research_results = await asyncio.wait_for(
                asyncio.gather(*research_tasks, return_exceptions=True),
                timeout=self.research_config.max_research_time
            )
            
            # Process research results
            contact_profile, company_intel, web_data, social_signals = research_results
            
            # Handle exceptions in results
            if isinstance(contact_profile, Exception):
                self.logger.warning(f"LinkedIn research failed: {contact_profile}")
                contact_profile = ContactProfile()
            
            if isinstance(company_intel, Exception):
                self.logger.warning(f"Company intelligence failed: {company_intel}")
                company_intel = CompanyIntelligence(company_name="Unknown")
            
            if isinstance(web_data, Exception):
                self.logger.warning(f"Web scraping failed: {web_data}")
                web_data = {}
            
            if isinstance(social_signals, Exception):
                self.logger.warning(f"Social signals failed: {social_signals}")
                social_signals = {}
            
            # Combine and validate research data
            research_result = await self._combine_research_data(
                prospect_id,
                contact_profile,
                company_intel,
                web_data,
                social_signals
            )
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            research_result.research_duration = execution_time
            
            # Encrypt sensitive data
            encrypted_research = await self._encrypt_research_data(research_result)
            
            # Update state
            state_updates = {
                "research_data": encrypted_research.dict(),
                "research_confidence": research_result.overall_confidence,
                "research_sources": research_result.sources_used,
                "status": AgentStatus.COMPLETED
            }
            
            self.logger.info(
                f"Research completed for prospect {prospect_id} "
                f"with confidence {research_result.overall_confidence:.2f}"
            )
            
            return AgentResult(
                agent_type=self.config.agent_type,
                status=AgentStatus.COMPLETED,
                data=state_updates,
                execution_time=execution_time,
                metadata={
                    "sources_used": len(research_result.sources_used),
                    "confidence_score": research_result.overall_confidence,
                    "compliance_flags": research_result.compliance_flags
                }
            )
            
        except asyncio.TimeoutError:
            return await self.handle_error(
                Exception("Research timeout exceeded"),
                state
            )
        except Exception as e:
            return await self.handle_error(e, state)
        finally:
            await self._cleanup_http_client()
    
    async def validate_input(self, state: AgentState) -> bool:
        """Validate that required inputs are present."""
        required_fields = ["prospect_id"]
        
        for field in required_fields:
            if not state.get(field):
                self.logger.error(f"Missing required field: {field}")
                return False
        
        # At least one identifier should be present
        identifiers = [
            state.get("phone_number"),
            state.get("salesforce_lead_id"),
            state.get("research_data", {}).get("company_name")
        ]
        
        if not any(identifiers):
            self.logger.error("No valid identifiers found for research")
            return False
        
        return True
    
    async def _initialize_http_client(self):
        """Initialize HTTP client with proper configuration."""
        timeout = httpx.Timeout(self.research_config.request_timeout)
        
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self._get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
    
    async def _cleanup_http_client(self):
        """Clean up HTTP client resources."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    async def _research_linkedin_profile(self, phone_number: str, prospect_id: str) -> ContactProfile:
        """
        Research LinkedIn profile information.
        
        Note: This is a placeholder implementation. In production, you would
        integrate with LinkedIn Sales Navigator API or similar service.
        """
        self.logger.info(f"Researching LinkedIn profile for {prospect_id}")
        
        # Simulate LinkedIn API research
        await asyncio.sleep(random.uniform(1, 3))  # Simulate API delay
        
        # In a real implementation, this would:
        # 1. Use LinkedIn Sales Navigator API
        # 2. Search by phone number or email
        # 3. Extract profile information
        # 4. Validate data quality
        
        profile = ContactProfile(
            confidence_score=0.7,
            data_sources=["linkedin_simulation"],
            last_updated=datetime.utcnow()
        )
        
        return profile
    
    async def _research_company_intelligence(self, state: AgentState) -> CompanyIntelligence:
        """
        Gather company intelligence from multiple sources.
        
        This method would integrate with services like:
        - Clearbit Company API
        - Apollo.io
        - ZoomInfo
        - BuiltWith
        """
        self.logger.info("Gathering company intelligence")
        
        company_name = state.get("research_data", {}).get("company_name", "Unknown")
        
        # Simulate company intelligence gathering
        await asyncio.sleep(random.uniform(2, 4))
        
        # In a real implementation, this would:
        # 1. Query multiple company intelligence APIs
        # 2. Scrape company websites
        # 3. Analyze technology stack
        # 4. Gather funding information
        # 5. Extract key personnel data
        
        intelligence = CompanyIntelligence(
            company_name=company_name,
            confidence_score=0.8,
            data_sources=["company_intelligence_simulation"],
            last_updated=datetime.utcnow()
        )
        
        return intelligence
    
    async def _scrape_web_data(self, state: AgentState) -> Dict[str, Any]:
        """
        Scrape web data for additional prospect information.
        
        This includes company websites, news articles, and social media.
        """
        self.logger.info("Scraping web data")
        
        # Simulate web scraping
        await asyncio.sleep(random.uniform(1, 2))
        
        # In a real implementation, this would:
        # 1. Scrape company website
        # 2. Search for recent news articles
        # 3. Analyze social media presence
        # 4. Extract contact information
        # 5. Identify buying signals
        
        web_data = {
            "website_content": {},
            "news_articles": [],
            "social_media": {},
            "contact_info": {},
            "confidence_score": 0.6,
            "sources": ["web_scraping_simulation"]
        }
        
        return web_data
    
    async def _gather_social_signals(self, state: AgentState) -> Dict[str, Any]:
        """
        Gather social signals and buying intent data.
        
        This includes social media activity, job postings, and other signals.
        """
        self.logger.info("Gathering social signals")
        
        # Simulate social signals gathering
        await asyncio.sleep(random.uniform(1, 2))
        
        # In a real implementation, this would:
        # 1. Monitor social media activity
        # 2. Track job postings
        # 3. Analyze company growth signals
        # 4. Identify technology adoption patterns
        # 5. Extract buying intent signals
        
        social_signals = {
            "social_activity": [],
            "job_postings": [],
            "growth_signals": [],
            "buying_intent": [],
            "confidence_score": 0.5,
            "sources": ["social_signals_simulation"]
        }
        
        return social_signals
    
    async def _combine_research_data(self,
                                   prospect_id: str,
                                   contact_profile: ContactProfile,
                                   company_intel: CompanyIntelligence,
                                   web_data: Dict[str, Any],
                                   social_signals: Dict[str, Any]) -> ResearchResult:
        """
        Combine research data from all sources and calculate confidence scores.
        """
        # Extract buying signals
        buying_signals = []
        buying_signals.extend(social_signals.get("buying_intent", []))
        
        # Extract pain points
        pain_points = []
        
        # Calculate decision maker score
        decision_maker_score = self._calculate_decision_maker_score(
            contact_profile, company_intel
        )
        
        # Calculate overall confidence
        confidence_scores = [
            contact_profile.confidence_score,
            company_intel.confidence_score,
            web_data.get("confidence_score", 0.0),
            social_signals.get("confidence_score", 0.0)
        ]
        overall_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Collect all sources
        sources_used = []
        sources_used.extend(contact_profile.data_sources)
        sources_used.extend(company_intel.data_sources)
        sources_used.extend(web_data.get("sources", []))
        sources_used.extend(social_signals.get("sources", []))
        
        # Check compliance flags
        compliance_flags = []
        if overall_confidence < self.research_config.min_confidence_score:
            compliance_flags.append("low_confidence_data")
        
        return ResearchResult(
            prospect_id=prospect_id,
            contact_profile=contact_profile,
            company_intelligence=company_intel,
            buying_signals=buying_signals,
            pain_points=pain_points,
            decision_maker_score=decision_maker_score,
            overall_confidence=overall_confidence,
            sources_used=list(set(sources_used)),  # Remove duplicates
            compliance_flags=compliance_flags
        )
    
    def _calculate_decision_maker_score(self,
                                      contact_profile: ContactProfile,
                                      company_intel: CompanyIntelligence) -> float:
        """
        Calculate how likely the contact is to be a decision maker.
        """
        score = 0.0
        
        # Job title analysis
        job_title = contact_profile.job_title or ""
        decision_maker_titles = [
            "ceo", "cto", "cfo", "president", "director", "vp", "vice president",
            "head of", "chief", "founder", "owner", "manager"
        ]
        
        for title in decision_maker_titles:
            if title in job_title.lower():
                score += 0.3
                break
        
        # Company size factor
        employee_count = company_intel.employee_count or 0
        if employee_count < 50:
            score += 0.2  # Smaller companies, higher chance of decision making
        elif employee_count < 200:
            score += 0.1
        
        # Experience factor
        experience_years = contact_profile.experience_years or 0
        if experience_years > 10:
            score += 0.2
        elif experience_years > 5:
            score += 0.1
        
        # LinkedIn connections (influence indicator)
        connections = contact_profile.connections or 0
        if connections > 500:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    async def _encrypt_research_data(self, research_result: ResearchResult) -> ResearchResult:
        """
        Encrypt sensitive PII data in research results.
        """
        # Create a copy to avoid modifying the original
        encrypted_result = research_result.copy(deep=True)
        
        # Encrypt contact profile PII
        if encrypted_result.contact_profile.email:
            encrypted_result.contact_profile.email = await encrypt_pii_data(
                encrypted_result.contact_profile.email
            )
        
        if encrypted_result.contact_profile.phone:
            encrypted_result.contact_profile.phone = await encrypt_pii_data(
                encrypted_result.contact_profile.phone
            )
        
        if encrypted_result.contact_profile.full_name:
            encrypted_result.contact_profile.full_name = await encrypt_pii_data(
                encrypted_result.contact_profile.full_name
            )
        
        return encrypted_result
    
    def _load_proxy_list(self) -> List[str]:
        """
        Load proxy list for web scraping.
        
        In production, this would load from a proxy service or configuration.
        """
        # Placeholder proxy list
        return [
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080"
        ]
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent string for web scraping."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        return random.choice(user_agents)
    
    async def _rate_limit_request(self, source: str):
        """
        Implement rate limiting for API requests.
        """
        now = datetime.utcnow()
        last_request = self.last_request_times.get(source)
        
        if last_request:
            time_since_last = (now - last_request).total_seconds()
            if time_since_last < 1.0:  # Minimum 1 second between requests
                await asyncio.sleep(1.0 - time_since_last)
        
        self.last_request_times[source] = now


# Factory function for creating research agent
def create_research_agent(config: Optional[Dict[str, Any]] = None) -> ProspectResearchAgent:
    """
    Factory function to create a configured prospect research agent.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured ProspectResearchAgent instance
    """
    agent_config = AgentConfig(
        agent_type=AgentType.RESEARCH,
        timeout_seconds=config.get("timeout_seconds", 300) if config else 300,
        retry_attempts=config.get("retry_attempts", 3) if config else 3,
        parallel_execution=True,
        parameters=config or {}
    )
    
    return ProspectResearchAgent(agent_config)