"""
Performance monitoring and optimization utilities.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

import structlog
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import redis.asyncio as redis
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_database_connections', 'Active database connections')
CACHE_HIT_RATE = Gauge('cache_hit_rate', 'Cache hit rate percentage')
API_CALL_DURATION = Histogram('external_api_call_duration_seconds', 'External API call duration', ['service'])
CONCURRENT_CALLS = Gauge('concurrent_calls_active', 'Number of active concurrent calls')

# Performance tracking
performance_metrics = {
    'request_count': 0,
    'average_response_time': 0.0,
    'cache_hits': 0,
    'cache_misses': 0,
    'active_calls': 0,
    'database_connections': 0
}


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
        self._metrics_server_started = False
    
    async def initialize(self):
        """Initialize performance monitoring."""
        try:
            # Initialize Redis connection for caching
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established for performance monitoring")
            
            # Start Prometheus metrics server
            if not self._metrics_server_started:
                start_http_server(9090)
                self._metrics_server_started = True
                logger.info("Prometheus metrics server started on port 9090")
            
        except Exception as e:
            logger.error("Failed to initialize performance monitoring", error=str(e))
            # Continue without Redis if it's not available
            self.redis_client = None
    
    async def close(self):
        """Close performance monitoring connections."""
        if self.redis_client:
            await self.redis_client.close()
    
    @asynccontextmanager
    async def track_request(self, method: str, endpoint: str):
        """Track HTTP request performance."""
        start_time = time.time()
        status = "200"
        
        try:
            yield
        except Exception as e:
            status = "500"
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_DURATION.observe(duration)
            
            # Update internal metrics
            performance_metrics['request_count'] += 1
            performance_metrics['average_response_time'] = (
                (performance_metrics['average_response_time'] * (performance_metrics['request_count'] - 1) + duration) /
                performance_metrics['request_count']
            )
    
    @asynccontextmanager
    async def track_api_call(self, service: str):
        """Track external API call performance."""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            API_CALL_DURATION.labels(service=service).observe(duration)
    
    async def cache_get(self, key: str) -> Optional[str]:
        """Get value from cache with hit/miss tracking."""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                performance_metrics['cache_hits'] += 1
            else:
                performance_metrics['cache_misses'] += 1
            
            # Update cache hit rate
            total_requests = performance_metrics['cache_hits'] + performance_metrics['cache_misses']
            if total_requests > 0:
                hit_rate = (performance_metrics['cache_hits'] / total_requests) * 100
                CACHE_HIT_RATE.set(hit_rate)
            
            return value
        except Exception as e:
            logger.error("Cache get error", key=key, error=str(e))
            performance_metrics['cache_misses'] += 1
            return None
    
    async def cache_set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error("Cache set error", key=key, error=str(e))
            return False
    
    async def cache_delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
            return False
    
    def track_concurrent_call(self, increment: bool = True):
        """Track concurrent call count."""
        if increment:
            performance_metrics['active_calls'] += 1
            CONCURRENT_CALLS.inc()
        else:
            performance_metrics['active_calls'] = max(0, performance_metrics['active_calls'] - 1)
            CONCURRENT_CALLS.dec()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return performance_metrics.copy()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def track_performance(func_name: str):
    """Decorator to track function performance."""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    logger.debug("Function performance", 
                               function=func_name, 
                               duration=duration)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    logger.debug("Function performance", 
                               function=func_name, 
                               duration=duration)
            return sync_wrapper
    return decorator


class ConnectionPool:
    """Enhanced connection pooling for external APIs."""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.active_connections = 0
        self.semaphore = asyncio.Semaphore(max_connections)
    
    @asynccontextmanager
    async def get_connection(self):
        """Get connection from pool."""
        async with self.semaphore:
            self.active_connections += 1
            ACTIVE_CONNECTIONS.set(self.active_connections)
            try:
                yield
            finally:
                self.active_connections -= 1
                ACTIVE_CONNECTIONS.set(self.active_connections)


# Global connection pools for different services
salesforce_pool = ConnectionPool(max_connections=5)
elevenlabs_pool = ConnectionPool(max_connections=10)
openrouter_pool = ConnectionPool(max_connections=8)


class BackgroundTaskManager:
    """Manage background tasks for async processing."""
    
    def __init__(self):
        self.tasks = set()
    
    def create_task(self, coro, name: str = None):
        """Create and track background task."""
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task
    
    async def shutdown(self):
        """Shutdown all background tasks."""
        if self.tasks:
            logger.info(f"Shutting down {len(self.tasks)} background tasks")
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)


# Global background task manager
background_tasks = BackgroundTaskManager()