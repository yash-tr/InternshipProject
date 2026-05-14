"""
Tests for security monitoring functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.security.monitoring import (
    SecurityMonitor,
    SecurityEvent,
    ThreatIndicator,
    EventType,
    ThreatLevel,
    get_security_monitor,
    log_security_event
)


class TestSecurityEvent:
    """Test SecurityEvent class functionality."""
    
    def test_security_event_creation(self):
        """Test security event creation."""
        event = SecurityEvent(
            event_id="test_event_1",
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_123",
            username="testuser",
            ip_address="192.168.1.1",
            outcome="success"
        )
        
        assert event.event_id == "test_event_1"
        assert event.event_type == EventType.LOGIN_SUCCESS
        assert event.user_id == "user_123"
        assert event.username == "testuser"
        assert event.ip_address == "192.168.1.1"
        assert event.outcome == "success"
        assert event.threat_level == ThreatLevel.LOW
        assert isinstance(event.timestamp, datetime)
    
    def test_security_event_to_dict(self):
        """Test security event dictionary conversion."""
        event = SecurityEvent(
            event_id="test_event_1",
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_123",
            details={"reason": "invalid_password"}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_id"] == "test_event_1"
        assert event_dict["event_type"] == "login_failure"
        assert event_dict["user_id"] == "user_123"
        assert event_dict["details"] == {"reason": "invalid_password"}
        assert "timestamp" in event_dict


class TestThreatIndicator:
    """Test ThreatIndicator class functionality."""
    
    def test_threat_indicator_creation(self):
        """Test threat indicator creation."""
        indicator = ThreatIndicator(
            indicator_id="test_indicator",
            name="Test Indicator",
            description="Test threat indicator",
            pattern_type="frequency",
            threshold=5.0,
            time_window=300,
            event_types={EventType.LOGIN_FAILURE},
            conditions={"outcome": "failure"},
            threat_level=ThreatLevel.HIGH
        )
        
        assert indicator.indicator_id == "test_indicator"
        assert indicator.name == "Test Indicator"
        assert indicator.pattern_type == "frequency"
        assert indicator.threshold == 5.0
        assert indicator.time_window == 300
        assert EventType.LOGIN_FAILURE in indicator.event_types
        assert indicator.conditions["outcome"] == "failure"
        assert indicator.threat_level == ThreatLevel.HIGH
        assert indicator.enabled is True
    
    def test_threat_indicator_matches_event(self):
        """Test threat indicator event matching."""
        indicator = ThreatIndicator(
            indicator_id="test_indicator",
            name="Test Indicator",
            description="Test threat indicator",
            pattern_type="frequency",
            threshold=5.0,
            time_window=300,
            event_types={EventType.LOGIN_FAILURE},
            conditions={"outcome": "failure"},
            threat_level=ThreatLevel.HIGH
        )
        
        # Matching event
        matching_event = SecurityEvent(
            event_id="event_1",
            event_type=EventType.LOGIN_FAILURE,
            outcome="failure"
        )
        assert indicator.matches_event(matching_event) is True
        
        # Non-matching event type
        non_matching_event = SecurityEvent(
            event_id="event_2",
            event_type=EventType.LOGIN_SUCCESS,
            outcome="failure"
        )
        assert indicator.matches_event(non_matching_event) is False
        
        # Non-matching condition
        non_matching_condition = SecurityEvent(
            event_id="event_3",
            event_type=EventType.LOGIN_FAILURE,
            outcome="success"
        )
        assert indicator.matches_event(non_matching_condition) is False
        
        # Disabled indicator
        indicator.enabled = False
        assert indicator.matches_event(matching_event) is False


class TestSecurityMonitor:
    """Test SecurityMonitor class functionality."""
    
    def test_security_monitor_init(self):
        """Test security monitor initialization."""
        monitor = SecurityMonitor()
        
        assert monitor.monitoring_enabled is True
        assert monitor.real_time_analysis is True
        assert len(monitor.threat_indicators) > 0
        assert isinstance(monitor.events, type(monitor.events))
        assert isinstance(monitor.event_index, dict)
    
    def test_add_threat_indicator(self):
        """Test adding threat indicator."""
        monitor = SecurityMonitor()
        
        indicator = ThreatIndicator(
            indicator_id="custom_indicator",
            name="Custom Indicator",
            description="Custom threat indicator",
            pattern_type="frequency",
            threshold=3.0,
            time_window=600,
            event_types={EventType.PERMISSION_DENIED},
            conditions={},
            threat_level=ThreatLevel.MEDIUM
        )
        
        monitor.add_threat_indicator(indicator)
        
        assert "custom_indicator" in monitor.threat_indicators
        assert monitor.threat_indicators["custom_indicator"] == indicator
    
    def test_remove_threat_indicator(self):
        """Test removing threat indicator."""
        monitor = SecurityMonitor()
        
        # Add indicator first
        indicator = ThreatIndicator(
            indicator_id="temp_indicator",
            name="Temp Indicator",
            description="Temporary indicator",
            pattern_type="frequency",
            threshold=1.0,
            time_window=60,
            event_types={EventType.DATA_ACCESS},
            conditions={},
            threat_level=ThreatLevel.LOW
        )
        
        monitor.add_threat_indicator(indicator)
        assert "temp_indicator" in monitor.threat_indicators
        
        # Remove indicator
        monitor.remove_threat_indicator("temp_indicator")
        assert "temp_indicator" not in monitor.threat_indicators
    
    def test_log_security_event(self):
        """Test logging security events."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False  # Disable for testing
        
        event = monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_123",
            username="testuser",
            ip_address="192.168.1.1",
            outcome="success",
            details={"method": "password"}
        )
        
        assert event.event_type == EventType.LOGIN_SUCCESS
        assert event.user_id == "user_123"
        assert event.username == "testuser"
        assert event.ip_address == "192.168.1.1"
        assert event.outcome == "success"
        assert event.details["method"] == "password"
        
        # Check event was stored
        assert len(monitor.events) == 1
        assert event in monitor.events
        
        # Check event was indexed
        assert event in monitor.event_index["user:user_123"]
        assert event in monitor.event_index["ip:192.168.1.1"]
        assert event in monitor.event_index["type:login_success"]
    
    def test_get_events_no_filters(self):
        """Test getting events without filters."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log multiple events
        for i in range(5):
            monitor.log_security_event(
                event_type=EventType.LOGIN_SUCCESS,
                user_id=f"user_{i}",
                ip_address="192.168.1.1"
            )
        
        events = monitor.get_events()
        assert len(events) == 5
    
    def test_get_events_with_user_filter(self):
        """Test getting events filtered by user."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log events for different users
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1",
            ip_address="192.168.1.1"
        )
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_2",
            ip_address="192.168.1.1"
        )
        monitor.log_security_event(
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_1",
            ip_address="192.168.1.1"
        )
        
        # Filter by user_1
        user_1_events = monitor.get_events(user_id="user_1")
        assert len(user_1_events) == 2
        assert all(event.user_id == "user_1" for event in user_1_events)
    
    def test_get_events_with_ip_filter(self):
        """Test getting events filtered by IP address."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log events from different IPs
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1",
            ip_address="192.168.1.1"
        )
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1",
            ip_address="192.168.1.2"
        )
        
        # Filter by IP
        ip_events = monitor.get_events(ip_address="192.168.1.1")
        assert len(ip_events) == 1
        assert ip_events[0].ip_address == "192.168.1.1"
    
    def test_get_events_with_event_type_filter(self):
        """Test getting events filtered by event type."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log different event types
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1"
        )
        monitor.log_security_event(
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_1"
        )
        monitor.log_security_event(
            event_type=EventType.PERMISSION_DENIED,
            user_id="user_1"
        )
        
        # Filter by event type
        login_events = monitor.get_events(event_type=EventType.LOGIN_SUCCESS)
        assert len(login_events) == 1
        assert login_events[0].event_type == EventType.LOGIN_SUCCESS
    
    def test_get_events_with_time_filter(self):
        """Test getting events filtered by time range."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        now = datetime.utcnow()
        past_time = now - timedelta(hours=1)
        future_time = now + timedelta(hours=1)
        
        # Log event
        event = monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1"
        )
        
        # Filter by time range
        events_in_range = monitor.get_events(
            start_time=past_time,
            end_time=future_time
        )
        assert len(events_in_range) == 1
        
        # Filter outside time range
        events_outside_range = monitor.get_events(
            start_time=future_time,
            end_time=future_time + timedelta(hours=1)
        )
        assert len(events_outside_range) == 0
    
    def test_get_events_with_limit(self):
        """Test getting events with limit."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log multiple events
        for i in range(10):
            monitor.log_security_event(
                event_type=EventType.LOGIN_SUCCESS,
                user_id=f"user_{i}"
            )
        
        # Get limited results
        limited_events = monitor.get_events(limit=5)
        assert len(limited_events) == 5
    
    def test_get_security_metrics(self):
        """Test getting security metrics."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False
        
        # Log various events
        monitor.log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_1",
            ip_address="192.168.1.1",
            outcome="success"
        )
        monitor.log_security_event(
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_2",
            ip_address="192.168.1.2",
            outcome="failure"
        )
        monitor.log_security_event(
            event_type=EventType.PERMISSION_DENIED,
            user_id="user_1",
            ip_address="192.168.1.1",
            outcome="blocked"
        )
        
        # Add a mock threat
        monitor.active_threats["threat_1"] = {
            "threat_level": "high",
            "status": "active"
        }
        
        metrics = monitor.get_security_metrics(time_window=3600)
        
        assert metrics["total_events"] == 3
        assert metrics["event_counts"]["login_success"] == 1
        assert metrics["event_counts"]["login_failure"] == 1
        assert metrics["event_counts"]["permission_denied"] == 1
        assert metrics["outcome_counts"]["success"] == 1
        assert metrics["outcome_counts"]["failure"] == 1
        assert metrics["outcome_counts"]["blocked"] == 1
        assert metrics["unique_users"] == 2
        assert metrics["unique_ips"] == 2
        assert metrics["active_threats"] == 1
        assert metrics["failed_logins"] == 1
        assert metrics["permission_denials"] == 1
    
    def test_threat_pattern_detection(self):
        """Test threat pattern detection."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = True
        
        # Create a custom indicator for testing
        indicator = ThreatIndicator(
            indicator_id="test_brute_force",
            name="Test Brute Force",
            description="Test brute force detection",
            pattern_type="frequency",
            threshold=3.0,  # 3 failed attempts
            time_window=300,  # 5 minutes
            event_types={EventType.LOGIN_FAILURE},
            conditions={"outcome": "failure"},
            threat_level=ThreatLevel.HIGH
        )
        
        monitor.add_threat_indicator(indicator)
        
        # Log failed login attempts
        for i in range(4):  # Exceed threshold
            monitor.log_security_event(
                event_type=EventType.LOGIN_FAILURE,
                user_id="user_1",
                ip_address="192.168.1.1",
                outcome="failure"
            )
        
        # Check if threat was detected
        assert len(monitor.active_threats) > 0
        
        # Find the threat related to our indicator
        threat_found = False
        for threat in monitor.active_threats.values():
            if threat.get("indicator_id") == "test_brute_force":
                threat_found = True
                assert threat["threat_level"] == "high"
                break
        
        assert threat_found
    
    def test_generate_event_id(self):
        """Test event ID generation."""
        monitor = SecurityMonitor()
        
        event_id_1 = monitor._generate_event_id()
        event_id_2 = monitor._generate_event_id()
        
        assert event_id_1.startswith("evt_")
        assert event_id_2.startswith("evt_")
        assert event_id_1 != event_id_2
        assert len(event_id_1) == 12  # "evt_" + 8 hex chars
    
    def test_index_event(self):
        """Test event indexing."""
        monitor = SecurityMonitor()
        
        event = SecurityEvent(
            event_id="test_event",
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_123",
            ip_address="192.168.1.1",
            session_id="session_456"
        )
        
        monitor._index_event(event)
        
        # Check all indexes
        assert event in monitor.event_index["user:user_123"]
        assert event in monitor.event_index["ip:192.168.1.1"]
        assert event in monitor.event_index["type:login_success"]
        assert event in monitor.event_index["session:session_456"]
    
    @patch('app.security.monitoring.logger')
    def test_trigger_threat_alert(self, mock_logger):
        """Test threat alert triggering."""
        monitor = SecurityMonitor()
        
        indicator = ThreatIndicator(
            indicator_id="test_indicator",
            name="Test Indicator",
            description="Test threat indicator",
            pattern_type="frequency",
            threshold=1.0,
            time_window=60,
            event_types={EventType.LOGIN_FAILURE},
            conditions={},
            threat_level=ThreatLevel.HIGH
        )
        
        event = SecurityEvent(
            event_id="test_event",
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_123",
            ip_address="192.168.1.1"
        )
        
        context = {"event_count": 5, "time_window": 300}
        
        monitor._trigger_threat_alert(indicator, event, context)
        
        # Check threat was created
        assert len(monitor.active_threats) == 1
        
        threat = list(monitor.active_threats.values())[0]
        assert threat["indicator_id"] == "test_indicator"
        assert threat["threat_level"] == "high"
        assert threat["status"] == "active"
        
        # Check logging was called
        mock_logger.warning.assert_called()


