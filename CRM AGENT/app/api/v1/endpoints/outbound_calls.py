"""
Outbound Calls API endpoints for managing autonomous call execution.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Form
from pydantic import BaseModel, Field

from ....services.outbound_call_manager import (
    outbound_call_manager, CallPriority, CallStatus, CallAttemptResult
)
from ....schemas.prospect_research import ResearchResultSchema
from ....core.config import get_settings

router = APIRouter()
settings = get_settings()


class ScheduleCallRequest(BaseModel):
    """Request model for scheduling outbound calls."""
    prospect_id: str = Field(..., description="Unique prospect identifier")
    phone_number: str = Field(..., description="Phone number to call")
    research_data: Dict[str, Any] = Field(..., description="Prospect research data")
    priority: CallPriority = Field(CallPriority.MEDIUM, description="Call priority level")
    preferred_time: Optional[datetime] = Field(None, description="Preferred call time")


class CallStatusResponse(BaseModel):
    """Response model for call status."""
    task_id: str
    prospect_id: str
    phone_number: str
    status: str
    priority: str
    attempt_count: int
    max_attempts: int
    scheduled_time: Optional[str]
    next_retry_time: Optional[str]
    attempts: List[Dict[str, Any]]


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    budget: Dict[str, Any]
    queue: Dict[str, int]
    active_calls: int
    completed_calls: int
    processing: bool


@router.post("/schedule", response_model=Dict[str, str])
async def schedule_outbound_call(
    request: ScheduleCallRequest,
    background_tasks: BackgroundTasks
):
    """
    Schedule an outbound call for a prospect.
    
    Args:
        request: Call scheduling request
        background_tasks: FastAPI background tasks
        
    Returns:
        Dict containing the task ID
    """
    try:
        # Convert research data to ResearchResultSchema if needed
        research_data = request.research_data
        if isinstance(research_data, dict):
            # Create a minimal ResearchResultSchema from dict
            research_result = type('ResearchResult', (), research_data)()
        else:
            research_result = research_data
        
        # Schedule the call
        task_id = await outbound_call_manager.schedule_call(
            prospect_id=request.prospect_id,
            phone_number=request.phone_number,
            research_data=research_result,
            priority=request.priority,
            preferred_time=request.preferred_time
        )
        
        return {
            "task_id": task_id,
            "status": "scheduled",
            "message": f"Call scheduled for prospect {request.prospect_id}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule call: {str(e)}"
        )


@router.get("/task/{task_id}", response_model=CallStatusResponse)
async def get_call_task_status(task_id: str):
    """
    Get the status of a specific call task.
    
    Args:
        task_id: Call task identifier
        
    Returns:
        Call task status information
    """
    try:
        status = await outbound_call_manager.get_task_status(task_id)
        
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Call task {task_id} not found"
            )
        
        return CallStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Get overall outbound calling system status.
    
    Returns:
        System status including budget, queue, and call metrics
    """
    try:
        status = await outbound_call_manager.get_system_status()
        return SystemStatusResponse(**status)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.post("/start-processing")
async def start_call_processing(background_tasks: BackgroundTasks):
    """
    Start the call processing loop.
    
    Returns:
        Success message
    """
    try:
        background_tasks.add_task(outbound_call_manager.start_call_processing)
        
        return {
            "status": "started",
            "message": "Call processing loop started"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start call processing: {str(e)}"
        )


@router.post("/stop-processing")
async def stop_call_processing():
    """
    Stop the call processing loop.
    
    Returns:
        Success message
    """
    try:
        await outbound_call_manager.stop_call_processing()
        
        return {
            "status": "stopped",
            "message": "Call processing loop stopped"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop call processing: {str(e)}"
        )


@router.post("/webhook/status/{task_id}")
async def handle_call_status_webhook(
    task_id: str,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    TranscriptionText: Optional[str] = Form(None)
):
    """
    Handle call status updates from Twilio webhooks.
    
    Args:
        task_id: Call task identifier
        CallSid: Twilio Call SID
        CallStatus: Current call status
        CallDuration: Call duration in seconds
        TranscriptionText: Call transcription if available
        
    Returns:
        Success acknowledgment
    """
    try:
        # Parse duration
        duration = None
        if CallDuration:
            try:
                duration = int(CallDuration)
            except ValueError:
                pass
        
        # Handle the status update
        await outbound_call_manager.handle_call_status_update(
            task_id=task_id,
            call_sid=CallSid,
            status=CallStatus,
            duration=duration,
            transcription=TranscriptionText
        )
        
        return {
            "status": "received",
            "message": f"Status update processed for call {CallSid}"
        }
        
    except Exception as e:
        # Log error but don't fail the webhook
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing call status webhook: {e}")
        
        return {
            "status": "error",
            "message": f"Failed to process status update: {str(e)}"
        }


