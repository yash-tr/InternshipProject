"""
AI Calling Agent MVP - FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.middleware.security import SecurityMiddleware
from app.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    settings = get_settings()
    
    # Setup logging
    setup_logging(settings.LOG_LEVEL)
    logger = structlog.get_logger()
    
    # Initialize Sentry for error tracking
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(auto_enable=True),
            ],
            traces_sample_rate=0.1,
            environment=settings.ENVIRONMENT,
        )
        logger.info("Sentry initialized", environment=settings.ENVIRONMENT)
    
    # Initialize performance monitoring
    from app.core.performance import performance_monitor
    from app.core.cache import cache_manager
    from app.core.background_tasks import task_queue
    from app.services.monitoring import monitoring_service
    
    await performance_monitor.initialize()
    await cache_manager.initialize()
    await task_queue.start_workers()
    await monitoring_service.start_monitoring()
    logger.info("Performance monitoring, caching, and alerting initialized")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    logger.info("AI Calling Agent MVP started", environment=settings.ENVIRONMENT)
    
    yield
    
    # Cleanup
    await monitoring_service.stop_monitoring()
    await task_queue.stop_workers()
    await cache_manager.close()
    await performance_monitor.close()
    await close_db()
    logger.info("AI Calling Agent MVP shutdown complete")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="AI Calling Agent MVP",
        description="Production-ready AI voice assistant with Salesforce CRM integration",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )
    
    # Performance monitoring middleware
    from app.middleware.performance import PerformanceMiddleware, CacheMiddleware
    app.add_middleware(PerformanceMiddleware)
    app.add_middleware(CacheMiddleware, cache_ttl=300)
    
    # Security middleware
    app.add_middleware(SecurityMiddleware)
    
    # Trusted host middleware for production
    if settings.ENVIRONMENT == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS
        )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Logging middleware
    app.add_middleware(LoggingMiddleware)
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    return app


app = create_application()


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint for monitoring."""
    from app.core.health import perform_health_checks
    
    health_status = await perform_health_checks()
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


@app.get("/metrics")
async def metrics() -> str:
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger = structlog.get_logger()
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )