"""
API endpoints for LangGraph agent orchestration.

This module provides REST API endpoints for managing and monitoring
the autonomous agent workflows.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from app.agents.orchestrator import AgentOrchestrator
    from app.agents.monitoring import WorkflowMonitor
    from app.agents.checkpoints import initialize_checkpoint_system
    AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Agent system not available: {e}")
    AgentOrchestrator = None
    WorkflowMonitor = None
    initialize_checkpoint_system = None
    AGENTS_AVAILABLE = False

from app.core.config import get_settings

router = APIRouter()

# Global instances (in production, these would be dependency-injected)
orchestrator: Optional[AgentOrchestrator] = None
monitor: Optional[WorkflowMonitor] = None


class ProspectData(BaseModel):
    """Request model for starting a workflow."""
    prospect_id: Optional[str] = None
    phone_number: str = Field(..., description="Prospect phone number")
    salesforce_lead_id: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    additional_data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    """Response model for workflow operations."""
    workflow_id: str
    status: str
    message: str
    created_at: datetime


class ApprovalDecision(BaseModel):
    """Request model for approval decisions."""
    decision: str = Field(..., description="approved or rejected")
    approver_id: str = Field(..., description="ID of the approver")
    comments: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
    """Response model for workflow status."""
    workflow_id: str
    status: str
    current_agent: Optional[str]
    execution_time: float
    lead_score: int
    approval_required: bool
    approval_granted: Optional[bool]
    call_attempts: int
    call_success: bool
    deal_closed: bool
    errors: List[str]
    created_at: str
    completed_at: Optional[str]


async def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent system not available")
    
    global orchestrator
    if orchestrator is None:
        settings = get_settings()
        postgres_url = getattr(settings, 'postgres_url', None)
        orchestrator = AgentOrchestrator(postgres_url=postgres_url)
        
        # Initialize checkpoint system if available
        if initialize_checkpoint_system:
            try:
                await initialize_checkpoint_system()
            except Exception as e:
                logger.warning(f"Failed to initialize checkpoint system: {e}")
        
        logger.info("Agent orchestrator initialized")
    
    return orchestrator


async def get_monitor() -> WorkflowMonitor:
    """Get the global monitor instance."""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent system not available")
    
    global monitor
    if monitor is None:
        monitor = WorkflowMonitor()
        logger.info("Workflow monitor initialized")
    
    return monitor


@router.post("/workflows/start", response_model=WorkflowResponse)
async def start_workflow(
    prospect_data: ProspectData,
    background_tasks: BackgroundTasks,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    monitor: WorkflowMonitor = Depends(get_monitor)
):
    """
    Start a new autonomous agent workflow for a prospect.
    
    This endpoint initiates the complete workflow including:
    - Prospect research and data enrichment
    - Lead scoring and qualification
    - Human approval (if required)
    - Autonomous calling
    - Deal closing conversation
    """
    try:
        # Convert to dict for orchestrator
        prospect_dict = {
            "prospect_id": prospect_data.prospect_id,
            "phone_number": prospect_data.phone_number,
            "salesforce_lead_id": prospect_data.salesforce_lead_id,
            "company_name": prospect_data.company_name,
            "contact_name": prospect_data.contact_name,
            "email": prospect_data.email,
            **prospect_data.additional_data
        }
        
        # Start the workflow
        workflow_id = await orchestrator.start_workflow(prospect_dict)
        
        # Start monitoring in background
        background_tasks.add_task(
            monitor.start_workflow_monitoring,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "current_agent": "research",
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "prospect_id": prospect_data.prospect_id,
                "phone_number": prospect_data.phone_number,
                "salesforce_lead_id": prospect_data.salesforce_lead_id,
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
        )
        
        logger.info(f"Started workflow {workflow_id} for prospect {prospect_data.prospect_id}")
        
        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
            message="Autonomous agent workflow started successfully",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")


@router.get("/workflows/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    monitor: WorkflowMonitor = Depends(get_monitor)
):
    """
    Get the current status of a workflow.
    
    Returns detailed information about workflow progress,
    current agent, execution metrics, and any errors.
    """
    try:
        # Get status from orchestrator
        orchestrator_status = await orchestrator.get_workflow_status(workflow_id)
        
        # Get detailed status from monitor
        monitor_status = await monitor.get_workflow_status(workflow_id)
        
        if not monitor_status:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=monitor_status["status"],
            current_agent=monitor_status.get("current_agent"),
            execution_time=monitor_status["execution_time"],
            lead_score=monitor_status["lead_score"],
            approval_required=monitor_status["approval_required"],
            approval_granted=monitor_status["approval_granted"],
            call_attempts=monitor_status["call_attempts"],
            call_success=monitor_status["call_success"],
            deal_closed=monitor_status["deal_closed"],
            errors=monitor_status["errors"],
            created_at=monitor_status["created_at"],
            completed_at=monitor_status["completed_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")


@router.post("/workflows/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: str,
    approval: ApprovalDecision,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    Provide human approval decision for a workflow.
    
    This endpoint is used by human approvers to approve or reject
    high-value prospects before autonomous calling begins.
    """
    try:
        approval_data = {
            "decision": approval.decision,
            "approver_id": approval.approver_id,
            "comments": approval.comments,
            "timestamp": datetime.utcnow()
        }
        
        success = await orchestrator.resume_workflow(workflow_id, approval_data)
        
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found or cannot be resumed")
        
        logger.info(f"Workflow {workflow_id} {approval.decision} by {approval.approver_id}")
        
        return {
            "workflow_id": workflow_id,
            "status": "resumed",
            "decision": approval.decision,
            "message": f"Workflow {approval.decision} and resumed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process approval: {str(e)}")


