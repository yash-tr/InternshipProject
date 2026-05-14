"""
Integration tests for the Prospect Research Agent.

Tests the complete research pipeline including LinkedIn integration,
web scraping, company intelligence gathering, and data validation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any

from app.agents.prospect_research import (
    ProspectResearchAgent, 
    ProspectResearchConfig,
    CompanyIntelligence,
    ContactProfile,
    ResearchResult,
    create_research_agent
)
from app.agents.base import AgentConfig, AgentType, AgentState, AgentStatus
from app.schemas.prospect_research import (
    ResearchResultSchema,
    ContactProfileSchema,
    CompanyIntelligenceSchema,
    DataSource
)


class TestProspectResearchAgent:
    """Test suite for ProspectResearchAgent."""
    
    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return AgentConfig(
            agent_type=AgentType.RESEARCH,
            timeout_seconds=60,
            retry_attempts=2,
            parallel_execution=True,
            parameters={
                "max_concurrent_requests": 3,
                "min_confidence_score": 0.6
            }
        )
    
    @pytest.fixture
    def research_agent(self, agent_config):
        """Create test research agent."""
        return ProspectResearchAgent(agent_config)
    
    @pytest.fixture
    def sample_state(self):
        """Create sample workflow state."""
        return {
            "workflow_id": "test_workflow_123",
            "prospect_id": "prospect_456",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead_789",
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
    
    @pytest.fixture
    def mock_contact_profile(self):
        """Create mock contact profile."""
        return ContactProfile(
            full_name="John Doe",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            job_title="VP of Sales",
            company_name="Example Corp",
            linkedin_url="https://linkedin.com/in/johndoe",
            location="San Francisco, CA",
            experience_years=10,
            skills=["sales", "leadership", "crm"],
            linkedin_connections=500,
            confidence_score=0.8,
            data_sources=["linkedin"],
            last_updated=datetime.utcnow()
        )
    
    @pytest.fixture
    def mock_company_intelligence(self):
        """Create mock company intelligence."""
        return CompanyIntelligence(
            company_name="Example Corp",
            domain="example.com",
            industry="Software",
            employee_count=150,
            revenue_range="10m_50m",
            founded_year=2010,
            headquarters="San Francisco, CA",
            description="Leading software company",
            technology_stack=["react", "python", "aws"],
            social_media={"linkedin": "https://linkedin.com/company/example-corp"},
            funding_info={"total_funding": 5000000},
            key_personnel=[{"name": "Jane Smith", "title": "CEO"}],
            recent_news=[{"title": "Company raises Series B", "url": "https://news.example.com"}],
            confidence_score=0.85,
            data_sources=["company_website", "clearbit"],
            last_updated=datetime.utcnow()
        )
    
    async def test_agent_initialization(self, agent_config):
        """Test agent initialization."""
        agent = ProspectResearchAgent(agent_config)
        
        assert agent.config.agent_type == AgentType.RESEARCH
        assert agent.config.timeout_seconds == 60
        assert agent.config.parallel_execution is True
        assert agent.research_config is not None
        assert agent.proxy_list is not None
        assert agent.current_proxy_index == 0
    
    async def test_input_validation_success(self, research_agent, sample_state):
        """Test successful input validation."""
        result = await research_agent.validate_input(sample_state)
        assert result is True
    
    async def test_input_validation_missing_prospect_id(self, research_agent, sample_state):
        """Test input validation with missing prospect ID."""
        sample_state["prospect_id"] = None
        result = await research_agent.validate_input(sample_state)
        assert result is False
    
    async def test_input_validation_no_identifiers(self, research_agent, sample_state):
        """Test input validation with no identifiers."""
        sample_state["phone_number"] = None
        sample_state["salesforce_lead_id"] = None
        sample_state["research_data"] = {}
        
        result = await research_agent.validate_input(sample_state)
        assert result is False
    
    @patch('app.agents.prospect_research.ProspectResearchAgent._research_linkedin_profile')
    @patch('app.agents.prospect_research.ProspectResearchAgent._research_company_intelligence')
    @patch('app.agents.prospect_research.ProspectResearchAgent._scrape_web_data')
    @patch('app.agents.prospect_research.ProspectResearchAgent._gather_social_signals')
    @patch('app.agents.prospect_research.ProspectResearchAgent._initialize_http_client')
    @patch('app.agents.prospect_research.ProspectResearchAgent._cleanup_http_client')
    async def test_execute_success(self, 
                                 mock_cleanup,
                                 mock_init,
                                 mock_social,
                                 mock_web,
                                 mock_company,
                                 mock_linkedin,
                                 research_agent,
                                 sample_state,
                                 mock_contact_profile,
                                 mock_company_intelligence):
        """Test successful agent execution."""
        # Setup mocks
        mock_init.return_value = None
        mock_cleanup.return_value = None
        mock_linkedin.return_value = mock_contact_profile
        mock_company.return_value = mock_company_intelligence
        mock_web.return_value = {"confidence_score": 0.7, "sources": ["web_scraping"]}
        mock_social.return_value = {"confidence_score": 0.6, "sources": ["social_media"]}
        
        # Execute agent
        result = await research_agent.execute(sample_state)
        
        # Verify result
        assert result.status == AgentStatus.COMPLETED
        assert result.agent_type == AgentType.RESEARCH
        assert "research_data" in result.data
        assert "research_confidence" in result.data
        assert "research_sources" in result.data
        assert result.execution_time > 0
        
        # Verify mocks were called
        mock_linkedin.assert_called_once()
        mock_company.assert_called_once()
        mock_web.assert_called_once()
        mock_social.assert_called_once()
    
    @patch('app.agents.prospect_research.ProspectResearchAgent._research_linkedin_profile')
    async def test_execute_with_timeout(self, mock_linkedin, research_agent, sample_state):
        """Test agent execution with timeout."""
        # Setup mock to simulate timeout
        async def slow_research(*args):
            await asyncio.sleep(10)  # Longer than timeout
            return ContactProfile()
        
        mock_linkedin.side_effect = slow_research
        
        # Set short timeout for test
        research_agent.research_config.max_research_time = 1
        
        # Execute agent
        result = await research_agent.execute(sample_state)
        
        # Verify timeout handling
        assert result.status == AgentStatus.FAILED
        assert "timeout" in str(result.errors[0]).lower()
    
    async def test_linkedin_research_simulation(self, research_agent):
        """Test LinkedIn research simulation."""
        result = await research_agent._research_linkedin_profile("+1234567890", "prospect_123")
        
        assert isinstance(result, ContactProfile)
        assert result.confidence_score > 0
        assert "linkedin_simulation" in result.data_sources
        assert result.last_updated is not None
    
    async def test_company_intelligence_simulation(self, research_agent, sample_state):
        """Test company intelligence simulation."""
        sample_state["research_data"] = {"company_name": "Test Corp"}
        
        result = await research_agent._research_company_intelligence(sample_state)
        
        assert isinstance(result, CompanyIntelligence)
        assert result.company_name == "Test Corp"
        assert result.confidence_score > 0
        assert "company_intelligence_simulation" in result.data_sources
    
    async def test_web_scraping_simulation(self, research_agent, sample_state):
        """Test web scraping simulation."""
        result = await research_agent._scrape_web_data(sample_state)
        
        assert isinstance(result, dict)
        assert "confidence_score" in result
        assert "sources" in result
        assert result["confidence_score"] > 0
    
    async def test_social_signals_simulation(self, research_agent, sample_state):
        """Test social signals gathering simulation."""
        result = await research_agent._gather_social_signals(sample_state)
        
        assert isinstance(result, dict)
        assert "confidence_score" in result
        assert "sources" in result
        assert result["confidence_score"] >= 0
    
    async def test_combine_research_data(self, 
                                       research_agent,
                                       mock_contact_profile,
                                       mock_company_intelligence):
        """Test research data combination."""
        web_data = {"confidence_score": 0.7, "sources": ["web_scraping"]}
        social_signals = {"confidence_score": 0.6, "sources": ["social_media"], "buying_intent": ["budget_mentioned"]}
        
        result = await research_agent._combine_research_data(
            "prospect_123",
            mock_contact_profile,
            mock_company_intelligence,
            web_data,
            social_signals
        )
        
        assert isinstance(result, ResearchResult)
        assert result.prospect_id == "prospect_123"
        assert result.overall_confidence > 0
        assert len(result.sources_used) > 0
        assert len(result.buying_signals) > 0
        assert result.decision_maker_score >= 0
    
    async def test_decision_maker_score_calculation(self, research_agent):
        """Test decision maker score calculation."""
        # High-level executive
        contact = ContactProfile(
            job_title="Chief Technology Officer",
            experience_years=15,
            linkedin_connections=1000
        )
        company = CompanyIntelligence(
            company_name="Test Corp",
            employee_count=50
        )
        
        score = research_agent._calculate_decision_maker_score(contact, company)
        assert score > 0.5  # Should be high for CTO
        
        # Junior employee
        contact_junior = ContactProfile(
            job_title="Junior Developer",
            experience_years=2,
            linkedin_connections=100
        )
        
        score_junior = research_agent._calculate_decision_maker_score(contact_junior, company)
        assert score_junior < score  # Should be lower for junior role
    
    @patch('app.utils.encryption.encrypt_pii_data')
    async def test_encrypt_research_data(self, mock_encrypt, research_agent, mock_contact_profile):
        """Test research data encryption."""
        mock_encrypt.return_value = "encrypted_data"
        
        research_result = ResearchResult(
            prospect_id="test_123",
            contact_profile=mock_contact_profile,
            company_intelligence=CompanyIntelligence(company_name="Test Corp"),
            overall_confidence=0.8
        )
        
        encrypted_result = await research_agent._encrypt_research_data(research_result)
        
        # Verify encryption was called for PII fields
        assert mock_encrypt.call_count >= 3  # email, phone, full_name
        assert encrypted_result.contact_profile.email == "encrypted_data"
    
    async def test_rate_limiting(self, research_agent):
        """Test rate limiting functionality."""
        source = "test_source"
        
        # First request should not be delayed
        start_time = datetime.utcnow()
        await research_agent._rate_limit_request(source)
        first_duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Second request should be delayed
        start_time = datetime.utcnow()
        await research_agent._rate_limit_request(source)
        second_duration = (datetime.utcnow() - start_time).total_seconds()
        
        assert second_duration >= 1.0  # Should be delayed by at least 1 second
    
    async def test_user_agent_rotation(self, research_agent):
        """Test user agent rotation."""
        user_agent1 = research_agent._get_random_user_agent()
        user_agent2 = research_agent._get_random_user_agent()
        
        assert isinstance(user_agent1, str)
        assert isinstance(user_agent2, str)
        assert len(user_agent1) > 50  # Should be a full user agent string
        
        # Test multiple calls to ensure rotation works
        user_agents = [research_agent._get_random_user_agent() for _ in range(10)]
        unique_agents = set(user_agents)
        assert len(unique_agents) > 1  # Should have some variety
    
    async def test_factory_function(self):
        """Test factory function for creating research agent."""
        config = {
            "timeout_seconds": 120,
            "retry_attempts": 5,
            "max_concurrent_requests": 5
        }
        
        agent = create_research_agent(config)
        
        assert isinstance(agent, ProspectResearchAgent)
        assert agent.config.timeout_seconds == 120
        assert agent.config.retry_attempts == 5
        assert agent.config.parameters["max_concurrent_requests"] == 5
    
    async def test_factory_function_default_config(self):
        """Test factory function with default configuration."""
        agent = create_research_agent()
        
        assert isinstance(agent, ProspectResearchAgent)
        assert agent.config.timeout_seconds == 300
        assert agent.config.retry_attempts == 3
        assert agent.config.parallel_execution is True


class TestResearchDataValidation:
    """Test suite for research data validation."""
    
    def test_contact_profile_schema_validation(self):
        """Test contact profile schema validation."""
        valid_data = {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+1-234-567-8900",
            "job_title": "VP of Sales",
            "company_name": "Example Corp",
            "experience_years": 10,
            "confidence_score": 0.8,
            "data_sources": ["linkedin"]
        }
        
        profile = ContactProfileSchema(**valid_data)
        assert profile.full_name == "John Doe"
        assert profile.confidence_level.value == "high"
    
    def test_contact_profile_invalid_email(self):
        """Test contact profile with invalid email."""
        invalid_data = {
            "full_name": "John Doe",
            "email": "invalid-email",
            "confidence_score": 0.8
        }
        
        with pytest.raises(ValueError):
            ContactProfileSchema(**invalid_data)
    
    def test_company_intelligence_schema_validation(self):
        """Test company intelligence schema validation."""
        valid_data = {
            "company_name": "Example Corp",
            "domain": "example.com",
            "industry": "Software",
            "employee_count": 150,
            "founded_year": 2010,
            "confidence_score": 0.85,
            "data_sources": ["clearbit"]
        }
        
        intelligence = CompanyIntelligenceSchema(**valid_data)
        assert intelligence.company_name == "Example Corp"
        assert intelligence.company_size == "medium"  # Auto-set based on employee count
    
    def test_research_result_schema_validation(self):
        """Test research result schema validation."""
        contact_data = {
            "full_name": "John Doe",
            "confidence_score": 0.8,
            "data_sources": ["linkedin"]
        }
        
        company_data = {
            "company_name": "Example Corp",
            "confidence_score": 0.85,
            "data_sources": ["clearbit"]
        }
        
        result_data = {
            "prospect_id": "prospect_123",
            "contact_profile": contact_data,
            "company_intelligence": company_data,
            "overall_confidence": 0.82,
            "sources_used": ["linkedin", "clearbit"]
        }
        
        result = ResearchResultSchema(**result_data)
        assert result.prospect_id == "prospect_123"
        assert result.is_high_quality is True
        assert result.confidence_level.value == "high"
    
    def test_buying_signal_validation(self):
        """Test buying signal validation."""
        from app.schemas.prospect_research import BuyingSignal
        
        valid_signal = {
            "signal_type": "budget_mentioned",
            "description": "Prospect mentioned $50k budget",
            "confidence": 0.9,
            "source": "linkedin"
        }
        
        signal = BuyingSignal(**valid_signal)
        assert signal.signal_type == "budget_mentioned"
        assert signal.confidence == 0.9
    
    def test_buying_signal_invalid_type(self):
        """Test buying signal with invalid type."""
        from app.schemas.prospect_research import BuyingSignal
        
        invalid_signal = {
            "signal_type": "invalid_signal",
            "description": "Test description",
            "confidence": 0.9,
            "source": "linkedin"
        }
        
        with pytest.raises(ValueError):
            BuyingSignal(**invalid_signal)


@pytest.mark.integration
class TestResearchIntegration:
    """Integration tests for the complete research pipeline."""
    
    @pytest.fixture
    def integration_agent(self):
        """Create agent for integration testing."""
        config = AgentConfig(
            agent_type=AgentType.RESEARCH,
            timeout_seconds=30,
            retry_attempts=1,
            parallel_execution=True
        )
        return ProspectResearchAgent(config)
    
    async def test_end_to_end_research_pipeline(self, integration_agent):
        """Test complete research pipeline end-to-end."""
        state = {
            "workflow_id": "integration_test",
            "prospect_id": "prospect_integration",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead_integration",
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "research_data": {"company_name": "Integration Test Corp"},
            "research_confidence": 0.0,
            "research_sources": [],
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        # Execute the complete pipeline
        result = await integration_agent.execute(state)
        
        # Verify successful execution
        assert result.status == AgentStatus.COMPLETED
        assert result.execution_time > 0
        assert "research_data" in result.data
        assert result.data["research_confidence"] > 0
        assert len(result.data["research_sources"]) > 0
        
        # Verify metadata
        assert "sources_used" in result.metadata
        assert "confidence_score" in result.metadata
        assert result.metadata["confidence_score"] > 0
    
    async def test_parallel_research_execution(self, integration_agent):
        """Test parallel execution of research tasks."""
        state = {
            "workflow_id": "parallel_test",
            "prospect_id": "prospect_parallel",
            "phone_number": "+1234567890",
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        start_time = datetime.utcnow()
        result = await integration_agent.execute(state)
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify parallel execution was faster than sequential
        assert result.status == AgentStatus.COMPLETED
        assert execution_time < 10  # Should complete quickly with simulated data
        
        # Verify all research sources were used
        sources_used = result.data.get("research_sources", [])
        assert len(sources_used) > 0
    
    async def test_error_handling_and_recovery(self, integration_agent):
        """Test error handling and recovery mechanisms."""
        # Test with invalid state
        invalid_state = {
            "workflow_id": "error_test",
            "prospect_id": None,  # Missing required field
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        result = await integration_agent.execute(invalid_state)
        
        # Verify error handling
        assert result.status == AgentStatus.FAILED
        assert len(result.errors) > 0
        assert "Invalid input state" in result.errors[0]