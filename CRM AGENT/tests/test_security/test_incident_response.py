"""
Tests for incident response functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.security.incident_response import (
    IncidentResponseManager,
    SecurityIncident,
    IncidentResponse,
    IncidentStatus,
    IncidentSeverity,
    ResponseAction,
    get_incident_response_manager
)
from app.security.monitoring import SecurityEvent, EventType, ThreatLevel


class TestSecurityIncident:
    """Test SecurityIncident class functionality."""
    
    def test_security_incident_creation(self):
        """Test security incident creation."""
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test incident description",
            severity=IncidentSeverity.HIGH
        )
        
        assert incident.incident_id == "inc_123"
        assert incident.title == "Test Incident"
        assert incident.description == "Test incident description"
        assert incident.severity == IncidentSeverity.HIGH
        assert incident.status == IncidentStatus.NEW
        assert isinstance(incident.created_at, datetime)
        assert isinstance(incident.updated_at, datetime)
        assert len(incident.affected_users) == 0
        assert len(incident.affected_ips) == 0
        assert len(incident.timeline) == 0
    
    def test_add_timeline_entry(self):
        """Test adding timeline entries."""
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.MEDIUM
        )
        
        incident.add_timeline_entry(
            action="investigation_started",
            details="Investigation started by security team",
            user="admin"
        )
        
        assert len(incident.timeline) == 1
        entry = incident.timeline[0]
        assert entry["action"] == "investigation_started"
        assert entry["details"] == "Investigation started by security team"
        assert entry["user"] == "admin"
        assert "timestamp" in entry
    
    def test_update_status(self):
        """Test status updates."""
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        original_status = incident.status
        incident.update_status(IncidentStatus.INVESTIGATING, "admin")
        
        assert incident.status == IncidentStatus.INVESTIGATING
        assert len(incident.timeline) == 1
        
        timeline_entry = incident.timeline[0]
        assert timeline_entry["action"] == "status_change"
        assert "new" in timeline_entry["details"]
        assert "investigating" in timeline_entry["details"]
        assert timeline_entry["user"] == "admin"
    
    def test_update_status_to_resolved(self):
        """Test updating status to resolved."""
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        incident.update_status(IncidentStatus.RESOLVED, "admin")
        
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None
        assert isinstance(incident.resolved_at, datetime)
    
    def test_to_dict(self):
        """Test incident dictionary conversion."""
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH,
            affected_users={"user_1", "user_2"},
            affected_ips={"192.168.1.1"},
            tags={"automated", "brute_force"}
        )
        
        incident_dict = incident.to_dict()
        
        assert incident_dict["incident_id"] == "inc_123"
        assert incident_dict["title"] == "Test Incident"
        assert incident_dict["severity"] == "high"
        assert incident_dict["status"] == "new"
        assert "user_1" in incident_dict["affected_users"]
        assert "user_2" in incident_dict["affected_users"]
        assert "192.168.1.1" in incident_dict["affected_ips"]
        assert "automated" in incident_dict["tags"]
        assert "brute_force" in incident_dict["tags"]


class TestIncidentResponse:
    """Test IncidentResponse class functionality."""
    
    def test_incident_response_creation(self):
        """Test incident response configuration creation."""
        response = IncidentResponse(
            response_id="test_response",
            name="Test Response",
            description="Test response configuration",
            trigger_conditions={"event_count": 5},
            actions=[ResponseAction.LOCK_USER_ACCOUNT, ResponseAction.SEND_ALERT],
            severity_threshold=IncidentSeverity.HIGH,
            auto_execute=True,
            cooldown_period=300,
            max_executions=3
        )
        
        assert response.response_id == "test_response"
        assert response.name == "Test Response"
        assert response.description == "Test response configuration"
        assert response.trigger_conditions["event_count"] == 5
        assert ResponseAction.LOCK_USER_ACCOUNT in response.actions
        assert ResponseAction.SEND_ALERT in response.actions
        assert response.severity_threshold == IncidentSeverity.HIGH
        assert response.auto_execute is True
        assert response.cooldown_period == 300
        assert response.max_executions == 3
        assert response.enabled is True


class TestIncidentResponseManager:
    """Test IncidentResponseManager class functionality."""
    
    def test_incident_response_manager_init(self):
        """Test incident response manager initialization."""
        manager = IncidentResponseManager()
        
        assert isinstance(manager.incidents, dict)
        assert isinstance(manager.response_configs, dict)
        assert isinstance(manager.response_handlers, dict)
        assert len(manager.response_configs) > 0  # Should have default configs
        assert len(manager.response_handlers) > 0  # Should have handlers
    
    def test_add_response_config(self):
        """Test adding response configuration."""
        manager = IncidentResponseManager()
        
        response = IncidentResponse(
            response_id="custom_response",
            name="Custom Response",
            description="Custom response configuration",
            trigger_conditions={"event_count": 3},
            actions=[ResponseAction.SEND_ALERT],
            severity_threshold=IncidentSeverity.MEDIUM
        )
        
        manager.add_response_config(response)
        
        assert "custom_response" in manager.response_configs
        assert manager.response_configs["custom_response"] == response
    
    def test_create_incident(self):
        """Test incident creation."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Security Incident",
            description="Test incident for unit testing",
            severity=IncidentSeverity.HIGH,
            affected_users={"user_1", "user_2"},
            affected_ips={"192.168.1.1"},
            tags={"test", "automated"}
        )
        
        assert incident.title == "Test Security Incident"
        assert incident.description == "Test incident for unit testing"
        assert incident.severity == IncidentSeverity.HIGH
        assert "user_1" in incident.affected_users
        assert "user_2" in incident.affected_users
        assert "192.168.1.1" in incident.affected_ips
        assert "test" in incident.tags
        assert "automated" in incident.tags
        assert incident.incident_id in manager.incidents
        assert len(incident.timeline) == 1  # Creation entry
    
    def test_get_incident(self):
        """Test getting incident by ID."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.MEDIUM
        )
        
        retrieved_incident = manager.get_incident(incident.incident_id)
        assert retrieved_incident == incident
        
        # Test non-existent incident
        non_existent = manager.get_incident("non_existent_id")
        assert non_existent is None
    
    def test_list_incidents_no_filters(self):
        """Test listing incidents without filters."""
        manager = IncidentResponseManager()
        
        # Create multiple incidents
        incident1 = manager.create_incident(
            title="Incident 1",
            description="First incident",
            severity=IncidentSeverity.HIGH
        )
        incident2 = manager.create_incident(
            title="Incident 2",
            description="Second incident",
            severity=IncidentSeverity.MEDIUM
        )
        
        incidents = manager.list_incidents()
        assert len(incidents) == 2
        
        # Should be sorted by creation time (newest first)
        assert incidents[0].created_at >= incidents[1].created_at
    
    def test_list_incidents_with_status_filter(self):
        """Test listing incidents with status filter."""
        manager = IncidentResponseManager()
        
        # Create incidents with different statuses
        incident1 = manager.create_incident(
            title="New Incident",
            description="New incident",
            severity=IncidentSeverity.HIGH
        )
        incident2 = manager.create_incident(
            title="Investigating Incident",
            description="Investigating incident",
            severity=IncidentSeverity.MEDIUM
        )
        incident2.update_status(IncidentStatus.INVESTIGATING)
        
        # Filter by status
        new_incidents = manager.list_incidents(status=IncidentStatus.NEW)
        assert len(new_incidents) == 1
        assert new_incidents[0].status == IncidentStatus.NEW
        
        investigating_incidents = manager.list_incidents(status=IncidentStatus.INVESTIGATING)
        assert len(investigating_incidents) == 1
        assert investigating_incidents[0].status == IncidentStatus.INVESTIGATING
    
    def test_list_incidents_with_severity_filter(self):
        """Test listing incidents with severity filter."""
        manager = IncidentResponseManager()
        
        # Create incidents with different severities
        high_incident = manager.create_incident(
            title="High Severity",
            description="High severity incident",
            severity=IncidentSeverity.HIGH
        )
        medium_incident = manager.create_incident(
            title="Medium Severity",
            description="Medium severity incident",
            severity=IncidentSeverity.MEDIUM
        )
        
        # Filter by severity
        high_incidents = manager.list_incidents(severity=IncidentSeverity.HIGH)
        assert len(high_incidents) == 1
        assert high_incidents[0].severity == IncidentSeverity.HIGH
        
        medium_incidents = manager.list_incidents(severity=IncidentSeverity.MEDIUM)
        assert len(medium_incidents) == 1
        assert medium_incidents[0].severity == IncidentSeverity.MEDIUM
    
    def test_update_incident_status(self):
        """Test updating incident status."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        # Update status
        success = manager.update_incident_status(
            incident.incident_id,
            IncidentStatus.INVESTIGATING,
            "admin"
        )
        
        assert success is True
        assert incident.status == IncidentStatus.INVESTIGATING
        
        # Test non-existent incident
        success = manager.update_incident_status(
            "non_existent_id",
            IncidentStatus.RESOLVED,
            "admin"
        )
        assert success is False
    
    def test_assign_incident(self):
        """Test assigning incident to user."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        # Assign incident
        success = manager.assign_incident(
            incident.incident_id,
            "security_analyst",
            "admin"
        )
        
        assert success is True
        assert incident.assigned_to == "security_analyst"
        
        # Check timeline entry
        assignment_entries = [
            entry for entry in incident.timeline
            if entry["action"] == "incident_assigned"
        ]
        assert len(assignment_entries) == 1
        assert "security_analyst" in assignment_entries[0]["details"]
    
    def test_add_incident_note(self):
        """Test adding note to incident."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        # Add note
        success = manager.add_incident_note(
            incident.incident_id,
            "Investigation findings: suspicious activity detected",
            "analyst"
        )
        
        assert success is True
        
        # Check timeline entry
        note_entries = [
            entry for entry in incident.timeline
            if entry["action"] == "note_added"
        ]
        assert len(note_entries) == 1
        assert "Investigation findings" in note_entries[0]["details"]
        assert note_entries[0]["user"] == "analyst"
    
    def test_resolve_incident(self):
        """Test resolving incident."""
        manager = IncidentResponseManager()
        
        incident = manager.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH
        )
        
        # Resolve incident
        success = manager.resolve_incident(
            incident.incident_id,
            "Threat mitigated by blocking IP address",
            "admin",
            "Need to improve detection rules"
        )
        
        assert success is True
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolution_summary == "Threat mitigated by blocking IP address"
        assert incident.lessons_learned == "Need to improve detection rules"
        assert incident.resolved_at is not None
    
    def test_matches_trigger_conditions(self):
        """Test trigger condition matching."""
        manager = IncidentResponseManager()
        
        response_config = IncidentResponse(
            response_id="test_response",
            name="Test Response",
            description="Test response",
            trigger_conditions={
                "threat_indicator": "brute_force_login",
                "event_count": 5
            },
            actions=[ResponseAction.SEND_ALERT],
            severity_threshold=IncidentSeverity.HIGH
        )
        
        # Matching threat data
        matching_threat_data = {
            "indicator_id": "brute_force_login",
            "threat_level": "high",
            "context": {"event_count": 6}
        }
        
        assert manager._matches_trigger_conditions(response_config, matching_threat_data) is True
        
        # Non-matching threat data (wrong indicator)
        non_matching_threat_data = {
            "indicator_id": "privilege_escalation",
            "threat_level": "high",
            "context": {"event_count": 6}
        }
        
        assert manager._matches_trigger_conditions(response_config, non_matching_threat_data) is False
        
        # Non-matching threat data (insufficient event count)
        insufficient_events = {
            "indicator_id": "brute_force_login",
            "threat_level": "high",
            "context": {"event_count": 3}
        }
        
        assert manager._matches_trigger_conditions(response_config, insufficient_events) is False
    
    def test_can_execute_response_within_limits(self):
        """Test response execution limit checking."""
        manager = IncidentResponseManager()
        
        response_config = IncidentResponse(
            response_id="test_response",
            name="Test Response",
            description="Test response",
            trigger_conditions={},
            actions=[ResponseAction.SEND_ALERT],
            severity_threshold=IncidentSeverity.MEDIUM,
            cooldown_period=300,  # 5 minutes
            max_executions=3
        )
        
        # Should be able to execute initially
        assert manager._can_execute_response(response_config) is True
        
        # Simulate executions
        now = datetime.utcnow()
        manager.execution_history[response_config.response_id] = [
            now - timedelta(seconds=100),  # Recent execution
            now - timedelta(seconds=200)   # Another recent execution
        ]
        
        # Should still be able to execute (under limit)
        assert manager._can_execute_response(response_config) is True
        
        # Add more executions to exceed limit
        manager.execution_history[response_config.response_id].append(
            now - timedelta(seconds=50)
        )
        
        # Should not be able to execute (at limit)
        assert manager._can_execute_response(response_config) is False
    
    def test_can_execute_response_cooldown(self):
        """Test response cooldown period."""
        manager = IncidentResponseManager()
        
        response_config = IncidentResponse(
            response_id="test_response",
            name="Test Response",
            description="Test response",
            trigger_conditions={},
            actions=[ResponseAction.SEND_ALERT],
            severity_threshold=IncidentSeverity.MEDIUM,
            cooldown_period=300,  # 5 minutes
            max_executions=3
        )
        
        # Add old executions (outside cooldown period)
        now = datetime.utcnow()
        manager.execution_history[response_config.response_id] = [
            now - timedelta(seconds=400),  # 6+ minutes ago
            now - timedelta(seconds=500),  # 8+ minutes ago
            now - timedelta(seconds=600)   # 10+ minutes ago
        ]
        
        # Should be able to execute (old executions don't count)
        assert manager._can_execute_response(response_config) is True
    
    def test_trigger_response(self):
        """Test triggering incident response."""
        manager = IncidentResponseManager()
        
        # Create a test response configuration
        response_config = IncidentResponse(
            response_id="test_brute_force_response",
            name="Test Brute Force Response",
            description="Test response for brute force attacks",
            trigger_conditions={
                "threat_indicator": "brute_force_login",
                "event_count": 3
            },
            actions=[ResponseAction.SEND_ALERT, ResponseAction.LOG_INCIDENT],
            severity_threshold=IncidentSeverity.HIGH,
            auto_execute=True
        )
        
        manager.add_response_config(response_config)
        
        # Create triggering event
        triggering_event = SecurityEvent(
            event_id="event_123",
            event_type=EventType.LOGIN_FAILURE,
            user_id="user_123",
            ip_address="192.168.1.100",
            outcome="failure"
        )
        
        # Create threat data
        threat_data = {
            "indicator_id": "brute_force_login",
            "indicator_name": "Brute Force Login Attempts",
            "threat_level": "high",
            "description": "Multiple failed login attempts detected",
            "context": {"event_count": 5}
        }
        
        # Trigger response
        incident_ids = manager.trigger_response(threat_data, triggering_event)
        
        assert len(incident_ids) == 1
        
        # Check incident was created
        incident = manager.get_incident(incident_ids[0])
        assert incident is not None
        assert incident.severity == IncidentSeverity.HIGH
        assert "user_123" in incident.affected_users
        assert "192.168.1.100" in incident.affected_ips
        assert "event_123" in incident.related_events
        
        # Check response actions were executed
        assert len(incident.response_actions) > 0
    
    def test_get_incident_statistics(self):
        """Test getting incident statistics."""
        manager = IncidentResponseManager()
        
        # Create incidents with different statuses and severities
        incident1 = manager.create_incident(
            title="High Severity New",
            description="High severity new incident",
            severity=IncidentSeverity.HIGH
        )
        
        incident2 = manager.create_incident(
            title="Medium Severity Investigating",
            description="Medium severity investigating incident",
            severity=IncidentSeverity.MEDIUM
        )
        incident2.update_status(IncidentStatus.INVESTIGATING)
        
        incident3 = manager.create_incident(
            title="Low Severity Resolved",
            description="Low severity resolved incident",
            severity=IncidentSeverity.LOW
        )
        incident3.update_status(IncidentStatus.RESOLVED)
        
        stats = manager.get_incident_statistics()
        
        assert stats["total_incidents"] == 3
        assert stats["status_counts"]["new"] == 1
        assert stats["status_counts"]["investigating"] == 1
        assert stats["status_counts"]["resolved"] == 1
        assert stats["severity_counts"]["high"] == 1
        assert stats["severity_counts"]["medium"] == 1
        assert stats["severity_counts"]["low"] == 1
        assert stats["resolved_incidents"] == 1
        assert stats["active_incidents"] == 2  # new + investigating
        assert stats["response_configs"] > 0  # Should have default configs
    
    @patch('app.security.incident_response.logger')
    def test_response_action_handlers(self, mock_logger):
        """Test response action handlers."""
        manager = IncidentResponseManager()
        
        incident = SecurityIncident(
            incident_id="inc_123",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH,
            affected_users={"user_1", "user_2"},
            affected_ips={"192.168.1.1"}
        )
        
        threat_data = {"threat_level": "high"}
        
        # Test various response actions
        result = manager._lock_user_account(incident, threat_data)
        assert "Locked" in result
        mock_logger.warning.assert_called()
        
        result = manager._block_ip_address(incident, threat_data)
        assert "Blocked" in result
        
        result = manager._send_alert(incident, threat_data)
        assert "alert sent" in result
        
        result = manager._escalate_to_admin(incident, threat_data)
        assert "Escalated" in result
        mock_logger.critical.assert_called()


