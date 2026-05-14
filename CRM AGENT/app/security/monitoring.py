"""
Security monitoring and threat detection system.
"""
import time
import hashlib
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import structlog
import asyncio
from collections import defaultdict, deque

logger = structlog.get_logger()


class ThreatLevel(Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(Enum):
    """Security event types."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # Authorization events
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHANGE = "role_change"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    
    # Data access events
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    
    # System events
    SYSTEM_ACCESS = "system_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    
    # Suspicious activities
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    SUSPICIOUS_LOGIN = "suspicious_login"
    UNUSUAL_ACCESS_PATTERN = "unusual_access_pattern"
    POTENTIAL_INTRUSION = "potential_intrusion"
    
    # API events
    API_RATE_LIMIT_EXCEEDED = "api_rate_limit_exceeded"
    API_ABUSE = "api_abuse"
    INVALID_API_REQUEST = "invalid_api_request"


@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_id: str
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    outcome: str = "unknown"  # success, failure, blocked
    threat_level: ThreatLevel = ThreatLevel.LOW
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    location: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging/storage."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'resource': self.resource,
            'action': self.action,
            'outcome': self.outcome,
            'threat_level': self.threat_level.value,
            'details': self.details,
            'session_id': self.session_id,
            'location': self.location
        }


@dataclass
class ThreatIndicator:
    """Threat indicator for pattern detection."""
    indicator_id: str
    name: str
    description: str
    pattern_type: str  # frequency, sequence, anomaly
    threshold: float
    time_window: int  # seconds
    event_types: Set[EventType]
    conditions: Dict[str, Any]
    threat_level: ThreatLevel
    enabled: bool = True
    
    def matches_event(self, event: SecurityEvent) -> bool:
        """Check if event matches this indicator."""
        if not self.enabled:
            return False
        
        if event.event_type not in self.event_types:
            return False
        
        # Check additional conditions
        for key, expected_value in self.conditions.items():
            event_value = getattr(event, key, None) or event.details.get(key)
            if event_value != expected_value:
                return False
        
        return True


class SecurityMonitor:
    """Security monitoring and threat detection system."""
    
    def __init__(self):
        """Initialize security monitor."""
        self.events: deque = deque(maxlen=10000)  # Keep last 10k events
        self.event_index: Dict[str, List[SecurityEvent]] = defaultdict(list)
        self.threat_indicators: Dict[str, ThreatIndicator] = {}
        self.active_threats: Dict[str, Dict[str, Any]] = {}
        
        # Monitoring settings
        self.monitoring_enabled = True
        self.real_time_analysis = True
        self.retention_days = 30
        
        # Pattern detection windows
        self.pattern_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Initialize default threat indicators
        self._initialize_default_indicators()
        
        # Background tasks
        self._cleanup_task = None
        self._analysis_task = None
    
    def _initialize_default_indicators(self):
        """Initialize default threat detection indicators."""
        
        # Brute force login attempts
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="brute_force_login",
            name="Brute Force Login Attempts",
            description="Multiple failed login attempts from same IP",
            pattern_type="frequency",
            threshold=5.0,  # 5 failed attempts
            time_window=300,  # in 5 minutes
            event_types={EventType.LOGIN_FAILURE},
            conditions={},
            threat_level=ThreatLevel.HIGH
        ))
        
        # Suspicious login patterns
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="suspicious_login_location",
            name="Suspicious Login Location",
            description="Login from unusual geographic location",
            pattern_type="anomaly",
            threshold=1.0,
            time_window=3600,  # 1 hour
            event_types={EventType.LOGIN_SUCCESS},
            conditions={},
            threat_level=ThreatLevel.MEDIUM
        ))
        
        # Privilege escalation attempts
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="privilege_escalation",
            name="Privilege Escalation Attempt",
            description="Attempt to access resources above user's privilege level",
            pattern_type="frequency",
            threshold=3.0,  # 3 permission denied events
            time_window=600,  # in 10 minutes
            event_types={EventType.PERMISSION_DENIED},
            conditions={},
            threat_level=ThreatLevel.HIGH
        ))
        
        # API abuse detection
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="api_abuse",
            name="API Abuse Pattern",
            description="Excessive API requests indicating abuse",
            pattern_type="frequency",
            threshold=100.0,  # 100 requests
            time_window=60,  # in 1 minute
            event_types={EventType.API_RATE_LIMIT_EXCEEDED},
            conditions={},
            threat_level=ThreatLevel.MEDIUM
        ))
        
        # Data exfiltration attempts
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="data_exfiltration",
            name="Potential Data Exfiltration",
            description="Large volume of data exports",
            pattern_type="frequency",
            threshold=10.0,  # 10 export operations
            time_window=3600,  # in 1 hour
            event_types={EventType.DATA_EXPORT},
            conditions={},
            threat_level=ThreatLevel.CRITICAL
        ))
        
        # Session hijacking indicators
        self.add_threat_indicator(ThreatIndicator(
            indicator_id="session_hijacking",
            name="Potential Session Hijacking",
            description="Rapid IP address changes for same session",
            pattern_type="anomaly",
            threshold=3.0,  # 3 IP changes
            time_window=300,  # in 5 minutes
            event_types={EventType.SUSPICIOUS_LOGIN},
            conditions={},
            threat_level=ThreatLevel.HIGH
        ))
    
    def add_threat_indicator(self, indicator: ThreatIndicator):
        """Add a threat detection indicator."""
        self.threat_indicators[indicator.indicator_id] = indicator
        logger.info(f"Added threat indicator: {indicator.name}")
    
    def remove_threat_indicator(self, indicator_id: str):
        """Remove a threat detection indicator."""
        if indicator_id in self.threat_indicators:
            del self.threat_indicators[indicator_id]
            logger.info(f"Removed threat indicator: {indicator_id}")
    
    def log_security_event(
        self,
        event_type: EventType,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        outcome: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        location: Optional[str] = None
    ) -> SecurityEvent:
        """
        Log a security event.
        
        Args:
            event_type: Type of security event
            user_id: User identifier
            username: Username
            ip_address: Client IP address
            user_agent: Client user agent
            resource: Resource being accessed
            action: Action being performed
            outcome: Event outcome (success, failure, blocked)
            details: Additional event details
            session_id: Session identifier
            location: Geographic location
            
        Returns:
            Created security event
        """
        event_id = self._generate_event_id()
        
        event = SecurityEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            outcome=outcome,
            details=details or {},
            session_id=session_id,
            location=location
        )
        
        # Store event
        self.events.append(event)
        
        # Index event for quick lookup
        self._index_event(event)
        
        # Log to structured logger
        logger.info(
            "Security event logged",
            **event.to_dict()
        )
        
        # Analyze for threats if real-time analysis is enabled
        if self.real_time_analysis:
            self._analyze_event_for_threats(event)
        
        return event
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = str(int(time.time() * 1000000))  # microsecond precision
        return f"evt_{hashlib.md5(timestamp.encode()).hexdigest()[:8]}"
    
    def _index_event(self, event: SecurityEvent):
        """Index event for efficient querying."""
        # Index by user
        if event.user_id:
            self.event_index[f"user:{event.user_id}"].append(event)
        
        # Index by IP
        if event.ip_address:
            self.event_index[f"ip:{event.ip_address}"].append(event)
        
        # Index by event type
        self.event_index[f"type:{event.event_type.value}"].append(event)
        
        # Index by session
        if event.session_id:
            self.event_index[f"session:{event.session_id}"].append(event)
    
    def _analyze_event_for_threats(self, event: SecurityEvent):
        """Analyze event for threat patterns."""
        for indicator in self.threat_indicators.values():
            if indicator.matches_event(event):
                self._check_threat_pattern(indicator, event)
    
    def _check_threat_pattern(self, indicator: ThreatIndicator, event: SecurityEvent):
        """Check if event triggers a threat pattern."""
        window_key = f"{indicator.indicator_id}:{event.ip_address or 'unknown'}"
        
        # Add event to pattern window
        self.pattern_windows[window_key].append(event)
        
        # Check pattern based on type
        if indicator.pattern_type == "frequency":
            self._check_frequency_pattern(indicator, window_key, event)
        elif indicator.pattern_type == "sequence":
            self._check_sequence_pattern(indicator, window_key, event)
        elif indicator.pattern_type == "anomaly":
            self._check_anomaly_pattern(indicator, window_key, event)
    
    def _check_frequency_pattern(self, indicator: ThreatIndicator, window_key: str, event: SecurityEvent):
        """Check frequency-based threat pattern."""
        window = self.pattern_windows[window_key]
        cutoff_time = datetime.utcnow() - timedelta(seconds=indicator.time_window)
        
        # Count events within time window
        recent_events = [
            e for e in window
            if e.timestamp > cutoff_time and indicator.matches_event(e)
        ]
        
        if len(recent_events) >= indicator.threshold:
            self._trigger_threat_alert(indicator, event, {
                'event_count': len(recent_events),
                'time_window': indicator.time_window,
                'events': [e.event_id for e in recent_events[-5:]]  # Last 5 events
            })
    
    def _check_sequence_pattern(self, indicator: ThreatIndicator, window_key: str, event: SecurityEvent):
        """Check sequence-based threat pattern."""
        # Implementation for sequence pattern detection
        # This would look for specific sequences of events
        pass
    
    def _check_anomaly_pattern(self, indicator: ThreatIndicator, window_key: str, event: SecurityEvent):
        """Check anomaly-based threat pattern."""
        # Implementation for anomaly detection
        # This would use statistical analysis or ML models
        pass
    
    def _trigger_threat_alert(
        self,
        indicator: ThreatIndicator,
        triggering_event: SecurityEvent,
        context: Dict[str, Any]
    ):
        """Trigger a threat alert."""
        threat_id = f"threat_{int(time.time())}_{indicator.indicator_id}"
        
        threat_data = {
            'threat_id': threat_id,
            'indicator_id': indicator.indicator_id,
            'indicator_name': indicator.name,
            'threat_level': indicator.threat_level.value,
            'description': indicator.description,
            'triggered_at': datetime.utcnow().isoformat(),
            'triggering_event': triggering_event.to_dict(),
            'context': context,
            'status': 'active'
        }
        
        self.active_threats[threat_id] = threat_data
        
        # Log threat alert
        logger.warning(
            "Security threat detected",
            threat_id=threat_id,
            indicator=indicator.name,
            threat_level=indicator.threat_level.value,
            user_id=triggering_event.user_id,
            ip_address=triggering_event.ip_address
        )
        
        # Send alert notifications
        self._send_threat_notification(threat_data)
    
    def _send_threat_notification(self, threat_data: Dict[str, Any]):
        """Send threat notification to security team."""
        # Implementation would send notifications via:
        # - Email alerts
        # - Slack/Teams notifications
        # - SIEM integration
        # - SMS for critical threats
        
        threat_level = threat_data['threat_level']
        
        if threat_level in ['high', 'critical']:
            logger.critical(
                "Critical security threat requires immediate attention",
                **threat_data
            )
        else:
            logger.warning(
                "Security threat notification",
                **threat_data
            )
    
    def get_events(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """
        Query security events.
        
        Args:
            user_id: Filter by user ID
            ip_address: Filter by IP address
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return
            
        Returns:
            List of matching security events
        """
        events = []
        
        # Use index if available
        if user_id:
            events = self.event_index.get(f"user:{user_id}", [])
        elif ip_address:
            events = self.event_index.get(f"ip:{ip_address}", [])
        elif event_type:
            events = self.event_index.get(f"type:{event_type.value}", [])
        else:
            events = list(self.events)
        
        # Apply additional filters
        filtered_events = []
        for event in events:
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if event_type and event.event_type != event_type:
                continue
            if user_id and event.user_id != user_id:
                continue
            if ip_address and event.ip_address != ip_address:
                continue
            
            filtered_events.append(event)
        
        # Sort by timestamp (newest first) and limit
        filtered_events.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered_events[:limit]
    
    def get_active_threats(self) -> List[Dict[str, Any]]:
        """Get list of active threats."""
        return list(self.active_threats.values())
    
    def resolve_threat(self, threat_id: str, resolution: str, resolved_by: str):
        """Mark a threat as resolved."""
        if threat_id in self.active_threats:
            self.active_threats[threat_id]['status'] = 'resolved'
            self.active_threats[threat_id]['resolved_at'] = datetime.utcnow().isoformat()
            self.active_threats[threat_id]['resolution'] = resolution
            self.active_threats[threat_id]['resolved_by'] = resolved_by
            
            logger.info(
                "Security threat resolved",
                threat_id=threat_id,
                resolution=resolution,
                resolved_by=resolved_by
            )
    
    def get_security_metrics(self, time_window: int = 3600) -> Dict[str, Any]:
        """
        Get security metrics for the specified time window.
        
        Args:
            time_window: Time window in seconds
            
        Returns:
            Dictionary with security metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=time_window)
        recent_events = [e for e in self.events if e.timestamp > cutoff_time]
        
        # Count events by type
        event_counts = defaultdict(int)
        for event in recent_events:
            event_counts[event.event_type.value] += 1
        
        # Count events by outcome
        outcome_counts = defaultdict(int)
        for event in recent_events:
            outcome_counts[event.outcome] += 1
        
        # Count unique users and IPs
        unique_users = set(e.user_id for e in recent_events if e.user_id)
        unique_ips = set(e.ip_address for e in recent_events if e.ip_address)
        
        # Count threats by level
        threat_counts = defaultdict(int)
        for threat in self.active_threats.values():
            threat_counts[threat['threat_level']] += 1
        
        return {
            'time_window_seconds': time_window,
            'total_events': len(recent_events),
            'event_counts': dict(event_counts),
            'outcome_counts': dict(outcome_counts),
            'unique_users': len(unique_users),
            'unique_ips': len(unique_ips),
            'active_threats': len(self.active_threats),
            'threat_counts': dict(threat_counts),
            'failed_logins': event_counts.get(EventType.LOGIN_FAILURE.value, 0),
            'permission_denials': event_counts.get(EventType.PERMISSION_DENIED.value, 0),
            'data_exports': event_counts.get(EventType.DATA_EXPORT.value, 0)
        }
    
    def start_background_tasks(self):
        """Start background monitoring tasks."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_events())
        
        if not self._analysis_task:
            self._analysis_task = asyncio.create_task(self._periodic_analysis())
    
    def stop_background_tasks(self):
        """Stop background monitoring tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        
        if self._analysis_task:
            self._analysis_task.cancel()
            self._analysis_task = None
    
    async def _cleanup_old_events(self):
        """Periodically clean up old events."""
        while True:
            try:
                cutoff_time = datetime.utcnow() - timedelta(days=self.retention_days)
                
                # Clean up old events from index
                for key, events in self.event_index.items():
                    self.event_index[key] = [
                        e for e in events if e.timestamp > cutoff_time
                    ]
                
                # Clean up resolved threats older than 7 days
                threat_cutoff = datetime.utcnow() - timedelta(days=7)
                resolved_threats = [
                    tid for tid, threat in self.active_threats.items()
                    if threat['status'] == 'resolved' and 
                    datetime.fromisoformat(threat.get('resolved_at', '1970-01-01')) < threat_cutoff
                ]
                
                for threat_id in resolved_threats:
                    del self.active_threats[threat_id]
                
                logger.info(f"Cleaned up old security data")
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    async def _periodic_analysis(self):
        """Perform periodic security analysis."""
        while True:
            try:
                # Analyze patterns that require longer time windows
                await self._analyze_long_term_patterns()
                
                # Generate security reports
                await self._generate_security_report()
                
                # Sleep for 15 minutes
                await asyncio.sleep(900)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis task: {e}")
                await asyncio.sleep(300)
    
    async def _analyze_long_term_patterns(self):
        """Analyze long-term security patterns."""
        # Implementation for long-term pattern analysis
        # This could include:
        # - User behavior analysis
        # - Geographic access patterns
        # - Time-based access patterns
        # - Correlation analysis between events
        pass
    
    async def _generate_security_report(self):
        """Generate periodic security reports."""
        metrics = self.get_security_metrics(time_window=3600)  # Last hour
        
        logger.info(
            "Hourly security report",
            **metrics
        )


# Global security monitor instance
_security_monitor = None


def get_security_monitor() -> SecurityMonitor:
    """Get the global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor


def log_security_event(
    event_type: EventType,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    outcome: str = "unknown",
    details: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    location: Optional[str] = None
) -> SecurityEvent:
    """
    Convenience function to log security events.
    
    Args:
        event_type: Type of security event
        user_id: User identifier
        username: Username
        ip_address: Client IP address
        user_agent: Client user agent
        resource: Resource being accessed
        action: Action being performed
        outcome: Event outcome
        details: Additional event details
        session_id: Session identifier
        location: Geographic location
        
    Returns:
        Created security event
    """
    monitor = get_security_monitor()
    return monitor.log_security_event(
        event_type=event_type,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        resource=resource,
        action=action,
        outcome=outcome,
        details=details,
        session_id=session_id,
        location=location
    )