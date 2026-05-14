"""
Tests for monitoring service functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.monitoring import (
    monitoring_service,
    AlertSeverity,
    AlertStatus,
    Alert,
    HealthCheck
)


@pytest.mark.asyncio
class TestMonitoringService:
    """Test monitoring service functionality."""
    
    async def test_create_alert(self):
        """Test creating alerts."""
        # Clear any existing alerts
        monitoring_service.active_alerts.clear()
        
        await monitoring_service._create_alert(
            alert_id="test_alert",
            title="Test Alert",
            description="This is a test alert",
            severity=AlertSeverity.WARNING,
            current_value=85.0,
            threshold_value=80.0
        )
        
        # Verify alert was created
        assert "test_alert" in monitoring_service.active_alerts
        alert = monitoring_service.active_alerts["test_alert"]
        assert alert.title == "Test Alert"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE
        assert alert.current_value == 85.0
        assert alert.threshold_value == 80.0
    
    async def test_duplicate_alert_prevention(self):
        """Test that duplicate alerts are not created."""
        # Clear any existing alerts
        monitoring_service.active_alerts.clear()
        
        # Create first alert
        await monitoring_service._create_alert(
            alert_id="duplicate_test",
            title="Duplicate Test",
            description="First alert",
            severity=AlertSeverity.ERROR,
            current_value=90.0,
            threshold_value=80.0
        )
        
        # Try to create duplicate alert
        await monitoring_service._create_alert(
            alert_id="duplicate_test",
            title="Duplicate Test 2",
            description="Second alert",
            severity=AlertSeverity.CRITICAL,
            current_value=95.0,
            threshold_value=80.0
        )
        
        # Verify only one alert exists
        assert len(monitoring_service.active_alerts) == 1
        alert = monitoring_service.active_alerts["duplicate_test"]
        assert alert.title == "Duplicate Test"  # Original title preserved
        assert alert.severity == AlertSeverity.ERROR  # Original severity preserved
    
    async def test_acknowledge_alert(self):
        """Test acknowledging alerts."""
        # Clear any existing alerts
        monitoring_service.active_alerts.clear()
        
        # Create alert
        await monitoring_service._create_alert(
            alert_id="ack_test",
            title="Acknowledge Test",
            description="Test acknowledgment",
            severity=AlertSeverity.WARNING,
            current_value=75.0,
            threshold_value=70.0
        )
        
        # Acknowledge alert
        success = await monitoring_service.acknowledge_alert("ack_test")
        
        assert success is True
        alert = monitoring_service.active_alerts["ack_test"]
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_at is not None
    
    async def test_resolve_alert(self):
        """Test resolving alerts."""
        # Clear any existing alerts
        monitoring_service.active_alerts.clear()
        
        # Create alert
        await monitoring_service._create_alert(
            alert_id="resolve_test",
            title="Resolve Test",
            description="Test resolution",
            severity=AlertSeverity.ERROR,
            current_value=85.0,
            threshold_value=80.0
        )
        
        # Resolve alert
        success = await monitoring_service.resolve_alert("resolve_test")
        
        assert success is True
        alert = monitoring_service.active_alerts["resolve_test"]
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None
    
    async def test_get_active_alerts(self):
        """Test getting active alerts."""
        # Clear any existing alerts
        monitoring_service.active_alerts.clear()
        
        # Create mix of alerts
        await monitoring_service._create_alert(
            alert_id="active_1",
            title="Active Alert 1",
            description="Active alert",
            severity=AlertSeverity.WARNING,
            current_value=75.0,
            threshold_value=70.0
        )
        
        await monitoring_service._create_alert(
            alert_id="active_2",
            title="Active Alert 2",
            description="Another active alert",
            severity=AlertSeverity.ERROR,
            current_value=85.0,
            threshold_value=80.0
        )
        
        # Acknowledge one alert
        await monitoring_service.acknowledge_alert("active_1")
        
        # Resolve another alert
        await monitoring_service._create_alert(
            alert_id="resolved_1",
            title="Resolved Alert",
            description="This will be resolved",
            severity=AlertSeverity.INFO,
            current_value=60.0,
            threshold_value=65.0
        )
        await monitoring_service.resolve_alert("resolved_1")
        
        # Get active alerts
        active_alerts = monitoring_service.get_active_alerts()
        
        # Should only return alerts with ACTIVE status
        assert len(active_alerts) == 1
        assert active_alerts[0].id == "active_2"
        assert active_alerts[0].status == AlertStatus.ACTIVE
    
    @patch('app.core.performance.performance_monitor')
    async def test_monitor_performance_metrics(self, mock_monitor):
        """Test performance metrics monitoring."""
        # Mock performance data that triggers alerts
        mock_monitor.get_metrics.return_value = {
            'average_response_time': 3.0,  # Above threshold of 2.0
            'cache_hits': 20,
            'cache_misses': 80,  # Hit rate = 20% (below threshold of 30%)
            'active_calls': 15   # Above threshold of 10
        }
        
        # Clear existing alerts
        monitoring_service.active_alerts.clear()
        
        # Run one iteration of performance monitoring
        await monitoring_service._monitor_performance_metrics()
        
        # Should have created alerts for high response time, low cache hit rate, and high concurrent calls
        assert len(monitoring_service.active_alerts) >= 2  # At least response time and cache hit rate
        
        # Check specific alerts
        assert "high_response_time" in monitoring_service.active_alerts
        assert "low_cache_hit_rate" in monitoring_service.active_alerts
    
    @patch('app.services.monitoring.psutil')
    async def test_check_system_resources(self, mock_psutil):
        """Test system resource monitoring."""
        # Mock system resource data
        mock_psutil.cpu_percent.return_value = 85.0  # Above threshold of 80%
        
        mock_memory = MagicMock()
        mock_memory.percent = 75.0  # Below threshold
        mock_psutil.virtual_memory.return_value = mock_memory
        
        mock_disk = MagicMock()
        mock_disk.used = 80 * 1024**3  # 80GB
        mock_disk.total = 100 * 1024**3  # 100GB (80% usage, below 85% threshold)
        mock_psutil.disk_usage.return_value = mock_disk
        
        # Clear existing alerts
        monitoring_service.active_alerts.clear()
        
        # Run system resource check
        await monitoring_service._check_system_resources()
        
        # Should create alert for high CPU usage
        assert "high_cpu_usage" in monitoring_service.active_alerts
        
        # Should update health check
        assert "system_resources" in monitoring_service.health_checks
        health_check = monitoring_service.health_checks["system_resources"]
        assert health_check.status == "degraded"  # Due to high CPU
        assert health_check.metadata["cpu_percent"] == 85.0
    
    @patch('app.core.database.get_async_session')
    async def test_check_database_health(self, mock_session):
        """Test database health monitoring."""
        # Mock successful database connection
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_session.return_value.__aexit__.return_value = None
        
        # Run database health check
        await monitoring_service._check_database_health()
        
        # Should update health check as healthy
        assert "database" in monitoring_service.health_checks
        health_check = monitoring_service.health_checks["database"]
        assert health_check.status == "healthy"
        assert health_check.response_time > 0
        
        # Verify database query was executed
        mock_db.execute.assert_called_once()
    
    @patch('app.core.database.get_async_session')
    async def test_check_database_health_failure(self, mock_session):
        """Test database health monitoring with failure."""
        # Mock database connection failure
        mock_session.side_effect = Exception("Database connection failed")
        
        # Clear existing alerts
        monitoring_service.active_alerts.clear()
        
        # Run database health check
        await monitoring_service._check_database_health()
        
        # Should update health check as unhealthy
        assert "database" in monitoring_service.health_checks
        health_check = monitoring_service.health_checks["database"]
        assert health_check.status == "unhealthy"
        assert health_check.error_message == "Database connection failed"
        
        # Should create critical alert
        assert "database_unhealthy" in monitoring_service.active_alerts
        alert = monitoring_service.active_alerts["database_unhealthy"]
        assert alert.severity == AlertSeverity.CRITICAL
    
    @patch('app.core.cache.cache_manager')
    async def test_check_cache_health(self, mock_cache):
        """Test cache health monitoring."""
        # Mock successful cache operations
        mock_cache.set.return_value = True
        mock_cache.get.return_value = "test_value"
        mock_cache.delete.return_value = True
        
        # Run cache health check
        await monitoring_service._check_cache_health()
        
        # Should update health check as healthy
        assert "cache" in monitoring_service.health_checks
        health_check = monitoring_service.health_checks["cache"]
        assert health_check.status == "healthy"
        assert health_check.response_time > 0
        
        # Verify cache operations were called
        mock_cache.set.assert_called_once()
        mock_cache.get.assert_called_once()
        mock_cache.delete.assert_called_once()
    
    @patch('httpx.AsyncClient')
    async def test_check_external_service_health(self, mock_client):
        """Test external service health monitoring."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None
        
        # Run ElevenLabs health check
        await monitoring_service._check_elevenlabs_health()
        
        # Should update health check as healthy
        assert "elevenlabs" in monitoring_service.health_checks
        health_check = monitoring_service.health_checks["elevenlabs"]
        assert health_check.status == "healthy"
        assert health_check.response_time > 0
        assert health_check.metadata["status_code"] == 200
    
    def test_get_health_status(self):
        """Test getting overall health status."""
        # Set up mock health checks
        monitoring_service.health_checks = {
            "database": HealthCheck(
                service="database",
                status="healthy",
                response_time=0.1,
                last_check=datetime.utcnow()
            ),
            "cache": HealthCheck(
                service="cache",
                status="degraded",
                response_time=0.5,
                last_check=datetime.utcnow(),
                error_message="Slow response"
            ),
            "external_api": HealthCheck(
                service="external_api",
                status="unhealthy",
                response_time=0.0,
                last_check=datetime.utcnow(),
                error_message="Connection failed"
            )
        }
        
        # Clear alerts and add one active alert
        monitoring_service.active_alerts.clear()
        monitoring_service.active_alerts["test_alert"] = Alert(
            id="test_alert",
            title="Test Alert",
            description="Test",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="test",
            current_value=80.0,
            threshold_value=70.0,
            created_at=datetime.utcnow()
        )
        
        # Get health status
        health_status = monitoring_service.get_health_status()
        
        # Verify overall status is unhealthy due to unhealthy service
        assert health_status["status"] == "unhealthy"
        assert "external_api" in health_status["unhealthy_services"]
        assert "cache" in health_status["degraded_services"]
        assert health_status["active_alerts"] == 1
        assert len(health_status["services"]) == 3
    
    @patch('smtplib.SMTP')
    async def test_send_email_alert(self, mock_smtp):
        """Test sending email alerts."""
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Set up email configuration
        monitoring_service.settings.SMTP_SERVER = "smtp.example.com"
        monitoring_service.settings.SMTP_PORT = 587
        monitoring_service.settings.SMTP_USERNAME = "test@example.com"
        monitoring_service.settings.SMTP_PASSWORD = "password"
        monitoring_service.settings.FROM_EMAIL = "alerts@example.com"
        monitoring_service.settings.APPROVER_EMAILS = ["admin@example.com"]
        
        # Create test alert
        alert = Alert(
            id="email_test",
            title="Email Test Alert",
            description="Test email notification",
            severity=AlertSeverity.ERROR,
            status=AlertStatus.ACTIVE,
            metric_name="test_metric",
            current_value=90.0,
            threshold_value=80.0,
            created_at=datetime.utcnow()
        )
        
        # Send email alert
        await monitoring_service._send_email_alert(alert)
        
        # Verify SMTP operations
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "password")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
    
    @patch('httpx.AsyncClient')
    async def test_send_slack_alert(self, mock_client):
        """Test sending Slack alerts."""
        # Mock successful Slack response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None
        
        # Set up Slack configuration
        monitoring_service.settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        
        # Create test alert
        alert = Alert(
            id="slack_test",
            title="Slack Test Alert",
            description="Test Slack notification",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="test_metric",
            current_value=75.0,
            threshold_value=70.0,
            created_at=datetime.utcnow()
        )
        
        # Send Slack alert
        await monitoring_service._send_slack_alert(alert)
        
        # Verify Slack API call
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"
        assert "json" in call_args[1]
        
        # Verify payload structure
        payload = call_args[1]["json"]
        assert "text" in payload
        assert "attachments" in payload
        assert payload["text"] == "Alert: Slack Test Alert"


