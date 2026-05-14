"""
Unit tests for base agent classes and state management.

Tests the foundational components of the LangGraph agent system
including state management, communication interfaces, and base agent functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import uuid

from app.agents.base import (
    AgentState, AgentStatus, AgentType, AgentResult, AgentConfig,
    BaseAgent, AgentCommunicationInterface
)


class TestAgentState:
    """Test AgentState TypedDict functionality."""
    
    def test_agent_state_creation(self):
        """Test creating a valid AgentState."""
        state: AgentState = {
            "workflow_id": "test-workflow-123",
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": "prospect-123",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead-123",
            "research_data": {"company": "Test Corp"},
            "research_confidence": 0.85,
            "research_sources": ["linkedin", "website"],
            "lead_score": 75,
            "scoring_rationale": "High-value prospect",
            "buying_signals": ["budget_mentioned", "timeline_urgent"],
            "approval_required": True,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        assert state["workflow_id"] == "test-workflow-123"
        assert state["status"] == AgentStatus.PENDING
        assert state["lead_score"] == 75
        assert state["approval_required"] is True


class TestAgentResult:
    """Test AgentResult model functionality."""
    
    def test_agent_result_creation(self):
        """Test creating a valid AgentResult."""
        result = AgentResult(
            agent_type=AgentType.RESEARCH,
            status=AgentStatus.COMPLETED,
            data={"research_complete": True},
            errors=[],
            next_agent="scoring",
            execution_time=45.2,
            metadata={"sources_used": 3}
        )
        
        assert result.agent_type == AgentType.RESEARCH
        assert result.status == AgentStatus.COMPLETED
        assert result.data["research_complete"] is True
        assert result.next_agent == "scoring"
        assert result.execution_time == 45.2
    
    def test_agent_result_defaults(self):
        """Test AgentResult with default values."""
        result = AgentResult(
            agent_type=AgentType.SCORING,
            status=AgentStatus.RUNNING
        )
        
        assert result.data == {}
        assert result.errors == []
        assert result.next_agent is None
        assert result.execution_time == 0.0
        assert result.metadata == {}


class TestAgentConfig:
    """Test AgentConfig model functionality."""
    
    def test_agent_config_creation(self):
        """Test creating a valid AgentConfig."""
        config = AgentConfig(
            agent_type=AgentType.RESEARCH,
            timeout_seconds=600,
            retry_attempts=5,
            parallel_execution=True,
            dependencies=["salesforce", "linkedin"],
            parameters={"max_sources": 5}
        )
        
        assert config.agent_type == AgentType.RESEARCH
        assert config.timeout_seconds == 600
        assert config.retry_attempts == 5
        assert config.parallel_execution is True
        assert "salesforce" in config.dependencies
        assert config.parameters["max_sources"] == 5
    
    def test_agent_config_defaults(self):
        """Test AgentConfig with default values."""
        config = AgentConfig(agent_type=AgentType.CALLING)
        
        assert config.timeout_seconds == 300
        assert config.retry_attempts == 3
        assert config.parallel_execution is False
        assert config.dependencies == []
        assert config.parameters == {}


class MockAgent(BaseAgent):
    """Mock agent implementation for testing."""
    
    def __init__(self, config: AgentConfig, should_fail: bool = False):
        super().__init__(config)
        self.should_fail = should_fail
        self.execution_count = 0
    
    async def execute(self, state: AgentState) -> AgentResult:
        """Mock execute method."""
        self.execution_count += 1
        
        if self.should_fail:
            raise Exception("Mock agent failure")
        
        return AgentResult(
            agent_type=self.config.agent_type,
            status=AgentStatus.COMPLETED,
            data={"mock_result": True, "execution_count": self.execution_count},
            execution_time=1.0
        )


class TestBaseAgent:
    """Test BaseAgent abstract class functionality."""
    
    def test_base_agent_initialization(self):
        """Test BaseAgent initialization."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        assert agent.config == config
        assert agent.agent_id is not None
        assert len(agent.agent_id) == 36  # UUID length
        assert agent.logger is not None
    
    @pytest.mark.asyncio
    async def test_agent_execute_success(self):
        """Test successful agent execution."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 0,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": False,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        result = await agent.execute(state)
        
        assert result.status == AgentStatus.COMPLETED
        assert result.agent_type == AgentType.RESEARCH
        assert result.data["mock_result"] is True
        assert result.execution_time == 1.0
        assert agent.execution_count == 1
    
    @pytest.mark.asyncio
    async def test_agent_execute_failure(self):
        """Test agent execution failure handling."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config, should_fail=True)
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 0,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": False,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        # Test that execute raises exception
        with pytest.raises(Exception, match="Mock agent failure"):
            await agent.execute(state)
    
    @pytest.mark.asyncio
    async def test_agent_handle_error(self):
        """Test agent error handling."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 0,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": False,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        error = Exception("Test error")
        result = await agent.handle_error(error, state)
        
        assert result.status == AgentStatus.FAILED
        assert result.agent_type == AgentType.RESEARCH
        assert "Test error" in result.errors
        assert result.metadata["error_type"] == "Exception"
        assert result.metadata["agent_id"] == agent.agent_id
    
    @pytest.mark.asyncio
    async def test_validate_input_default(self):
        """Test default input validation."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 0,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": False,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        is_valid = await agent.validate_input(state)
        assert is_valid is True
    
    def test_update_state(self):
        """Test state update functionality."""
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        original_state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 0,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": False,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 0,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        updates = {
            "lead_score": 85,
            "research_data": {"company": "Test Corp"},
            "research_confidence": 0.9
        }
        
        updated_state = agent.update_state(original_state, updates)
        
        assert updated_state["lead_score"] == 85
        assert updated_state["research_data"]["company"] == "Test Corp"
        assert updated_state["research_confidence"] == 0.9
        assert updated_state["current_agent"] == "research"
        assert len(updated_state["audit_trail"]) == 1
        
        audit_entry = updated_state["audit_trail"][0]
        assert audit_entry["agent_type"] == "research"
        assert audit_entry["agent_id"] == agent.agent_id
        assert "lead_score" in audit_entry["updates"]


