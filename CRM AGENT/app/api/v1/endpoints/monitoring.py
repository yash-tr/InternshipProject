"""
Monitoring and alerting API endpoints.
"""
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.monitoring import (
    monitoring_service,
    Alert,
    HealthCheck,
    AlertSeverity,
    AlertStatus
)

logger = structlog.get_logger()

router = APIRouter()


class AlertResponse(BaseModel):
    """Alert response model."""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    current_value: float
    threshold_value: float
    created_at: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None


class HealthStatusResponse(BaseModel):
    """Health status response model."""
    status: str
    services: Dict[str, Any]
    unhealthy_services: List[str]
    degraded_services: List[str]
    active_alerts: int
    last_updated: str


@router.get("/health", response_model=HealthStatusResponse)
async def get_health_status() -> HealthStatusResponse:
    """Get overall system health status."""
    try:
        health_status = monitoring_service.get_health_status()
        
        logger.info("Health status retrieved", 
                   status=health_status["status"],
                   active_alerts=health_status["active_alerts"])
        
        return HealthStatusResponse(**health_status)
        
    except Exception as e:
        logger.error("Failed to get health status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get health status")


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[AlertStatus] = Query(None, description="Filter alerts by status"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter alerts by severity")
) -> List[AlertResponse]:
    """Get alerts with optional filtering."""
    try:
        all_alerts = monitoring_service.get_all_alerts()
        
        # Apply filters
        filtered_alerts = all_alerts
        
        if status:
            filtered_alerts = [alert for alert in filtered_alerts if alert.status == status]
        
        if severity:
            filtered_alerts = [alert for alert in filtered_alerts if alert.severity == severity]
        
        # Convert to response format
        alert_responses = []
        for alert in filtered_alerts:
            alert_responses.append(AlertResponse(
                id=alert.id,
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value,
                created_at=alert.created_at.isoformat(),
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None
            ))
        
        logger.info("Alerts retrieved", 
                   total_alerts=len(all_alerts),
                   filtered_alerts=len(alert_responses))
        
        return alert_responses
        
    except Exception as e:
        logger.error("Failed to get alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get alerts")