@router.get("/queue/status")
async def get_queue_status():
    """
    Get current call queue status.
    
    Returns:
        Queue status by priority level
    """
    try:
        queue_status = await outbound_call_manager.call_queue.get_queue_status()
        
        return {
            "queue_status": queue_status,
            "total_queued": sum(queue_status.values()),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue status: {str(e)}"
        )


@router.get("/budget/status")
async def get_budget_status():
    """
    Get current budget status and limits.
    
    Returns:
        Budget status including daily limits and usage
    """
    try:
        budget_status = await outbound_call_manager.budget_controller.get_budget_status()
        
        return {
            "budget_status": budget_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get budget status: {str(e)}"
        )


@router.delete("/task/{task_id}")
async def cancel_call_task(task_id: str):
    """
    Cancel a scheduled call task.
    
    Args:
        task_id: Call task identifier
        
    Returns:
        Cancellation confirmation
    """
    try:
        # Remove from queue
        removed = await outbound_call_manager.call_queue.remove_task(task_id)
        
        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"Call task {task_id} not found or already completed"
            )
        
        return {
            "status": "cancelled",
            "task_id": task_id,
            "message": f"Call task {task_id} has been cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel call task: {str(e)}"
        )


@router.post("/bulk-schedule")
async def bulk_schedule_calls(
    requests: List[ScheduleCallRequest],
    background_tasks: BackgroundTasks
):
    """
    Schedule multiple outbound calls in bulk.
    
    Args:
        requests: List of call scheduling requests
        background_tasks: FastAPI background tasks
        
    Returns:
        List of scheduled task IDs and any errors
    """
    try:
        results = []
        errors = []
        
        for i, request in enumerate(requests):
            try:
                # Convert research data
                research_data = request.research_data
                if isinstance(research_data, dict):
                    research_result = type('ResearchResult', (), research_data)()
                else:
                    research_result = research_data
                
                # Schedule the call
                task_id = await outbound_call_manager.schedule_call(
                    prospect_id=request.prospect_id,
                    phone_number=request.phone_number,
                    research_data=research_result,
                    priority=request.priority,
                    preferred_time=request.preferred_time
                )
                
                results.append({
                    "index": i,
                    "prospect_id": request.prospect_id,
                    "task_id": task_id,
                    "status": "scheduled"
                })
                
            except Exception as e:
                errors.append({
                    "index": i,
                    "prospect_id": request.prospect_id,
                    "error": str(e)
                })
        
        return {
            "scheduled": len(results),
            "errors": len(errors),
            "results": results,
            "errors_detail": errors
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to bulk schedule calls: {str(e)}"
        )


@router.get("/metrics/daily")
async def get_daily_metrics():
    """
    Get daily call metrics and performance data.
    
    Returns:
        Daily metrics including call volume, success rates, and costs
    """
    try:
        budget_status = await outbound_call_manager.budget_controller.get_budget_status()
        
        # Calculate success rates from call history
        call_history = outbound_call_manager.call_history
        
        total_calls = len(call_history)
        successful_calls = sum(
            1 for task in call_history.values()
            if any(att.result == CallAttemptResult.SUCCESS for att in task.attempts)
        )
        voicemail_calls = sum(
            1 for task in call_history.values()
            if any(att.result == CallAttemptResult.VOICEMAIL for att in task.attempts)
        )
        
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        answer_rate = ((successful_calls + voicemail_calls) / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "date": datetime.utcnow().date().isoformat(),
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "voicemail_calls": voicemail_calls,
            "success_rate_percent": round(success_rate, 2),
            "answer_rate_percent": round(answer_rate, 2),
            "total_cost_cents": budget_status.get("total_cost_cents", 0),
            "daily_budget_used_percent": round(
                (budget_status.get("daily_calls_made", 0) / 
                 outbound_call_manager.budget_controller.limits.max_daily_calls * 100), 2
            )
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily metrics: {str(e)}"
        )