"""
Objection Handling API endpoints.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ....services.objection_handler import (
    enhanced_objection_handler,
    ObjectionType,
    ObjectionSeverity,
    ResponseStrategy
)

router = APIRouter()


class HandleObjectionRequest(BaseModel):
    """Request model for handling objections."""
    call_sid: str = Field(..., description="Call identifier")
    user_input: str = Field(..., description="User's objection text")
    prospect_data: Dict[str, Any] = Field(..., description="Prospect information")
    conversation_context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class UpdateObjectionRequest(BaseModel):
    """Request model for updating objection outcomes."""
    objection_id: str = Field(..., description="Objection identifier")
    user_response: str = Field(..., description="User's response to objection handling")
    resolved: Optional[bool] = Field(None, description="Whether objection was resolved")


class ObjectionResponse(BaseModel):
    """Response model for objection handling."""
    response_text: str
    should_escalate: bool
    objection_info: Dict[str, Any]


class ObjectionAnalyticsResponse(BaseModel):
    """Response model for objection analytics."""
    call_sid: str
    total_objections: int
    objections_by_type: Dict[str, int]
    objections_by_severity: Dict[str, int]
    resolution_rate: float
    escalation_rate: float
    average_resolution_time: float
    most_common_objection: Optional[str]
    success_rate_by_strategy: Dict[str, float]


class SystemMetricsResponse(BaseModel):
    """Response model for system objection metrics."""
    total_objections: int
    objections_by_type: Dict[str, int]
    objections_by_severity: Dict[str, int]
    overall_resolution_rate: float
    overall_escalation_rate: float
    strategy_effectiveness: Dict[str, Dict[str, Any]]
    most_common_objection: Optional[str]
    active_calls_with_objections: int


@router.post("/handle", response_model=ObjectionResponse)
async def handle_objection(request: HandleObjectionRequest):
    """
    Handle an objection with classification, response generation, and tracking.
    
    Args:
        request: Objection handling request
        
    Returns:
        AI response and objection information
    """
    try:
        response_text, should_escalate, objection_info = await enhanced_objection_handler.handle_objection(
            call_sid=request.call_sid,
            user_input=request.user_input,
            prospect_data=request.prospect_data,
            conversation_context=request.conversation_context
        )
        
        return ObjectionResponse(
            response_text=response_text,
            should_escalate=should_escalate,
            objection_info=objection_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to handle objection: {str(e)}"
        )


@router.put("/update", response_model=Dict[str, bool])
async def update_objection_outcome(request: UpdateObjectionRequest):
    """
    Update objection outcome based on user response.
    
    Args:
        request: Objection update request
        
    Returns:
        Whether objection was resolved
    """
    try:
        resolved = await enhanced_objection_handler.update_objection_outcome(
            objection_id=request.objection_id,
            user_response=request.user_response,
            resolved=request.resolved
        )
        
        return {"resolved": resolved}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update objection outcome: {str(e)}"
        )


@router.get("/analytics/{call_sid}", response_model=ObjectionAnalyticsResponse)
async def get_call_objection_analytics(call_sid: str):
    """
    Get objection analytics for a specific call.
    
    Args:
        call_sid: Call identifier
        
    Returns:
        Objection analytics for the call
    """
    try:
        analytics = await enhanced_objection_handler.get_call_objection_analytics(call_sid)
        
        if not analytics:
            raise HTTPException(
                status_code=404,
                detail=f"No objection data found for call {call_sid}"
            )
        
        return ObjectionAnalyticsResponse(
            call_sid=analytics.call_sid,
            total_objections=analytics.total_objections,
            objections_by_type={k.value: v for k, v in analytics.objections_by_type.items()},
            objections_by_severity={k.value: v for k, v in analytics.objections_by_severity.items()},
            resolution_rate=analytics.resolution_rate,
            escalation_rate=analytics.escalation_rate,
            average_resolution_time=analytics.average_resolution_time,
            most_common_objection=analytics.most_common_objection.value if analytics.most_common_objection else None,
            success_rate_by_strategy={k.value: v for k, v in analytics.success_rate_by_strategy.items()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get objection analytics: {str(e)}"
        )


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_objection_metrics():
    """
    Get system-wide objection handling metrics.
    
    Returns:
        System objection metrics and performance data
    """
    try:
        metrics = await enhanced_objection_handler.get_system_objection_metrics()
        
        if "error" in metrics:
            raise HTTPException(
                status_code=500,
                detail=metrics["error"]
            )
        
        return SystemMetricsResponse(**metrics)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system metrics: {str(e)}"
        )


@router.get("/types")
async def get_objection_types():
    """
    Get all available objection types.
    
    Returns:
        List of objection types and their descriptions
    """
    try:
        objection_descriptions = {
            ObjectionType.PRICE: "Budget or cost-related concerns",
            ObjectionType.TIMING: "Timing or scheduling concerns",
            ObjectionType.AUTHORITY: "Decision-making authority concerns",
            ObjectionType.NEED: "Questioning the need for the solution",
            ObjectionType.TRUST: "Trust or credibility concerns",
            ObjectionType.COMPETITION: "Already have a competing solution",
            ObjectionType.PRIORITY: "Other priorities taking precedence",
            ObjectionType.FEATURE: "Missing specific features",
            ObjectionType.IMPLEMENTATION: "Implementation or integration concerns",
            ObjectionType.SUPPORT: "Support or service concerns",
            ObjectionType.UNKNOWN: "Unclassified objection"
        }
        
        return {
            "objection_types": [
                {
                    "type": objection_type.value,
                    "description": objection_descriptions[objection_type]
                }
                for objection_type in ObjectionType
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get objection types: {str(e)}"
        )


@router.get("/severities")
async def get_objection_severities():
    """
    Get all available objection severity levels.
    
    Returns:
        List of severity levels and their descriptions
    """
    try:
        severity_descriptions = {
            ObjectionSeverity.LOW: "Minor concern, easy to address",
            ObjectionSeverity.MEDIUM: "Moderate concern, requires explanation",
            ObjectionSeverity.HIGH: "Major concern, needs strong response",
            ObjectionSeverity.CRITICAL: "Deal-breaking concern, may need escalation"
        }
        
        return {
            "severity_levels": [
                {
                    "level": severity.value,
                    "description": severity_descriptions[severity]
                }
                for severity in ObjectionSeverity
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get severity levels: {str(e)}"
        )


@router.get("/strategies")
async def get_response_strategies():
    """
    Get all available response strategies.
    
    Returns:
        List of response strategies and their descriptions
    """
    try:
        strategy_descriptions = {
            ResponseStrategy.ACKNOWLEDGE_REDIRECT: "Acknowledge concern and redirect conversation",
            ResponseStrategy.FEEL_FELT_FOUND: "Use empathy-based response (feel, felt, found)",
            ResponseStrategy.QUESTION_BACK: "Answer objection with a question",
            ResponseStrategy.EVIDENCE_BASED: "Provide proof or evidence to address concern",
            ResponseStrategy.REFRAME: "Reframe the objection in a different context",
            ResponseStrategy.TRIAL_CLOSE: "Attempt to close after addressing objection",
            ResponseStrategy.ESCALATE: "Escalate to human agent"
        }
        
        return {
            "response_strategies": [
                {
                    "strategy": strategy.value,
                    "description": strategy_descriptions[strategy]
                }
                for strategy in ResponseStrategy
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response strategies: {str(e)}"
        )


@router.post("/classify")
async def classify_objection(
    user_input: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Classify an objection without handling it.
    
    Args:
        user_input: User's objection text
        context: Additional context for classification
        
    Returns:
        Objection classification results
    """
    try:
        objection_type, severity, confidence = enhanced_objection_handler.classifier.classify_objection(
            user_input, context
        )
        
        return {
            "user_input": user_input,
            "objection_type": objection_type.value,
            "severity": severity.value,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to classify objection: {str(e)}"
        )


