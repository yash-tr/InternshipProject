"""
Base agent classes and state management for LangGraph orchestration.

This module provides the foundational classes for all agents in the system,
including state management, communication interfaces, and common functionality.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import logging
import uuid

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    """Types of agents in the system."""
    RESEARCH = "research"
    SCORING = "scoring"
    APPROVAL = "approval"
    CALLING = "calling"
    DEAL_CLOSING = "deal_closing"


class AgentState(TypedDict):
    """
    LangGraph state structure for agent workflow.
    
    This defines the shared state that flows between all agents
    in the workflow graph.
    """
    # Workflow metadata
    workflow_id: str
    current_agent: str
    status: AgentStatus
    created_at: datetime
    updated_at: datetime
    
    # Prospect data
    prospect_id: Optional[str]
    phone_number: Optional[str]
    salesforce_lead_id: Optional[str]
    
    # Research results
    research_data: Dict[str, Any]
    research_confidence: float
    research_sources: List[str]
    
    # Scoring results
    lead_score: int
    scoring_rationale: str
    buying_signals: List[str]
    
    # Approval workflow
    approval_required: bool
    approval_status: Optional[str]
    approver_id: Optional[str]
    approval_timestamp: Optional[datetime]
    
    # Call execution
    call_sid: Optional[str]
    call_status: Optional[str]
    call_attempts: int
    next_call_time: Optional[datetime]
    
    # Deal closing
    deal_stage: str
    conversation_context: List[Dict[str, str]]
    objections_handled: List[str]
    closing_outcome: Optional[str]
    
    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int
    
    # Compliance and audit
    compliance_flags: List[str]
    audit_trail: List[Dict[str, Any]]


class AgentResult(BaseModel):
    """Result structure returned by agent execution."""
    agent_type: AgentType
    status: AgentStatus
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    next_agent: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration for agent execution."""
    agent_type: AgentType
    timeout_seconds: int = 300
    retry_attempts: int = 3
    parallel_execution: bool = False
    dependencies: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the LangGraph workflow.
    
    Provides common functionality for state management, error handling,
    and communication between agents.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id = str(uuid.uuid4())
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{self.agent_id[:8]}")
        
    @abstractmethod
    async def execute(self, state: AgentState) -> AgentResult:
        """
        Execute the agent's main functionality.
        
        Args:
            state: Current workflow state
            
        Returns:
            AgentResult with execution results and next steps
        """
        pass
    
    async def validate_input(self, state: AgentState) -> bool:
        """
        Validate that the agent has all required inputs.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if inputs are valid, False otherwise
        """
        return True
    
    async def handle_error(self, error: Exception, state: AgentState) -> AgentResult:
        """
        Handle errors during agent execution.
        
        Args:
            error: Exception that occurred
            state: Current workflow state
            
        Returns:
            AgentResult with error information
        """
        error_info = {
            "agent_type": self.config.agent_type.value,
            "agent_id": self.agent_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.error(f"Agent execution failed: {error_info}")
        
        return AgentResult(
            agent_type=self.config.agent_type,
            status=AgentStatus.FAILED,
            errors=[str(error)],
            metadata=error_info
        )
    
    def update_state(self, state: AgentState, updates: Dict[str, Any]) -> AgentState:
        """
        Update the workflow state with new data.
        
        Args:
            state: Current workflow state
            updates: Dictionary of updates to apply
            
        Returns:
            Updated state
        """
        # Create audit trail entry
        audit_entry = {
            "agent_type": self.config.agent_type.value,
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "updates": list(updates.keys())
        }
        
        # Update state
        new_state = state.copy()
        new_state.update(updates)
        new_state["updated_at"] = datetime.utcnow()
        new_state["current_agent"] = self.config.agent_type.value
        
        # Add to audit trail
        if "audit_trail" not in new_state:
            new_state["audit_trail"] = []
        new_state["audit_trail"].append(audit_entry)
        
        return new_state
    
    def log_execution(self, state: AgentState, result: AgentResult):
        """
        Log agent execution for monitoring and debugging.
        
        Args:
            state: Workflow state
            result: Agent execution result
        """
        log_data = {
            "workflow_id": state.get("workflow_id"),
            "agent_type": self.config.agent_type.value,
            "agent_id": self.agent_id,
            "status": result.status.value,
            "execution_time": result.execution_time,
            "errors": result.errors,
            "next_agent": result.next_agent
        }
        
        if result.status == AgentStatus.COMPLETED:
            self.logger.info(f"Agent execution completed: {log_data}")
        elif result.status == AgentStatus.FAILED:
            self.logger.error(f"Agent execution failed: {log_data}")
        else:
            self.logger.debug(f"Agent execution status: {log_data}")


class AgentCommunicationInterface:
    """
    Interface for communication between agents and external systems.
    
    Provides methods for agents to communicate with each other,
    external APIs, and the human-in-the-loop system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._message_queue: List[Dict[str, Any]] = []
    
    async def send_message(self, 
                          from_agent: str, 
                          to_agent: str, 
                          message: Dict[str, Any]) -> bool:
        """
        Send a message between agents.
        
        Args:
            from_agent: Source agent identifier
            to_agent: Target agent identifier
            message: Message payload
            
        Returns:
            True if message was sent successfully
        """
        message_envelope = {
            "id": str(uuid.uuid4()),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        self._message_queue.append(message_envelope)
        self.logger.debug(f"Message queued: {from_agent} -> {to_agent}")
        
        return True
    
    async def get_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get pending messages for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            List of pending messages
        """
        messages = [
            msg for msg in self._message_queue 
            if msg["to_agent"] == agent_id and msg["status"] == "pending"
        ]
        
        # Mark messages as delivered
        for msg in messages:
            msg["status"] = "delivered"
            msg["delivered_at"] = datetime.utcnow().isoformat()
        
        return messages
    
    async def notify_human_approval_required(self, 
                                           workflow_id: str, 
                                           approval_data: Dict[str, Any]) -> str:
        """
        Notify human approvers that approval is required.
        
        Args:
            workflow_id: Workflow requiring approval
            approval_data: Data for approval decision
            
        Returns:
            Approval request ID
        """
        approval_id = str(uuid.uuid4())
        
        # In a real implementation, this would send notifications
        # via Slack, email, or dashboard
        self.logger.info(f"Human approval required for workflow {workflow_id}: {approval_id}")
        
        return approval_id
    
    async def check_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Check the status of a human approval request.
        
        Args:
            approval_id: Approval request identifier
            
        Returns:
            Approval status and decision, or None if pending
        """
        # In a real implementation, this would check the approval system
        # For now, return None to indicate pending
        return None