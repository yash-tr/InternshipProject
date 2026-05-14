"""
Health check system for monitoring application and dependencies.
"""
import asyncio
import time
from typing import Dict, Any

import httpx
import structlog
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_async_session

logger = structlog.get_logger()


async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and performance."""
    try:
        start_time = time.time()
        
        async for session in get_async_session():
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "details": "Database connection successful"
        }
        
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Database connection failed"
        }


async def check_salesforce_health() -> Dict[str, Any]:
    """Check Salesforce API connectivity."""
    try:
        settings = get_settings()
        start_time = time.time()
        
        # Test Salesforce connectivity with a simple API call
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.salesforce_base_url}/services/oauth2/token",
                params={
                    "grant_type": "password",
                    "client_id": settings.SALESFORCE_CLIENT_ID,
                    "client_secret": settings.SALESFORCE_CLIENT_SECRET,
                    "username": settings.SALESFORCE_USERNAME,
                    "password": f"{settings.SALESFORCE_PASSWORD}{settings.SALESFORCE_SECURITY_TOKEN}"
                }
            )
        
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "Salesforce API accessible"
            }
        else:
            return {
                "status": "unhealthy",
                "response_code": response.status_code,
                "details": "Salesforce API authentication failed"
            }
            
    except Exception as e:
        logger.error("Salesforce health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Salesforce API connection failed"
        }


async def check_elevenlabs_health() -> Dict[str, Any]:
    """Check ElevenLabs API connectivity."""
    try:
        settings = get_settings()
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY}
            )
        
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "ElevenLabs API accessible"
            }
        else:
            return {
                "status": "unhealthy",
                "response_code": response.status_code,
                "details": "ElevenLabs API authentication failed"
            }
            
    except Exception as e:
        logger.error("ElevenLabs health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "ElevenLabs API connection failed"
        }


async def check_openrouter_health() -> Dict[str, Any]:
    """Check OpenRouter API connectivity."""
    try:
        settings = get_settings()
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
            )
        
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "OpenRouter API accessible"
            }
        else:
            return {
                "status": "unhealthy",
                "response_code": response.status_code,
                "details": "OpenRouter API authentication failed"
            }
            
    except Exception as e:
        logger.error("OpenRouter health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "OpenRouter API connection failed"
        }


async def check_twilio_health() -> Dict[str, Any]:
    """Check Twilio API connectivity."""
    try:
        settings = get_settings()
        start_time = time.time()
        
        # Basic auth for Twilio
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}.json",
                auth=auth
            )
        
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "Twilio API accessible"
            }
        else:
            return {
                "status": "unhealthy",
                "response_code": response.status_code,
                "details": "Twilio API authentication failed"
            }
            
    except Exception as e:
        logger.error("Twilio health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Twilio API connection failed"
        }


async def check_llm_service_health() -> Dict[str, Any]:
    """Check LLM service health and usage statistics."""
    try:
        from app.services.openrouter_llm import openrouter_llm_service
        
        # Get usage statistics
        usage_stats = await openrouter_llm_service.get_token_usage_stats()
        
        # Check if service is accessible (basic validation)
        active_sessions = len(openrouter_llm_service.active_sessions)
        
        return {
            "status": "healthy",
            "active_sessions": active_sessions,
            "daily_tokens": usage_stats.get('daily_usage', {}).get('total_tokens', 0),
            "daily_cost": usage_stats.get('daily_usage', {}).get('cost_estimate', 0.0),
            "model_name": usage_stats.get('model_name', 'unknown'),
            "details": "LLM service operational"
        }
        
    except Exception as e:
        logger.error("LLM service health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "LLM service health check failed"
        }


async def perform_health_checks() -> Dict[str, Any]:
    """Perform all health checks and return comprehensive status."""
    start_time = time.time()
    
    # Run all health checks concurrently
    health_checks = await asyncio.gather(
        check_database_health(),
        check_salesforce_health(),
        check_elevenlabs_health(),
        check_openrouter_health(),
        check_twilio_health(),
        check_llm_service_health(),
        return_exceptions=True
    )
    
    # Map results to service names
    services = {
        "database": health_checks[0],
        "salesforce": health_checks[1],
        "elevenlabs": health_checks[2],
        "openrouter": health_checks[3],
        "twilio": health_checks[4],
        "llm_service": health_checks[5],
    }
    
    # Handle any exceptions
    for service_name, result in services.items():
        if isinstance(result, Exception):
            services[service_name] = {
                "status": "unhealthy",
                "error": str(result),
                "details": f"{service_name} health check failed with exception"
            }
    
    # Determine overall health status
    all_healthy = all(
        service.get("status") == "healthy" 
        for service in services.values()
    )
    
    total_time = (time.time() - start_time) * 1000
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": time.time(),
        "total_check_time_ms": round(total_time, 2),
        "services": services,
        "version": "0.1.0"
    }