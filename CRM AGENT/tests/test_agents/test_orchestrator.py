"""
Unit tests for the LangGraph agent orchestrator.

Tests the main orchestration logic, workflow management,
and agent coordination functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import uuid
import asyncio

from app.agents.orchestrator import AgentOrchestrator, WorkflowConfig
from app.agents.base import (
    AgentState, AgentStatus, AgentType, AgentResult, AgentConfig, BaseAgent
)


class MockAgent(BaseAgent):
    """Mock agent for testing orchestrator functionality."""
    
    def __init__(self, config: AgentConfig, result_data: dict = None, should_fail: bool = False):
        super().__init__(config)
        self.result_data = result_data or {}
        self.should_fail = should_fail
        self.execution_count = 0
    
    async def execute(self, state: AgentState) -> AgentResult:
        """Mock execute method."""
        self.execution_count += 1
        
        if self.should_fail:
            raise Exception(f"Mock {self.config.agent_type.value} agent failure")
        
        return AgentResult(
            agent_type=self.config.agent_type,
            status=AgentStatus.COMPLETED,
            data=self.result_data,
            execution_time=1.0
        )


class TestWorkflowConfig:
    """Test WorkflowConfig functionality."""
    
    def test_workflow_config_defaults(self):
        """Test default workflow configuration values."""
        config = WorkflowConfig()
        
        assert config.max_execution_time == timedelta(hours=2)
        assert config.checkpoint_interval == timedelta(minutes=5)
        assert config.retry_delays == [1, 5, 15, 60]
        assert config.parallel_research_sources == 3
        assert config.approval_timeout == timedelta(hours=24)
        assert len(config.call_retry_intervals) == 3


class TestAgentOrchestrator:
    """Test AgentOrchestrator functionality."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        config = WorkflowConfig()
        orchestrator = AgentOrchestrator(config=config)
        
        assert orchestrator.config == config
        assert orchestrator.communication is not None
        assert orchestrator._agents == {}
        assert orchestrator.workflow_graph is not None
    
    def test_register_agent(self):
        """Test agent registration."""
        orchestrator = AgentOrchestrator()
        
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config)
        
        orchestrator.register_agent(AgentType.RESEARCH, agent)
        
        assert AgentType.RESEARCH.value in orchestrator._agents
        assert orchestrator._agents[AgentType.RESEARCH.value] == agent
    
    @pytest.mark.asyncio
    async def test_start_workflow(self):
        """Test starting a new workflow."""
        orchestrator = AgentOrchestrator()
        
        prospect_data = {
            "prospect_id": "prospect-123",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead-123"
        }
        
        with patch.object(orchestrator, '_execute_workflow') as mock_execute:
            mock_execute.return_value = None
            
            workflow_id = await orchestrator.start_workflow(prospect_data)
            
            assert workflow_id is not None
            assert len(workflow_id) == 36  # UUID length
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_workflow_with_id(self):
        """Test starting a workflow with a specific ID."""
        orchestrator = AgentOrchestrator()
        
        prospect_data = {"prospect_id": "prospect-123"}
        custom_workflow_id = "custom-workflow-123"
        
        with patch.object(orchestrator, '_execute_workflow') as mock_execute:
            mock_execute.return_value = None
            
            workflow_id = await orchestrator.start_workflow(prospect_data, custom_workflow_id)
            
            assert workflow_id == custom_workflow_id
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_workflow_failure(self):
        """Test workflow start failure handling."""
        orchestrator = AgentOrchestrator()
        
        prospect_data = {"prospect_id": "prospect-123"}
        
        with patch.object(orchestrator, '_execute_workflow') as mock_execute:
            mock_execute.side_effect = Exception("Workflow start failed")
            
            with pytest.raises(Exception, match="Workflow start failed"):
                await orchestrator.start_workflow(prospect_data)
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_no_checkpointer(self):
        """Test getting workflow status without checkpointer."""
        orchestrator = AgentOrchestrator()
        
        status = await orchestrator.get_workflow_status("workflow-123")
        assert status is None
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_with_checkpointer(self):
        """Test getting workflow status with checkpointer."""
        with patch('langgraph_checkpoint_postgres.PostgresSaver') as mock_saver:
            mock_checkpointer = Mock()
            mock_saver.from_conn_string.return_value = mock_checkpointer
            
            orchestrator = AgentOrchestrator(postgres_url="postgresql://test")
            
            # Mock workflow graph state
            mock_state = Mock()
            mock_state.values = {
                "status": AgentStatus.RUNNING,
                "current_agent": "research",
                "updated_at": datetime.utcnow(),
                "lead_score": 75,
                "call_attempts": 1,
                "errors": []
            }
            
            orchestrator.workflow_graph.aget_state = AsyncMock(return_value=mock_state)
            
            status = await orchestrator.get_workflow_status("workflow-123")
            
            assert status is not None
            assert status["workflow_id"] == "workflow-123"
            assert status["status"] == AgentStatus.RUNNING
            assert status["current_agent"] == "research"
            assert status["lead_score"] == 75
    
    @pytest.mark.asyncio
    async def test_resume_workflow(self):
        """Test resuming a workflow after approval."""
        with patch('langgraph_checkpoint_postgres.PostgresSaver') as mock_saver:
            mock_checkpointer = Mock()
            mock_saver.from_conn_string.return_value = mock_checkpointer
            
            orchestrator = AgentOrchestrator(postgres_url="postgresql://test")
            
            # Mock workflow graph methods
            mock_state = Mock()
            mock_state.values = {"status": AgentStatus.PENDING}
            
            orchestrator.workflow_graph.aget_state = AsyncMock(return_value=mock_state)
            orchestrator.workflow_graph.aupdate_state = AsyncMock()
            
            approval_decision = {
                "decision": "approved",
                "approver_id": "user-123"
            }
            
            success = await orchestrator.resume_workflow("workflow-123", approval_decision)
            
            assert success is True
            orchestrator.workflow_graph.aupdate_state.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_research_node_success(self):
        """Test successful research node execution."""
        orchestrator = AgentOrchestrator()
        
        # Register mock research agent
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        research_data = {
            "research_data": {"company": "Test Corp"},
            "research_confidence": 0.85,
            "research_sources": ["linkedin", "website"]
        }
        agent = MockAgent(config, research_data)
        orchestrator.register_agent(AgentType.RESEARCH, agent)
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "research",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": "prospect-123",
            "phone_number": "+1234567890",
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
        
        result_state = await orchestrator._research_node(state)
        
        assert result_state["research_data"]["company"] == "Test Corp"
        assert result_state["research_confidence"] == 0.85
        assert "linkedin" in result_state["research_sources"]
        assert agent.execution_count == 1
    
    @pytest.mark.asyncio
    async def test_research_node_agent_not_registered(self):
        """Test research node when agent is not registered."""
        orchestrator = AgentOrchestrator()
        
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
        
        result_state = await orchestrator._research_node(state)
        
        assert result_state["status"] == AgentStatus.FAILED
        assert len(result_state["errors"]) == 1
        assert "Research agent not registered" in str(result_state["errors"][0])
    
    @pytest.mark.asyncio
    async def test_research_node_agent_failure(self):
        """Test research node when agent execution fails."""
        orchestrator = AgentOrchestrator()
        
        # Register failing mock research agent
        config = AgentConfig(agent_type=AgentType.RESEARCH)
        agent = MockAgent(config, should_fail=True)
        orchestrator.register_agent(AgentType.RESEARCH, agent)
        
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
        
        result_state = await orchestrator._research_node(state)
        
        assert result_state["status"] == AgentStatus.FAILED
        assert len(result_state["errors"]) == 1
        assert "Research agent failed" in str(result_state["errors"][0])
    
    def test_should_require_approval_high_score(self):
        """Test approval requirement for high lead scores."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "scoring",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 85,  # High score
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
        
        decision = orchestrator._should_require_approval(state)
        assert decision == "approval_required"
    
    def test_should_require_approval_medium_score(self):
        """Test auto-approval for medium lead scores."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "scoring",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 70,  # Medium score
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
        
        decision = orchestrator._should_require_approval(state)
        assert decision == "auto_approve"
    
    def test_should_require_approval_low_score(self):
        """Test rejection for low lead scores."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "scoring",
            "status": AgentStatus.RUNNING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "prospect_id": None,
            "phone_number": None,
            "salesforce_lead_id": None,
            "research_data": {},
            "research_confidence": 0.0,
            "research_sources": [],
            "lead_score": 45,  # Low score
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
        
        decision = orchestrator._should_require_approval(state)
        assert decision == "reject"
    
    def test_check_approval_decision_approved(self):
        """Test checking approved decision."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "approval",
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
            "approval_required": True,
            "approval_status": "approved",
            "approver_id": "user-123",
            "approval_timestamp": datetime.utcnow(),
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
        
        decision = orchestrator._check_approval_decision(state)
        assert decision == "approved"
    
    def test_check_approval_decision_rejected(self):
        """Test checking rejected decision."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "approval",
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
            "approval_required": True,
            "approval_status": "rejected",
            "approver_id": "user-123",
            "approval_timestamp": datetime.utcnow(),
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
        
        decision = orchestrator._check_approval_decision(state)
        assert decision == "rejected"
    
    def test_check_call_outcome_answered(self):
        """Test call outcome when call is answered."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "calling",
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
            "call_sid": "call-123",
            "call_status": "answered",
            "call_attempts": 1,
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
        
        outcome = orchestrator._check_call_outcome(state)
        assert outcome == "answered"
    
    def test_check_call_outcome_max_attempts(self):
        """Test call outcome when max attempts reached."""
        orchestrator = AgentOrchestrator()
        
        state: AgentState = {
            "workflow_id": "test-123",
            "current_agent": "calling",
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
            "call_status": "no-answer",
            "call_attempts": 3,  # Max attempts
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
        
        outcome = orchestrator._check_call_outcome(state)
        assert outcome == "max_attempts"