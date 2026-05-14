"""
Budget Enforcement Middleware.

This middleware provides budget enforcement at the HTTP request level,
integrating with the workflow integration service for comprehensive cost control.
"""

import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import structlog

from app.services.workflow_integration import workflow_integration_service
from app.core.config import get_settings

logger = structlog.get_logger()


class BudgetEnforcementMiddleware:
    """
    Middleware for enforcing budget constraints at the API level.
    
    Integrates with the workflow integration service to provide
    comprehensive budget enforcement across all operations.
    """
    
    def __init__(self, app):
        self.app = app
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Budget-sensitive endpoints
        self._budget_endpoints = {
            "/api/v1/workflows/start": {
                "operation": "workflow_start",
                "cost_estimate": 0.10,
                "requires_budget_check": True
            },
            "/api/v1/research/enrich": {
                "operation": "api_call",
                "cost_estimate": 0.01,
                "requires_budget_check": True
            },
            "/api/v1/llm/generate": {
                "operation": "llm_call",
                "cost_estimate": 0.05,
                "requires_budget_check": True
            },
            "/webhook/twilio/call": {
                "operation": "call_handling",
                "cost_estimate": 0.02,
                "requires_budget_check": False  # Don't block incoming calls
            }
        }
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process request with budget enforcement."""
        start_time = time.time()
        
        try:
            # Check if endpoint requires budget enforcement
            endpoint_config = self._get_endpoint_config(request.url.path)
            
            if endpoint_config and endpoint_config.get("requires_budget_check"):
                # Perform budget check
                budget_check = await self._check_endpoint_budget(request, endpoint_config)
                
                if not budget_check["allowed"]:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Budget limit exceeded",
                            "details": budget_check.get("error"),
                            "budget_status": budget_check,
                            "retry_after": budget_check.get("retry_after", 3600)
                        }
                    )
            
            # Process request
            response = await call_next(request)
            
            # Track successful operation
            if endpoint_config:
                await self._track_operation_success(request, endpoint_config, response)
            
            # Add budget headers to response
            if endpoint_config and endpoint_config.get("requires_budget_check"):
                await self._add_budget_headers(response, request)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Budget enforcement middleware error: {e}")
            # Don't block requests due to middleware errors
            return await call_next(request)
        finally:
            # Track request timing
            processing_time = time.time() - start_time
            logger.info(
                "Request processed",
                path=request.url.path,
                method=request.method,
                processing_time=processing_time
            )
    
    def _get_endpoint_config(self, path: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific endpoint."""
        # Exact match first
        if path in self._budget_endpoints:
            return self._budget_endpoints[path]
        
        # Pattern matching for dynamic paths
        for endpoint_pattern, config in self._budget_endpoints.items():
            if self._path_matches_pattern(path, endpoint_pattern):
                return config
        
        return None
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a pattern with wildcards."""
        # Simple pattern matching - could be enhanced with regex
        if "*" in pattern:
            pattern_parts = pattern.split("*")
            return all(part in path for part in pattern_parts if part)
        return path == pattern
    
    async def _check_endpoint_budget(self, 
                                   request: Request, 
                                   endpoint_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check budget constraints for an endpoint."""
        try:
            operation = endpoint_config["operation"]
            cost_estimate = endpoint_config["cost_estimate"]
            
            # Get request context
            request_data = await self._extract_request_context(request)
            
            # Check daily budget limits
            daily_budget_check = await workflow_integration_service._get_budget_utilization()
            
            # Check if adding this operation would exceed limits
            current_cost = daily_budget_check.get("cost", {}).get("used", 0.0)
            daily_limit = daily_budget_check.get("cost", {}).get("limit", 50.0)
            
            if current_cost + cost_estimate > daily_limit:
                return {
                    "allowed": False,
                    "error": f"Daily cost limit would be exceeded ({current_cost + cost_estimate:.2f} > {daily_limit:.2f})",
                    "budget_type": "daily_cost",
                    "retry_after": self._calculate_retry_after()
                }
            
            # Check API call limits for API operations
            if operation == "api_call":
                current_api_calls = daily_budget_check.get("api_calls", {}).get("used", 0)
                api_limit = daily_budget_check.get("api_calls", {}).get("limit", 1000)
                
                if current_api_calls >= api_limit:
                    return {
                        "allowed": False,
                        "error": f"Daily API call limit exceeded ({current_api_calls}/{api_limit})",
                        "budget_type": "daily_api_calls",
                        "retry_after": self._calculate_retry_after()
                    }
            
            # Check LLM token limits for LLM operations
            if operation == "llm_call":
                current_tokens = daily_budget_check.get("llm_tokens", {}).get("used", 0)
                token_limit = daily_budget_check.get("llm_tokens", {}).get("limit", 50000)
                
                # Estimate tokens for this request
                estimated_tokens = self._estimate_llm_tokens(request_data)
                
                if current_tokens + estimated_tokens > token_limit:
                    return {
                        "allowed": False,
                        "error": f"Daily LLM token limit would be exceeded ({current_tokens + estimated_tokens}/{token_limit})",
                        "budget_type": "daily_llm_tokens",
                        "retry_after": self._calculate_retry_after()
                    }
            
            # Check workflow-specific limits for workflow operations
            if operation == "workflow_start":
                # Check concurrent workflow limits
                active_workflows = len(workflow_integration_service._active_workflows)
                workflow_limit = workflow_integration_service.budget_limits.concurrent_workflows
                
                if active_workflows >= workflow_limit:
                    return {
                        "allowed": False,
                        "error": f"Concurrent workflow limit exceeded ({active_workflows}/{workflow_limit})",
                        "budget_type": "concurrent_workflows",
                        "retry_after": 300  # 5 minutes
                    }
            
            return {
                "allowed": True,
                "estimated_cost": cost_estimate,
                "remaining_budget": {
                    "cost": daily_limit - current_cost,
                    "api_calls": daily_budget_check.get("api_calls", {}).get("limit", 1000) - daily_budget_check.get("api_calls", {}).get("used", 0),
                    "llm_tokens": daily_budget_check.get("llm_tokens", {}).get("limit", 50000) - daily_budget_check.get("llm_tokens", {}).get("used", 0)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Budget check failed: {e}")
            # Allow request if budget check fails (fail open)
            return {"allowed": True, "error": f"Budget check failed: {e}"}
    
    async def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """Extract relevant context from the request."""
        try:
            # Get request body if present
            body = {}
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.json()
                except:
                    body = {}
            
            # Get query parameters
            query_params = dict(request.query_params)
            
            # Get headers
            headers = dict(request.headers)
            
            return {
                "method": request.method,
                "path": request.url.path,
                "body": body,
                "query_params": query_params,
                "user_agent": headers.get("user-agent"),
                "content_length": headers.get("content-length", "0")
            }
            
        except Exception as e:
            self.logger.error(f"Failed to extract request context: {e}")
            return {}
    
    def _estimate_llm_tokens(self, request_data: Dict[str, Any]) -> int:
        """Estimate LLM tokens for a request."""
        try:
            # Simple estimation based on request content
            body = request_data.get("body", {})
            
            # Count characters in text fields
            text_content = ""
            for key, value in body.items():
                if isinstance(value, str):
                    text_content += value
            
            # Rough estimation: 4 characters per token
            estimated_tokens = len(text_content) // 4
            
            # Add base overhead
            estimated_tokens += 50
            
            # Cap at reasonable maximum
            return min(estimated_tokens, 1000)
            
        except Exception as e:
            self.logger.error(f"Token estimation failed: {e}")
            return 100  # Default estimate
    
    def _calculate_retry_after(self) -> int:
        """Calculate retry-after time in seconds."""
        # Calculate seconds until next day (when daily limits reset)
        now = datetime.utcnow()
        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if next_day <= now:
            next_day = next_day.replace(day=next_day.day + 1)
        
        return int((next_day - now).total_seconds())
    
    async def _track_operation_success(self, 
                                     request: Request, 
                                     endpoint_config: Dict[str, Any], 
                                     response: Response):
        """Track successful operation for budget accounting."""
        try:
            if response.status_code < 400:  # Success response
                operation = endpoint_config["operation"]
                cost_estimate = endpoint_config["cost_estimate"]
                
                # Update budget tracking
                today = datetime.utcnow().strftime("%Y-%m-%d")
                
                if workflow_integration_service.redis_client:
                    # Update daily cost
                    await workflow_integration_service.redis_client.incrbyfloat(
                        f"daily_budget:{today}:cost", 
                        cost_estimate
                    )
                    
                    # Update operation-specific counters
                    if operation == "api_call":
                        await workflow_integration_service.redis_client.incr(
                            f"daily_budget:{today}:api_calls"
                        )
                    elif operation == "llm_call":
                        # This would be updated with actual token count from response
                        estimated_tokens = 100  # Placeholder
                        await workflow_integration_service.redis_client.incr(
                            f"daily_budget:{today}:llm_tokens",
                            estimated_tokens
                        )
                
                # Update global metrics
                async with workflow_integration_service._metrics_lock:
                    workflow_integration_service.metrics.total_cost += cost_estimate
                    
                    if operation == "api_call":
                        workflow_integration_service.metrics.total_api_calls += 1
                    elif operation == "llm_call":
                        workflow_integration_service.metrics.total_llm_tokens += 100  # Placeholder
                
        except Exception as e:
            self.logger.error(f"Failed to track operation success: {e}")
    
    async def _add_budget_headers(self, response: Response, request: Request):
        """Add budget-related headers to the response."""
        try:
            budget_utilization = await workflow_integration_service._get_budget_utilization()
            
            # Add budget utilization headers
            response.headers["X-Budget-Cost-Used"] = str(budget_utilization.get("cost", {}).get("used", 0))
            response.headers["X-Budget-Cost-Limit"] = str(budget_utilization.get("cost", {}).get("limit", 50))
            response.headers["X-Budget-API-Calls-Used"] = str(budget_utilization.get("api_calls", {}).get("used", 0))
            response.headers["X-Budget-API-Calls-Limit"] = str(budget_utilization.get("api_calls", {}).get("limit", 1000))
            response.headers["X-Budget-Tokens-Used"] = str(budget_utilization.get("llm_tokens", {}).get("used", 0))
            response.headers["X-Budget-Tokens-Limit"] = str(budget_utilization.get("llm_tokens", {}).get("limit", 50000))
            
        except Exception as e:
            self.logger.error(f"Failed to add budget headers: {e}")


def create_budget_enforcement_middleware():
    """Factory function to create budget enforcement middleware."""
    return BudgetEnforcementMiddleware