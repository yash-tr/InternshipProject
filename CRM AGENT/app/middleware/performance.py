"""
Performance monitoring middleware for request tracking.
"""
import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.performance import performance_monitor

logger = structlog.get_logger()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track request performance metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request performance and metrics."""
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Track concurrent requests
        performance_monitor.track_concurrent_call(increment=True)
        
        try:
            # Use performance monitor context manager
            async with performance_monitor.track_request(method, path):
                response = await call_next(request)
            
            # Log slow requests
            duration = time.time() - start_time
            if duration > 2.0:  # Log requests slower than 2 seconds
                logger.warning("Slow request detected", 
                             method=method, 
                             path=path, 
                             duration=duration,
                             status_code=response.status_code)
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            response.headers["X-Request-ID"] = str(id(request))
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error("Request failed", 
                        method=method, 
                        path=path, 
                        duration=duration,
                        error=str(e))
            raise
        finally:
            # Track concurrent requests
            performance_monitor.track_concurrent_call(increment=False)


class CacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add caching headers and cache responses."""
    
    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add caching logic for appropriate endpoints."""
        method = request.method
        path = request.url.path
        
        # Only cache GET requests for specific endpoints
        cacheable_paths = ["/health", "/metrics", "/api/v1/prospects/"]
        
        if method == "GET" and any(path.startswith(cp) for cp in cacheable_paths):
            # Generate cache key
            cache_key = f"response:{method}:{path}:{str(request.query_params)}"
            
            # Try to get cached response
            cached_response = await performance_monitor.cache_get(cache_key)
            if cached_response:
                logger.debug("Serving cached response", path=path)
                return Response(
                    content=cached_response,
                    media_type="application/json",
                    headers={"X-Cache": "HIT"}
                )
        
        # Process request normally
        response = await call_next(request)
        
        # Cache successful GET responses
        if (method == "GET" and 
            response.status_code == 200 and 
            any(path.startswith(cp) for cp in cacheable_paths)):
            
            # Cache the response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            await performance_monitor.cache_set(
                cache_key, 
                response_body.decode(), 
                ttl=self.cache_ttl
            )
            
            # Recreate response with cached body
            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            response.headers["X-Cache"] = "MISS"
        
        return response