class TestIncidentResponseIntegration:
    """Test incident response integration scenarios."""
    
    def test_complete_brute_force_response_scenario(self):
        """Test complete brute force attack response scenario."""
        manager = IncidentResponseManager()
        
        # Create triggering event
        triggering_event = SecurityEvent(
            event_id="event_brute_force",
            event_type=EventType.LOGIN_FAILURE,
            user_id="target_user",
            ip_address="192.168.1.100",
            outcome="failure"
        )
        
        # Create threat data matching brute force indicator
        threat_data = {
            "indicator_id": "brute_force_login",
            "indicator_name": "Brute Force Login Attempts",
            "threat_level": "high",
            "description": "Multiple failed login attempts from same IP",
            "context": {"event_count": 6, "time_window": 300}
        }
        
        # Trigger response
        incident_ids = manager.trigger_response(threat_data, triggering_event)
        
        assert len(incident_ids) > 0
        
        # Get the created incident
        incident = manager.get_incident(incident_ids[0])
        
        # Verify incident details
        assert incident.severity == IncidentSeverity.HIGH
        assert "target_user" in incident.affected_users
        assert "192.168.1.100" in incident.affected_ips
        assert "brute_force_response" in incident.tags
        
        # Verify response actions were executed
        assert len(incident.response_actions) > 0
        
        # Check for expected actions
        action_types = [action["action"] for action in incident.response_actions]
        assert "block_ip_address" in action_types
        assert "send_alert" in action_types
        assert "log_incident" in action_types
    
    def test_privilege_escalation_response_scenario(self):
        """Test privilege escalation response scenario."""
        manager = IncidentResponseManager()
        
        # Create triggering event
        triggering_event = SecurityEvent(
            event_id="event_privilege_escalation",
            event_type=EventType.PERMISSION_DENIED,
            user_id="suspicious_user",
            ip_address="192.168.1.50",
            resource="/admin/users",
            action="read",
            outcome="blocked"
        )
        
        # Create threat data matching privilege escalation indicator
        threat_data = {
            "indicator_id": "privilege_escalation",
            "indicator_name": "Privilege Escalation Attempt",
            "threat_level": "high",
            "description": "Multiple permission denied events",
            "context": {"event_count": 4, "time_window": 600}
        }
        
        # Trigger response
        incident_ids = manager.trigger_response(threat_data, triggering_event)
        
        if incident_ids:  # May not trigger if auto_execute is False
            incident = manager.get_incident(incident_ids[0])
            assert incident.severity == IncidentSeverity.HIGH
            assert "suspicious_user" in incident.affected_users
    
    def test_multiple_concurrent_incidents(self):
        """Test handling multiple concurrent incidents."""
        manager = IncidentResponseManager()
        
        # Create multiple different threat scenarios
        scenarios = [
            {
                "event": SecurityEvent(
                    event_id="event_1",
                    event_type=EventType.LOGIN_FAILURE,
                    user_id="user_1",
                    ip_address="192.168.1.100"
                ),
                "threat": {
                    "indicator_id": "brute_force_login",
                    "threat_level": "high",
                    "context": {"event_count": 5}
                }
            },
            {
                "event": SecurityEvent(
                    event_id="event_2",
                    event_type=EventType.API_RATE_LIMIT_EXCEEDED,
                    ip_address="192.168.1.200"
                ),
                "threat": {
                    "indicator_id": "api_abuse",
                    "threat_level": "medium",
                    "context": {"event_count": 100}
                }
            }
        ]
        
        all_incident_ids = []
        
        # Trigger responses for all scenarios
        for scenario in scenarios:
            incident_ids = manager.trigger_response(
                scenario["threat"],
                scenario["event"]
            )
            all_incident_ids.extend(incident_ids)
        
        # Verify multiple incidents were created
        assert len(all_incident_ids) >= 2
        
        # Verify incidents are independent
        incidents = [manager.get_incident(iid) for iid in all_incident_ids]
        incident_types = set()
        for incident in incidents:
            if incident:
                for tag in incident.tags:
                    if "response" in tag:
                        incident_types.add(tag)
        
        assert len(incident_types) >= 2  # Different response types
    
    def test_incident_lifecycle(self):
        """Test complete incident lifecycle."""
        manager = IncidentResponseManager()
        
        # Create incident
        incident = manager.create_incident(
            title="Security Breach Investigation",
            description="Potential security breach detected",
            severity=IncidentSeverity.CRITICAL,
            affected_users={"admin", "user_123"},
            affected_ips={"192.168.1.100"},
            tags={"security_breach", "investigation"}
        )
        
        # Assign incident
        manager.assign_incident(incident.incident_id, "security_analyst", "admin")
        
        # Update status to investigating
        manager.update_incident_status(
            incident.incident_id,
            IncidentStatus.INVESTIGATING,
            "security_analyst"
        )
        
        # Add investigation notes
        manager.add_incident_note(
            incident.incident_id,
            "Initial analysis shows suspicious login patterns",
            "security_analyst"
        )
        
        manager.add_incident_note(
            incident.incident_id,
            "Blocked suspicious IP addresses",
            "security_analyst"
        )
        
        # Update to contained
        manager.update_incident_status(
            incident.incident_id,
            IncidentStatus.CONTAINED,
            "security_analyst"
        )
        
        # Resolve incident
        manager.resolve_incident(
            incident.incident_id,
            "Threat contained by blocking IP and resetting user passwords",
            "security_analyst",
            "Need to improve monitoring for similar attack patterns"
        )
        
        # Verify final state
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.assigned_to == "security_analyst"
        assert incident.resolution_summary is not None
        assert incident.lessons_learned is not None
        assert incident.resolved_at is not None
        
        # Verify timeline has all expected entries
        timeline_actions = [entry["action"] for entry in incident.timeline]
        assert "incident_created" in timeline_actions
        assert "incident_assigned" in timeline_actions
        assert "status_change" in timeline_actions
        assert "note_added" in timeline_actions
        
        # Count status changes
        status_changes = [
            entry for entry in incident.timeline
            if entry["action"] == "status_change"
        ]
        assert len(status_changes) >= 3  # investigating, contained, resolved


class TestIncidentResponseUtilities:
    """Test incident response utility functions."""
    
    def test_get_incident_response_manager(self):
        """Test getting global incident response manager instance."""
        manager1 = get_incident_response_manager()
        manager2 = get_incident_response_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, IncidentResponseManager)


@pytest.fixture
def incident_response_manager():
    """Incident response manager fixture."""
    return IncidentResponseManager()


@pytest.fixture
def sample_security_incident():
    """Sample security incident fixture."""
    return SecurityIncident(
        incident_id="test_inc_123",
        title="Test Security Incident",
        description="Test incident for unit testing",
        severity=IncidentSeverity.HIGH,
        affected_users={"user_1", "user_2"},
        affected_ips={"192.168.1.1"},
        tags={"test", "automated"}
    )


@pytest.fixture
def sample_incident_response():
    """Sample incident response configuration fixture."""
    return IncidentResponse(
        response_id="test_response",
        name="Test Response Configuration",
        description="Test response for unit testing",
        trigger_conditions={"event_count": 5},
        actions=[ResponseAction.SEND_ALERT, ResponseAction.LOG_INCIDENT],
        severity_threshold=IncidentSeverity.HIGH,
        auto_execute=True
    )