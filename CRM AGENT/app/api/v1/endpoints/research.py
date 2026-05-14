"""
API endpoints for prospect research functionality.

This module provides REST API endpoints for triggering prospect research,
checking research status, and retrieving research results.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ....agents.orchestrator import AgentOrchestrator
from ....agents.prospect_research import create_research_agent
from ....schemas.prospect_research import (
    ResearchRequest,
    ResearchStatus,
    ResearchResultSchema,
    DataSource
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Global orchestrator instance (in production, this would be dependency injected)
orchestrator = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the agent orchestrator."""
    global orchestrator
    if orchestrator is None:
        postgres_url = None  # For testing, disable PostgreSQL checkpoints
        orchestrator = AgentOrchestrator(postgres_url=postgres_url)
    return orchestrator


class ResearchTriggerRequest(BaseModel):
    """Request to trigger prospect research."""
    
    prospect_id: str = Field(..., description="Unique prospect identifier")
    phone_number: Optional[str] = Field(None, description="Prospect phone number")
    email: Optional[str] = Field(None, description="Prospect email")
    company_name: Optional[str] = Field(None, description="Company name")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    salesforce_lead_id: Optional[str] = Field(None, description="Salesforce lead ID")
    
    # Research parameters
    research_depth: str = Field("standard", description="Research depth level")
    max_duration: int = Field(300, description="Maximum research duration in seconds")
    required_sources: List[DataSource] = Field(default_factory=list, description="Required data sources")


