"""
Unit tests for workflow monitoring and debugging tools.

Tests the monitoring, analytics, and debugging capabilities
for the LangGraph agent system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from collections import Counter

from app.agents.monitoring import (
    WorkflowMonitor, WorkflowDebugger, WorkflowMetrics, MetricType
)
from app.agents.base import AgentState, AgentStatus


class TestWorkflowMetrics:
    """Test WorkflowMetrics dataclass functionality."""
    
    def test_workflow_metrics_creation(self):
        """Test creating WorkflowMetrics."""
        metrics = WorkflowMetrics(
            workflow_id="test-123",
            total_execution_time=120.5,
            agent_execution_times={"research": 45.2, "scoring": 30.1},
            success=True,
            errors=[],
            lead_score=85,
            approval_required=True,
            approval_granted=True,
            call_attempts=2,
            call_success=True,
            deal_closed=True,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        assert metrics.workflow_id == "test-123"
        assert metrics.total_execution_time == 120.5
        assert metrics.success is True
        assert metrics.lead_score == 85
        assert metrics.deal_closed is True


class TestWorkflowMonitor:
    """Test WorkflowMonitor functionality."""
    
    def test_monitor_initialization(self):
        """Test monitor initialization."""
        monitor = WorkflowMonitor()
        
        assert monitor._workflow_metrics == {}
        assert monitor._active_workflows == {}
        assert monitor._performance_history == []
        assert monitor._monitoring_enabled is True
        assert "error_rate" in monitor._alert_thresholds
    
    @pytest.mark.asyncio
    async def test_start_workflow_monitoring(self):
        """Test starting workflow monitoring."""
        monitor = WorkflowMonitor()
        
        initial_state: AgentState = {
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
            "lead_score": 75,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": True,
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
        
        await monitor.start_workflow_monitoring("test-123", initial_state)
        
        assert "test-123" in monitor._workflow_metrics
        assert "test-123" in monitor._active_workflows
        
        metrics = monitor._workflow_metrics["test-123"]
        assert metrics.workflow_id == "test-123"
        assert metrics.lead_score == 75
        assert metrics.approval_required is True
    
    @pytest.mark.asyncio
    async def test_update_workflow_metrics(self):
        """Test updating workflow metrics."""
        monitor = WorkflowMonitor()
        
        # Start monitoring first
        initial_state: AgentState = {
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
            "lead_score": 50,
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
        
        await monitor.start_workflow_monitoring("test-123", initial_state)
        
        # Update with new state
        updated_state = initial_state.copy()
        updated_state.update({
            "lead_score": 85,
            "call_attempts": 2,
            "call_status": "answered",
            "approval_status": "approved",
            "closing_outcome": "qualified"
        })
        
        await monitor.update_workflow_metrics("test-123", updated_state)
        
        metrics = monitor._workflow_metrics["test-123"]
        assert metrics.lead_score == 85
        assert metrics.call_attempts == 2
        assert metrics.call_success is True
        assert metrics.approval_granted is True
        assert metrics.deal_closed is True
    
    @pytest.mark.asyncio
    async def test_update_workflow_metrics_completion(self):
        """Test updating metrics when workflow completes."""
        monitor = WorkflowMonitor()
        
        # Start monitoring
        initial_state: AgentState = {
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
        
        await monitor.start_workflow_monitoring("test-123", initial_state)
        
        # Complete the workflow
        completed_state = initial_state.copy()
        completed_state["status"] = AgentStatus.COMPLETED
        
        with patch.object(monitor, '_check_performance_alerts') as mock_alerts:
            await monitor.update_workflow_metrics("test-123", completed_state)
        
        # Check that workflow was archived
        assert "test-123" not in monitor._active_workflows
        assert len(monitor._performance_history) == 1
        
        metrics = monitor._performance_history[0]
        assert metrics.workflow_id == "test-123"
        assert metrics.success is True
        assert metrics.completed_at is not None
        assert metrics.total_execution_time > 0
        
        # Check that alerts were checked
        mock_alerts.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_workflow_status(self):
        """Test getting workflow status."""
        monitor = WorkflowMonitor()
        
        # Test non-existent workflow
        status = await monitor.get_workflow_status("non-existent")
        assert status is None
        
        # Start monitoring a workflow
        initial_state: AgentState = {
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
            "lead_score": 75,
            "scoring_rationale": "",
            "buying_signals": [],
            "approval_required": True,
            "approval_status": None,
            "approver_id": None,
            "approval_timestamp": None,
            "call_sid": None,
            "call_status": None,
            "call_attempts": 1,
            "next_call_time": None,
            "deal_stage": "initial",
            "conversation_context": [],
            "objections_handled": [],
            "closing_outcome": None,
            "errors": ["Test error"],
            "retry_count": 0,
            "compliance_flags": [],
            "audit_trail": []
        }
        
        await monitor.start_workflow_monitoring("test-123", initial_state)
        
        status = await monitor.get_workflow_status("test-123")
        
        assert status is not None
        assert status["workflow_id"] == "test-123"
        assert status["status"] == "running"
        assert status["lead_score"] == 75
        assert status["approval_required"] is True
        assert status["call_attempts"] == 1
        assert status["errors"] == ["Test error"]
        assert "execution_time" in status
        assert "created_at" in status
    
    @pytest.mark.asyncio
    async def test_get_performance_analytics_no_data(self):
        """Test getting analytics with no data."""
        monitor = WorkflowMonitor()
        
        analytics = await monitor.get_performance_analytics()
        
        assert "message" in analytics
        assert "No data available" in analytics["message"]
    
    @pytest.mark.asyncio
    async def test_get_performance_analytics_with_data(self):
        """Test getting analytics with historical data."""
        monitor = WorkflowMonitor()
        
        # Add some test metrics to history
        test_metrics = [
            WorkflowMetrics(
                workflow_id="test-1",
                total_execution_time=120.0,
                agent_execution_times={},
                success=True,
                errors=[],
                lead_score=85,
                approval_required=True,
                approval_granted=True,
                call_attempts=1,
                call_success=True,
                deal_closed=True,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            ),
            WorkflowMetrics(
                workflow_id="test-2",
                total_execution_time=180.0,
                agent_execution_times={},
                success=False,
                errors=["API timeout"],
                lead_score=45,
                approval_required=False,
                approval_granted=None,
                call_attempts=3,
                call_success=False,
                deal_closed=False,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
        ]
        
        monitor._performance_history = test_metrics
        
        analytics = await monitor.get_performance_analytics()
        
        assert analytics["total_workflows"] == 2
        assert analytics["success_rate"] == 0.5  # 1 out of 2 successful
        assert analytics["avg_execution_time_seconds"] == 150.0  # (120 + 180) / 2
        assert analytics["avg_lead_score"] == 65.0  # (85 + 45) / 2
        assert analytics["approval_rate"] == 1.0  # 1 approval required, 1 granted
        assert analytics["call_success_rate"] == 0.5  # 1 out of 2 successful
        assert analytics["deal_close_rate"] == 0.5  # 1 out of 2 closed
        assert analytics["total_errors"] == 1
        assert "workflows_by_hour" in analytics
        assert "lead_score_distribution" in analytics
    
    @pytest.mark.asyncio
    async def test_get_active_workflows(self):
        """Test getting active workflows."""
        monitor = WorkflowMonitor()
        
        # Start monitoring multiple workflows
        start_time = datetime.utcnow()
        monitor._active_workflows = {
            "workflow-1": start_time - timedelta(minutes=5),
            "workflow-2": start_time - timedelta(minutes=2)
        }
        
        # Add metrics for the workflows
        monitor._workflow_metrics = {
            "workflow-1": WorkflowMetrics(
                workflow_id="workflow-1",
                total_execution_time=0,
                agent_execution_times={},
                success=False,
                errors=[],
                lead_score=75,
                approval_required=False,
                approval_granted=None,
                call_attempts=1,
                call_success=False,
                deal_closed=False,
                created_at=start_time - timedelta(minutes=5),
                completed_at=None
            ),
            "workflow-2": WorkflowMetrics(
                workflow_id="workflow-2",
                total_execution_time=0,
                agent_execution_times={},
                success=False,
                errors=["Test error"],
                lead_score=60,
                approval_required=True,
                approval_granted=None,
                call_attempts=0,
                call_success=False,
                deal_closed=False,
                created_at=start_time - timedelta(minutes=2),
                completed_at=None
            )
        }
        
        active_workflows = await monitor.get_active_workflows()
        
        assert len(active_workflows) == 2
        
        # Should be sorted by execution time (longest first)
        assert active_workflows[0]["workflow_id"] == "workflow-1"
        assert active_workflows[1]["workflow_id"] == "workflow-2"
        
        # Check workflow details
        workflow_1 = active_workflows[0]
        assert workflow_1["execution_time"] >= 300  # At least 5 minutes
        assert workflow_1["lead_score"] == 75
        assert workflow_1["call_attempts"] == 1
        assert workflow_1["errors"] == 0
        
        workflow_2 = active_workflows[1]
        assert workflow_2["execution_time"] >= 120  # At least 2 minutes
        assert workflow_2["lead_score"] == 60
        assert workflow_2["call_attempts"] == 0
        assert workflow_2["errors"] == 1
    
    @pytest.mark.asyncio
    async def test_debug_workflow(self):
        """Test debugging workflow functionality."""
        monitor = WorkflowMonitor()
        
        # Test non-existent workflow
        debug_info = await monitor.debug_workflow("non-existent")
        assert "error" in debug_info
        assert debug_info["error"] == "Workflow not found"
        
        # Add a test workflow
        test_metrics = WorkflowMetrics(
            workflow_id="test-123",
            total_execution_time=150.5,
            agent_execution_times={"research": 60.2, "scoring": 45.1, "calling": 45.2},
            success=True,
            errors=["Minor timeout"],
            lead_score=85,
            approval_required=True,
            approval_granted=True,
            call_attempts=2,
            call_success=True,
            deal_closed=True,
            created_at=datetime.utcnow() - timedelta(minutes=10),
            completed_at=datetime.utcnow()
        )
        
        monitor._workflow_metrics["test-123"] = test_metrics
        
        debug_info = await monitor.debug_workflow("test-123")
        
        assert debug_info["workflow_id"] == "test-123"
        assert "metrics" in debug_info
        assert "errors" in debug_info
        assert "timeline" in debug_info
        assert "performance_analysis" in debug_info
        
        # Check metrics
        metrics = debug_info["metrics"]
        assert metrics["total_execution_time"] == 150.5
        assert metrics["success"] is True
        assert metrics["lead_score"] == 85
        assert metrics["deal_closed"] is True
        
        # Check performance analysis
        analysis = debug_info["performance_analysis"]
        assert "performance_rating" in analysis
        assert "bottlenecks" in analysis
        assert "recommendations" in analysis


class TestWorkflowDebugger:
    """Test WorkflowDebugger functionality."""
    
    def test_debugger_initialization(self):
        """Test debugger initialization."""
        monitor = WorkflowMonitor()
        debugger = WorkflowDebugger(monitor)
        
        assert debugger.monitor == monitor
        assert debugger.logger is not None
    
    @pytest.mark.asyncio
    async def test_trace_workflow_execution(self):
        """Test workflow execution tracing."""
        monitor = WorkflowMonitor()
        debugger = WorkflowDebugger(monitor)
        
        # Test non-existent workflow
        trace = await debugger.trace_workflow_execution("non-existent")
        assert "error" in trace
        
        # Add a test workflow to monitor
        test_metrics = WorkflowMetrics(
            workflow_id="test-123",
            total_execution_time=120.0,
            agent_execution_times={"research": 45.0, "scoring": 30.0, "calling": 45.0},
            success=True,
            errors=[],
            lead_score=85,
            approval_required=True,
            approval_granted=True,
            call_attempts=1,
            call_success=True,
            deal_closed=True,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        monitor._workflow_metrics["test-123"] = test_metrics
        
        trace = await debugger.trace_workflow_execution("test-123")
        
        assert trace["workflow_id"] == "test-123"
        assert "execution_path" in trace
        assert "agent_performance" in trace
        assert "decision_points" in trace
        assert "error_analysis" in trace
        
        # Check execution path
        execution_path = trace["execution_path"]
        assert "research" in execution_path
        assert "scoring" in execution_path
        assert "approval" in execution_path
        assert "calling" in execution_path
        
        # Check decision points
        decision_points = trace["decision_points"]
        assert decision_points["approval_required"] is True
        assert decision_points["approval_granted"] is True
        assert decision_points["call_success"] is True
        assert decision_points["deal_closed"] is True
    
    def test_analyze_errors_no_errors(self):
        """Test error analysis with no errors."""
        monitor = WorkflowMonitor()
        debugger = WorkflowDebugger(monitor)
        
        analysis = debugger._analyze_errors([])
        
        assert analysis["total_errors"] == 0
        assert analysis["error_types"] == {}
        assert analysis["recommendations"] == []
    
    def test_analyze_errors_with_errors(self):
        """Test error analysis with various error types."""
        monitor = WorkflowMonitor()
        debugger = WorkflowDebugger(monitor)
        
        errors = [
            {"message": "API timeout occurred"},
            {"message": "Authentication failed"},
            "API timeout occurred",  # Duplicate
            {"message": "Connection timeout"}
        ]
        
        analysis = debugger._analyze_errors(errors)
        
        assert analysis["total_errors"] == 4
        assert "API timeout occurred" in analysis["error_types"]
        assert analysis["error_types"]["API timeout occurred"] == 2
        assert analysis["most_common_error"][0] == "API timeout occurred"
        assert len(analysis["recommendations"]) > 0
        
        # Check that timeout-related recommendations are included
        recommendations = " ".join(analysis["recommendations"])
        assert "timeout" in recommendations.lower()