@router.get("/alerts/active", response_model=List[AlertResponse])
async def get_active_alerts() -> List[AlertResponse]:
    """Get only active alerts."""
    try:
        active_alerts = monitoring_service.get_active_alerts()
        
        alert_responses = []
        for alert in active_alerts:
            alert_responses.append(AlertResponse(
                id=alert.id,
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value,
                created_at=alert.created_at.isoformat(),
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None
            ))
        
        logger.info("Active alerts retrieved", count=len(alert_responses))
        
        return alert_responses
        
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get active alerts")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an active alert."""
    try:
        success = await monitoring_service.acknowledge_alert(alert_id)
        
        if success:
            logger.info("Alert acknowledged", alert_id=alert_id)
            return {"status": "success", "message": f"Alert {alert_id} acknowledged"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or not active")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    try:
        success = await monitoring_service.resolve_alert(alert_id)
        
        if success:
            logger.info("Alert resolved", alert_id=alert_id)
            return {"status": "success", "message": f"Alert {alert_id} resolved"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resolve alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.get("/services")
async def get_service_health() -> Dict[str, Any]:
    """Get health status of all monitored services."""
    try:
        health_status = monitoring_service.get_health_status()
        
        # Format service health data
        services = {}
        for service_name, health_check in health_status["services"].items():
            services[service_name] = {
                "status": health_check.status,
                "response_time": health_check.response_time,
                "last_check": health_check.last_check.isoformat(),
                "error_message": health_check.error_message,
                "metadata": health_check.metadata
            }
        
        return {
            "services": services,
            "summary": {
                "total_services": len(services),
                "healthy_services": len([s for s in services.values() if s["status"] == "healthy"]),
                "degraded_services": len([s for s in services.values() if s["status"] == "degraded"]),
                "unhealthy_services": len([s for s in services.values() if s["status"] == "unhealthy"])
            }
        }
        
    except Exception as e:
        logger.error("Failed to get service health", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get service health")


@router.get("/metrics/system")
async def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics."""
    try:
        from app.core.performance import performance_monitor
        import psutil
        
        # Get performance metrics
        perf_metrics = performance_monitor.get_metrics()
        
        # Get system metrics
        system_metrics = {}
        try:
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            }
        except ImportError:
            logger.warning("psutil not available for system metrics")
        
        return {
            "performance_metrics": perf_metrics,
            "system_metrics": system_metrics,
            "timestamp": monitoring_service.get_health_status()["last_updated"]
        }
        
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/uptime")
async def get_uptime_status() -> Dict[str, Any]:
    """Get system uptime and availability metrics."""
    try:
        import time
        import os
        
        # Get system uptime (approximate)
        uptime_seconds = time.time() - os.path.getctime('/proc/1/stat') if os.path.exists('/proc/1/stat') else 0
        
        # Get service health for availability calculation
        health_status = monitoring_service.get_health_status()
        
        # Calculate availability percentage (simplified)
        total_services = len(health_status["services"])
        healthy_services = total_services - len(health_status["unhealthy_services"])
        availability_percent = (healthy_services / total_services * 100) if total_services > 0 else 100
        
        return {
            "uptime_seconds": uptime_seconds,
            "uptime_hours": uptime_seconds / 3600,
            "uptime_days": uptime_seconds / 86400,
            "availability_percent": availability_percent,
            "service_status": {
                "total": total_services,
                "healthy": healthy_services,
                "degraded": len(health_status["degraded_services"]),
                "unhealthy": len(health_status["unhealthy_services"])
            },
            "active_alerts": health_status["active_alerts"]
        }
        
    except Exception as e:
        logger.error("Failed to get uptime status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get uptime status")


@router.post("/monitoring/start")
async def start_monitoring():
    """Start the monitoring service."""
    try:
        await monitoring_service.start_monitoring()
        
        logger.info("Monitoring service started via API")
        return {"status": "success", "message": "Monitoring service started"}
        
    except Exception as e:
        logger.error("Failed to start monitoring service", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start monitoring service")


@router.post("/monitoring/stop")
async def stop_monitoring():
    """Stop the monitoring service."""
    try:
        await monitoring_service.stop_monitoring()
        
        logger.info("Monitoring service stopped via API")
        return {"status": "success", "message": "Monitoring service stopped"}
        
    except Exception as e:
        logger.error("Failed to stop monitoring service", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to stop monitoring service")


@router.get("/monitoring/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """Get monitoring service status."""
    try:
        return {
            "running": monitoring_service.running,
            "active_tasks": len(monitoring_service.monitoring_tasks),
            "active_alerts": len(monitoring_service.get_active_alerts()),
            "health_checks": len(monitoring_service.health_checks),
            "thresholds": monitoring_service.thresholds
        }
        
    except Exception as e:
        logger.error("Failed to get monitoring status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")


@router.put("/monitoring/thresholds")
async def update_thresholds(thresholds: Dict[str, float]):
    """Update monitoring thresholds."""
    try:
        # Validate threshold values
        valid_thresholds = [
            "response_time", "error_rate", "cache_hit_rate", "concurrent_calls",
            "memory_usage", "cpu_usage", "disk_usage", "database_connections",
            "api_response_time"
        ]
        
        for key in thresholds.keys():
            if key not in valid_thresholds:
                raise HTTPException(status_code=400, detail=f"Invalid threshold: {key}")
        
        # Update thresholds
        monitoring_service.thresholds.update(thresholds)
        
        logger.info("Monitoring thresholds updated", thresholds=thresholds)
        return {
            "status": "success", 
            "message": "Thresholds updated",
            "updated_thresholds": thresholds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update thresholds", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update thresholds")