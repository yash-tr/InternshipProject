"""
External API Integration and Management Service.

This service provides comprehensive management of external API integrations
with circuit breakers, rate limiting, health monitoring, caching, and cost tracking.
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import hashlib

import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)


class APIProvider(str, Enum):
    """External API providers."""
    SALESFORCE = "salesforce"
    ELEVENLABS = "elevenlabs"
    OPENROUTER = "openrouter"
    TWILIO = "twilio"
    LINKEDIN = "linkedin"
    APOLLO = "apollo"
    ZOOMINFO = "zoominfo"
    SCRAPY = "scrapy"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class APICallResult(str, Enum):
    """API call result types."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class APIEndpoint:
    """Configuration for an API endpoint."""
    provider: APIProvider
    name: str
    base_url: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    cost_per_request: float = 0.01
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    health_check_path: Optional[str] = None
    required_headers: Dict[str, str] = field(default_factory=dict)
    cache_ttl: int = 300  # 5 minutes default


@dataclass
class CircuitBreaker:
    """Circuit breaker for API endpoint."""
    endpoint_name: str
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    failure_threshold: int = 5
    timeout_seconds: int = 60
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None
    success_count_in_half_open: int = 0
    required_successes_to_close: int = 3


@dataclass
class RateLimiter:
    """Rate limiter for API endpoint."""
    endpoint_name: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    current_minute_count: int = 0
    current_hour_count: int = 0
    minute_window_start: datetime = field(default_factory=datetime.utcnow)
    hour_window_start: datetime = field(default_factory=datetime.utcnow)


@dataclass
class APIMetrics:
    """Metrics for API endpoint."""
    endpoint_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    rate_limited_requests: int = 0
    circuit_open_requests: int = 0
    total_cost: float = 0.0
    average_response_time: float = 0.0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None


