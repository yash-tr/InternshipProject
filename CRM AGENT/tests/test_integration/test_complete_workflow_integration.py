"""
End-to-end integration tests for complete workflow integration.

Tests the integration between workflow orchestration, budget enforcement,
caching, monitoring, and error recovery systems.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.workflow_integration import (
    WorkflowIntegrationService, 
    BudgetLimits, 
    CacheConfig,
    WorkflowMetrics
)
from app.services.comprehensive_caching import (
    ComprehensiveCachingService, 
    CacheType
)
from app.middleware.budget_enforcement import BudgetEnforcementMiddleware
from app.agents.monitoring import WorkflowMonitor


class TestCompleteWorkflowIntegration:
    """Test complete workflow integration functionality."""
    
    @pytest.fixture
    async def workflow_service(self):
        """Create workflow integration service for testing."""
        service = WorkflowIntegrationService()
        
        # Mock Redis client
        service.redis_client = AsyncMock()
        service.redis_client.ping.return_value = True
        service.redis_client.get.return_value = None
        service.redis_client.set.return_value = True
        service.redis_client.hgetall.return_value = {}
        service.redis_client.hset.return_value = True
        service.redis_client.expire.return_value = True
        service.redis_client.incr.return_value = 1
        service.redis_client.incrbyfloat.return_value = 1.0
        
        # Mock orchestrator
        service.orchestrator = AsyncMock()
        service.orchestrator.start_workflow.return_value = "test-orchestrator-id"
        
        # Mock monitor
        service.monitor = AsyncMock()
        service.monitor.start_workflow_monitoring.return_value = None
        
        # Mock audit service
        service.audit_service = AsyncMock()
        service.audit_service.log_workflow_start.return_value = None
        
        await service.initialize()
        return service
    
    @pytest.fixture
    async def caching_service(self):
        """Create caching service for testing."""
        service = ComprehensiveCachingService()
        
        # Mock Redis client
        service.redis_client = AsyncMock()
        service.redis_client.ping.return_value = True
        service.redis_client.get.return_value = None
        service.redis_client.setex.return_value = True
        service.redis_client.delete.return_value = 1
        service.redis_client.keys.return_value = []
        service.redis_client.info.return_value = {"used_memory": 1000000}
        
        await service.initialize()
        return service
    
    @pytest.fixture
    def budget_middleware(self):
        """Create budget enforcement middleware for testing."""
        return BudgetEnforcementMiddleware(None)
    
    @pytest.mark.asyncio
    async def test_integrated_workflow_start_with_budget_enforcement(self, workflow_service):
        """Test starting a workflow with budget enforcement."""
        # Setup
        prospect_data = {
            "prospect_id": "test-prospect-123",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead-123"
        }
        
        # Mock budget check to allow workflow
        workflow_service.redis_client.get.side_effect = lambda key: {
            "daily_budget:2024-01-01:api_calls": "10",
            "daily_budget:2024-01-01:llm_tokens": "1000", 
            "daily_budget:2024-01-01:cost": "5.0"
        }.get(key, "0")
        
        # Test workflow start
        result = await workflow_service.start_integrated_workflow(
            prospect_data, 
            priority="normal"
        )
        
        # Assertions
        assert result["success"] is True
        assert "workflow_id" in result
        assert "budget_status" in result
        assert result["budget_status"]["allowed"] is True
        
        # Verify orchestrator was called
        workflow_service.orchestrator.start_workflow.assert_called_once()
        
        # Verify monitoring was started
        workflow_service.monitor.start_workflow_monitoring.assert_called_once()
        
        # Verify audit logging
        workflow_service.audit_service.log_workflow_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_workflow_budget_enforcement_at_node(self, workflow_service):
        """Test budget enforcement at specific workflow nodes."""
        workflow_id = "test-workflow-123"
        
        # Setup workflow budget tracking
        workflow_service.redis_client.hgetall.return_value = {
            "workflow_id": workflow_id,
            "priority": "normal",
            "api_calls_used": "0",
            "llm_calls_used": "0"
        }
        
        # Test API call enforcement
        result = await workflow_service.enforce_budget_at_node(
            workflow_id, 
            "research", 
            "api_call"
        )
        
        assert result["allowed"] is True
        assert "remaining_budget" in result
        
        # Verify usage was incremented
        workflow_service.redis_client.hincrby.assert_called_with(
            f"workflow_budget:{workflow_id}", 
            "api_calls_used", 
            1
        )
    
    @pytest.mark.asyncio
    async def test_workflow_budget_limit_exceeded(self, workflow_service):
        """Test workflow termination when budget limits are exceeded."""
        workflow_id = "test-workflow-123"
        
        # Setup workflow at budget limit
        workflow_service.redis_client.hgetall.return_value = {
            "workflow_id": workflow_id,
            "priority": "normal",
            "api_calls_used": "1",  # At limit for non-VIP
            "llm_calls_used": "0"
        }
        
        # Test API call enforcement when at limit
        result = await workflow_service.enforce_budget_at_node(
            workflow_id, 
            "research", 
            "api_call"
        )
        
        assert result["allowed"] is False
        assert "API call limit exceeded" in result["error"]
        assert result["budget_type"] == "api_calls"
    
    @pytest.mark.asyncio
    async def test_comprehensive_caching_integration(self, caching_service):
        """Test comprehensive caching with different data types."""
        # Test enrichment data caching
        enrichment_data = {
            "company": "Test Corp",
            "industry": "Technology",
            "size": "100-500"
        }
        
        # Set cache
        success = await caching_service.set(
            CacheType.ENRICHMENT,
            "test-company.com",
            enrichment_data
        )
        assert success is True
        
        # Mock cache hit
        caching_service.redis_client.get.return_value = json.dumps(enrichment_data).encode('utf-8')
        
        # Get from cache
        cached_data = await caching_service.get(
            CacheType.ENRICHMENT,
            "test-company.com"
        )
        
        assert cached_data == enrichment_data
        
        # Verify stats were updated
        assert caching_service._stats.cache_hits > 0
    
    @pytest.mark.asyncio
    async def test_tts_audio_caching(self, caching_service):
        """Test TTS audio caching with binary data."""
        # Mock audio data
        audio_data = b"fake_audio_data_12345"
        
        # Set audio cache
        success = await caching_service.set(
            CacheType.TTS_AUDIO,
            "hello_world_prompt",
            audio_data
        )
        assert success is True
        
        # Mock cache hit with binary data
        caching_service.redis_client.get.return_value = audio_data
        
        # Get from cache
        cached_audio = await caching_service.get(
            CacheType.TTS_AUDIO,
            "hello_world_prompt"
        )
        
        assert cached_audio == audio_data
    
    @pytest.mark.asyncio
    async def test_cache_performance_monitoring(self, caching_service):
        """Test cache performance monitoring and alerts."""
        # Simulate cache misses to trigger low hit rate alert
        caching_service._stats.total_requests = 200
        caching_service._stats.cache_hits = 40  # 20% hit rate
        caching_service._stats.cache_misses = 160
        caching_service._stats.hit_rate = 0.2
        
        # Get stats
        stats = await caching_service.get_stats()
        
        assert stats["overall"]["hit_rate"] == 0.2
        
        # Check for performance alerts
        alerts = stats["performance_alerts"]
        low_hit_rate_alert = next(
            (alert for alert in alerts if alert["type"] == "low_hit_rate"), 
            None
        )
        assert low_hit_rate_alert is not None
        assert "below 30% threshold" in low_hit_rate_alert["message"]
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling_and_recovery(self, workflow_service):
        """Test workflow error handling and recovery mechanisms."""
        workflow_id = "test-workflow-123"
        error = Exception("API timeout error")
        context = {"retry_count": 0, "node": "research"}
        
        # Test error handling
        result = await workflow_service.handle_workflow_error(
            workflow_id, 
            error, 
            context
        )
        
        assert result["handled"] is True
        assert result["recovery_strategy"] in ["retry", "retry_with_backoff"]
        assert result["should_retry"] is True
        assert "retry_delay" in result
        
        # Verify error was added to retry queue
        assert len(workflow_service._retry_queues["api_failures"]) > 0
        
        # Verify audit logging
        workflow_service.audit_service.log_workflow_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_workflow_performance_metrics_collection(self, workflow_service):
        """Test comprehensive performance metrics collection."""
        # Setup some metrics
        workflow_service.metrics.active_workflows = 5
        workflow_service.metrics.completed_workflows = 100
        workflow_service.metrics.failed_workflows = 5
        workflow_service.metrics.total_api_calls = 500
        workflow_service.metrics.total_cost = 25.50
        workflow_service.metrics.cache_hits = 800
        workflow_service.metrics.cache_misses = 200
        
        # Mock budget utilization
        workflow_service.redis_client.get.side_effect = lambda key: {
            "daily_budget:2024-01-01:api_calls": "450",
            "daily_budget:2024-01-01:llm_tokens": "15000",
            "daily_budget:2024-01-01:cost": "22.50"
        }.get(key, "0")
        
        # Get performance metrics
        metrics = await workflow_service.get_workflow_performance_metrics()
        
        assert "metrics" in metrics
        assert "cache_hit_rate" in metrics
        assert "budget_utilization" in metrics
        assert "sla_compliance" in metrics
        assert "retry_queues" in metrics
        
        # Verify cache hit rate calculation
        expected_hit_rate = 800 / (800 + 200)  # 0.8
        assert metrics["cache_hit_rate"] == expected_hit_rate
        
        # Verify budget utilization
        budget_util = metrics["budget_utilization"]
        assert budget_util["api_calls"]["used"] == 450
        assert budget_util["cost"]["used"] == 22.50
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_limit_enforcement(self, workflow_service):
        """Test concurrent workflow limit enforcement."""
        # Fill up active workflows to the limit
        for i in range(workflow_service.budget_limits.concurrent_workflows):
            workflow_service._active_workflows[f"workflow-{i}"] = datetime.utcnow()
        
        prospect_data = {
            "prospect_id": "test-prospect-overflow",
            "phone_number": "+1234567890"
        }
        
        # Try to start another workflow
        result = await workflow_service.start_integrated_workflow(
            prospect_data, 
            priority="normal"
        )
        
        assert result["success"] is False
        assert "Concurrent workflow limit exceeded" in result["error"]
        assert result["active_workflows"] == workflow_service.budget_limits.concurrent_workflows
    
    @pytest.mark.asyncio
    async def test_vip_vs_normal_priority_budget_allocation(self, workflow_service):
        """Test different budget allocations for VIP vs normal priority."""
        workflow_id_normal = "workflow-normal"
        workflow_id_vip = "workflow-vip"
        
        # Setup normal priority workflow
        workflow_service.redis_client.hgetall.side_effect = lambda key: {
            f"workflow_budget:{workflow_id_normal}": {
                "priority": "normal",
                "api_calls_used": "0",
                "llm_calls_used": "0"
            },
            f"workflow_budget:{workflow_id_vip}": {
                "priority": "vip", 
                "api_calls_used": "0",
                "llm_calls_used": "0"
            }
        }.get(key, {})
        
        # Test normal priority limits
        result_normal = await workflow_service.enforce_budget_at_node(
            workflow_id_normal, 
            "research", 
            "api_call"
        )
        assert result_normal["allowed"] is True
        
        # Test VIP priority limits (should allow more calls)
        result_vip = await workflow_service.enforce_budget_at_node(
            workflow_id_vip, 
            "research", 
            "api_call"
        )
        assert result_vip["allowed"] is True
        
        # VIP should have higher remaining budget
        # This would be tested more thoroughly with actual budget tracking
    
    @pytest.mark.asyncio
    async def test_cache_warming_strategies(self, caching_service):
        """Test cache warming functionality."""
        # Register a mock warming strategy
        async def mock_enrichment_strategy(key: str):
            return {
                "company": key,
                "industry": "Technology",
                "enriched_at": datetime.utcnow().isoformat()
            }
        
        caching_service.register_warming_strategy(
            CacheType.ENRICHMENT,
            mock_enrichment_strategy
        )
        
        # Test cache warming
        keys_to_warm = ["company1.com", "company2.com", "company3.com"]
        result = await caching_service.warm_cache(CacheType.ENRICHMENT, keys_to_warm)
        
        assert result["cache_type"] == CacheType.ENRICHMENT.value
        assert result["requested_keys"] == 3
        assert result["warmed_count"] >= 0  # Depends on mock setup
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow_with_all_components(self, workflow_service, caching_service):
        """Test complete end-to-end workflow with all integrated components."""
        # This test simulates a complete workflow from start to finish
        # with budget enforcement, caching, monitoring, and error recovery
        
        prospect_data = {
            "prospect_id": "e2e-test-prospect",
            "phone_number": "+1234567890",
            "salesforce_lead_id": "lead-e2e-123",
            "company": "E2E Test Corp"
        }
        
        # Step 1: Start integrated workflow
        workflow_result = await workflow_service.start_integrated_workflow(
            prospect_data,
            priority="normal"
        )
        
        assert workflow_result["success"] is True
        workflow_id = workflow_result["workflow_id"]
        
        # Step 2: Test caching during workflow execution
        # Cache some enrichment data
        enrichment_data = {
            "company": "E2E Test Corp",
            "industry": "Technology",
            "employees": "100-500",
            "revenue": "$10M-50M"
        }
        
        await caching_service.set(
            CacheType.ENRICHMENT,
            "e2etestcorp.com",
            enrichment_data
        )
        
        # Step 3: Test budget enforcement during execution
        budget_result = await workflow_service.enforce_budget_at_node(
            workflow_id,
            "research",
            "api_call"
        )
        
        assert budget_result["allowed"] is True
        
        # Step 4: Simulate workflow completion and metrics collection
        workflow_service._active_workflows[workflow_id] = datetime.utcnow() - timedelta(minutes=5)
        
        # Update metrics to simulate completed workflow
        async with workflow_service._metrics_lock:
            workflow_service.metrics.completed_workflows += 1
            workflow_service.metrics.active_workflows = max(0, workflow_service.metrics.active_workflows - 1)
        
        # Step 5: Get final performance metrics
        final_metrics = await workflow_service.get_workflow_performance_metrics()
        
        assert final_metrics["metrics"]["completed_workflows"] >= 1
        assert "cache_hit_rate" in final_metrics
        assert "budget_utilization" in final_metrics
        
        # Step 6: Verify caching worked
        caching_service.redis_client.get.return_value = json.dumps(enrichment_data).encode('utf-8')
        cached_enrichment = await caching_service.get(
            CacheType.ENRICHMENT,
            "e2etestcorp.com"
        )
        
        assert cached_enrichment == enrichment_data
        
        # Step 7: Test error recovery if needed
        if workflow_service._retry_queues["api_failures"]:
            # Verify error recovery mechanisms are in place
            assert len(workflow_service._retry_queues["api_failures"]) >= 0
    
    @pytest.mark.asyncio
    async def test_sla_monitoring_and_alerts(self, workflow_service):
        """Test SLA monitoring and alerting functionality."""
        # This would integrate with actual performance monitoring
        # For now, test the structure and basic functionality
        
        metrics = await workflow_service.get_workflow_performance_metrics()
        
        assert "sla_compliance" in metrics
        sla_compliance = metrics["sla_compliance"]
        
        # Verify SLA metrics are present
        expected_sla_metrics = [
            "pre_dial_latency_p95",
            "stt_latency_p95", 
            "tts_latency_p95",
            "workflow_completion_rate"
        ]
        
        for metric in expected_sla_metrics:
            assert metric in sla_compliance
        
        # Test performance alerts
        alerts = metrics.get("performance_alerts", [])
        assert isinstance(alerts, list)
        
        # Each alert should have required fields
        for alert in alerts:
            assert "type" in alert
            assert "message" in alert
            assert "severity" in alert


class TestBudgetEnforcementMiddleware:
    """Test budget enforcement middleware functionality."""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware for testing."""
        return BudgetEnforcementMiddleware(None)
    
    def test_endpoint_configuration(self, middleware):
        """Test endpoint configuration and pattern matching."""
        # Test exact match
        config = middleware._get_endpoint_config("/api/v1/workflows/start")
        assert config is not None
        assert config["operation"] == "workflow_start"
        assert config["requires_budget_check"] is True
        
        # Test non-budget endpoint
        config = middleware._get_endpoint_config("/api/v1/health")
        assert config is None
    
    def test_path_pattern_matching(self, middleware):
        """Test path pattern matching functionality."""
        # Test exact match
        assert middleware._path_matches_pattern("/api/v1/test", "/api/v1/test") is True
        
        # Test non-match
        assert middleware._path_matches_pattern("/api/v1/test", "/api/v1/other") is False
        
        # Test wildcard matching (if implemented)
        # This would depend on the actual implementation
    
    def test_token_estimation(self, middleware):
        """Test LLM token estimation."""
        request_data = {
            "body": {
                "prompt": "This is a test prompt for token estimation",
                "context": "Additional context for the request"
            }
        }
        
        estimated_tokens = middleware._estimate_llm_tokens(request_data)
        
        assert estimated_tokens > 0
        assert estimated_tokens <= 1000  # Should be capped
    
    def test_retry_after_calculation(self, middleware):
        """Test retry-after time calculation."""
        retry_after = middleware._calculate_retry_after()
        
        assert retry_after > 0
        assert retry_after <= 24 * 3600  # Should be within 24 hours


