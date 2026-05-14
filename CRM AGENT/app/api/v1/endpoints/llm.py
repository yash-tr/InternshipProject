"""
API endpoints for LLM service management and monitoring.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from app.schemas.llm import (
    LLMRequestCreate, LLMResponseResponse, LLMHealthCheck, LLMUsageStats,
    ConversationAnalysisResponse, LeadScoringResponse, ConversationSessionResponse
)
from app.services.openrouter_llm import openrouter_llm_service
from app.core.config import get_settings


logger = structlog.get_logger()
router = APIRouter()


@router.post("/generate", response_model=Dict[str, Any])
async def generate_llm_response(
    request: LLMRequestCreate,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Generate AI response for conversation turn.
    
    This endpoint is primarily for testing and debugging.
    Normal conversation flow uses the call handler service.
    """
    try:
        response_text, tokens_used, analysis_data = await openrouter_llm_service.generate_response(
            call_sid=request.call_sid,
            user_input=request.user_input,
            contact_context=request.contact_context,
            conversation_context=None  # Would be provided by call handler
        )
        
        return {
            "response_text": response_text,
            "tokens_used": tokens_used,
            "analysis_data": analysis_data,
            "call_sid": request.call_sid,
            "model_name": openrouter_llm_service.model_name
        }
        
    except Exception as e:
        logger.error(
            "Failed to generate LLM response via API",
            call_sid=request.call_sid,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.post("/analyze-intent", response_model=Dict[str, Any])
async def analyze_conversation_intent(
    call_sid: str,
    conversation_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Analyze conversation intent and extract insights.
    """
    try:
        analysis = await openrouter_llm_service.analyze_conversation_intent(
            call_sid=call_sid,
            conversation_history=conversation_history
        )
        
        return {
            "call_sid": call_sid,
            "analysis": analysis,
            "timestamp": analysis.get('timestamp')
        }
        
    except Exception as e:
        logger.error(
            "Failed to analyze conversation intent",
            call_sid=call_sid,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze intent: {str(e)}"
        )


@router.post("/calculate-lead-score", response_model=Dict[str, Any])
async def calculate_lead_score(
    call_sid: str
) -> Dict[str, Any]:
    """
    Calculate lead qualification score for active conversation.
    """
    try:
        # Check if session exists
        if call_sid not in openrouter_llm_service.active_sessions:
            raise HTTPException(
                status_code=404,
                detail="No active conversation session found"
            )
        
        lead_score, rationale = await openrouter_llm_service.calculate_lead_score(
            call_sid=call_sid,
            conversation_context=None  # Uses active session
        )
        
        return {
            "call_sid": call_sid,
            "lead_score": lead_score,
            "rationale": rationale,
            "max_score": 100
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to calculate lead score",
            call_sid=call_sid,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate lead score: {str(e)}"
        )


@router.get("/sessions", response_model=Dict[str, Any])
async def get_active_sessions() -> Dict[str, Any]:
    """
    Get information about active conversation sessions.
    """
    try:
        sessions_info = {}
        
        for call_sid, session in openrouter_llm_service.active_sessions.items():
            sessions_info[call_sid] = {
                "call_sid": call_sid,
                "message_count": len(session.conversation_history),
                "lead_score": session.lead_score,
                "current_intent": session.current_intent,
                "buying_signals": session.buying_signals,
                "tokens_used": session.token_usage.total_tokens,
                "cost_estimate": session.token_usage.cost_estimate,
                "duration_minutes": (session.last_updated - session.created_at).total_seconds() / 60,
                "last_updated": session.last_updated.isoformat()
            }
        
        return {
            "active_sessions": sessions_info,
            "total_sessions": len(sessions_info),
            "timestamp": openrouter_llm_service.daily_usage.last_reset.isoformat() if hasattr(openrouter_llm_service.daily_usage, 'last_reset') else None
        }
        
    except Exception as e:
        logger.error("Failed to get active sessions", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sessions: {str(e)}"
        )


@router.get("/session/{call_sid}", response_model=Dict[str, Any])
async def get_session_details(call_sid: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific conversation session.
    """
    try:
        if call_sid not in openrouter_llm_service.active_sessions:
            raise HTTPException(
                status_code=404,
                detail="Conversation session not found"
            )
        
        summary = await openrouter_llm_service.get_conversation_summary(call_sid)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get session details",
            call_sid=call_sid,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session details: {str(e)}"
        )


@router.delete("/session/{call_sid}")
async def cleanup_session(call_sid: str) -> Dict[str, str]:
    """
    Manually cleanup a conversation session.
    """
    try:
        if call_sid not in openrouter_llm_service.active_sessions:
            raise HTTPException(
                status_code=404,
                detail="Conversation session not found"
            )
        
        await openrouter_llm_service.cleanup_session(call_sid)
        
        return {
            "message": f"Session {call_sid} cleaned up successfully",
            "call_sid": call_sid
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to cleanup session",
            call_sid=call_sid,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup session: {str(e)}"
        )


@router.get("/usage", response_model=LLMUsageStats)
async def get_usage_statistics() -> LLMUsageStats:
    """
    Get current LLM usage statistics and costs.
    """
    try:
        stats = await openrouter_llm_service.get_token_usage_stats()
        
        return LLMUsageStats(
            daily_usage=stats['daily_usage'],
            total_usage=stats['total_usage'],
            active_sessions=stats['active_sessions'],
            model_name=stats['model_name'],
            reset_date=stats['daily_usage']['reset_date'],
            last_updated=stats['last_updated']
        )
        
    except Exception as e:
        logger.error("Failed to get usage statistics", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get usage statistics: {str(e)}"
        )


@router.get("/health", response_model=LLMHealthCheck)
async def get_llm_health() -> LLMHealthCheck:
    """
    Get LLM service health status and performance metrics.
    """
    try:
        from app.core.health import check_llm_service_health
        
        health_data = await check_llm_service_health()
        
        return LLMHealthCheck(
            service_name="OpenRouter LLM Service",
            status=health_data['status'],
            model_name=health_data.get('model_name', 'unknown'),
            api_accessible=health_data['status'] == 'healthy',
            daily_token_usage=health_data.get('daily_tokens', 0),
            daily_cost_estimate=health_data.get('daily_cost', 0.0),
            active_sessions=health_data.get('active_sessions', 0),
            error_message=health_data.get('error')
        )
        
    except Exception as e:
        logger.error("Failed to get LLM health status", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get health status: {str(e)}"
        )


@router.post("/test-connection")
async def test_llm_connection() -> Dict[str, Any]:
    """
    Test LLM service connection with a simple request.
    """
    try:
        test_call_sid = "TEST_CONNECTION_CALL"
        test_input = "Hello, this is a connection test."
        
        response_text, tokens_used, analysis_data = await openrouter_llm_service.generate_response(
            call_sid=test_call_sid,
            user_input=test_input
        )
        
        # Cleanup test session
        await openrouter_llm_service.cleanup_session(test_call_sid)
        
        return {
            "status": "success",
            "message": "LLM service connection successful",
            "test_response": response_text,
            "tokens_used": tokens_used,
            "model_name": openrouter_llm_service.model_name
        }
        
    except Exception as e:
        logger.error("LLM connection test failed", error=str(e))
        return {
            "status": "error",
            "message": "LLM service connection failed",
            "error": str(e)
        }


@router.get("/models")
async def get_available_models() -> Dict[str, Any]:
    """
    Get information about available LLM models.
    """
    try:
        settings = get_settings()
        
        return {
            "current_model": settings.OPENROUTER_MODEL,
            "provider": "OpenRouter",
            "api_base": "https://openrouter.ai/api/v1",
            "supported_models": [
                "anthropic/claude-3.5-sonnet",
                "anthropic/claude-3-haiku",
                "mistralai/mistral-nemo:free",
                "openai/gpt-4o-mini",
                "openai/gpt-3.5-turbo"
            ],
            "current_settings": {
                "max_tokens": openrouter_llm_service.max_tokens,
                "temperature": openrouter_llm_service.temperature,
                "context_window_limit": openrouter_llm_service.context_window_limit
            }
        }
        
    except Exception as e:
        logger.error("Failed to get model information", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model information: {str(e)}"
        )