class TestAgentCommunicationInterface:
    """Test AgentCommunicationInterface functionality."""
    
    def test_communication_interface_initialization(self):
        """Test communication interface initialization."""
        comm = AgentCommunicationInterface()
        
        assert comm.logger is not None
        assert comm._message_queue == []
    
    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending messages between agents."""
        comm = AgentCommunicationInterface()
        
        message = {"type": "data_request", "data": {"prospect_id": "123"}}
        success = await comm.send_message("research", "scoring", message)
        
        assert success is True
        assert len(comm._message_queue) == 1
        
        queued_message = comm._message_queue[0]
        assert queued_message["from_agent"] == "research"
        assert queued_message["to_agent"] == "scoring"
        assert queued_message["message"] == message
        assert queued_message["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_get_messages(self):
        """Test retrieving messages for an agent."""
        comm = AgentCommunicationInterface()
        
        # Send multiple messages
        await comm.send_message("research", "scoring", {"data": "test1"})
        await comm.send_message("approval", "scoring", {"data": "test2"})
        await comm.send_message("research", "calling", {"data": "test3"})
        
        # Get messages for scoring agent
        messages = await comm.get_messages("scoring")
        
        assert len(messages) == 2
        assert all(msg["to_agent"] == "scoring" for msg in messages)
        assert all(msg["status"] == "delivered" for msg in messages)
        
        # Verify messages are marked as delivered
        pending_messages = [msg for msg in comm._message_queue if msg["status"] == "pending"]
        assert len(pending_messages) == 1  # Only the message to "calling" should be pending
    
    @pytest.mark.asyncio
    async def test_notify_human_approval_required(self):
        """Test human approval notification."""
        comm = AgentCommunicationInterface()
        
        approval_data = {
            "prospect_id": "123",
            "lead_score": 85,
            "rationale": "High-value prospect"
        }
        
        approval_id = await comm.notify_human_approval_required("workflow-123", approval_data)
        
        assert approval_id is not None
        assert len(approval_id) == 36  # UUID length
    
    @pytest.mark.asyncio
    async def test_check_approval_status(self):
        """Test checking approval status."""
        comm = AgentCommunicationInterface()
        
        # For now, this should return None (pending)
        status = await comm.check_approval_status("approval-123")
        assert status is None