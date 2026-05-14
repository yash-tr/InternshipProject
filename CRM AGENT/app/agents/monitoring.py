"""
Workflow monitoring and debugging tools for LangGraph agents.

This module provides comprehensive monitoring, debugging, and analytics
capabilities for the agent orchestration system.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
import json
import asyncio
from collections import defaultdict, Counter

from .base import AgentState, AgentStatus, AgentType

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics collected."""
    EXECUTION_TIME = "execution_time"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    LEAD_CONVERSION = "lead_conversion"
    APPROVAL_RATE = "approval_rate"
    CALL_SUCCESS_RATE = "call_success_rate"


@dataclass
class WorkflowMetrics:
    """Metrics for workflow performance."""
    workflow_id: str
    total_execution_time: float
    agent_execution_times: Dict[str, float]
    success: bool
    errors: List[str]
    lead_score: int
    approval_required: bool
    approval_granted: Optional[bool]
    call_attempts: int
    call_success: bool
    deal_closed: bool
    created_at: datetime
    completed_at: Optional[datetime]


class WorkflowMonitor:
    """
    Monitor and analyze workflow execution for performance optimization.
    
    Provides real-time monitoring, historical analysis, and debugging
    capabilities for the agent orchestration system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._workflow_metrics: Dict[str, WorkflowMetrics] = {}
        self._active_workflows: Dict[str, datetime] = {}
        self._performance_history: List[WorkflowMetrics] = []
        
        # Real-time monitoring
        self._monitoring_enabled = True
        self._alert_thresholds = {
            "error_rate": 0.1,  # 10% error rate threshold
            "avg_execution_time": 1800,  # 30 minutes
            "approval_timeout_rate": 0.2  # 20% timeout rate
        }
    
    async def start_workflow_monitoring(self, workflow_id: str, initial_state: AgentState):
        """
        Start monitoring a workflow.
        
        Args:
            workflow_id: Workflow identifier
            initial_state: Initial workflow state
        """
        self._active_workflows[workflow_id] = datetime.utcnow()
        
        metrics = WorkflowMetrics(
            workflow_id=workflow_id,
            total_execution_time=0.0,
            agent_execution_times={},
            success=False,
            errors=[],
            lead_score=initial_state.get("lead_score", 0),
            approval_required=initial_state.get("approval_required", False),
            approval_granted=None,
            call_attempts=0,
            call_success=False,
            deal_closed=False,
            created_at=datetime.utcnow(),
            completed_at=None
        )
        
        self._workflow_metrics[workflow_id] = metrics
        self.logger.info(f"Started monitoring workflow {workflow_id}")
    
    async def update_workflow_metrics(self, workflow_id: str, state: AgentState):
        """
        Update metrics for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            state: Current workflow state
        """
        if workflow_id not in self._workflow_metrics:
            return
        
        metrics = self._workflow_metrics[workflow_id]
        
        # Update metrics from state
        metrics.lead_score = state.get("lead_score", metrics.lead_score)
        metrics.approval_required = state.get("approval_required", metrics.approval_required)
        metrics.call_attempts = state.get("call_attempts", metrics.call_attempts)
        metrics.errors = state.get("errors", [])
        
        # Check approval status
        if state.get("approval_status"):
            metrics.approval_granted = state.get("approval_status") == "approved"
        
        # Check call success
        if state.get("call_status") == "answered":
            metrics.call_success = True
        
        # Check deal closing
        if state.get("closing_outcome") in ["closed", "qualified"]:
            metrics.deal_closed = True
        
        # Update completion status
        if state.get("status") in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
            metrics.completed_at = datetime.utcnow()
            metrics.success = state.get("status") == AgentStatus.COMPLETED
            
            # Calculate total execution time
            if workflow_id in self._active_workflows:
                start_time = self._active_workflows[workflow_id]
                metrics.total_execution_time = (datetime.utcnow() - start_time).total_seconds()
                del self._active_workflows[workflow_id]
            
            # Archive metrics
            self._performance_history.append(metrics)
            
            # Check for alerts
            await self._check_performance_alerts(metrics)
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Detailed workflow status
        """
        if workflow_id not in self._workflow_metrics:
            return None
        
        metrics = self._workflow_metrics[workflow_id]
        
        # Calculate current execution time
        current_execution_time = 0.0
        if workflow_id in self._active_workflows:
            start_time = self._active_workflows[workflow_id]
            current_execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "workflow_id": workflow_id,
            "status": "completed" if metrics.completed_at else "running",
            "execution_time": metrics.total_execution_time or current_execution_time,
            "lead_score": metrics.lead_score,
            "approval_required": metrics.approval_required,
            "approval_granted": metrics.approval_granted,
            "call_attempts": metrics.call_attempts,
            "call_success": metrics.call_success,
            "deal_closed": metrics.deal_closed,
            "errors": metrics.errors,
            "created_at": metrics.created_at.isoformat(),
            "completed_at": metrics.completed_at.isoformat() if metrics.completed_at else None
        }
    
    async def get_performance_analytics(self, 
                                      time_range: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """
        Get performance analytics for the specified time range.
        
        Args:
            time_range: Time range for analytics
            
        Returns:
            Performance analytics data
        """
        cutoff_time = datetime.utcnow() - time_range
        recent_metrics = [
            m for m in self._performance_history 
            if m.created_at >= cutoff_time
        ]
        
        if not recent_metrics:
            return {"message": "No data available for the specified time range"}
        
        # Calculate aggregate metrics
        total_workflows = len(recent_metrics)
        successful_workflows = sum(1 for m in recent_metrics if m.success)
        
        # Execution time statistics
        execution_times = [m.total_execution_time for m in recent_metrics if m.total_execution_time > 0]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # Lead scoring statistics
        lead_scores = [m.lead_score for m in recent_metrics]
        avg_lead_score = sum(lead_scores) / len(lead_scores) if lead_scores else 0
        
        # Approval statistics
        approval_workflows = [m for m in recent_metrics if m.approval_required]
        approval_rate = 0
        if approval_workflows:
            approved = sum(1 for m in approval_workflows if m.approval_granted)
            approval_rate = approved / len(approval_workflows)
        
        # Call statistics
        call_workflows = [m for m in recent_metrics if m.call_attempts > 0]
        call_success_rate = 0
        if call_workflows:
            successful_calls = sum(1 for m in call_workflows if m.call_success)
            call_success_rate = successful_calls / len(call_workflows)
        
        # Deal closing statistics
        deal_close_rate = sum(1 for m in recent_metrics if m.deal_closed) / total_workflows
        
        # Error analysis
        all_errors = []
        for m in recent_metrics:
            all_errors.extend(m.errors)
        
        error_counter = Counter(error["message"] if isinstance(error, dict) else str(error) for error in all_errors)
        
        return {
            "time_range_days": time_range.days,
            "total_workflows": total_workflows,
            "success_rate": successful_workflows / total_workflows,
            "avg_execution_time_seconds": avg_execution_time,
            "avg_lead_score": avg_lead_score,
            "approval_rate": approval_rate,
            "call_success_rate": call_success_rate,
            "deal_close_rate": deal_close_rate,
            "total_errors": len(all_errors),
            "top_errors": dict(error_counter.most_common(5)),
            "workflows_by_hour": self._get_workflows_by_hour(recent_metrics),
            "lead_score_distribution": self._get_lead_score_distribution(recent_metrics)
        }
    
    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """
        Get information about currently active workflows.
        
        Returns:
            List of active workflow information
        """
        active_workflows = []
        
        for workflow_id, start_time in self._active_workflows.items():
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            metrics = self._workflow_metrics.get(workflow_id)
            
            workflow_info = {
                "workflow_id": workflow_id,
                "execution_time": execution_time,
                "started_at": start_time.isoformat(),
                "lead_score": metrics.lead_score if metrics else 0,
                "call_attempts": metrics.call_attempts if metrics else 0,
                "errors": len(metrics.errors) if metrics else 0
            }
            
            active_workflows.append(workflow_info)
        
        return sorted(active_workflows, key=lambda x: x["execution_time"], reverse=True)
    
    async def debug_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get detailed debugging information for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Detailed debugging information
        """
        if workflow_id not in self._workflow_metrics:
            return {"error": "Workflow not found"}
        
        metrics = self._workflow_metrics[workflow_id]
        
        debug_info = {
            "workflow_id": workflow_id,
            "metrics": {
                "total_execution_time": metrics.total_execution_time,
                "agent_execution_times": metrics.agent_execution_times,
                "success": metrics.success,
                "lead_score": metrics.lead_score,
                "approval_required": metrics.approval_required,
                "approval_granted": metrics.approval_granted,
                "call_attempts": metrics.call_attempts,
                "call_success": metrics.call_success,
                "deal_closed": metrics.deal_closed
            },
            "errors": metrics.errors,
            "timeline": {
                "created_at": metrics.created_at.isoformat(),
                "completed_at": metrics.completed_at.isoformat() if metrics.completed_at else None
            },
            "performance_analysis": self._analyze_workflow_performance(metrics)
        }
        
        return debug_info
    
    def _get_workflows_by_hour(self, metrics: List[WorkflowMetrics]) -> Dict[str, int]:
        """Get workflow distribution by hour of day."""
        hourly_counts = defaultdict(int)
        
        for m in metrics:
            hour = m.created_at.hour
            hourly_counts[f"{hour:02d}:00"] += 1
        
        return dict(hourly_counts)
    
    def _get_lead_score_distribution(self, metrics: List[WorkflowMetrics]) -> Dict[str, int]:
        """Get lead score distribution."""
        score_ranges = {
            "0-20": 0,
            "21-40": 0,
            "41-60": 0,
            "61-80": 0,
            "81-100": 0
        }
        
        for m in metrics:
            score = m.lead_score
            if score <= 20:
                score_ranges["0-20"] += 1
            elif score <= 40:
                score_ranges["21-40"] += 1
            elif score <= 60:
                score_ranges["41-60"] += 1
            elif score <= 80:
                score_ranges["61-80"] += 1
            else:
                score_ranges["81-100"] += 1
        
        return score_ranges
    
    def _analyze_workflow_performance(self, metrics: WorkflowMetrics) -> Dict[str, Any]:
        """Analyze individual workflow performance."""
        analysis = {
            "performance_rating": "good",
            "bottlenecks": [],
            "recommendations": []
        }
        
        # Analyze execution time
        if metrics.total_execution_time > 1800:  # 30 minutes
            analysis["performance_rating"] = "slow"
            analysis["bottlenecks"].append("Long execution time")
            analysis["recommendations"].append("Review agent timeout settings")
        
        # Analyze errors
        if metrics.errors:
            analysis["performance_rating"] = "poor"
            analysis["bottlenecks"].append("Multiple errors occurred")
            analysis["recommendations"].append("Review error handling logic")
        
        # Analyze call attempts
        if metrics.call_attempts > 2:
            analysis["bottlenecks"].append("Multiple call attempts required")
            analysis["recommendations"].append("Optimize call timing strategy")
        
        # Analyze approval process
        if metrics.approval_required and not metrics.approval_granted:
            analysis["bottlenecks"].append("Approval process failed or timed out")
            analysis["recommendations"].append("Review approval notification system")
        
        return analysis
    
    async def _check_performance_alerts(self, metrics: WorkflowMetrics):
        """Check if performance alerts should be triggered."""
        alerts = []
        
        # Check execution time
        if metrics.total_execution_time > self._alert_thresholds["avg_execution_time"]:
            alerts.append(f"Workflow {metrics.workflow_id} exceeded execution time threshold")
        
        # Check error rate (based on recent history)
        recent_workflows = [
            m for m in self._performance_history[-100:] 
            if m.completed_at and m.completed_at >= datetime.utcnow() - timedelta(hours=1)
        ]
        
        if recent_workflows:
            error_rate = sum(1 for m in recent_workflows if m.errors) / len(recent_workflows)
            if error_rate > self._alert_thresholds["error_rate"]:
                alerts.append(f"Error rate ({error_rate:.2%}) exceeded threshold")
        
        # Send alerts
        for alert in alerts:
            self.logger.warning(f"Performance Alert: {alert}")
            # In a real implementation, this would send notifications
            # via Slack, email, or monitoring systems


class WorkflowDebugger:
    """
    Advanced debugging tools for workflow troubleshooting.
    
    Provides detailed analysis, state inspection, and diagnostic
    capabilities for complex workflow issues.
    """
    
    def __init__(self, monitor: WorkflowMonitor):
        self.monitor = monitor
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def trace_workflow_execution(self, workflow_id: str) -> Dict[str, Any]:
        """
        Trace the execution path of a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Detailed execution trace
        """
        # This would integrate with Langfuse for detailed tracing
        # For now, return basic information
        
        debug_info = await self.monitor.debug_workflow(workflow_id)
        
        if "error" in debug_info:
            return debug_info
        
        trace = {
            "workflow_id": workflow_id,
            "execution_path": [
                "research",
                "scoring", 
                "approval" if debug_info["metrics"]["approval_required"] else "calling",
                "calling" if debug_info["metrics"]["approval_required"] else "deal_closing",
                "deal_closing" if debug_info["metrics"]["call_success"] else "completion",
                "completion"
            ],
            "agent_performance": debug_info["metrics"]["agent_execution_times"],
            "decision_points": {
                "approval_required": debug_info["metrics"]["approval_required"],
                "approval_granted": debug_info["metrics"]["approval_granted"],
                "call_success": debug_info["metrics"]["call_success"],
                "deal_closed": debug_info["metrics"]["deal_closed"]
            },
            "error_analysis": self._analyze_errors(debug_info["errors"])
        }
        
        return trace
    
    def _analyze_errors(self, errors: List[Any]) -> Dict[str, Any]:
        """Analyze errors for patterns and root causes."""
        if not errors:
            return {"total_errors": 0, "error_types": {}, "recommendations": []}
        
        error_types = Counter()
        for error in errors:
            if isinstance(error, dict):
                error_type = error.get("message", "Unknown error")
            else:
                error_type = str(error)
            
            error_types[error_type] += 1
        
        recommendations = []
        
        # Analyze common error patterns
        for error_type, count in error_types.most_common():
            if "timeout" in error_type.lower():
                recommendations.append("Consider increasing timeout values")
            elif "api" in error_type.lower():
                recommendations.append("Check external API connectivity and rate limits")
            elif "authentication" in error_type.lower():
                recommendations.append("Verify API credentials and token refresh logic")
        
        return {
            "total_errors": len(errors),
            "error_types": dict(error_types),
            "most_common_error": error_types.most_common(1)[0] if error_types else None,
            "recommendations": recommendations
        }