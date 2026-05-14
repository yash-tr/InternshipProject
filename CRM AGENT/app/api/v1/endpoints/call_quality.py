"""
Call Quality Monitoring API endpoints.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field

from ....services.call_quality_monitor import (
    call_quality_monitor, 
    OptimizationSettings,
    CallQualityLevel,
    AudioIssueType,
    OptimizationAction
)

router = APIRouter()


class StartMonitoringRequest(BaseModel):
    """Request model for starting call monitoring."""
    call_sid: str = Field(..., description="Twilio Call SID")
    optimization_settings: Optional[OptimizationSettings] = Field(None, description="Initial optimization settings")


class AudioMetricsRequest(BaseModel):
    """Request model for recording audio metrics."""
    call_sid: str = Field(..., description="Twilio Call SID")
    sample_rate: int = Field(8000, description="Audio sample rate")


class PerformanceMetricsRequest(BaseModel):
    """Request model for recording performance metrics."""
    call_sid: str = Field(..., description="Twilio Call SID")
    stt_latency_ms: float = Field(..., description="Speech-to-text latency in milliseconds")
    tts_latency_ms: float = Field(..., description="Text-to-speech latency in milliseconds")
    response_generation_ms: float = Field(..., description="AI response generation time in milliseconds")
    stt_confidence: float = Field(1.0, description="STT confidence score (0.0 to 1.0)")
    connection_quality: float = Field(1.0, description="Network connection quality (0.0 to 1.0)")


class CallQualityResponse(BaseModel):
    """Response model for call quality analysis."""
    call_sid: str
    timestamp: str
    overall_score: float
    quality_level: str
    audio_quality_score: float
    performance_score: float
    detected_issues: List[str]
    optimization_actions: List[str]


class SystemMetricsResponse(BaseModel):
    """Response model for system metrics."""
    active_monitored_calls: int
    average_quality_score: float
    current_issue_counts: Dict[str, int]
    total_calls_monitored: int
    system_status: str


@router.post("/start", response_model=Dict[str, str])
async def start_call_monitoring(request: StartMonitoringRequest):
    """
    Start monitoring call quality for a specific call.
    
    Args:
        request: Monitoring start request
        
    Returns:
        Success confirmation
    """
    try:
        session = await call_quality_monitor.start_monitoring(
            call_sid=request.call_sid,
            initial_settings=request.optimization_settings
        )
        
        return {
            "status": "started",
            "call_sid": session.call_sid,
            "start_time": session.start_time.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start call monitoring: {str(e)}"
        )


@router.post("/audio-metrics", response_model=Dict[str, Any])
async def record_audio_metrics(
    request: AudioMetricsRequest,
    audio_file: UploadFile = File(...)
):
    """
    Record audio metrics from audio data.
    
    Args:
        request: Audio metrics request
        audio_file: Audio file to analyze
        
    Returns:
        Audio metrics analysis
    """
    try:
        # Read audio data
        audio_data = await audio_file.read()
        
        # Analyze audio metrics
        metrics = await call_quality_monitor.record_audio_metrics(
            call_sid=request.call_sid,
            audio_data=audio_data,
            sample_rate=request.sample_rate
        )
        
        return {
            "call_sid": request.call_sid,
            "timestamp": metrics.timestamp.isoformat(),
            "volume_level": metrics.volume_level,
            "noise_level": metrics.noise_level,
            "signal_to_noise_ratio": metrics.signal_to_noise_ratio,
            "frequency_response": metrics.frequency_response,
            "distortion_level": metrics.distortion_level,
            "echo_detected": metrics.echo_detected,
            "dropout_count": metrics.dropout_count,
            "quality_score": metrics.quality_score
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record audio metrics: {str(e)}"
        )


@router.post("/performance-metrics", response_model=Dict[str, Any])
async def record_performance_metrics(request: PerformanceMetricsRequest):
    """
    Record performance metrics for a call turn.
    
    Args:
        request: Performance metrics request
        
    Returns:
        Performance metrics analysis
    """
    try:
        metrics = await call_quality_monitor.record_performance_metrics(
            call_sid=request.call_sid,
            stt_latency_ms=request.stt_latency_ms,
            tts_latency_ms=request.tts_latency_ms,
            response_generation_ms=request.response_generation_ms,
            stt_confidence=request.stt_confidence,
            connection_quality=request.connection_quality
        )
        
        return {
            "call_sid": request.call_sid,
            "timestamp": metrics.timestamp.isoformat(),
            "stt_latency_ms": metrics.stt_latency_ms,
            "tts_latency_ms": metrics.tts_latency_ms,
            "response_generation_ms": metrics.response_generation_ms,
            "total_turn_latency_ms": metrics.total_turn_latency_ms,
            "stt_confidence": metrics.stt_confidence,
            "stt_word_error_rate": metrics.stt_word_error_rate,
            "connection_quality": metrics.connection_quality,
            "packet_loss_rate": metrics.packet_loss_rate,
            "jitter_ms": metrics.jitter_ms,
            "performance_score": metrics.performance_score
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record performance metrics: {str(e)}"
        )


@router.get("/analyze/{call_sid}", response_model=CallQualityResponse)
async def analyze_call_quality(call_sid: str):
    """
    Analyze current call quality and get recommendations.
    
    Args:
        call_sid: Twilio Call SID
        
    Returns:
        Call quality analysis and recommendations
    """
    try:
        snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"No quality data found for call {call_sid}"
            )
        
        return CallQualityResponse(
            call_sid=snapshot.call_sid,
            timestamp=snapshot.timestamp.isoformat(),
            overall_score=snapshot.overall_score,
            quality_level=snapshot.quality_level.value,
            audio_quality_score=snapshot.audio_metrics.quality_score,
            performance_score=snapshot.performance_metrics.performance_score,
            detected_issues=[issue.value for issue in snapshot.detected_issues],
            optimization_actions=[action.value for action in snapshot.optimization_actions]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze call quality: {str(e)}"
        )


@router.delete("/stop/{call_sid}")
async def stop_call_monitoring(call_sid: str):
    """
    Stop monitoring call quality and get final report.
    
    Args:
        call_sid: Twilio Call SID
        
    Returns:
        Final call quality report
    """
    try:
        report = await call_quality_monitor.stop_monitoring(call_sid)
        
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring session found for call {call_sid}"
            )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop call monitoring: {str(e)}"
        )


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics():
    """
    Get system-wide call quality metrics.
    
    Returns:
        System metrics and performance data
    """
    try:
        metrics = await call_quality_monitor.get_system_metrics()
        return SystemMetricsResponse(**metrics)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system metrics: {str(e)}"
        )


@router.get("/history/{call_sid}")
async def get_call_quality_history(call_sid: str, limit: int = 50):
    """
    Get call quality history for a specific call.
    
    Args:
        call_sid: Twilio Call SID
        limit: Maximum number of snapshots to return
        
    Returns:
        Call quality history
    """
    try:
        history = call_quality_monitor.quality_history.get(call_sid, [])
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No quality history found for call {call_sid}"
            )
        
        # Return latest snapshots up to limit
        recent_history = list(history)[-limit:]
        
        return {
            "call_sid": call_sid,
            "total_snapshots": len(history),
            "returned_snapshots": len(recent_history),
            "history": [
                {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "overall_score": snapshot.overall_score,
                    "quality_level": snapshot.quality_level.value,
                    "audio_quality_score": snapshot.audio_metrics.quality_score,
                    "performance_score": snapshot.performance_metrics.performance_score,
                    "detected_issues": [issue.value for issue in snapshot.detected_issues],
                    "optimization_actions": [action.value for action in snapshot.optimization_actions]
                }
                for snapshot in recent_history
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get call quality history: {str(e)}"
        )


@router.get("/settings/{call_sid}")
async def get_optimization_settings(call_sid: str):
    """
    Get current optimization settings for a call.
    
    Args:
        call_sid: Twilio Call SID
        
    Returns:
        Current optimization settings
    """
    try:
        session = call_quality_monitor.active_monitors.get(call_sid)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring session found for call {call_sid}"
            )
        
        return {
            "call_sid": call_sid,
            "settings": session.settings.__dict__,
            "session_start_time": session.start_time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get optimization settings: {str(e)}"
        )


@router.put("/settings/{call_sid}")
async def update_optimization_settings(call_sid: str, settings: OptimizationSettings):
    """
    Update optimization settings for a call.
    
    Args:
        call_sid: Twilio Call SID
        settings: New optimization settings
        
    Returns:
        Success confirmation
    """
    try:
        session = call_quality_monitor.active_monitors.get(call_sid)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring session found for call {call_sid}"
            )
        
        # Update settings
        session.settings = settings
        
        return {
            "status": "updated",
            "call_sid": call_sid,
            "new_settings": settings.__dict__
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update optimization settings: {str(e)}"
        )


@router.get("/issues")
async def get_issue_types():
    """
    Get all available audio issue types.
    
    Returns:
        List of audio issue types and their descriptions
    """
    try:
        issue_descriptions = {
            AudioIssueType.HIGH_LATENCY: "Response latency exceeds acceptable thresholds",
            AudioIssueType.LOW_VOLUME: "Audio volume is too low for clear communication",
            AudioIssueType.BACKGROUND_NOISE: "Excessive background noise detected",
            AudioIssueType.ECHO: "Echo or feedback detected in audio",
            AudioIssueType.DISTORTION: "Audio distortion or clipping detected",
            AudioIssueType.DROPOUTS: "Audio dropouts or silence periods detected",
            AudioIssueType.POOR_STT_ACCURACY: "Speech-to-text accuracy is below threshold",
            AudioIssueType.TTS_DELAYS: "Text-to-speech generation is too slow"
        }
        
        return {
            "issue_types": [
                {
                    "type": issue.value,
                    "description": issue_descriptions[issue]
                }
                for issue in AudioIssueType
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get issue types: {str(e)}"
        )


@router.get("/actions")
async def get_optimization_actions():
    """
    Get all available optimization actions.
    
    Returns:
        List of optimization actions and their descriptions
    """
    try:
        action_descriptions = {
            OptimizationAction.ADJUST_AUDIO_SETTINGS: "Adjust volume, echo cancellation, and other audio parameters",
            OptimizationAction.SWITCH_TTS_MODEL: "Switch to a faster or higher quality TTS model",
            OptimizationAction.REDUCE_RESPONSE_LENGTH: "Reduce AI response length to improve latency",
            OptimizationAction.INCREASE_TIMEOUT: "Increase timeout values to handle slow connections",
            OptimizationAction.ENABLE_NOISE_REDUCTION: "Enable noise reduction processing",
            OptimizationAction.FALLBACK_TO_HUMAN: "Transfer call to human agent due to quality issues"
        }
        
        return {
            "optimization_actions": [
                {
                    "action": action.value,
                    "description": action_descriptions[action]
                }
                for action in OptimizationAction
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get optimization actions: {str(e)}"
        )