class ResearchResponse(BaseModel):
    """Response for research operations."""
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    workflow_id: Optional[str] = Field(None, description="Workflow identifier")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/trigger", response_model=ResearchResponse)
async def trigger_prospect_research(
    request: ResearchTriggerRequest,
    background_tasks: BackgroundTasks,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> ResearchResponse:
    """
    Trigger prospect research for a given prospect.
    
    This endpoint starts an autonomous research workflow that will:
    1. Research LinkedIn profile information
    2. Gather company intelligence
    3. Scrape web data for additional insights
    4. Collect social signals and buying intent
    5. Calculate confidence scores and decision maker likelihood
    
    Args:
        request: Research trigger request
        background_tasks: FastAPI background tasks
        orchestrator: Agent orchestrator instance
        
    Returns:
        Research response with workflow ID
    """
    try:
        logger.info(f"Triggering research for prospect {request.prospect_id}")
        
        # Validate request
        if not any([request.phone_number, request.email, request.company_name, request.linkedin_url]):
            raise HTTPException(
                status_code=400,
                detail="At least one identifier (phone, email, company name, or LinkedIn URL) is required"
            )
        
        # Prepare prospect data
        prospect_data = {
            "prospect_id": request.prospect_id,
            "phone_number": request.phone_number,
            "email": request.email,
            "company_name": request.company_name,
            "linkedin_url": request.linkedin_url,
            "salesforce_lead_id": request.salesforce_lead_id,
            "research_depth": request.research_depth,
            "max_duration": request.max_duration,
            "required_sources": [source.value for source in request.required_sources]
        }
        
        # Start workflow
        workflow_id = await orchestrator.start_workflow(prospect_data)
        
        logger.info(f"Started research workflow {workflow_id} for prospect {request.prospect_id}")
        
        return ResearchResponse(
            success=True,
            message=f"Research workflow started for prospect {request.prospect_id}",
            workflow_id=workflow_id,
            data={
                "prospect_id": request.prospect_id,
                "estimated_duration": request.max_duration,
                "research_depth": request.research_depth
            }
        )
        
    except Exception as e:
        logger.error(f"Error triggering research for prospect {request.prospect_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger research: {str(e)}"
        )


@router.get("/status/{workflow_id}", response_model=ResearchStatus)
async def get_research_status(
    workflow_id: str,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> ResearchStatus:
    """
    Get the status of a research workflow.
    
    Args:
        workflow_id: Workflow identifier
        orchestrator: Agent orchestrator instance
        
    Returns:
        Research status information
    """
    try:
        status_info = await orchestrator.get_workflow_status(workflow_id)
        
        if not status_info:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Map orchestrator status to research status
        status_mapping = {
            "pending": "pending",
            "running": "in_progress",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled"
        }
        
        mapped_status = status_mapping.get(status_info["status"], "pending")
        
        return ResearchStatus(
            prospect_id=status_info.get("prospect_id", "unknown"),
            status=mapped_status,
            progress=0.8 if mapped_status == "in_progress" else (1.0 if mapped_status == "completed" else 0.0),
            current_source=DataSource.LINKEDIN if mapped_status == "in_progress" else None,
            estimated_completion=None,
            error_message=status_info.get("errors", [])[-1] if status_info.get("errors") else None,
            preliminary_confidence=status_info.get("lead_score", 0) / 100.0,
            sources_completed=[DataSource.LINKEDIN, DataSource.COMPANY_WEBSITE] if mapped_status != "pending" else []
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research status for workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get research status: {str(e)}"
        )


@router.get("/results/{workflow_id}", response_model=ResearchResponse)
async def get_research_results(
    workflow_id: str,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> ResearchResponse:
    """
    Get the results of a completed research workflow.
    
    Args:
        workflow_id: Workflow identifier
        orchestrator: Agent orchestrator instance
        
    Returns:
        Research results
    """
    try:
        status_info = await orchestrator.get_workflow_status(workflow_id)
        
        if not status_info:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found"
            )
        
        if status_info["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Workflow {workflow_id} is not completed (status: {status_info['status']})"
            )
        
        # In a real implementation, this would fetch the complete research results
        # from the database. For now, return a placeholder response.
        return ResearchResponse(
            success=True,
            message=f"Research results for workflow {workflow_id}",
            workflow_id=workflow_id,
            data={
                "workflow_id": workflow_id,
                "status": status_info["status"],
                "lead_score": status_info.get("lead_score", 0),
                "confidence": status_info.get("research_confidence", 0.0),
                "sources_used": ["linkedin", "company_website", "web_scraping"],
                "research_completed_at": status_info.get("updated_at"),
                "note": "Complete research data would be available in production implementation"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research results for workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get research results: {str(e)}"
        )


@router.post("/test", response_model=ResearchResponse)
async def test_research_agent(
    prospect_id: str = Query(..., description="Test prospect ID"),
    phone_number: str = Query("+1234567890", description="Test phone number")
) -> ResearchResponse:
    """
    Test endpoint for the research agent (development only).
    
    This endpoint directly tests the research agent without the full workflow.
    
    Args:
        prospect_id: Test prospect identifier
        phone_number: Test phone number
        
    Returns:
        Test research results
    """
    try:
        logger.info(f"Testing research agent for prospect {prospect_id}")
        
        # Create test research agent
        research_agent = create_research_agent({
            "timeout_seconds": 60,
            "retry_attempts": 1
        })
        
        # Create test state
        test_state = {
            "workflow_id": f"test_{prospect_id}",
            "prospect_id": prospect_id,
            "phone_number": phone_number,
            "salesforce_lead_id": f"lead_{prospect_id}",
            "current_agent": "research",
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "research_data": {"company_name": "Test Company"},
            "research_confidence": 0.0,
            "research_sources": [],
            "errors": [],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        # Execute research agent
        result = await research_agent.execute(test_state)
        
        return ResearchResponse(
            success=result.status.value == "completed",
            message=f"Research agent test {'completed' if result.status.value == 'completed' else 'failed'}",
            workflow_id=f"test_{prospect_id}",
            data={
                "agent_type": result.agent_type.value,
                "status": result.status.value,
                "execution_time": result.execution_time,
                "confidence_score": result.metadata.get("confidence_score", 0.0),
                "sources_used": result.metadata.get("sources_used", 0),
                "errors": result.errors,
                "research_data_keys": list(result.data.get("research_data", {}).keys()) if result.data else []
            }
        )
        
    except Exception as e:
        logger.error(f"Error testing research agent for prospect {prospect_id}: {e}")
        return ResearchResponse(
            success=False,
            message=f"Research agent test failed: {str(e)}",
            workflow_id=f"test_{prospect_id}",
            data={"error": str(e)}
        )


@router.get("/sources", response_model=List[str])
async def get_available_data_sources() -> List[str]:
    """
    Get list of available data sources for research.
    
    Returns:
        List of available data source names
    """
    return [source.value for source in DataSource]


@router.get("/health")
async def research_health_check() -> Dict[str, Any]:
    """
    Health check endpoint for research service.
    
    Returns:
        Health status information
    """
    try:
        # Test research agent creation
        test_agent = create_research_agent()
        
        return {
            "status": "healthy",
            "service": "prospect_research",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_initialized": test_agent is not None,
            "available_sources": len(DataSource),
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Research health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "prospect_research",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }