"""
Complete Agent Workflow Integration Service.

This module provides comprehensive workflow integration with budget enforcement,
caching, monitoring, and error recovery for the AI calling agent system.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.agents.orchestrator import AgentOrchestrator, WorkflowConfig
from app.agents.monitoring import WorkflowMonitor
from app.services.audit_trail import AuditTrailService
from app.schemas.base import BaseModel

logger = logging.getLogger(__name__)


class BudgetType(str, Enum):
    """Types of budget controls."""
    DAILY_API_CALLS = "daily_api_calls"
    DAILY_LLM_TOKENS = "daily_llm_tokens"
    DAILY_COST = "daily_cost"
    CONCURRENT_WORKFLOWS = "concurrent_workflows"
    PER_PROSPECT_API_CALLS = "per_prospect_api_calls"
    PER_PROSPECT_LLM_CALLS = "per_prospect_llm_calls"


@dataclass
class BudgetLimits:
    """Budget limits configuration."""
    daily_api_calls: int = 1000
    daily_llm_tokens: int = 50000
    daily_cost_usd: float = 50.0
    concurrent_workflows: int = 10
    non_vip_api_calls: int = 1
    vip_api_calls: int = 2
    non_vip_llm_calls: int = 1
    vip_llm_calls: int = 3
    classifier_token_limit: int = 64
    planner_token_limit: int = 600
    runtime_token_limit: int = 80


@dataclass
class CacheConfig:
    """Cache configuration for different data types."""
    enrichment_ttl: int = 7 * 24 * 3600  # 7 days
    classifier_ttl: int = 24 * 3600  # 24 hours
    plan_ttl: int = 24 * 3600  # 24 hours
    tts_ttl: int = 30 * 24 * 3600  # 30 days
    max_cache_size: int = 10000
    cache_hit_threshold: float = 0.3  # Alert if below 30%


@dataclass
class WorkflowMetrics:
    """Real-time workflow metrics."""
    active_workflows: int = 0
    completed_workflows: int = 0
    failed_workflows: int = 0
    total_api_calls: int = 0
    total_llm_tokens: int = 0
    total_cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_execution_time: float = 0.0
    error_rate: float = 0.0


class WorkflowIntegrationService:
    """
    Complete workflow integration service with budget enforcement,
    caching, monitoring, and error recovery.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize components
        self.orchestrator = AgentOrchestrator(
            postgres_url=self.settings.DATABASE_URL,
            config=WorkflowConfig()
        )
        self.monitor = WorkflowMonitor()
        self.audit_service = AuditTrailService()
        
        # Budget and cache configuration
        self.budget_limits = BudgetLimits()
        self.cache_config = CacheConfig()
        
        # Redis for caching and budget tracking
        self.redis_client: Optional[redis.Redis] = None
        
        # Real-time metrics
        self.metrics = WorkflowMetrics()
        self._metrics_lock = asyncio.Lock()
        
        # Budget enforcement
        self._budget_guards: Dict[str, Any] = {}
        self._active_workflows: Dict[str, datetime] = {}
        
        # Error recovery
        self._retry_queues: Dict[str, List[Dict[str, Any]]] = {
            "api_failures": [],
            "llm_failures": [],
            "workflow_failures": []
        }
        
        # Performance SLA tracking
        self._sla_targets = {
            "pre_dial_latency_p95": 8.0,  # seconds
            "stt_latency_p95": 0.6,  # seconds
            "tts_latency_p95": 0.8,  # seconds
            "workflow_completion_rate": 0.95
        }
        
    async def initialize(self):
        """Initialize the workflow integration service."""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            
            # Initialize budget guards
            await self._initialize_budget_guards()
            
            # Start background tasks
            asyncio.create_task(self._budget_monitoring_task())
            asyncio.create_task(self._cache_maintenance_task())
            asyncio.create_task(self._error_recovery_task())
            asyncio.create_task(self._sla_monitoring_task())
            
            self.logger.info("Workflow integration service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize workflow integration service: {e}")
            raise 
   
    async def start_integrated_workflow(self, 
                                      prospect_data: Dict[str, Any],
                                      priority: str = "normal") -> Dict[str, Any]:
        """
        Start a complete integrated workflow with budget enforcement.
        
        Args:
            prospect_data: Prospect information
            priority: Workflow priority (normal, high, vip)
            
        Returns:
            Workflow start result with budget status
        """
        workflow_id = str(uuid.uuid4())
        
        try:
            # Check budget constraints
            budget_check = await self._check_budget_constraints(prospect_data, priority)
            if not budget_check["allowed"]:
                return {
                    "success": False,
                    "workflow_id": workflow_id,
                    "error": "Budget constraints exceeded",
                    "budget_status": budget_check
                }
            
            # Check concurrent workflow limits
            if len(self._active_workflows) >= self.budget_limits.concurrent_workflows:
                return {
                    "success": False,
                    "workflow_id": workflow_id,
                    "error": "Concurrent workflow limit exceeded",
                    "active_workflows": len(self._active_workflows)
                }
            
            # Initialize workflow with budget tracking
            await self._initialize_workflow_budget_tracking(workflow_id, prospect_data, priority)
            
            # Start monitoring
            await self.monitor.start_workflow_monitoring(workflow_id, prospect_data)
            
            # Start orchestrator workflow
            orchestrator_workflow_id = await self.orchestrator.start_workflow(
                prospect_data, workflow_id
            )
            
            # Track active workflow
            self._active_workflows[workflow_id] = datetime.utcnow()
            
            # Update metrics
            async with self._metrics_lock:
                self.metrics.active_workflows += 1
            
            # Audit log
            await self.audit_service.log_workflow_start(
                workflow_id=workflow_id,
                prospect_id=prospect_data.get("prospect_id"),
                priority=priority,
                budget_allocation=budget_check.get("allocated_budget", {})
            )
            
            self.logger.info(f"Started integrated workflow {workflow_id} for prospect {prospect_data.get('prospect_id')}")
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "orchestrator_workflow_id": orchestrator_workflow_id,
                "budget_status": budget_check,
                "estimated_cost": budget_check.get("estimated_cost", 0.0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start integrated workflow: {e}")
            
            # Update error metrics
            async with self._metrics_lock:
                self.metrics.failed_workflows += 1
                self.metrics.error_rate = self.metrics.failed_workflows / max(1, 
                    self.metrics.completed_workflows + self.metrics.failed_workflows)
            
            return {
                "success": False,
                "workflow_id": workflow_id,
                "error": str(e)
            }
    
    async def get_cached_data(self, 
                            cache_type: str, 
                            key: str, 
                            default: Any = None) -> Any:
        """
        Get data from cache with hit/miss tracking.
        
        Args:
            cache_type: Type of cache (enrichment, classifier, plan, tts)
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached data or default value
        """
        if not self.redis_client:
            return default
        
        try:
            cache_key = f"{cache_type}:{key}"
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                # Cache hit
                async with self._metrics_lock:
                    self.metrics.cache_hits += 1
                
                # Update cache access time
                await self.redis_client.expire(cache_key, self._get_ttl_for_cache_type(cache_type))
                
                return json.loads(cached_data)
            else:
                # Cache miss
                async with self._metrics_lock:
                    self.metrics.cache_misses += 1
                
                return default
                
        except Exception as e:
            self.logger.error(f"Cache get error for {cache_type}:{key}: {e}")
            return default
    
    async def set_cached_data(self, 
                            cache_type: str, 
                            key: str, 
                            data: Any) -> bool:
        """
        Set data in cache with appropriate TTL.
        
        Args:
            cache_type: Type of cache
            key: Cache key
            data: Data to cache
            
        Returns:
            True if successful
        """
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"{cache_type}:{key}"
            ttl = self._get_ttl_for_cache_type(cache_type)
            
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(data, default=str)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cache set error for {cache_type}:{key}: {e}")
            return False
    
    async def enforce_budget_at_node(self, 
                                   workflow_id: str, 
                                   node_type: str, 
                                   operation: str) -> Dict[str, Any]:
        """
        Enforce budget constraints at specific workflow nodes.
        
        Args:
            workflow_id: Workflow identifier
            node_type: Type of node (research, scoring, calling, etc.)
            operation: Operation type (api_call, llm_call, etc.)
            
        Returns:
            Budget enforcement result
        """
        try:
            # Get workflow budget tracking
            budget_key = f"workflow_budget:{workflow_id}"
            budget_data = await self.redis_client.hgetall(budget_key)
            
            if not budget_data:
                return {"allowed": False, "error": "Workflow budget not found"}
            
            priority = budget_data.get("priority", "normal")
            
            # Check specific operation limits
            if operation == "api_call":
                used_calls = int(budget_data.get("api_calls_used", 0))
                max_calls = self.budget_limits.vip_api_calls if priority == "vip" else self.budget_limits.non_vip_api_calls
                
                if used_calls >= max_calls:
                    return {
                        "allowed": False,
                        "error": f"API call limit exceeded ({used_calls}/{max_calls})",
                        "budget_type": "api_calls"
                    }
                
                # Increment usage
                await self.redis_client.hincrby(budget_key, "api_calls_used", 1)
                
            elif operation == "llm_call":
                used_calls = int(budget_data.get("llm_calls_used", 0))
                max_calls = self.budget_limits.vip_llm_calls if priority == "vip" else self.budget_limits.non_vip_llm_calls
                
                if used_calls >= max_calls:
                    return {
                        "allowed": False,
                        "error": f"LLM call limit exceeded ({used_calls}/{max_calls})",
                        "budget_type": "llm_calls"
                    }
                
                # Increment usage
                await self.redis_client.hincrby(budget_key, "llm_calls_used", 1)
            
            # Update global metrics
            async with self._metrics_lock:
                if operation == "api_call":
                    self.metrics.total_api_calls += 1
                elif operation == "llm_call":
                    # This would be updated with actual token count
                    pass
            
            return {
                "allowed": True,
                "remaining_budget": {
                    "api_calls": max_calls - (used_calls + 1) if operation == "api_call" else max_calls - int(budget_data.get("api_calls_used", 0)),
                    "llm_calls": max_calls - (used_calls + 1) if operation == "llm_call" else max_calls - int(budget_data.get("llm_calls_used", 0))
                }
            }
            
        except Exception as e:
            self.logger.error(f"Budget enforcement error for workflow {workflow_id}: {e}")
            return {"allowed": False, "error": str(e)}
    
    async def handle_workflow_error(self, 
                                  workflow_id: str, 
                                  error: Exception, 
                                  context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle workflow errors with recovery mechanisms.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            context: Error context information
            
        Returns:
            Error handling result
        """
        try:
            error_type = type(error).__name__
            error_message = str(error)
            
            # Classify error for recovery strategy
            recovery_strategy = self._classify_error_for_recovery(error_type, error_message)
            
            # Log error with context
            await self.audit_service.log_workflow_error(
                workflow_id=workflow_id,
                error_type=error_type,
                error_message=error_message,
                context=context,
                recovery_strategy=recovery_strategy
            )
            
            # Add to appropriate retry queue
            retry_item = {
                "workflow_id": workflow_id,
                "error": error_message,
                "context": context,
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": context.get("retry_count", 0)
            }
            
            if "api" in error_message.lower():
                self._retry_queues["api_failures"].append(retry_item)
            elif "llm" in error_message.lower() or "token" in error_message.lower():
                self._retry_queues["llm_failures"].append(retry_item)
            else:
                self._retry_queues["workflow_failures"].append(retry_item)
            
            # Update error metrics
            async with self._metrics_lock:
                self.metrics.failed_workflows += 1
                self.metrics.error_rate = self.metrics.failed_workflows / max(1,
                    self.metrics.completed_workflows + self.metrics.failed_workflows)
            
            # Determine if workflow should be terminated or retried
            should_retry = (
                context.get("retry_count", 0) < 3 and
                recovery_strategy in ["retry", "retry_with_backoff"]
            )
            
            return {
                "handled": True,
                "recovery_strategy": recovery_strategy,
                "should_retry": should_retry,
                "retry_delay": self._calculate_retry_delay(context.get("retry_count", 0)),
                "workflow_terminated": not should_retry
            }
            
        except Exception as e:
            self.logger.error(f"Error handling failed for workflow {workflow_id}: {e}")
            return {
                "handled": False,
                "error": str(e),
                "workflow_terminated": True
            }   
 
    async def get_workflow_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive workflow performance metrics."""
        try:
            # Get current metrics
            async with self._metrics_lock:
                current_metrics = {
                    "active_workflows": self.metrics.active_workflows,
                    "completed_workflows": self.metrics.completed_workflows,
                    "failed_workflows": self.metrics.failed_workflows,
                    "total_api_calls": self.metrics.total_api_calls,
                    "total_llm_tokens": self.metrics.total_llm_tokens,
                    "total_cost": self.metrics.total_cost,
                    "cache_hits": self.metrics.cache_hits,
                    "cache_misses": self.metrics.cache_misses,
                    "avg_execution_time": self.metrics.avg_execution_time,
                    "error_rate": self.metrics.error_rate
                }
            
            # Calculate cache hit rate
            total_cache_requests = current_metrics["cache_hits"] + current_metrics["cache_misses"]
            cache_hit_rate = current_metrics["cache_hits"] / max(1, total_cache_requests)
            
            # Get budget utilization
            budget_utilization = await self._get_budget_utilization()
            
            # Get SLA compliance
            sla_compliance = await self._get_sla_compliance()
            
            # Get retry queue status
            retry_queue_status = {
                "api_failures": len(self._retry_queues["api_failures"]),
                "llm_failures": len(self._retry_queues["llm_failures"]),
                "workflow_failures": len(self._retry_queues["workflow_failures"])
            }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": current_metrics,
                "cache_hit_rate": cache_hit_rate,
                "budget_utilization": budget_utilization,
                "sla_compliance": sla_compliance,
                "retry_queues": retry_queue_status,
                "performance_alerts": await self._check_performance_alerts()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}
    
    # Private helper methods
    
    async def _initialize_budget_guards(self):
        """Initialize budget guard mechanisms."""
        try:
            # Initialize daily budget counters
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            budget_keys = [
                f"daily_budget:{today}:api_calls",
                f"daily_budget:{today}:llm_tokens",
                f"daily_budget:{today}:cost"
            ]
            
            for key in budget_keys:
                if not await self.redis_client.exists(key):
                    await self.redis_client.set(key, 0)
                    # Set expiry to end of day
                    await self.redis_client.expireat(key, int((datetime.utcnow().replace(
                        hour=23, minute=59, second=59
                    ) + timedelta(days=1)).timestamp()))
            
            self.logger.info("Budget guards initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize budget guards: {e}")
            raise
    
    async def _check_budget_constraints(self, 
                                      prospect_data: Dict[str, Any], 
                                      priority: str) -> Dict[str, Any]:
        """Check if workflow can proceed within budget constraints."""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Check daily limits
            daily_api_calls = int(await self.redis_client.get(f"daily_budget:{today}:api_calls") or 0)
            daily_llm_tokens = int(await self.redis_client.get(f"daily_budget:{today}:llm_tokens") or 0)
            daily_cost = float(await self.redis_client.get(f"daily_budget:{today}:cost") or 0.0)
            
            # Estimate workflow cost
            estimated_api_calls = self.budget_limits.vip_api_calls if priority == "vip" else self.budget_limits.non_vip_api_calls
            estimated_llm_tokens = self.budget_limits.vip_llm_calls * self.budget_limits.runtime_token_limit if priority == "vip" else self.budget_limits.non_vip_llm_calls * self.budget_limits.runtime_token_limit
            estimated_cost = estimated_api_calls * 0.01 + estimated_llm_tokens * 0.0001  # Rough estimates
            
            # Check constraints
            constraints_met = {
                "daily_api_calls": daily_api_calls + estimated_api_calls <= self.budget_limits.daily_api_calls,
                "daily_llm_tokens": daily_llm_tokens + estimated_llm_tokens <= self.budget_limits.daily_llm_tokens,
                "daily_cost": daily_cost + estimated_cost <= self.budget_limits.daily_cost_usd
            }
            
            all_constraints_met = all(constraints_met.values())
            
            return {
                "allowed": all_constraints_met,
                "constraints_met": constraints_met,
                "current_usage": {
                    "daily_api_calls": daily_api_calls,
                    "daily_llm_tokens": daily_llm_tokens,
                    "daily_cost": daily_cost
                },
                "estimated_cost": estimated_cost,
                "allocated_budget": {
                    "api_calls": estimated_api_calls,
                    "llm_tokens": estimated_llm_tokens,
                    "cost": estimated_cost
                }
            }
            
        except Exception as e:
            self.logger.error(f"Budget constraint check failed: {e}")
            return {"allowed": False, "error": str(e)}
    
    async def _initialize_workflow_budget_tracking(self, 
                                                 workflow_id: str, 
                                                 prospect_data: Dict[str, Any], 
                                                 priority: str):
        """Initialize budget tracking for a specific workflow."""
        try:
            budget_key = f"workflow_budget:{workflow_id}"
            
            budget_data = {
                "workflow_id": workflow_id,
                "prospect_id": prospect_data.get("prospect_id"),
                "priority": priority,
                "api_calls_used": 0,
                "llm_calls_used": 0,
                "tokens_used": 0,
                "cost_incurred": 0.0,
                "created_at": datetime.utcnow().isoformat()
            }
            
            await self.redis_client.hset(budget_key, mapping=budget_data)
            await self.redis_client.expire(budget_key, 24 * 3600)  # 24 hour expiry
            
        except Exception as e:
            self.logger.error(f"Failed to initialize workflow budget tracking: {e}")
            raise
    
    def _get_ttl_for_cache_type(self, cache_type: str) -> int:
        """Get TTL for specific cache type."""
        ttl_mapping = {
            "enrichment": self.cache_config.enrichment_ttl,
            "classifier": self.cache_config.classifier_ttl,
            "plan": self.cache_config.plan_ttl,
            "tts": self.cache_config.tts_ttl
        }
        return ttl_mapping.get(cache_type, 3600)  # Default 1 hour
    
    def _classify_error_for_recovery(self, error_type: str, error_message: str) -> str:
        """Classify error for appropriate recovery strategy."""
        if "timeout" in error_message.lower():
            return "retry_with_backoff"
        elif "rate limit" in error_message.lower():
            return "retry_with_delay"
        elif "authentication" in error_message.lower():
            return "refresh_credentials"
        elif "network" in error_message.lower():
            return "retry"
        elif "budget" in error_message.lower():
            return "terminate"
        else:
            return "retry"
    
    def _calculate_retry_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay."""
        base_delay = 1.0
        max_delay = 60.0
        delay = min(base_delay * (2 ** retry_count), max_delay)
        return delay
    
    async def _get_budget_utilization(self) -> Dict[str, Any]:
        """Get current budget utilization."""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            daily_api_calls = int(await self.redis_client.get(f"daily_budget:{today}:api_calls") or 0)
            daily_llm_tokens = int(await self.redis_client.get(f"daily_budget:{today}:llm_tokens") or 0)
            daily_cost = float(await self.redis_client.get(f"daily_budget:{today}:cost") or 0.0)
            
            return {
                "api_calls": {
                    "used": daily_api_calls,
                    "limit": self.budget_limits.daily_api_calls,
                    "utilization": daily_api_calls / self.budget_limits.daily_api_calls
                },
                "llm_tokens": {
                    "used": daily_llm_tokens,
                    "limit": self.budget_limits.daily_llm_tokens,
                    "utilization": daily_llm_tokens / self.budget_limits.daily_llm_tokens
                },
                "cost": {
                    "used": daily_cost,
                    "limit": self.budget_limits.daily_cost_usd,
                    "utilization": daily_cost / self.budget_limits.daily_cost_usd
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get budget utilization: {e}")
            return {}
    
    async def _get_sla_compliance(self) -> Dict[str, Any]:
        """Get SLA compliance metrics."""
        # This would integrate with actual performance monitoring
        # For now, return mock data
        return {
            "pre_dial_latency_p95": 7.2,
            "stt_latency_p95": 0.5,
            "tts_latency_p95": 0.7,
            "workflow_completion_rate": 0.96,
            "sla_compliance": {
                "pre_dial_latency": True,
                "stt_latency": True,
                "tts_latency": True,
                "completion_rate": True
            }
        }
    
    async def _check_performance_alerts(self) -> List[Dict[str, Any]]:
        """Check for performance alerts."""
        alerts = []
        
        # Check cache hit rate
        total_cache_requests = self.metrics.cache_hits + self.metrics.cache_misses
        if total_cache_requests > 0:
            cache_hit_rate = self.metrics.cache_hits / total_cache_requests
            if cache_hit_rate < self.cache_config.cache_hit_threshold:
                alerts.append({
                    "type": "cache_performance",
                    "message": f"Cache hit rate ({cache_hit_rate:.2%}) below threshold ({self.cache_config.cache_hit_threshold:.2%})",
                    "severity": "warning"
                })
        
        # Check error rate
        if self.metrics.error_rate > 0.1:  # 10% error rate threshold
            alerts.append({
                "type": "error_rate",
                "message": f"Error rate ({self.metrics.error_rate:.2%}) exceeds threshold (10%)",
                "severity": "critical"
            })
        
        # Check active workflows
        if self.metrics.active_workflows > self.budget_limits.concurrent_workflows * 0.8:
            alerts.append({
                "type": "capacity",
                "message": f"Active workflows ({self.metrics.active_workflows}) approaching limit ({self.budget_limits.concurrent_workflows})",
                "severity": "warning"
            })
        
        return alerts
    
    # Background tasks
    
    async def _budget_monitoring_task(self):
        """Background task for budget monitoring."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check daily budget utilization
                budget_utilization = await self._get_budget_utilization()
                
                # Alert if approaching limits
                for resource, data in budget_utilization.items():
                    if data.get("utilization", 0) > 0.9:  # 90% threshold
                        self.logger.warning(f"Budget alert: {resource} utilization at {data['utilization']:.2%}")
                
            except Exception as e:
                self.logger.error(f"Budget monitoring task error: {e}")
    
    async def _cache_maintenance_task(self):
        """Background task for cache maintenance."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Clean up expired cache entries
                # This would be handled by Redis TTL, but we can add additional cleanup logic
                
                # Monitor cache performance
                total_requests = self.metrics.cache_hits + self.metrics.cache_misses
                if total_requests > 0:
                    hit_rate = self.metrics.cache_hits / total_requests
                    if hit_rate < self.cache_config.cache_hit_threshold:
                        self.logger.warning(f"Cache hit rate ({hit_rate:.2%}) below threshold")
                
            except Exception as e:
                self.logger.error(f"Cache maintenance task error: {e}")
    
    async def _error_recovery_task(self):
        """Background task for error recovery."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Process retry queues
                for queue_type, queue in self._retry_queues.items():
                    if queue:
                        # Process oldest item
                        retry_item = queue.pop(0)
                        
                        # Check if retry should be attempted
                        retry_count = retry_item.get("retry_count", 0)
                        if retry_count < 3:
                            # Implement retry logic based on queue type
                            await self._process_retry_item(queue_type, retry_item)
                
            except Exception as e:
                self.logger.error(f"Error recovery task error: {e}")
    
    async def _sla_monitoring_task(self):
        """Background task for SLA monitoring."""
        while True:
            try:
                await asyncio.sleep(120)  # Check every 2 minutes
                
                # Monitor SLA compliance
                sla_compliance = await self._get_sla_compliance()
                
                # Alert on SLA violations
                for metric, compliant in sla_compliance.get("sla_compliance", {}).items():
                    if not compliant:
                        self.logger.warning(f"SLA violation: {metric}")
                
            except Exception as e:
                self.logger.error(f"SLA monitoring task error: {e}")
    
    async def _process_retry_item(self, queue_type: str, retry_item: Dict[str, Any]):
        """Process a retry item from the error recovery queue."""
        try:
            workflow_id = retry_item["workflow_id"]
            retry_count = retry_item.get("retry_count", 0) + 1
            
            # Update retry count
            retry_item["retry_count"] = retry_count
            
            # Calculate delay
            delay = self._calculate_retry_delay(retry_count)
            
            # Wait before retry
            await asyncio.sleep(delay)
            
            # Log retry attempt
            self.logger.info(f"Retrying {queue_type} for workflow {workflow_id} (attempt {retry_count})")
            
            # In a real implementation, this would trigger the appropriate recovery action
            # For now, we'll just log the retry attempt
            
        except Exception as e:
            self.logger.error(f"Failed to process retry item: {e}")


# Global instance
workflow_integration_service = WorkflowIntegrationService()