@router.get("/templates/{objection_type}/{severity}")
async def get_response_templates(objection_type: str, severity: str):
    """
    Get response templates for a specific objection type and severity.
    
    Args:
        objection_type: Type of objection
        severity: Severity level
        
    Returns:
        Available response templates
    """
    try:
        # Validate objection type and severity
        try:
            obj_type = ObjectionType(objection_type)
            obj_severity = ObjectionSeverity(severity)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid objection type or severity: {str(e)}"
            )
        
        # Get templates
        template_key = (obj_type, obj_severity)
        templates = enhanced_objection_handler.response_generator.response_templates.get(template_key, [])
        
        if not templates:
            return {
                "objection_type": objection_type,
                "severity": severity,
                "templates": [],
                "message": "No templates found for this combination"
            }
        
        return {
            "objection_type": objection_type,
            "severity": severity,
            "templates": [
                {
                    "strategy": template.strategy.value,
                    "template": template.template,
                    "follow_up_questions": template.follow_up_questions,
                    "success_indicators": template.success_indicators,
                    "escalation_triggers": template.escalation_triggers
                }
                for template in templates
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response templates: {str(e)}"
        )


@router.get("/test-patterns")
async def test_objection_patterns():
    """
    Test objection classification patterns with sample inputs.
    
    Returns:
        Test results for objection classification
    """
    try:
        test_cases = [
            "This is too expensive for our budget",
            "We don't have time for this right now",
            "I need to check with my boss first",
            "We already have a solution that works fine",
            "I'm not sure I trust this new technology",
            "This isn't a priority for us right now",
            "We don't really need this",
            "Can you prove this actually works?"
        ]
        
        results = []
        for test_input in test_cases:
            objection_type, severity, confidence = enhanced_objection_handler.classifier.classify_objection(test_input)
            results.append({
                "input": test_input,
                "objection_type": objection_type.value,
                "severity": severity.value,
                "confidence": confidence
            })
        
        return {
            "test_results": results,
            "total_patterns": len(enhanced_objection_handler.classifier.patterns)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test objection patterns: {str(e)}"
        )