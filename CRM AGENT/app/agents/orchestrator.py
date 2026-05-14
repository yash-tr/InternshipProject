"""
LangGraph Agent Orchestrator for workflow management.

This module provides the main orchestration logic using LangGraph
to coordinate between different agents in the autonomous calling workflow.
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import asyncio
import logging
import uuid
import os

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

# Optional PostgreSQL checkpoint support
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_AVAILABLE = True
except ImportError:
    PostgresSaver = None
    POSTGRES_AVAILABLE = False

from .base import (
    AgentState, AgentStatus, AgentType, AgentResult, 
    BaseAgent, AgentCommunicationInterface
)
from .prospect_research import create_research_agent
from .tracing import agent_tracer

logger = logging.getLogger(__name__)


class WorkflowConfig:
    """Configuration for the agent workflow."""
    
    def __init__(self):
        self.max_execution_time = timedelta(hours=2)
        self.checkpoint_interval = timedelta(minutes=5)
        self.retry_delays = [1, 5, 15, 60]  # seconds
        self.parallel_research_sources = 3
        self.approval_timeout = timedelta(hours=24)
        self.call_retry_intervals = [timedelta(hours=1), timedelta(hours=4), timedelta(days=1)]


class AgentOrchestrator:
    """
    Main orchestrator for the LangGraph agent workflow.
    
    Manages the execution flow between research, scoring, approval,
    calling, and deal closing agents.
    """
    
    def __init__(self, 
                 postgres_url: Optional[str] = None,
                 config: Optional[WorkflowConfig] = None):
        self.config = config or WorkflowConfig()
        self.communication = AgentCommunicationInterface()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize PostgreSQL checkpointer for state persistence
        self.checkpointer = None
        if postgres_url and POSTGRES_AVAILABLE and PostgresSaver:
            try:
                self.checkpointer = PostgresSaver.from_conn_string(postgres_url)
            except Exception as e:
                self.logger.warning(f"Failed to initialize PostgreSQL checkpointer: {e}")
                self.checkpointer = None
        
        # Agent registry
        self._agents: Dict[str, BaseAgent] = {}
        
        # Initialize default agents
        self._initialize_default_agents()
        
        # Workflow graph
        self.workflow_graph = None
        self._build_workflow_graph()
    
    def register_agent(self, agent_type: AgentType, agent: BaseAgent):
        """
        Register an agent with the orchestrator.
        
        Args:
            agent_type: Type of agent
            agent: Agent instance
        """
        self._agents[agent_type.value] = agent
        self.logger.info(f"Registered agent: {agent_type.value}")
    
    def _build_workflow_graph(self):
        """Build the LangGraph workflow definition."""
        
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes for each agent type
        workflow.add_node("research", self._research_node)
        workflow.add_node("scoring", self._scoring_node)
        workflow.add_node("approval", self._approval_node)
        workflow.add_node("calling", self._calling_node)
        workflow.add_node("deal_closing", self._deal_closing_node)
        workflow.add_node("completion", self._completion_node)
        workflow.add_node("error_handler", self._error_handler_node)
        
        # Define the workflow edges
        workflow.set_entry_point("research")
        
        # Research -> Scoring
        workflow.add_edge("research", "scoring")
        
        # Scoring -> Approval (conditional based on score)
        workflow.add_conditional_edges(
            "scoring",
            self._should_require_approval,
            {
                "approval_required": "approval",
                "auto_approve": "calling",
                "reject": "completion"
            }
        )
        
        # Approval -> Calling or Completion
        workflow.add_conditional_edges(
            "approval",
            self._check_approval_decision,
            {
                "approved": "calling",
                "rejected": "completion",
                "timeout": "completion"
            }
        )
        
        # Calling -> Deal Closing or Completion
        workflow.add_conditional_edges(
            "calling",
            self._check_call_outcome,
            {
                "answered": "deal_closing",
                "no_answer": "calling",  # Retry logic
                "failed": "completion",
                "max_attempts": "completion"
            }
        )
        
        # Deal Closing -> Completion
        workflow.add_edge("deal_closing", "completion")
        
        # Error handling
        workflow.add_edge("error_handler", "completion")
        
        # Completion is the end
        workflow.add_edge("completion", END)
        
        # Compile the workflow
        self.workflow_graph = workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["approval"]  # Human-in-the-loop checkpoint
        )
    
    async def start_workflow(self, 
                           prospect_data: Dict[str, Any],
                           workflow_id: Optional[str] = None) -> str:
        """
        Start a new agent workflow for a prospect.
        
        Args:
            prospect_data: Initial prospect information
            workflow_id: Optional workflow identifier
            
        Returns:
            Workflow ID
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())
        
        # Initialize workflow state
        initial_state: AgentState = {
            "workflow_id": workflow_id,
            "current_agent": "research",
            "status": AgentStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            
            # Prospect data
            "prospect_id": prospect_data.get("prospect_id"),
            "phone_number": prospect_data.get("phone_number"),
            "salesforce_lead_id": prospect_data.get("salesforce_lead_id"),
            
            # Initialize empty results
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
        
        # Start tracing
        agent_tracer.start_workflow_trace(workflow_id, initial_state)
        
        # Start the workflow
        config = RunnableConfig(
            configurable={"thread_id": workflow_id},
            tags=["ai_calling_agent", "autonomous_workflow"]
        )
        
        try:
            # Execute the workflow asynchronously
            asyncio.create_task(
                self._execute_workflow(initial_state, config)
            )
            
            self.logger.info(f"Started workflow {workflow_id} for prospect {prospect_data.get('prospect_id')}")
            return workflow_id
            
        except Exception as e:
            self.logger.error(f"Failed to start workflow {workflow_id}: {e}")
            raise
    
    async def _execute_workflow(self, initial_state: AgentState, config: RunnableConfig):
        """Execute the workflow graph."""
        try:
            async for state in self.workflow_graph.astream(initial_state, config):
                self.logger.debug(f"Workflow state update: {state}")
                
                # Check for completion or errors
                if state.get("status") in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
                    break
                    
        except Exception as e:
            self.logger.error(f"Workflow execution failed: {e}")
            # Update state to failed
            await self._handle_workflow_error(initial_state["workflow_id"], e)
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow status information
        """
        if not self.checkpointer:
            return None
        
        try:
            config = RunnableConfig(configurable={"thread_id": workflow_id})
            state = await self.workflow_graph.aget_state(config)
            
            return {
                "workflow_id": workflow_id,
                "status": state.values.get("status"),
                "current_agent": state.values.get("current_agent"),
                "updated_at": state.values.get("updated_at"),
                "lead_score": state.values.get("lead_score"),
                "call_attempts": state.values.get("call_attempts"),
                "errors": state.values.get("errors", [])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get workflow status {workflow_id}: {e}")
            return None
    
    async def resume_workflow(self, workflow_id: str, approval_decision: Dict[str, Any]) -> bool:
        """
        Resume a workflow after human approval.
        
        Args:
            workflow_id: Workflow identifier
            approval_decision: Approval decision data
            
        Returns:
            True if workflow was resumed successfully
        """
        try:
            config = RunnableConfig(configurable={"thread_id": workflow_id})
            
            # Update state with approval decision
            current_state = await self.workflow_graph.aget_state(config)
            updated_state = current_state.values.copy()
            updated_state.update({
                "approval_status": approval_decision.get("decision"),
                "approver_id": approval_decision.get("approver_id"),
                "approval_timestamp": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            # Resume workflow
            await self.workflow_graph.aupdate_state(config, updated_state)
            
            self.logger.info(f"Resumed workflow {workflow_id} with approval: {approval_decision}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to resume workflow {workflow_id}: {e}")
            return False
    
    # Node implementations
    async def _research_node(self, state: AgentState) -> AgentState:
        """Execute the research agent."""
        agent = self._agents.get("research")
        if not agent:
            return self._add_error(state, "Research agent not registered")
        
        try:
            result = await agent.execute(state)
            
            # Trace agent execution
            agent_tracer.trace_agent_execution(
                state["workflow_id"], 
                AgentType.RESEARCH, 
                state, 
                result
            )
            
            return self._update_state_from_result(state, result)
        except Exception as e:
            return self._add_error(state, f"Research agent failed: {e}")
    
    async def _scoring_node(self, state: AgentState) -> AgentState:
        """Execute the scoring agent."""
        agent = self._agents.get("scoring")
        if not agent:
            return self._add_error(state, "Scoring agent not registered")
        
        try:
            result = await agent.execute(state)
            
            # Trace agent execution
            agent_tracer.trace_agent_execution(
                state["workflow_id"], 
                AgentType.SCORING, 
                state, 
                result
            )
            
            return self._update_state_from_result(state, result)
        except Exception as e:
            return self._add_error(state, f"Scoring agent failed: {e}")
    
    async def _approval_node(self, state: AgentState) -> AgentState:
        """Execute the approval agent."""
        agent = self._agents.get("approval")
        if not agent:
            return self._add_error(state, "Approval agent not registered")
        
        try:
            result = await agent.execute(state)
            
            # Trace agent execution
            agent_tracer.trace_agent_execution(
                state["workflow_id"], 
                AgentType.APPROVAL, 
                state, 
                result
            )
            
            return self._update_state_from_result(state, result)
        except Exception as e:
            return self._add_error(state, f"Approval agent failed: {e}")
    
    async def _calling_node(self, state: AgentState) -> AgentState:
        """Execute the calling agent."""
        agent = self._agents.get("calling")
        if not agent:
            return self._add_error(state, "Calling agent not registered")
        
        try:
            result = await agent.execute(state)
            
            # Trace agent execution
            agent_tracer.trace_agent_execution(
                state["workflow_id"], 
                AgentType.CALLING, 
                state, 
                result
            )
            
            return self._update_state_from_result(state, result)
        except Exception as e:
            return self._add_error(state, f"Calling agent failed: {e}")
    
    async def _deal_closing_node(self, state: AgentState) -> AgentState:
        """Execute the deal closing agent."""
        agent = self._agents.get("deal_closing")
        if not agent:
            return self._add_error(state, "Deal closing agent not registered")
        
        try:
            result = await agent.execute(state)
            
            # Trace agent execution
            agent_tracer.trace_agent_execution(
                state["workflow_id"], 
                AgentType.DEAL_CLOSING, 
                state, 
                result
            )
            
            return self._update_state_from_result(state, result)
        except Exception as e:
            return self._add_error(state, f"Deal closing agent failed: {e}")
    
    async def _completion_node(self, state: AgentState) -> AgentState:
        """Handle workflow completion."""
        updated_state = state.copy()
        updated_state["status"] = AgentStatus.COMPLETED
        updated_state["updated_at"] = datetime.utcnow()
        
        # Complete tracing
        agent_tracer.complete_workflow_trace(
            state["workflow_id"], 
            updated_state, 
            success=True
        )
        
        self.logger.info(f"Workflow {state['workflow_id']} completed")
        return updated_state
    
    async def _error_handler_node(self, state: AgentState) -> AgentState:
        """Handle workflow errors."""
        updated_state = state.copy()
        updated_state["status"] = AgentStatus.FAILED
        updated_state["updated_at"] = datetime.utcnow()
        
        self.logger.error(f"Workflow {state['workflow_id']} failed with errors: {state.get('errors', [])}")
        return updated_state
    
    # Conditional edge functions
    def _should_require_approval(self, state: AgentState) -> str:
        """Determine if human approval is required based on lead score."""
        lead_score = state.get("lead_score", 0)
        
        if lead_score >= 80:
            return "approval_required"
        elif lead_score >= 60:
            return "auto_approve"
        else:
            return "reject"
    
    def _check_approval_decision(self, state: AgentState) -> str:
        """Check the approval decision."""
        approval_status = state.get("approval_status")
        
        if approval_status == "approved":
            return "approved"
        elif approval_status == "rejected":
            return "rejected"
        else:
            # Check for timeout
            approval_timestamp = state.get("approval_timestamp")
            if approval_timestamp:
                time_since_approval = datetime.utcnow() - approval_timestamp
                if time_since_approval > self.config.approval_timeout:
                    return "timeout"
            
            return "timeout"  # Default to timeout if no decision
    
    def _check_call_outcome(self, state: AgentState) -> str:
        """Check the outcome of a call attempt."""
        call_status = state.get("call_status")
        call_attempts = state.get("call_attempts", 0)
        
        if call_status == "answered":
            return "answered"
        elif call_attempts >= 3:
            return "max_attempts"
        elif call_status in ["no-answer", "busy"]:
            return "no_answer"
        else:
            return "failed"
    
    # Helper methods
    def _update_state_from_result(self, state: AgentState, result: AgentResult) -> AgentState:
        """Update state based on agent result."""
        updated_state = state.copy()
        updated_state.update(result.data)
        updated_state["updated_at"] = datetime.utcnow()
        
        if result.errors:
            if "errors" not in updated_state:
                updated_state["errors"] = []
            updated_state["errors"].extend(result.errors)
        
        return updated_state
    
    def _add_error(self, state: AgentState, error_message: str) -> AgentState:
        """Add an error to the state."""
        updated_state = state.copy()
        if "errors" not in updated_state:
            updated_state["errors"] = []
        
        updated_state["errors"].append({
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": updated_state.get("current_agent")
        })
        updated_state["status"] = AgentStatus.FAILED
        updated_state["updated_at"] = datetime.utcnow()
        
        return updated_state
    
    async def _handle_workflow_error(self, workflow_id: str, error: Exception):
        """Handle workflow-level errors."""
        self.logger.error(f"Workflow {workflow_id} encountered error: {error}")
        
        # In a real implementation, this would update the database
        # and send notifications to administrators
    
    def _initialize_default_agents(self):
        """Initialize default agents for the workflow."""
        # Create and register research agent
        research_agent = create_research_agent({
            "timeout_seconds": 300,
            "retry_attempts": 3,
            "max_concurrent_requests": 3
        })
        self.register_agent(AgentType.RESEARCH, research_agent)