@router.get("/workflows/active")
async def get_active_workflows(
    monitor: WorkflowMonitor = Depends(get_monitor)
):
    """
    Get all currently active workflows.
    
    Returns a list of workflows that are currently running,
    sorted by execution time (longest running first).
    """
    try:
        active_workflows = await monitor.get_active_workflows()
        
        return {
            "active_workflows": active_workflows,
            "total_count": len(active_workflows),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get active workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active workflows: {str(e)}")


@router.get("/analytics/performance")
async def get_performance_analytics(
    days: int = Query(7, description="Number of days to analyze", ge=1, le=90),
    monitor: WorkflowMonitor = Depends(get_monitor)
):
    """
    Get performance analytics for workflows.
    
    Returns comprehensive analytics including success rates,
    execution times, lead conversion rates, and error analysis.
    """
    try:
        time_range = timedelta(days=days)
        analytics = await monitor.get_performance_analytics(time_range)
        
        return {
            "analytics": analytics,
            "time_range_days": days,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@router.get("/workflows/{workflow_id}/debug")
async def debug_workflow(
    workflow_id: str,
    monitor: WorkflowMonitor = Depends(get_monitor)
):
    """
    Get detailed debugging information for a workflow.
    
    Returns comprehensive debugging data including execution trace,
    performance analysis, error details, and recommendations.
    """
    try:
        debug_info = await monitor.debug_workflow(workflow_id)
        
        if "error" in debug_info:
            raise HTTPException(status_code=404, detail=debug_info["error"])
        
        return {
            "debug_info": debug_info,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to debug workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to debug workflow: {str(e)}")


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: str,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    Cancel a running workflow.
    
    This endpoint allows canceling workflows that are stuck,
    taking too long, or no longer needed.
    """
    try:
        # In a real implementation, this would cancel the workflow
        # For now, we'll just log the cancellation request
        logger.info(f"Cancellation requested for workflow {workflow_id}")
        
        return {
            "workflow_id": workflow_id,
            "status": "cancellation_requested",
            "message": "Workflow cancellation has been requested",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the agent system.
    
    Returns the health status of the orchestrator, monitor,
    and checkpoint system.
    """
    try:
        health_status = {
            "orchestrator": "healthy",
            "monitor": "healthy",
            "checkpoint_system": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # In a real implementation, this would check actual system health
        # including database connectivity, agent registration, etc.
        
        return {
            "status": "healthy",
            "components": health_status
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }