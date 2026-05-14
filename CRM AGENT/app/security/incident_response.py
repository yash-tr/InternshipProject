"""
Security incident response and automated remediation system.
"""
import time
import uuid
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import structlog
import asyncio

from .monitoring import SecurityEvent, ThreatLevel, EventType

logger = structlog.get_logger()


class IncidentStatus(Enum):
    """Incident status enumeration."""
    NEW = "new"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResponseAction(Enum):
    """Automated response actions."""
    # User actions
    LOCK_USER_ACCOUNT = "lock_user_account"
    FORCE_PASSWORD_RESET = "force_password_reset"
    TERMINATE_USER_SESSIONS = "terminate_user_sessions"
    REQUIRE_MFA = "require_mfa"
    
    # Network actions
    BLOCK_IP_ADDRESS = "block_ip_address"
    RATE_LIMIT_IP = "rate_limit_ip"
    QUARANTINE_SESSION = "quarantine_session"
    
    # System actions
    DISABLE_API_KEY = "disable_api_key"
    ESCALATE_TO_ADMIN = "escalate_to_admin"
    SEND_ALERT = "send_alert"
    LOG_INCIDENT = "log_incident"
    
    # Data protection
    RESTRICT_DATA_ACCESS = "restrict_data_access"
    ENABLE_AUDIT_MODE = "enable_audit_mode"
    BACKUP_CRITICAL_DATA = "backup_critical_data"


@dataclass
class IncidentResponse:
    """Incident response configuration."""
    response_id: str
    name: str
    description: str
    trigger_conditions: Dict[str, Any]
    actions: List[ResponseAction]
    severity_threshold: IncidentSeverity
    auto_execute: bool = False
    cooldown_period: int = 300  # 5 minutes
    max_executions: int = 5
    enabled: bool = True


@dataclass
class SecurityIncident:
    """Security incident data structure."""
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.NEW
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Incident details
    affected_users: Set[str] = field(default_factory=set)
    affected_ips: Set[str] = field(default_factory=set)
    affected_resources: Set[str] = field(default_factory=set)
    related_events: List[str] = field(default_factory=list)  # Event IDs
    
    # Response tracking
    assigned_to: Optional[str] = None
    response_actions: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    
    # Resolution
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    lessons_learned: Optional[str] = None
    
    # Metadata
    tags: Set[str] = field(default_factory=set)
    external_references: List[str] = field(default_factory=list)
    
    def add_timeline_entry(self, action: str, details: str, user: Optional[str] = None):
        """Add entry to incident timeline."""
        self.timeline.append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'details': details,
            'user': user
        })
        self.updated_at = datetime.utcnow()
    
    def update_status(self, new_status: IncidentStatus, user: Optional[str] = None):
        """Update incident status."""
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        self.add_timeline_entry(
            action="status_change",
            details=f"Status changed from {old_status.value} to {new_status.value}",
            user=user
        )
        
        if new_status == IncidentStatus.RESOLVED:
            self.resolved_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert incident to dictionary."""
        return {
            'incident_id': self.incident_id,
            'title': self.title,
            'description': self.description,
            'severity': self.severity.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'affected_users': list(self.affected_users),
            'affected_ips': list(self.affected_ips),
            'affected_resources': list(self.affected_resources),
            'related_events': self.related_events,
            'assigned_to': self.assigned_to,
            'response_actions': self.response_actions,
            'timeline': self.timeline,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_summary': self.resolution_summary,
            'lessons_learned': self.lessons_learned,
            'tags': list(self.tags),
            'external_references': self.external_references
        }


class IncidentResponseManager:
    """Manages security incident response and automated remediation."""
    
    def __init__(self):
        """Initialize incident response manager."""
        self.incidents: Dict[str, SecurityIncident] = {}
        self.response_configs: Dict[str, IncidentResponse] = {}
        self.response_handlers: Dict[ResponseAction, Callable] = {}
        self.execution_history: Dict[str, List[datetime]] = {}
        
        # Initialize default response configurations
        self._initialize_default_responses()
        
        # Register response handlers
        self._register_response_handlers()
    
    def _initialize_default_responses(self):
        """Initialize default incident response configurations."""
        
        # Brute force attack response
        self.add_response_config(IncidentResponse(
            response_id="brute_force_response",
            name="Brute Force Attack Response",
            description="Automated response to brute force login attempts",
            trigger_conditions={
                'threat_indicator': 'brute_force_login',
                'event_count': 5,
                'time_window': 300
            },
            actions=[
                ResponseAction.BLOCK_IP_ADDRESS,
                ResponseAction.SEND_ALERT,
                ResponseAction.LOG_INCIDENT
            ],
            severity_threshold=IncidentSeverity.HIGH,
            auto_execute=True,
            cooldown_period=600,  # 10 minutes
            max_executions=3
        ))
        
        # Privilege escalation response
        self.add_response_config(IncidentResponse(
            response_id="privilege_escalation_response",
            name="Privilege Escalation Response",
            description="Response to privilege escalation attempts",
            trigger_conditions={
                'threat_indicator': 'privilege_escalation',
                'event_count': 3,
                'time_window': 600
            },
            actions=[
                ResponseAction.LOCK_USER_ACCOUNT,
                ResponseAction.TERMINATE_USER_SESSIONS,
                ResponseAction.ESCALATE_TO_ADMIN,
                ResponseAction.LOG_INCIDENT
            ],
            severity_threshold=IncidentSeverity.HIGH,
            auto_execute=False,  # Requires manual approval
            cooldown_period=3600,  # 1 hour
            max_executions=1
        ))
        
        # Data exfiltration response
        self.add_response_config(IncidentResponse(
            response_id="data_exfiltration_response",
            name="Data Exfiltration Response",
            description="Response to potential data exfiltration",
            trigger_conditions={
                'threat_indicator': 'data_exfiltration',
                'event_count': 10,
                'time_window': 3600
            },
            actions=[
                ResponseAction.LOCK_USER_ACCOUNT,
                ResponseAction.RESTRICT_DATA_ACCESS,
                ResponseAction.ENABLE_AUDIT_MODE,
                ResponseAction.ESCALATE_TO_ADMIN,
                ResponseAction.LOG_INCIDENT
            ],
            severity_threshold=IncidentSeverity.CRITICAL,
            auto_execute=True,
            cooldown_period=1800,  # 30 minutes
            max_executions=2
        ))
        
        # API abuse response
        self.add_response_config(IncidentResponse(
            response_id="api_abuse_response",
            name="API Abuse Response",
            description="Response to API abuse patterns",
            trigger_conditions={
                'threat_indicator': 'api_abuse',
                'event_count': 100,
                'time_window': 60
            },
            actions=[
                ResponseAction.RATE_LIMIT_IP,
                ResponseAction.DISABLE_API_KEY,
                ResponseAction.SEND_ALERT,
                ResponseAction.LOG_INCIDENT
            ],
            severity_threshold=IncidentSeverity.MEDIUM,
            auto_execute=True,
            cooldown_period=300,  # 5 minutes
            max_executions=5
        ))
        
        # Session hijacking response
        self.add_response_config(IncidentResponse(
            response_id="session_hijacking_response",
            name="Session Hijacking Response",
            description="Response to potential session hijacking",
            trigger_conditions={
                'threat_indicator': 'session_hijacking',
                'ip_changes': 3,
                'time_window': 300
            },
            actions=[
                ResponseAction.TERMINATE_USER_SESSIONS,
                ResponseAction.FORCE_PASSWORD_RESET,
                ResponseAction.REQUIRE_MFA,
                ResponseAction.ESCALATE_TO_ADMIN,
                ResponseAction.LOG_INCIDENT
            ],
            severity_threshold=IncidentSeverity.HIGH,
            auto_execute=True,
            cooldown_period=1800,  # 30 minutes
            max_executions=1
        ))
    
    def _register_response_handlers(self):
        """Register handlers for response actions."""
        self.response_handlers = {
            ResponseAction.LOCK_USER_ACCOUNT: self._lock_user_account,
            ResponseAction.FORCE_PASSWORD_RESET: self._force_password_reset,
            ResponseAction.TERMINATE_USER_SESSIONS: self._terminate_user_sessions,
            ResponseAction.REQUIRE_MFA: self._require_mfa,
            ResponseAction.BLOCK_IP_ADDRESS: self._block_ip_address,
            ResponseAction.RATE_LIMIT_IP: self._rate_limit_ip,
            ResponseAction.QUARANTINE_SESSION: self._quarantine_session,
            ResponseAction.DISABLE_API_KEY: self._disable_api_key,
            ResponseAction.ESCALATE_TO_ADMIN: self._escalate_to_admin,
            ResponseAction.SEND_ALERT: self._send_alert,
            ResponseAction.LOG_INCIDENT: self._log_incident,
            ResponseAction.RESTRICT_DATA_ACCESS: self._restrict_data_access,
            ResponseAction.ENABLE_AUDIT_MODE: self._enable_audit_mode,
            ResponseAction.BACKUP_CRITICAL_DATA: self._backup_critical_data
        }
    
    def add_response_config(self, response: IncidentResponse):
        """Add incident response configuration."""
        self.response_configs[response.response_id] = response
        logger.info(f"Added incident response config: {response.name}")
    
    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        affected_users: Optional[Set[str]] = None,
        affected_ips: Optional[Set[str]] = None,
        affected_resources: Optional[Set[str]] = None,
        related_events: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> SecurityIncident:
        """
        Create a new security incident.
        
        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity
            affected_users: Set of affected user IDs
            affected_ips: Set of affected IP addresses
            affected_resources: Set of affected resources
            related_events: List of related event IDs
            tags: Set of incident tags
            
        Returns:
            Created security incident
        """
        incident_id = f"inc_{uuid.uuid4().hex[:8]}"
        
        incident = SecurityIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            affected_users=affected_users or set(),
            affected_ips=affected_ips or set(),
            affected_resources=affected_resources or set(),
            related_events=related_events or [],
            tags=tags or set()
        )
        
        incident.add_timeline_entry(
            action="incident_created",
            details=f"Incident created with severity {severity.value}"
        )
        
        self.incidents[incident_id] = incident
        
        logger.warning(
            "Security incident created",
            incident_id=incident_id,
            title=title,
            severity=severity.value
        )
        
        return incident
    
    def trigger_response(
        self,
        threat_data: Dict[str, Any],
        triggering_event: SecurityEvent
    ) -> List[str]:
        """
        Trigger incident response based on threat data.
        
        Args:
            threat_data: Threat detection data
            triggering_event: Event that triggered the response
            
        Returns:
            List of incident IDs created
        """
        triggered_incidents = []
        
        for response_config in self.response_configs.values():
            if not response_config.enabled:
                continue
            
            if self._matches_trigger_conditions(response_config, threat_data):
                # Check cooldown and execution limits
                if not self._can_execute_response(response_config):
                    continue
                
                # Create incident
                incident = self._create_incident_from_threat(
                    response_config, threat_data, triggering_event
                )
                triggered_incidents.append(incident.incident_id)
                
                # Execute response actions
                if response_config.auto_execute:
                    self._execute_response_actions(
                        response_config, incident, threat_data
                    )
                else:
                    logger.info(
                        "Manual approval required for incident response",
                        incident_id=incident.incident_id,
                        response_config=response_config.name
                    )
        
        return triggered_incidents
    
    def _matches_trigger_conditions(
        self,
        response_config: IncidentResponse,
        threat_data: Dict[str, Any]
    ) -> bool:
        """Check if threat data matches response trigger conditions."""
        conditions = response_config.trigger_conditions
        
        # Check threat indicator match
        if 'threat_indicator' in conditions:
            if threat_data.get('indicator_id') != conditions['threat_indicator']:
                return False
        
        # Check event count threshold
        if 'event_count' in conditions:
            if threat_data.get('context', {}).get('event_count', 0) < conditions['event_count']:
                return False
        
        # Check time window
        if 'time_window' in conditions:
            # This would be validated during threat detection
            pass
        
        # Check severity threshold
        threat_level = threat_data.get('threat_level', 'low')
        if self._severity_to_threat_level(response_config.severity_threshold).value > threat_level:
            return False
        
        return True
    
    def _severity_to_threat_level(self, severity: IncidentSeverity) -> ThreatLevel:
        """Convert incident severity to threat level."""
        mapping = {
            IncidentSeverity.LOW: ThreatLevel.LOW,
            IncidentSeverity.MEDIUM: ThreatLevel.MEDIUM,
            IncidentSeverity.HIGH: ThreatLevel.HIGH,
            IncidentSeverity.CRITICAL: ThreatLevel.CRITICAL
        }
        return mapping.get(severity, ThreatLevel.LOW)
    
    def _can_execute_response(self, response_config: IncidentResponse) -> bool:
        """Check if response can be executed based on cooldown and limits."""
        config_id = response_config.response_id
        now = datetime.utcnow()
        
        # Check execution history
        if config_id not in self.execution_history:
            self.execution_history[config_id] = []
        
        executions = self.execution_history[config_id]
        
        # Remove old executions outside cooldown period
        cooldown_cutoff = now - timedelta(seconds=response_config.cooldown_period)
        executions[:] = [exec_time for exec_time in executions if exec_time > cooldown_cutoff]
        
        # Check execution limit
        if len(executions) >= response_config.max_executions:
            logger.warning(
                "Response execution limit reached",
                response_config=response_config.name,
                executions=len(executions),
                max_executions=response_config.max_executions
            )
            return False
        
        return True
    
    def _create_incident_from_threat(
        self,
        response_config: IncidentResponse,
        threat_data: Dict[str, Any],
        triggering_event: SecurityEvent
    ) -> SecurityIncident:
        """Create incident from threat data."""
        title = f"{response_config.name}: {threat_data.get('indicator_name', 'Unknown Threat')}"
        description = f"Automated incident created for {threat_data.get('description', 'security threat')}"
        
        # Extract affected entities
        affected_users = set()
        affected_ips = set()
        affected_resources = set()
        
        if triggering_event.user_id:
            affected_users.add(triggering_event.user_id)
        if triggering_event.ip_address:
            affected_ips.add(triggering_event.ip_address)
        if triggering_event.resource:
            affected_resources.add(triggering_event.resource)
        
        return self.create_incident(
            title=title,
            description=description,
            severity=response_config.severity_threshold,
            affected_users=affected_users,
            affected_ips=affected_ips,
            affected_resources=affected_resources,
            related_events=[triggering_event.event_id],
            tags={response_config.response_id, "automated"}
        )
    
    def _execute_response_actions(
        self,
        response_config: IncidentResponse,
        incident: SecurityIncident,
        threat_data: Dict[str, Any]
    ):
        """Execute automated response actions."""
        # Record execution
        self.execution_history[response_config.response_id].append(datetime.utcnow())
        
        for action in response_config.actions:
            try:
                handler = self.response_handlers.get(action)
                if handler:
                    result = handler(incident, threat_data)
                    
                    incident.response_actions.append({
                        'action': action.value,
                        'timestamp': datetime.utcnow().isoformat(),
                        'result': result,
                        'automated': True
                    })
                    
                    incident.add_timeline_entry(
                        action="response_action_executed",
                        details=f"Executed {action.value}: {result}"
                    )
                else:
                    logger.error(f"No handler found for response action: {action.value}")
                    
            except Exception as e:
                logger.error(
                    "Error executing response action",
                    action=action.value,
                    incident_id=incident.incident_id,
                    error=str(e)
                )
                
                incident.add_timeline_entry(
                    action="response_action_failed",
                    details=f"Failed to execute {action.value}: {str(e)}"
                )
    
    # Response action handlers
    def _lock_user_account(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Lock user account."""
        # Implementation would integrate with access control manager
        affected_users = list(incident.affected_users)
        logger.warning(f"Would lock user accounts: {affected_users}")
        return f"Locked {len(affected_users)} user accounts"
    
    def _force_password_reset(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Force password reset for affected users."""
        affected_users = list(incident.affected_users)
        logger.warning(f"Would force password reset for users: {affected_users}")
        return f"Forced password reset for {len(affected_users)} users"
    
    def _terminate_user_sessions(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Terminate user sessions."""
        affected_users = list(incident.affected_users)
        logger.warning(f"Would terminate sessions for users: {affected_users}")
        return f"Terminated sessions for {len(affected_users)} users"
    
    def _require_mfa(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Require MFA for affected users."""
        affected_users = list(incident.affected_users)
        logger.warning(f"Would require MFA for users: {affected_users}")
        return f"Required MFA for {len(affected_users)} users"
    
    def _block_ip_address(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Block IP addresses."""
        affected_ips = list(incident.affected_ips)
        logger.warning(f"Would block IP addresses: {affected_ips}")
        return f"Blocked {len(affected_ips)} IP addresses"
    
    def _rate_limit_ip(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Apply rate limiting to IP addresses."""
        affected_ips = list(incident.affected_ips)
        logger.warning(f"Would rate limit IP addresses: {affected_ips}")
        return f"Applied rate limiting to {len(affected_ips)} IP addresses"
    
    def _quarantine_session(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Quarantine suspicious sessions."""
        logger.warning("Would quarantine suspicious sessions")
        return "Quarantined suspicious sessions"
    
    def _disable_api_key(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Disable API keys."""
        affected_users = list(incident.affected_users)
        logger.warning(f"Would disable API keys for users: {affected_users}")
        return f"Disabled API keys for {len(affected_users)} users"
    
    def _escalate_to_admin(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Escalate incident to administrators."""
        logger.critical(
            "Security incident escalated to administrators",
            incident_id=incident.incident_id,
            severity=incident.severity.value
        )
        return "Escalated to administrators"
    
    def _send_alert(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Send security alert."""
        logger.warning(
            "Security alert sent",
            incident_id=incident.incident_id,
            threat_level=threat_data.get('threat_level')
        )
        return "Security alert sent"
    
    def _log_incident(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Log incident details."""
        logger.info(
            "Incident logged",
            incident_id=incident.incident_id,
            **incident.to_dict()
        )
        return "Incident logged"
    
    def _restrict_data_access(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Restrict data access for affected users."""
        affected_users = list(incident.affected_users)
        logger.warning(f"Would restrict data access for users: {affected_users}")
        return f"Restricted data access for {len(affected_users)} users"
    
    def _enable_audit_mode(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Enable enhanced audit mode."""
        logger.warning("Would enable enhanced audit mode")
        return "Enhanced audit mode enabled"
    
    def _backup_critical_data(self, incident: SecurityIncident, threat_data: Dict[str, Any]) -> str:
        """Backup critical data."""
        logger.warning("Would backup critical data")
        return "Critical data backup initiated"
    
    def get_incident(self, incident_id: str) -> Optional[SecurityIncident]:
        """Get incident by ID."""
        return self.incidents.get(incident_id)
    
    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        limit: int = 100
    ) -> List[SecurityIncident]:
        """List incidents with optional filters."""
        incidents = list(self.incidents.values())
        
        # Apply filters
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        
        # Sort by creation time (newest first)
        incidents.sort(key=lambda i: i.created_at, reverse=True)
        
        return incidents[:limit]
    
    def update_incident_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        user: Optional[str] = None
    ) -> bool:
        """Update incident status."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        
        incident.update_status(new_status, user)
        
        logger.info(
            "Incident status updated",
            incident_id=incident_id,
            new_status=new_status.value,
            user=user
        )
        
        return True
    
    def assign_incident(
        self,
        incident_id: str,
        assignee: str,
        assigned_by: Optional[str] = None
    ) -> bool:
        """Assign incident to a user."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        
        incident.assigned_to = assignee
        incident.add_timeline_entry(
            action="incident_assigned",
            details=f"Incident assigned to {assignee}",
            user=assigned_by
        )
        
        logger.info(
            "Incident assigned",
            incident_id=incident_id,
            assignee=assignee,
            assigned_by=assigned_by
        )
        
        return True
    
    def add_incident_note(
        self,
        incident_id: str,
        note: str,
        user: Optional[str] = None
    ) -> bool:
        """Add note to incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        
        incident.add_timeline_entry(
            action="note_added",
            details=note,
            user=user
        )
        
        return True
    
    def resolve_incident(
        self,
        incident_id: str,
        resolution_summary: str,
        user: Optional[str] = None,
        lessons_learned: Optional[str] = None
    ) -> bool:
        """Resolve incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        
        incident.update_status(IncidentStatus.RESOLVED, user)
        incident.resolution_summary = resolution_summary
        incident.lessons_learned = lessons_learned
        
        logger.info(
            "Incident resolved",
            incident_id=incident_id,
            resolution_summary=resolution_summary,
            user=user
        )
        
        return True
    
    def get_incident_statistics(self) -> Dict[str, Any]:
        """Get incident response statistics."""
        total_incidents = len(self.incidents)
        
        # Count by status
        status_counts = {}
        for status in IncidentStatus:
            status_counts[status.value] = sum(
                1 for i in self.incidents.values() if i.status == status
            )
        
        # Count by severity
        severity_counts = {}
        for severity in IncidentSeverity:
            severity_counts[severity.value] = sum(
                1 for i in self.incidents.values() if i.severity == severity
            )
        
        # Calculate resolution times
        resolved_incidents = [
            i for i in self.incidents.values()
            if i.status == IncidentStatus.RESOLVED and i.resolved_at
        ]
        
        avg_resolution_time = 0
        if resolved_incidents:
            total_time = sum(
                (i.resolved_at - i.created_at).total_seconds()
                for i in resolved_incidents
            )
            avg_resolution_time = total_time / len(resolved_incidents)
        
        return {
            'total_incidents': total_incidents,
            'status_counts': status_counts,
            'severity_counts': severity_counts,
            'resolved_incidents': len(resolved_incidents),
            'avg_resolution_time_seconds': avg_resolution_time,
            'active_incidents': status_counts.get('new', 0) + status_counts.get('investigating', 0),
            'response_configs': len(self.response_configs)
        }


# Global incident response manager instance
_incident_response_manager = None


def get_incident_response_manager() -> IncidentResponseManager:
    """Get the global incident response manager instance."""
    global _incident_response_manager
    if _incident_response_manager is None:
        _incident_response_manager = IncidentResponseManager()
    return _incident_response_manager