class ExternalAPIManager:
    """
    Comprehensive external API management with circuit breakers,
    rate limiting, health monitoring, caching, and cost tracking.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audit_service = AuditTrailService()
        
        # Redis for caching and state management
        self.redis_client: Optional[redis.Redis] = None
        
        # HTTP client with connection pooling
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # API endpoint configurations
        self.endpoints: Dict[str, APIEndpoint] = {}
        
        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Rate limiters
        self.rate_limiters: Dict[str, RateLimiter] = {}
        
        # Metrics
        self.metrics: Dict[str, APIMetrics] = {}
        
        # Health check results
        self.health_status: Dict[str, Dict[str, Any]] = {}
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._metrics_update_task: Optional[asyncio.Task] = None
        self._rate_limit_reset_task: Optional[asyncio.Task] = None
        
        # Initialize default endpoints
        self._initialize_default_endpoints()
    
    async def initialize(self):
        """Initialize the external API manager."""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            
            # Initialize HTTP client with connection pooling
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100
                )
            )
            
            # Initialize circuit breakers and rate limiters
            for endpoint_name in self.endpoints:
                await self._initialize_circuit_breaker(endpoint_name)
                await self._initialize_rate_limiter(endpoint_name)
                await self._initialize_metrics(endpoint_name)
            
            # Start background tasks
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._metrics_update_task = asyncio.create_task(self._metrics_update_loop())
            self._rate_limit_reset_task = asyncio.create_task(self._rate_limit_reset_loop())
            
            self.logger.info("External API manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize external API manager: {e}")
            raise
    
    async def make_api_call(self,
                          endpoint_name: str,
                          method: str,
                          path: str = "",
                          params: Optional[Dict[str, Any]] = None,
                          data: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None,
                          cache_key: Optional[str] = None,
                          bypass_cache: bool = False) -> Dict[str, Any]:
        """
        Make an API call with circuit breaker, rate limiting, and caching.
        
        Args:
            endpoint_name: Name of the API endpoint
            method: HTTP method (GET, POST, etc.)
            path: API path to append to base URL
            params: Query parameters
            data: Request body data
            headers: Additional headers
            cache_key: Cache key for response caching
            bypass_cache: Whether to bypass cache
            
        Returns:
            API response with metadata
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Get endpoint configuration
            endpoint = self.endpoints.get(endpoint_name)
            if not endpoint:
                raise ValueError(f"Unknown endpoint: {endpoint_name}")
            
            # Check cache first (if cache_key provided and not bypassing)
            if cache_key and not bypass_cache:
                cached_response = await self._get_cached_response(endpoint_name, cache_key)
                if cached_response:
                    return {
                        "success": True,
                        "data": cached_response,
                        "cached": True,
                        "request_id": request_id,
                        "response_time": time.time() - start_time
                    }
            
            # Check circuit breaker
            circuit_check = await self._check_circuit_breaker(endpoint_name)
            if not circuit_check["allowed"]:
                await self._update_metrics(endpoint_name, APICallResult.CIRCUIT_OPEN, 0, endpoint.cost_per_request)
                return {
                    "success": False,
                    "error": "Circuit breaker is open",
                    "circuit_state": circuit_check["state"],
                    "request_id": request_id,
                    "response_time": time.time() - start_time
                }
            
            # Check rate limits
            rate_limit_check = await self._check_rate_limits(endpoint_name)
            if not rate_limit_check["allowed"]:
                await self._update_metrics(endpoint_name, APICallResult.RATE_LIMITED, 0, 0)
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "rate_limit_info": rate_limit_check,
                    "request_id": request_id,
                    "response_time": time.time() - start_time
                }
            
            # Prepare request
            url = f"{endpoint.base_url.rstrip('/')}/{path.lstrip('/')}" if path else endpoint.base_url
            request_headers = {**endpoint.required_headers}
            if headers:
                request_headers.update(headers)
            
            # Make the API call with retries
            response_data = await self._make_request_with_retries(
                endpoint, method, url, params, data, request_headers, request_id
            )
            
            # Update circuit breaker on success
            await self._record_circuit_breaker_success(endpoint_name)
            
            # Update metrics
            response_time = time.time() - start_time
            await self._update_metrics(endpoint_name, APICallResult.SUCCESS, response_time, endpoint.cost_per_request)
            
            # Cache response if cache_key provided
            if cache_key and response_data.get("success"):
                await self._cache_response(endpoint_name, cache_key, response_data["data"], endpoint.cache_ttl)
            
            # Audit log
            await self.audit_service.log_api_call(
                endpoint_name=endpoint_name,
                method=method,
                url=url,
                request_id=request_id,
                success=response_data.get("success", False),
                response_time=response_time,
                cost=endpoint.cost_per_request
            )
            
            return {
                **response_data,
                "request_id": request_id,
                "response_time": response_time,
                "cached": False
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Update circuit breaker on failure
            await self._record_circuit_breaker_failure(endpoint_name)
            
            # Update metrics
            await self._update_metrics(endpoint_name, APICallResult.FAILURE, response_time, 0)
            
            # Audit log
            await self.audit_service.log_api_call_error(
                endpoint_name=endpoint_name,
                method=method,
                request_id=request_id,
                error=str(e),
                response_time=response_time
            )
            
            self.logger.error(f"API call failed for {endpoint_name}: {e}", request_id=request_id)
            
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id,
                "response_time": response_time
            }
    
    async def get_api_health_status(self, endpoint_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get health status for API endpoints.
        
        Args:
            endpoint_name: Specific endpoint name, or None for all endpoints
            
        Returns:
            Health status information
        """
        if endpoint_name:
            return self.health_status.get(endpoint_name, {"status": "unknown"})
        else:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "endpoints": self.health_status.copy(),
                "overall_health": self._calculate_overall_health()
            }
    
    async def get_api_metrics(self, endpoint_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive API metrics.
        
        Args:
            endpoint_name: Specific endpoint name, or None for all endpoints
            
        Returns:
            API metrics
        """
        if endpoint_name:
            metrics = self.metrics.get(endpoint_name)
            if not metrics:
                return {"error": f"No metrics found for {endpoint_name}"}
            
            return {
                "endpoint_name": metrics.endpoint_name,
                "total_requests": metrics.total_requests,
                "success_rate": metrics.successful_requests / max(1, metrics.total_requests),
                "failure_rate": metrics.failed_requests / max(1, metrics.total_requests),
                "average_response_time": metrics.average_response_time,
                "total_cost": metrics.total_cost,
                "last_success": metrics.last_success_time.isoformat() if metrics.last_success_time else None,
                "last_failure": metrics.last_failure_time.isoformat() if metrics.last_failure_time else None
            }
        else:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "endpoints": {
                    name: {
                        "total_requests": metrics.total_requests,
                        "success_rate": metrics.successful_requests / max(1, metrics.total_requests),
                        "total_cost": metrics.total_cost,
                        "average_response_time": metrics.average_response_time
                    }
                    for name, metrics in self.metrics.items()
                },
                "totals": self._calculate_total_metrics()
            }
    
    async def get_circuit_breaker_status(self, endpoint_name: Optional[str] = None) -> Dict[str, Any]:
        """Get circuit breaker status for endpoints."""
        if endpoint_name:
            cb = self.circuit_breakers.get(endpoint_name)
            if not cb:
                return {"error": f"No circuit breaker found for {endpoint_name}"}
            
            return {
                "endpoint_name": cb.endpoint_name,
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "failure_threshold": cb.failure_threshold,
                "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None,
                "next_attempt": cb.next_attempt_time.isoformat() if cb.next_attempt_time else None
            }
        else:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "circuit_breakers": {
                    name: {
                        "state": cb.state.value,
                        "failure_count": cb.failure_count,
                        "failure_threshold": cb.failure_threshold
                    }
                    for name, cb in self.circuit_breakers.items()
                }
            }
    
    async def reset_circuit_breaker(self, endpoint_name: str) -> bool:
        """Manually reset a circuit breaker."""
        try:
            cb = self.circuit_breakers.get(endpoint_name)
            if not cb:
                return False
            
            cb.state = CircuitBreakerState.CLOSED
            cb.failure_count = 0
            cb.last_failure_time = None
            cb.next_attempt_time = None
            cb.success_count_in_half_open = 0
            
            # Update in Redis
            await self._store_circuit_breaker_state(cb)
            
            self.logger.info(f"Circuit breaker reset for {endpoint_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reset circuit breaker for {endpoint_name}: {e}")
            return False
    
    async def update_endpoint_configuration(self, 
                                          endpoint_name: str, 
                                          config_updates: Dict[str, Any]) -> bool:
        """Update endpoint configuration dynamically."""
        try:
            endpoint = self.endpoints.get(endpoint_name)
            if not endpoint:
                return False
            
            # Update allowed configuration fields
            allowed_fields = [
                'timeout_seconds', 'max_retries', 'retry_delay',
                'rate_limit_per_minute', 'rate_limit_per_hour',
                'cost_per_request', 'circuit_breaker_threshold',
                'circuit_breaker_timeout', 'cache_ttl'
            ]
            
            for field, value in config_updates.items():
                if field in allowed_fields:
                    setattr(endpoint, field, value)
            
            # Update circuit breaker configuration
            if endpoint_name in self.circuit_breakers:
                cb = self.circuit_breakers[endpoint_name]
                if 'circuit_breaker_threshold' in config_updates:
                    cb.failure_threshold = config_updates['circuit_breaker_threshold']
                if 'circuit_breaker_timeout' in config_updates:
                    cb.timeout_seconds = config_updates['circuit_breaker_timeout']
            
            # Update rate limiter configuration
            if endpoint_name in self.rate_limiters:
                rl = self.rate_limiters[endpoint_name]
                if 'rate_limit_per_minute' in config_updates:
                    rl.requests_per_minute = config_updates['rate_limit_per_minute']
                if 'rate_limit_per_hour' in config_updates:
                    rl.requests_per_hour = config_updates['rate_limit_per_hour']
            
            self.logger.info(f"Updated configuration for {endpoint_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration for {endpoint_name}: {e}")
            return False    

    # Private helper methods
    
    def _initialize_default_endpoints(self):
        """Initialize default API endpoint configurations."""
        self.endpoints = {
            "salesforce_auth": APIEndpoint(
                provider=APIProvider.SALESFORCE,
                name="salesforce_auth",
                base_url="https://login.salesforce.com",
                timeout_seconds=10.0,
                max_retries=2,
                rate_limit_per_minute=30,
                rate_limit_per_hour=1000,
                cost_per_request=0.001,
                circuit_breaker_threshold=3,
                health_check_path="/services/oauth2/token"
            ),
            "salesforce_api": APIEndpoint(
                provider=APIProvider.SALESFORCE,
                name="salesforce_api",
                base_url=f"https://{self.settings.SALESFORCE_INSTANCE_URL}",
                timeout_seconds=15.0,
                max_retries=3,
                rate_limit_per_minute=100,
                rate_limit_per_hour=5000,
                cost_per_request=0.002,
                circuit_breaker_threshold=5,
                cache_ttl=300
            ),
            "elevenlabs_tts": APIEndpoint(
                provider=APIProvider.ELEVENLABS,
                name="elevenlabs_tts",
                base_url="https://api.elevenlabs.io/v1",
                timeout_seconds=30.0,
                max_retries=2,
                rate_limit_per_minute=20,
                rate_limit_per_hour=1000,
                cost_per_request=0.05,
                circuit_breaker_threshold=3,
                required_headers={"xi-api-key": self.settings.ELEVENLABS_API_KEY}
            ),
            "elevenlabs_stt": APIEndpoint(
                provider=APIProvider.ELEVENLABS,
                name="elevenlabs_stt",
                base_url="https://api.elevenlabs.io/v1",
                timeout_seconds=45.0,
                max_retries=2,
                rate_limit_per_minute=15,
                rate_limit_per_hour=500,
                cost_per_request=0.03,
                circuit_breaker_threshold=3,
                required_headers={"xi-api-key": self.settings.ELEVENLABS_API_KEY}
            ),
            "openrouter_llm": APIEndpoint(
                provider=APIProvider.OPENROUTER,
                name="openrouter_llm",
                base_url="https://openrouter.ai/api/v1",
                timeout_seconds=60.0,
                max_retries=2,
                rate_limit_per_minute=30,
                rate_limit_per_hour=1000,
                cost_per_request=0.10,
                circuit_breaker_threshold=3,
                required_headers={
                    "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": self.settings.OPENROUTER_REFERER,
                    "X-Title": "AI Calling Agent"
                }
            ),
            "twilio_voice": APIEndpoint(
                provider=APIProvider.TWILIO,
                name="twilio_voice",
                base_url=f"https://api.twilio.com/2010-04-01/Accounts/{self.settings.TWILIO_ACCOUNT_SID}",
                timeout_seconds=20.0,
                max_retries=3,
                rate_limit_per_minute=60,
                rate_limit_per_hour=3000,
                cost_per_request=0.02,
                circuit_breaker_threshold=5
            ),
            "linkedin_api": APIEndpoint(
                provider=APIProvider.LINKEDIN,
                name="linkedin_api",
                base_url="https://api.linkedin.com/v2",
                timeout_seconds=30.0,
                max_retries=2,
                rate_limit_per_minute=10,
                rate_limit_per_hour=200,
                cost_per_request=0.01,
                circuit_breaker_threshold=3,
                cache_ttl=3600  # 1 hour
            ),
            "apollo_api": APIEndpoint(
                provider=APIProvider.APOLLO,
                name="apollo_api",
                base_url="https://api.apollo.io/v1",
                timeout_seconds=25.0,
                max_retries=2,
                rate_limit_per_minute=20,
                rate_limit_per_hour=1000,
                cost_per_request=0.015,
                circuit_breaker_threshold=3,
                cache_ttl=1800  # 30 minutes
            )
        }
    
    async def _initialize_circuit_breaker(self, endpoint_name: str):
        """Initialize circuit breaker for an endpoint."""
        endpoint = self.endpoints[endpoint_name]
        
        # Try to load existing state from Redis
        cb_data = await self.redis_client.hgetall(f"circuit_breaker:{endpoint_name}")
        
        if cb_data:
            # Restore from Redis
            self.circuit_breakers[endpoint_name] = CircuitBreaker(
                endpoint_name=endpoint_name,
                state=CircuitBreakerState(cb_data.get("state", "closed")),
                failure_count=int(cb_data.get("failure_count", 0)),
                failure_threshold=endpoint.circuit_breaker_threshold,
                timeout_seconds=endpoint.circuit_breaker_timeout,
                last_failure_time=datetime.fromisoformat(cb_data["last_failure_time"]) if cb_data.get("last_failure_time") else None,
                next_attempt_time=datetime.fromisoformat(cb_data["next_attempt_time"]) if cb_data.get("next_attempt_time") else None
            )
        else:
            # Create new circuit breaker
            self.circuit_breakers[endpoint_name] = CircuitBreaker(
                endpoint_name=endpoint_name,
                failure_threshold=endpoint.circuit_breaker_threshold,
                timeout_seconds=endpoint.circuit_breaker_timeout
            )
    
    async def _initialize_rate_limiter(self, endpoint_name: str):
        """Initialize rate limiter for an endpoint."""
        endpoint = self.endpoints[endpoint_name]
        
        self.rate_limiters[endpoint_name] = RateLimiter(
            endpoint_name=endpoint_name,
            requests_per_minute=endpoint.rate_limit_per_minute,
            requests_per_hour=endpoint.rate_limit_per_hour
        )
    
    async def _initialize_metrics(self, endpoint_name: str):
        """Initialize metrics for an endpoint."""
        # Try to load existing metrics from Redis
        metrics_data = await self.redis_client.hgetall(f"api_metrics:{endpoint_name}")
        
        if metrics_data:
            self.metrics[endpoint_name] = APIMetrics(
                endpoint_name=endpoint_name,
                total_requests=int(metrics_data.get("total_requests", 0)),
                successful_requests=int(metrics_data.get("successful_requests", 0)),
                failed_requests=int(metrics_data.get("failed_requests", 0)),
                timeout_requests=int(metrics_data.get("timeout_requests", 0)),
                rate_limited_requests=int(metrics_data.get("rate_limited_requests", 0)),
                circuit_open_requests=int(metrics_data.get("circuit_open_requests", 0)),
                total_cost=float(metrics_data.get("total_cost", 0.0)),
                average_response_time=float(metrics_data.get("average_response_time", 0.0)),
                last_success_time=datetime.fromisoformat(metrics_data["last_success_time"]) if metrics_data.get("last_success_time") else None,
                last_failure_time=datetime.fromisoformat(metrics_data["last_failure_time"]) if metrics_data.get("last_failure_time") else None
            )
        else:
            self.metrics[endpoint_name] = APIMetrics(endpoint_name=endpoint_name)
    
    async def _check_circuit_breaker(self, endpoint_name: str) -> Dict[str, Any]:
        """Check if circuit breaker allows the request."""
        cb = self.circuit_breakers.get(endpoint_name)
        if not cb:
            return {"allowed": True, "state": "unknown"}
        
        now = datetime.utcnow()
        
        if cb.state == CircuitBreakerState.CLOSED:
            return {"allowed": True, "state": "closed"}
        
        elif cb.state == CircuitBreakerState.OPEN:
            if cb.next_attempt_time and now >= cb.next_attempt_time:
                # Transition to half-open
                cb.state = CircuitBreakerState.HALF_OPEN
                cb.success_count_in_half_open = 0
                await self._store_circuit_breaker_state(cb)
                return {"allowed": True, "state": "half_open"}
            else:
                return {"allowed": False, "state": "open"}
        
        elif cb.state == CircuitBreakerState.HALF_OPEN:
            return {"allowed": True, "state": "half_open"}
        
        return {"allowed": False, "state": "unknown"}
    
    async def _record_circuit_breaker_success(self, endpoint_name: str):
        """Record a successful API call for circuit breaker."""
        cb = self.circuit_breakers.get(endpoint_name)
        if not cb:
            return
        
        if cb.state == CircuitBreakerState.HALF_OPEN:
            cb.success_count_in_half_open += 1
            if cb.success_count_in_half_open >= cb.required_successes_to_close:
                # Transition back to closed
                cb.state = CircuitBreakerState.CLOSED
                cb.failure_count = 0
                cb.last_failure_time = None
                cb.next_attempt_time = None
                cb.success_count_in_half_open = 0
                
                self.logger.info(f"Circuit breaker closed for {endpoint_name}")
        
        await self._store_circuit_breaker_state(cb)
    
    async def _record_circuit_breaker_failure(self, endpoint_name: str):
        """Record a failed API call for circuit breaker."""
        cb = self.circuit_breakers.get(endpoint_name)
        if not cb:
            return
        
        cb.failure_count += 1
        cb.last_failure_time = datetime.utcnow()
        
        if cb.state == CircuitBreakerState.HALF_OPEN:
            # Transition back to open
            cb.state = CircuitBreakerState.OPEN
            cb.next_attempt_time = datetime.utcnow() + timedelta(seconds=cb.timeout_seconds)
            cb.success_count_in_half_open = 0
            
            self.logger.warning(f"Circuit breaker opened for {endpoint_name} (half-open failure)")
        
        elif cb.state == CircuitBreakerState.CLOSED and cb.failure_count >= cb.failure_threshold:
            # Transition to open
            cb.state = CircuitBreakerState.OPEN
            cb.next_attempt_time = datetime.utcnow() + timedelta(seconds=cb.timeout_seconds)
            
            self.logger.warning(f"Circuit breaker opened for {endpoint_name} (threshold exceeded)")
        
        await self._store_circuit_breaker_state(cb)
    
    async def _store_circuit_breaker_state(self, cb: CircuitBreaker):
        """Store circuit breaker state in Redis."""
        cb_data = {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "last_failure_time": cb.last_failure_time.isoformat() if cb.last_failure_time else "",
            "next_attempt_time": cb.next_attempt_time.isoformat() if cb.next_attempt_time else "",
            "success_count_in_half_open": cb.success_count_in_half_open
        }
        
        await self.redis_client.hset(f"circuit_breaker:{cb.endpoint_name}", mapping=cb_data)
        await self.redis_client.expire(f"circuit_breaker:{cb.endpoint_name}", 24 * 3600)  # 24 hours
    
    async def _check_rate_limits(self, endpoint_name: str) -> Dict[str, Any]:
        """Check if rate limits allow the request."""
        rl = self.rate_limiters.get(endpoint_name)
        if not rl:
            return {"allowed": True}
        
        now = datetime.utcnow()
        
        # Check minute window
        if now - rl.minute_window_start >= timedelta(minutes=1):
            rl.minute_window_start = now
            rl.current_minute_count = 0
        
        # Check hour window
        if now - rl.hour_window_start >= timedelta(hours=1):
            rl.hour_window_start = now
            rl.current_hour_count = 0
        
        # Check limits
        if rl.current_minute_count >= rl.requests_per_minute:
            return {
                "allowed": False,
                "reason": "minute_limit_exceeded",
                "reset_time": (rl.minute_window_start + timedelta(minutes=1)).isoformat()
            }
        
        if rl.current_hour_count >= rl.requests_per_hour:
            return {
                "allowed": False,
                "reason": "hour_limit_exceeded",
                "reset_time": (rl.hour_window_start + timedelta(hours=1)).isoformat()
            }
        
        # Increment counters
        rl.current_minute_count += 1
        rl.current_hour_count += 1
        
        return {
            "allowed": True,
            "remaining_minute": rl.requests_per_minute - rl.current_minute_count,
            "remaining_hour": rl.requests_per_hour - rl.current_hour_count
        }
    
    async def _make_request_with_retries(self,
                                       endpoint: APIEndpoint,
                                       method: str,
                                       url: str,
                                       params: Optional[Dict[str, Any]],
                                       data: Optional[Dict[str, Any]],
                                       headers: Dict[str, str],
                                       request_id: str) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        last_exception = None
        
        for attempt in range(endpoint.max_retries + 1):
            try:
                # Make the request
                response = await self.http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=endpoint.timeout_seconds
                )
                
                # Check if response is successful
                if response.status_code < 400:
                    try:
                        response_data = response.json()
                    except:
                        response_data = {"raw_response": response.text}
                    
                    return {
                        "success": True,
                        "data": response_data,
                        "status_code": response.status_code,
                        "attempt": attempt + 1
                    }
                else:
                    # HTTP error
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    
                    # Don't retry on 4xx errors (client errors)
                    if 400 <= response.status_code < 500:
                        return {
                            "success": False,
                            "error": error_msg,
                            "status_code": response.status_code,
                            "attempt": attempt + 1
                        }
                    
                    # Retry on 5xx errors (server errors)
                    last_exception = Exception(error_msg)
                    
            except httpx.TimeoutException as e:
                last_exception = e
                await self._update_metrics(endpoint.name, APICallResult.TIMEOUT, 0, 0)
                
            except Exception as e:
                last_exception = e
            
            # Wait before retry (except on last attempt)
            if attempt < endpoint.max_retries:
                await asyncio.sleep(endpoint.retry_delay * (2 ** attempt))  # Exponential backoff
        
        # All retries failed
        return {
            "success": False,
            "error": str(last_exception),
            "attempt": endpoint.max_retries + 1
        }
    
    async def _get_cached_response(self, endpoint_name: str, cache_key: str) -> Optional[Any]:
        """Get cached API response."""
        try:
            full_cache_key = f"api_cache:{endpoint_name}:{cache_key}"
            cached_data = await self.redis_client.get(full_cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            return None
    
    async def _cache_response(self, endpoint_name: str, cache_key: str, data: Any, ttl: int):
        """Cache API response."""
        try:
            full_cache_key = f"api_cache:{endpoint_name}:{cache_key}"
            await self.redis_client.setex(
                full_cache_key,
                ttl,
                json.dumps(data, default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")
    
    async def _update_metrics(self, endpoint_name: str, result: APICallResult, response_time: float, cost: float):
        """Update API metrics."""
        metrics = self.metrics.get(endpoint_name)
        if not metrics:
            return
        
        metrics.total_requests += 1
        metrics.total_cost += cost
        
        # Update response time average
        if response_time > 0:
            if metrics.average_response_time == 0:
                metrics.average_response_time = response_time
            else:
                # Running average
                metrics.average_response_time = (
                    (metrics.average_response_time * (metrics.total_requests - 1) + response_time) /
                    metrics.total_requests
                )
        
        # Update result-specific counters
        now = datetime.utcnow()
        
        if result == APICallResult.SUCCESS:
            metrics.successful_requests += 1
            metrics.last_success_time = now
        elif result == APICallResult.FAILURE:
            metrics.failed_requests += 1
            metrics.last_failure_time = now
        elif result == APICallResult.TIMEOUT:
            metrics.timeout_requests += 1
            metrics.last_failure_time = now
        elif result == APICallResult.RATE_LIMITED:
            metrics.rate_limited_requests += 1
        elif result == APICallResult.CIRCUIT_OPEN:
            metrics.circuit_open_requests += 1
        
        # Store in Redis periodically
        if metrics.total_requests % 10 == 0:  # Every 10 requests
            await self._store_metrics(metrics)
    
    async def _store_metrics(self, metrics: APIMetrics):
        """Store metrics in Redis."""
        metrics_data = {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "timeout_requests": metrics.timeout_requests,
            "rate_limited_requests": metrics.rate_limited_requests,
            "circuit_open_requests": metrics.circuit_open_requests,
            "total_cost": metrics.total_cost,
            "average_response_time": metrics.average_response_time,
            "last_success_time": metrics.last_success_time.isoformat() if metrics.last_success_time else "",
            "last_failure_time": metrics.last_failure_time.isoformat() if metrics.last_failure_time else ""
        }
        
        await self.redis_client.hset(f"api_metrics:{metrics.endpoint_name}", mapping=metrics_data)
        await self.redis_client.expire(f"api_metrics:{metrics.endpoint_name}", 7 * 24 * 3600)  # 7 days
    
    def _calculate_overall_health(self) -> str:
        """Calculate overall health status."""
        if not self.health_status:
            return "unknown"
        
        healthy_count = sum(1 for status in self.health_status.values() if status.get("status") == "healthy")
        total_count = len(self.health_status)
        
        if healthy_count == total_count:
            return "healthy"
        elif healthy_count >= total_count * 0.7:  # 70% healthy
            return "degraded"
        else:
            return "unhealthy"
    
    def _calculate_total_metrics(self) -> Dict[str, Any]:
        """Calculate total metrics across all endpoints."""
        totals = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_cost": 0.0,
            "average_response_time": 0.0
        }
        
        if not self.metrics:
            return totals
        
        for metrics in self.metrics.values():
            totals["total_requests"] += metrics.total_requests
            totals["successful_requests"] += metrics.successful_requests
            totals["failed_requests"] += metrics.failed_requests
            totals["total_cost"] += metrics.total_cost
        
        # Calculate overall success rate
        if totals["total_requests"] > 0:
            totals["success_rate"] = totals["successful_requests"] / totals["total_requests"]
        else:
            totals["success_rate"] = 0.0
        
        # Calculate weighted average response time
        total_weighted_time = sum(
            metrics.average_response_time * metrics.total_requests
            for metrics in self.metrics.values()
            if metrics.total_requests > 0
        )
        
        if totals["total_requests"] > 0:
            totals["average_response_time"] = total_weighted_time / totals["total_requests"]
        
        return totals
    
    # Background tasks
    
    async def _health_check_loop(self):
        """Background loop for health checking endpoints."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                for endpoint_name, endpoint in self.endpoints.items():
                    if endpoint.health_check_path:
                        await self._perform_health_check(endpoint_name, endpoint)
                
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
    
    async def _perform_health_check(self, endpoint_name: str, endpoint: APIEndpoint):
        """Perform health check for an endpoint."""
        try:
            start_time = time.time()
            
            # Make health check request
            url = f"{endpoint.base_url.rstrip('/')}/{endpoint.health_check_path.lstrip('/')}"
            
            response = await self.http_client.get(
                url,
                headers=endpoint.required_headers,
                timeout=10.0
            )
            
            response_time = time.time() - start_time
            
            if response.status_code < 400:
                self.health_status[endpoint_name] = {
                    "status": "healthy",
                    "response_time": response_time,
                    "last_check": datetime.utcnow().isoformat(),
                    "status_code": response.status_code
                }
            else:
                self.health_status[endpoint_name] = {
                    "status": "unhealthy",
                    "response_time": response_time,
                    "last_check": datetime.utcnow().isoformat(),
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            self.health_status[endpoint_name] = {
                "status": "unhealthy",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _metrics_update_loop(self):
        """Background loop for updating metrics in Redis."""
        while True:
            try:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                for metrics in self.metrics.values():
                    await self._store_metrics(metrics)
                
            except Exception as e:
                self.logger.error(f"Metrics update loop error: {e}")
    
    async def _rate_limit_reset_loop(self):
        """Background loop for resetting rate limit windows."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.utcnow()
                
                for rl in self.rate_limiters.values():
                    # Reset minute window if needed
                    if now - rl.minute_window_start >= timedelta(minutes=1):
                        rl.minute_window_start = now
                        rl.current_minute_count = 0
                    
                    # Reset hour window if needed
                    if now - rl.hour_window_start >= timedelta(hours=1):
                        rl.hour_window_start = now
                        rl.current_hour_count = 0
                
            except Exception as e:
                self.logger.error(f"Rate limit reset loop error: {e}")


# Global instance
external_api_manager = ExternalAPIManager()