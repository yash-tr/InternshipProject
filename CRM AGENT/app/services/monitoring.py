"""
Operational monitoring and alerting service.
"""
import asyncio
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

import httpx
import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.cache import cache_manager
from app.core.performance import performance_monitor

logger = structlog.get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class MonitoringMetric(BaseModel):
    """Monitoring metric data model."""
    name: str
    value: float
    threshold: float
    unit: str
    timestamp: datetime
    status: str  # "ok", "warning", "critical"
    metadata: Dict[str, Any] = {}


class Alert(BaseModel):
    """Alert data model."""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    current_value: float
    threshold_value: float
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class HealthCheck(BaseModel):
    """Health check result model."""
    service: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time: float
    last_check: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class MonitoringService:
    """Operational monitoring and alerting service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.active_alerts: Dict[str, Alert] = {}
        self.health_checks: Dict[str, HealthCheck] = {}
        self.monitoring_tasks: List[asyncio.Task] = []
        self.alert_handlers: List[Callable] = []
        self.running = False
        
        # Monitoring thresholds
        self.thresholds = {
            "response_time": 2.0,           # seconds
            "error_rate": 5.0,              # percentage
            "cache_hit_rate": 30.0,         # percentage (minimum)
            "concurrent_calls": 10,         # maximum concurrent calls
            "memory_usage": 80.0,           # percentage
            "cpu_usage": 80.0,              # percentage
            "disk_usage": 85.0,             # percentage
            "database_connections": 15,     # maximum connections
            "api_response_time": 5.0,       # seconds for external APIs
        }
    
    async def start_monitoring(self):
        """Start monitoring tasks."""
        if self.running:
            return
        
        self.running = True
        
        # Start monitoring tasks
        self.monitoring_tasks = [
            asyncio.create_task(self._monitor_system_health()),
            asyncio.create_task(self._monitor_performance_metrics()),
            asyncio.create_task(self._monitor_external_services()),
            asyncio.create_task(self._monitor_business_metrics()),
            asyncio.create_task(self._process_alerts())
        ]
        
        logger.info("Monitoring service started")
    
    async def stop_monitoring(self):
        """Stop monitoring tasks."""
        self.running = False
        
        for task in self.monitoring_tasks:
            task.cancel()
        
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        
        self.monitoring_tasks = []
        logger.info("Monitoring service stopped")
    
    async def _monitor_system_health(self):
        """Monitor system health metrics."""
        while self.running:
            try:
                # Check system resources
                await self._check_system_resources()
                
                # Check database health
                await self._check_database_health()
                
                # Check cache health
                await self._check_cache_health()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("System health monitoring error", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_performance_metrics(self):
        """Monitor application performance metrics."""
        while self.running:
            try:
                # Get performance metrics
                metrics = performance_monitor.get_metrics()
                
                # Check response time
                avg_response_time = metrics.get('average_response_time', 0)
                if avg_response_time > self.thresholds['response_time']:
                    await self._create_alert(
                        "high_response_time",
                        "High Response Time",
                        f"Average response time is {avg_response_time:.2f}s",
                        AlertSeverity.WARNING,
                        avg_response_time,
                        self.thresholds['response_time']
                    )
                
                # Check cache hit rate
                cache_hits = metrics.get('cache_hits', 0)
                cache_misses = metrics.get('cache_misses', 0)
                total_requests = cache_hits + cache_misses
                
                if total_requests > 0:
                    hit_rate = (cache_hits / total_requests) * 100
                    if hit_rate < self.thresholds['cache_hit_rate']:
                        await self._create_alert(
                            "low_cache_hit_rate",
                            "Low Cache Hit Rate",
                            f"Cache hit rate is {hit_rate:.1f}%",
                            AlertSeverity.WARNING,
                            hit_rate,
                            self.thresholds['cache_hit_rate']
                        )
                
                # Check concurrent calls
                active_calls = metrics.get('active_calls', 0)
                if active_calls > self.thresholds['concurrent_calls']:
                    await self._create_alert(
                        "high_concurrent_calls",
                        "High Concurrent Calls",
                        f"Currently handling {active_calls} concurrent calls",
                        AlertSeverity.ERROR,
                        active_calls,
                        self.thresholds['concurrent_calls']
                    )
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Performance monitoring error", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_external_services(self):
        """Monitor external service health."""
        while self.running:
            try:
                # Check Salesforce API
                await self._check_salesforce_health()
                
                # Check ElevenLabs API
                await self._check_elevenlabs_health()
                
                # Check OpenRouter API
                await self._check_openrouter_health()
                
                # Check Twilio API
                await self._check_twilio_health()
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("External service monitoring error", error=str(e))
                await asyncio.sleep(300)
    
    async def _monitor_business_metrics(self):
        """Monitor business-critical metrics."""
        while self.running:
            try:
                from app.services.analytics import analytics_service
                
                # Get recent call analytics
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                
                analytics = await analytics_service.get_call_analytics(start_time, end_time)
                
                # Check answer rate
                if analytics.total_calls > 10 and analytics.answer_rate < 50.0:
                    await self._create_alert(
                        "low_answer_rate",
                        "Low Call Answer Rate",
                        f"Answer rate is {analytics.answer_rate:.1f}% in the last hour",
                        AlertSeverity.WARNING,
                        analytics.answer_rate,
                        50.0
                    )
                
                # Check qualification rate
                if analytics.answered_calls > 5 and analytics.qualification_rate < 20.0:
                    await self._create_alert(
                        "low_qualification_rate",
                        "Low Lead Qualification Rate",
                        f"Qualification rate is {analytics.qualification_rate:.1f}% in the last hour",
                        AlertSeverity.WARNING,
                        analytics.qualification_rate,
                        20.0
                    )
                
                await asyncio.sleep(1800)  # Check every 30 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Business metrics monitoring error", error=str(e))
                await asyncio.sleep(1800)
    
    async def _check_system_resources(self):
        """Check system resource usage."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.thresholds['cpu_usage']:
                await self._create_alert(
                    "high_cpu_usage",
                    "High CPU Usage",
                    f"CPU usage is {cpu_percent:.1f}%",
                    AlertSeverity.ERROR,
                    cpu_percent,
                    self.thresholds['cpu_usage']
                )
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent > self.thresholds['memory_usage']:
                await self._create_alert(
                    "high_memory_usage",
                    "High Memory Usage",
                    f"Memory usage is {memory_percent:.1f}%",
                    AlertSeverity.ERROR,
                    memory_percent,
                    self.thresholds['memory_usage']
                )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.thresholds['disk_usage']:
                await self._create_alert(
                    "high_disk_usage",
                    "High Disk Usage",
                    f"Disk usage is {disk_percent:.1f}%",
                    AlertSeverity.ERROR,
                    disk_percent,
                    self.thresholds['disk_usage']
                )
            
            # Update health check
            self.health_checks['system_resources'] = HealthCheck(
                service="system_resources",
                status="healthy" if all([
                    cpu_percent < self.thresholds['cpu_usage'],
                    memory_percent < self.thresholds['memory_usage'],
                    disk_percent < self.thresholds['disk_usage']
                ]) else "degraded",
                response_time=0.0,
                last_check=datetime.utcnow(),
                metadata={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": disk_percent
                }
            )
            
        except ImportError:
            logger.warning("psutil not available, skipping system resource monitoring")
        except Exception as e:
            logger.error("System resource check failed", error=str(e))
    
    async def _check_database_health(self):
        """Check database health."""
        try:
            from app.core.database import get_async_session
            
            start_time = datetime.utcnow()
            
            async for session in get_async_session():
                # Simple query to test database
                await session.execute("SELECT 1")
                break
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.health_checks['database'] = HealthCheck(
                service="database",
                status="healthy",
                response_time=response_time,
                last_check=datetime.utcnow()
            )
            
        except Exception as e:
            self.health_checks['database'] = HealthCheck(
                service="database",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
            await self._create_alert(
                "database_unhealthy",
                "Database Health Check Failed",
                f"Database health check failed: {str(e)}",
                AlertSeverity.CRITICAL,
                0,
                1
            )
    
    async def _check_cache_health(self):
        """Check cache health."""
        try:
            start_time = datetime.utcnow()
            
            # Test cache operations
            test_key = "health_check_test"
            await cache_manager.set(test_key, "test_value", ttl=60)
            result = await cache_manager.get(test_key)
            await cache_manager.delete(test_key)
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            if result == "test_value":
                status = "healthy"
                error_message = None
            else:
                status = "degraded"
                error_message = "Cache read/write test failed"
            
            self.health_checks['cache'] = HealthCheck(
                service="cache",
                status=status,
                response_time=response_time,
                last_check=datetime.utcnow(),
                error_message=error_message
            )
            
        except Exception as e:
            self.health_checks['cache'] = HealthCheck(
                service="cache",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def _check_salesforce_health(self):
        """Check Salesforce API health."""
        try:
            from app.services.salesforce import SalesforceService
            
            start_time = datetime.utcnow()
            sf_service = SalesforceService()
            
            # Test authentication
            await sf_service.authenticate()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            if response_time > self.thresholds['api_response_time']:
                status = "degraded"
                await self._create_alert(
                    "salesforce_slow",
                    "Salesforce API Slow Response",
                    f"Salesforce API response time is {response_time:.2f}s",
                    AlertSeverity.WARNING,
                    response_time,
                    self.thresholds['api_response_time']
                )
            else:
                status = "healthy"
            
            self.health_checks['salesforce'] = HealthCheck(
                service="salesforce",
                status=status,
                response_time=response_time,
                last_check=datetime.utcnow()
            )
            
        except Exception as e:
            self.health_checks['salesforce'] = HealthCheck(
                service="salesforce",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
            await self._create_alert(
                "salesforce_unhealthy",
                "Salesforce API Unavailable",
                f"Salesforce API health check failed: {str(e)}",
                AlertSeverity.CRITICAL,
                0,
                1
            )
    
    async def _check_elevenlabs_health(self):
        """Check ElevenLabs API health."""
        try:
            async with httpx.AsyncClient() as client:
                start_time = datetime.utcnow()
                
                response = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": self.settings.ELEVENLABS_API_KEY},
                    timeout=10.0
                )
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                if response.status_code == 200:
                    status = "healthy" if response_time < self.thresholds['api_response_time'] else "degraded"
                else:
                    status = "unhealthy"
                
                self.health_checks['elevenlabs'] = HealthCheck(
                    service="elevenlabs",
                    status=status,
                    response_time=response_time,
                    last_check=datetime.utcnow(),
                    metadata={"status_code": response.status_code}
                )
                
        except Exception as e:
            self.health_checks['elevenlabs'] = HealthCheck(
                service="elevenlabs",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def _check_openrouter_health(self):
        """Check OpenRouter API health."""
        try:
            async with httpx.AsyncClient() as client:
                start_time = datetime.utcnow()
                
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}"},
                    timeout=10.0
                )
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                if response.status_code == 200:
                    status = "healthy" if response_time < self.thresholds['api_response_time'] else "degraded"
                else:
                    status = "unhealthy"
                
                self.health_checks['openrouter'] = HealthCheck(
                    service="openrouter",
                    status=status,
                    response_time=response_time,
                    last_check=datetime.utcnow(),
                    metadata={"status_code": response.status_code}
                )
                
        except Exception as e:
            self.health_checks['openrouter'] = HealthCheck(
                service="openrouter",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def _check_twilio_health(self):
        """Check Twilio API health."""
        try:
            from twilio.rest import Client
            
            start_time = datetime.utcnow()
            client = Client(self.settings.TWILIO_ACCOUNT_SID, self.settings.TWILIO_AUTH_TOKEN)
            
            # Test by fetching account info
            account = client.api.accounts(self.settings.TWILIO_ACCOUNT_SID).fetch()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            status = "healthy" if response_time < self.thresholds['api_response_time'] else "degraded"
            
            self.health_checks['twilio'] = HealthCheck(
                service="twilio",
                status=status,
                response_time=response_time,
                last_check=datetime.utcnow(),
                metadata={"account_status": account.status}
            )
            
        except Exception as e:
            self.health_checks['twilio'] = HealthCheck(
                service="twilio",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def _create_alert(
        self,
        alert_id: str,
        title: str,
        description: str,
        severity: AlertSeverity,
        current_value: float,
        threshold_value: float,
        metadata: Dict[str, Any] = None
    ):
        """Create or update an alert."""
        # Check if alert already exists and is active
        if alert_id in self.active_alerts and self.active_alerts[alert_id].status == AlertStatus.ACTIVE:
            return  # Don't create duplicate alerts
        
        alert = Alert(
            id=alert_id,
            title=title,
            description=description,
            severity=severity,
            status=AlertStatus.ACTIVE,
            metric_name=alert_id,
            current_value=current_value,
            threshold_value=threshold_value,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.active_alerts[alert_id] = alert
        
        logger.warning("Alert created", 
                      alert_id=alert_id, 
                      title=title, 
                      severity=severity.value)
        
        # Trigger alert notifications
        await self._send_alert_notifications(alert)
    
    async def _process_alerts(self):
        """Process and manage active alerts."""
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                # Auto-resolve alerts that are no longer triggered
                alerts_to_resolve = []
                
                for alert_id, alert in self.active_alerts.items():
                    if alert.status == AlertStatus.ACTIVE:
                        # Check if alert condition is still true
                        should_resolve = await self._should_resolve_alert(alert)
                        
                        if should_resolve:
                            alerts_to_resolve.append(alert_id)
                        
                        # Auto-acknowledge old alerts
                        elif (current_time - alert.created_at).total_seconds() > 3600:  # 1 hour
                            alert.status = AlertStatus.ACKNOWLEDGED
                            alert.acknowledged_at = current_time
                
                # Resolve alerts
                for alert_id in alerts_to_resolve:
                    await self.resolve_alert(alert_id)
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Alert processing error", error=str(e))
                await asyncio.sleep(300)
    
    async def _should_resolve_alert(self, alert: Alert) -> bool:
        """Check if an alert should be automatically resolved."""
        try:
            # Get current metrics
            metrics = performance_monitor.get_metrics()
            
            # Check specific alert conditions
            if alert.id == "high_response_time":
                current_value = metrics.get('average_response_time', 0)
                return current_value <= alert.threshold_value
            
            elif alert.id == "low_cache_hit_rate":
                cache_hits = metrics.get('cache_hits', 0)
                cache_misses = metrics.get('cache_misses', 0)
                total = cache_hits + cache_misses
                if total > 0:
                    hit_rate = (cache_hits / total) * 100
                    return hit_rate >= alert.threshold_value
            
            elif alert.id == "high_concurrent_calls":
                current_value = metrics.get('active_calls', 0)
                return current_value <= alert.threshold_value
            
            # For external service alerts, check health status
            elif alert.id.endswith("_unhealthy"):
                service_name = alert.id.replace("_unhealthy", "")
                health_check = self.health_checks.get(service_name)
                return health_check and health_check.status == "healthy"
            
            return False
            
        except Exception as e:
            logger.error("Error checking alert resolution", alert_id=alert.id, error=str(e))
            return False
    
    async def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications via configured channels."""
        try:
            # Send email notification
            if self.settings.SMTP_SERVER and self.settings.FROM_EMAIL:
                await self._send_email_alert(alert)
            
            # Send Slack notification
            if self.settings.SLACK_WEBHOOK_URL:
                await self._send_slack_alert(alert)
            
        except Exception as e:
            logger.error("Failed to send alert notifications", alert_id=alert.id, error=str(e))
    
    async def _send_email_alert(self, alert: Alert):
        """Send email alert notification."""
        try:
            msg = MimeMultipart()
            msg['From'] = self.settings.FROM_EMAIL
            msg['To'] = ", ".join(self.settings.APPROVER_EMAILS or [])
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.title}"
            
            body = f"""
            Alert: {alert.title}
            Severity: {alert.severity.upper()}
            Description: {alert.description}
            Current Value: {alert.current_value}
            Threshold: {alert.threshold_value}
            Time: {alert.created_at.isoformat()}
            
            Please investigate and take appropriate action.
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.settings.SMTP_SERVER, self.settings.SMTP_PORT)
            server.starttls()
            server.login(self.settings.SMTP_USERNAME, self.settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            logger.info("Email alert sent", alert_id=alert.id)
            
        except Exception as e:
            logger.error("Failed to send email alert", alert_id=alert.id, error=str(e))
    
    async def _send_slack_alert(self, alert: Alert):
        """Send Slack alert notification."""
        try:
            color_map = {
                AlertSeverity.INFO: "good",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.ERROR: "danger",
                AlertSeverity.CRITICAL: "danger"
            }
            
            payload = {
                "text": f"Alert: {alert.title}",
                "attachments": [
                    {
                        "color": color_map.get(alert.severity, "warning"),
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.upper(),
                                "short": True
                            },
                            {
                                "title": "Current Value",
                                "value": str(alert.current_value),
                                "short": True
                            },
                            {
                                "title": "Threshold",
                                "value": str(alert.threshold_value),
                                "short": True
                            },
                            {
                                "title": "Description",
                                "value": alert.description,
                                "short": False
                            }
                        ],
                        "ts": int(alert.created_at.timestamp())
                    }
                ]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.settings.SLACK_WEBHOOK_URL,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("Slack alert sent", alert_id=alert.id)
                else:
                    logger.error("Failed to send Slack alert", 
                               alert_id=alert.id, 
                               status_code=response.status_code)
            
        except Exception as e:
            logger.error("Failed to send Slack alert", alert_id=alert.id, error=str(e))
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            if alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.utcnow()
                
                logger.info("Alert acknowledged", alert_id=alert_id)
                return True
        
        return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            if alert.status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                
                logger.info("Alert resolved", alert_id=alert_id)
                return True
        
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [
            alert for alert in self.active_alerts.values()
            if alert.status == AlertStatus.ACTIVE
        ]
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        return list(self.active_alerts.values())
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        overall_status = "healthy"
        unhealthy_services = []
        degraded_services = []
        
        for service, health_check in self.health_checks.items():
            if health_check.status == "unhealthy":
                overall_status = "unhealthy"
                unhealthy_services.append(service)
            elif health_check.status == "degraded":
                if overall_status == "healthy":
                    overall_status = "degraded"
                degraded_services.append(service)
        
        return {
            "status": overall_status,
            "services": self.health_checks,
            "unhealthy_services": unhealthy_services,
            "degraded_services": degraded_services,
            "active_alerts": len(self.get_active_alerts()),
            "last_updated": datetime.utcnow().isoformat()
        }


# Global monitoring service instance
monitoring_service = MonitoringService()