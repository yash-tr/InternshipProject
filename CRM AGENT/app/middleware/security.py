"""
Security middleware for the AI Calling Agent application.
"""
import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware to add security headers and basic protection."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security enhancements."""
        start_time = time.time()
        
        # Add security headers
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "media-src 'self'; "
            "frame-src 'none';"
        )
        
        # Remove server header for security
        if "server" in response.headers:
            del response.headers["server"]
        
        # Add custom server header
        response.headers["Server"] = "AI-Calling-Agent"
        
        # Log request processing time
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log security events
        if process_time > 5.0:  # Log slow requests
            logger.warning(
                "Slow request detected",
                path=request.url.path,
                method=request.method,
                process_time=process_time,
                client_ip=request.client.host if request.client else "unknown"
            )
        
        return response