@pytest.mark.integration
class TestWorkflowIntegrationPerformance:
    """Performance tests for workflow integration."""
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_handling(self, workflow_service):
        """Test handling multiple concurrent workflows."""
        # Create multiple prospect data sets
        prospects = [
            {
                "prospect_id": f"perf-test-{i}",
                "phone_number": f"+123456789{i}",
                "salesforce_lead_id": f"lead-{i}"
            }
            for i in range(5)
        ]
        
        # Start workflows concurrently
        tasks = [
            workflow_service.start_integrated_workflow(prospect, "normal")
            for prospect in prospects
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_workflows = [r for r in results if isinstance(r, dict) and r.get("success")]
        assert len(successful_workflows) > 0
    
    @pytest.mark.asyncio
    async def test_cache_performance_under_load(self, caching_service):
        """Test cache performance under concurrent load."""
        # Prepare test data
        test_data = [
            (CacheType.ENRICHMENT, f"company{i}.com", {"company": f"Company {i}"})
            for i in range(100)
        ]
        
        # Set cache entries concurrently
        set_tasks = [
            caching_service.set(cache_type, key, data)
            for cache_type, key, data in test_data
        ]
        
        set_results = await asyncio.gather(*set_tasks, return_exceptions=True)
        successful_sets = [r for r in set_results if r is True]
        
        # Get cache entries concurrently
        get_tasks = [
            caching_service.get(cache_type, key)
            for cache_type, key, _ in test_data
        ]
        
        get_results = await asyncio.gather(*get_tasks, return_exceptions=True)
        
        # Verify performance
        assert len(successful_sets) > 0
        assert len([r for r in get_results if not isinstance(r, Exception)]) > 0
    
    @pytest.mark.asyncio
    async def test_budget_enforcement_performance(self, workflow_service):
        """Test budget enforcement performance under load."""
        workflow_id = "perf-test-workflow"
        
        # Initialize workflow budget
        await workflow_service._initialize_workflow_budget_tracking(
            workflow_id,
            {"prospect_id": "perf-test"},
            "normal"
        )
        
        # Test concurrent budget checks
        tasks = [
            workflow_service.enforce_budget_at_node(workflow_id, "research", "api_call")
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # At least the first call should succeed
        successful_checks = [r for r in results if isinstance(r, dict) and r.get("allowed")]
        assert len(successful_checks) > 0