@pytest.mark.asyncio
class TestMonitoringErrorHandling:
    """Test monitoring error handling."""
    
    async def test_monitoring_with_exceptions(self):
        """Test that monitoring continues despite exceptions."""
        with patch.object(monitoring_service, '_check_system_resources') as mock_check:
            # Mock exception in system resource check
            mock_check.side_effect = Exception("System check failed")
            
            # Start monitoring briefly
            monitoring_service.running = True
            task = asyncio.create_task(monitoring_service._monitor_system_health())
            
            # Let it run briefly then cancel
            await asyncio.sleep(0.1)
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Monitoring should have attempted the check despite the exception
            mock_check.assert_called()
    
    async def test_alert_notification_failures(self):
        """Test handling of alert notification failures."""
        with patch.object(monitoring_service, '_send_email_alert') as mock_email:
            with patch.object(monitoring_service, '_send_slack_alert') as mock_slack:
                # Mock notification failures
                mock_email.side_effect = Exception("Email failed")
                mock_slack.side_effect = Exception("Slack failed")
                
                # Create alert (which triggers notifications)
                await monitoring_service._create_alert(
                    alert_id="notification_test",
                    title="Notification Test",
                    description="Test notification failure handling",
                    severity=AlertSeverity.ERROR,
                    current_value=90.0,
                    threshold_value=80.0
                )
                
                # Alert should still be created despite notification failures
                assert "notification_test" in monitoring_service.active_alerts
                
                # Notification methods should have been called
                mock_email.assert_called()
                mock_slack.assert_called()