class TestSecurityMonitorUtilities:
    """Test security monitor utility functions."""
    
    def test_get_security_monitor(self):
        """Test getting global security monitor instance."""
        monitor1 = get_security_monitor()
        monitor2 = get_security_monitor()
        
        # Should return same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, SecurityMonitor)
    
    def test_log_security_event_utility(self):
        """Test log security event utility function."""
        event = log_security_event(
            event_type=EventType.LOGIN_SUCCESS,
            user_id="user_123",
            username="testuser",
            ip_address="192.168.1.1",
            outcome="success"
        )
        
        assert isinstance(event, SecurityEvent)
        assert event.event_type == EventType.LOGIN_SUCCESS
        assert event.user_id == "user_123"
        assert event.username == "testuser"
        assert event.ip_address == "192.168.1.1"
        assert event.outcome == "success"


class TestSecurityMonitorIntegration:
    """Test security monitor integration scenarios."""
    
    def test_brute_force_detection_scenario(self):
        """Test complete brute force attack detection scenario."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = True
        
        # Simulate brute force attack
        attacker_ip = "192.168.1.100"
        target_user = "admin"
        
        # Log multiple failed login attempts
        for i in range(6):  # Exceed default threshold of 5
            monitor.log_security_event(
                event_type=EventType.LOGIN_FAILURE,
                user_id=target_user,
                ip_address=attacker_ip,
                outcome="failure",
                details={"reason": "invalid_password", "attempt": i + 1}
            )
        
        # Check that threat was detected
        assert len(monitor.active_threats) > 0
        
        # Verify threat details
        brute_force_threats = [
            threat for threat in monitor.active_threats.values()
            if "brute_force" in threat.get("indicator_id", "")
        ]
        
        assert len(brute_force_threats) > 0
        threat = brute_force_threats[0]
        assert threat["threat_level"] in ["high", "critical"]
        assert threat["status"] == "active"
    
    def test_privilege_escalation_detection_scenario(self):
        """Test privilege escalation detection scenario."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = True
        
        user_id = "user_123"
        ip_address = "192.168.1.50"
        
        # Log multiple permission denied events
        for i in range(4):  # Exceed threshold of 3
            monitor.log_security_event(
                event_type=EventType.PERMISSION_DENIED,
                user_id=user_id,
                ip_address=ip_address,
                resource=f"/admin/resource_{i}",
                action="read",
                outcome="blocked"
            )
        
        # Check for privilege escalation threat
        privilege_threats = [
            threat for threat in monitor.active_threats.values()
            if "privilege_escalation" in threat.get("indicator_id", "")
        ]
        
        assert len(privilege_threats) > 0
    
    def test_api_abuse_detection_scenario(self):
        """Test API abuse detection scenario."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = True
        
        # Log excessive API rate limit events
        for i in range(101):  # Exceed threshold of 100
            monitor.log_security_event(
                event_type=EventType.API_RATE_LIMIT_EXCEEDED,
                ip_address="192.168.1.200",
                resource="/api/v1/data",
                outcome="blocked"
            )
        
        # Check for API abuse threat
        api_threats = [
            threat for threat in monitor.active_threats.values()
            if "api_abuse" in threat.get("indicator_id", "")
        ]
        
        assert len(api_threats) > 0
    
    def test_multiple_threat_detection(self):
        """Test detection of multiple simultaneous threats."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = True
        
        # Simulate multiple attack vectors
        
        # Brute force from IP 1
        for i in range(6):
            monitor.log_security_event(
                event_type=EventType.LOGIN_FAILURE,
                user_id="user_1",
                ip_address="192.168.1.100",
                outcome="failure"
            )
        
        # Privilege escalation from IP 2
        for i in range(4):
            monitor.log_security_event(
                event_type=EventType.PERMISSION_DENIED,
                user_id="user_2",
                ip_address="192.168.1.101",
                outcome="blocked"
            )
        
        # API abuse from IP 3
        for i in range(101):
            monitor.log_security_event(
                event_type=EventType.API_RATE_LIMIT_EXCEEDED,
                ip_address="192.168.1.102",
                outcome="blocked"
            )
        
        # Should detect multiple threats
        assert len(monitor.active_threats) >= 3
        
        # Verify different threat types
        threat_indicators = set()
        for threat in monitor.active_threats.values():
            threat_indicators.add(threat.get("indicator_id", ""))
        
        # Should have different types of threats
        assert len(threat_indicators) >= 3
    
    def test_performance_with_high_volume(self):
        """Test monitor performance with high volume of events."""
        monitor = SecurityMonitor()
        monitor.real_time_analysis = False  # Disable for performance test
        
        import time
        start_time = time.time()
        
        # Log large number of events
        for i in range(1000):
            monitor.log_security_event(
                event_type=EventType.LOGIN_SUCCESS,
                user_id=f"user_{i % 100}",  # 100 unique users
                ip_address=f"192.168.1.{i % 255}",  # Various IPs
                outcome="success"
            )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        assert processing_time < 5.0, f"Processing took too long: {processing_time}s"
        
        # Verify all events were stored
        assert len(monitor.events) == 1000
        
        # Test query performance
        start_time = time.time()
        user_events = monitor.get_events(user_id="user_50", limit=100)
        query_time = time.time() - start_time
        
        assert query_time < 1.0, f"Query took too long: {query_time}s"
        assert len(user_events) == 10  # user_50 appears 10 times (50, 150, 250, ...)


@pytest.fixture
def security_monitor():
    """Security monitor fixture."""
    monitor = SecurityMonitor()
    monitor.real_time_analysis = False  # Disable for testing
    return monitor


@pytest.fixture
def sample_security_event():
    """Sample security event fixture."""
    return SecurityEvent(
        event_id="test_event_123",
        event_type=EventType.LOGIN_SUCCESS,
        user_id="user_123",
        username="testuser",
        ip_address="192.168.1.1",
        outcome="success",
        details={"method": "password"}
    )