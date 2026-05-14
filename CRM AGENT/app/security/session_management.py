"""
Advanced session management with security features.
"""
import secrets
import hashlib
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import structlog

from .access_control import User

logger = structlog.get_logger()


class SessionStatus(Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPICIOUS = "suspicious"


@dataclass
class SessionInfo:
    """Extended session information with security tracking."""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    
    # Security tracking
    login_method: str = "password"  # password, api_key, sso
    mfa_verified: bool = False
    device_fingerprint: Optional[str] = None
    location: Optional[str] = None
    
    # Activity tracking
    request_count: int = 0
    last_request_time: Optional[datetime] = None
    suspicious_activity_count: int = 0
    
    # Session metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE and not self.is_expired()
    
    def update_activity(self):
        """Update session activity."""
        now = datetime.utcnow()
        self.last_activity = now
        self.last_request_time = now
        self.request_count += 1
    
    def mark_suspicious(self, reason: str):
        """Mark session as suspicious."""
        self.suspicious_activity_count += 1
        self.status = SessionStatus.SUSPICIOUS
        self.metadata['suspicious_reason'] = reason
        self.metadata['suspicious_timestamp'] = datetime.utcnow().isoformat()
        
        logger.warning(
            "Session marked as suspicious",
            session_id=self.session_id,
            user_id=self.user_id,
            reason=reason
        )


class SessionManager:
    """Advanced session management with security features."""
    
    def __init__(self):
        """Initialize session manager."""
        self.sessions: Dict[str, SessionInfo] = {}
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> session_ids
        
        # Security settings
        self.max_sessions_per_user = 5
        self.session_timeout = 3600  # 1 hour
        self.absolute_timeout = 86400  # 24 hours
        self.inactivity_timeout = 1800  # 30 minutes
        
        # Suspicious activity thresholds
        self.max_requests_per_minute = 60
        self.max_ip_changes = 3
        self.max_user_agent_changes = 2
        
        # Cleanup settings
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = datetime.utcnow()
    
    def create_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        login_method: str = "password",
        mfa_verified: bool = False,
        device_fingerprint: Optional[str] = None,
        location: Optional[str] = None
    ) -> SessionInfo:
        """
        Create a new session for user.
        
        Args:
            user: User object
            ip_address: Client IP address
            user_agent: Client user agent
            login_method: Authentication method used
            mfa_verified: Whether MFA was verified
            device_fingerprint: Device fingerprint
            location: Geographic location
            
        Returns:
            New session info
        """
        # Check session limits
        self._enforce_session_limits(user.user_id)
        
        # Generate session ID
        session_id = self._generate_session_id()
        
        # Calculate expiry times
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.session_timeout)
        
        # Create session
        session = SessionInfo(
            session_id=session_id,
            user_id=user.user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
            mfa_verified=mfa_verified,
            device_fingerprint=device_fingerprint,
            location=location
        )
        
        # Store session
        self.sessions[session_id] = session
        
        # Track user sessions
        if user.user_id not in self.user_sessions:
            self.user_sessions[user.user_id] = set()
        self.user_sessions[user.user_id].add(session_id)
        
        logger.info(
            "Session created",
            session_id=session_id,
            user_id=user.user_id,
            ip_address=ip_address,
            login_method=login_method,
            mfa_verified=mfa_verified
        )
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session info or None if not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Check if session is expired
        if not session.is_active():
            self.terminate_session(session_id, "expired")
            return None
        
        return session
    
    def validate_session(
        self,
        session_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[SessionInfo]:
        """
        Validate session and update activity.
        
        Args:
            session_id: Session identifier
            ip_address: Current IP address
            user_agent: Current user agent
            
        Returns:
            Valid session info or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Check for suspicious activity
        if self._detect_suspicious_activity(session, ip_address, user_agent):
            return None
        
        # Update activity
        session.update_activity()
        
        # Extend session if needed (sliding window)
        self._extend_session(session)
        
        return session
    
    def terminate_session(self, session_id: str, reason: str = "manual"):
        """
        Terminate a session.
        
        Args:
            session_id: Session identifier
            reason: Termination reason
        """
        session = self.sessions.get(session_id)
        if not session:
            return
        
        # Update session status
        session.status = SessionStatus.TERMINATED
        session.metadata['termination_reason'] = reason
        session.metadata['terminated_at'] = datetime.utcnow().isoformat()
        
        # Remove from active sessions
        del self.sessions[session_id]
        
        # Remove from user sessions
        if session.user_id in self.user_sessions:
            self.user_sessions[session.user_id].discard(session_id)
            if not self.user_sessions[session.user_id]:
                del self.user_sessions[session.user_id]
        
        logger.info(
            "Session terminated",
            session_id=session_id,
            user_id=session.user_id,
            reason=reason
        )
    
    def terminate_user_sessions(self, user_id: str, exclude_session: Optional[str] = None):
        """
        Terminate all sessions for a user.
        
        Args:
            user_id: User identifier
            exclude_session: Session ID to exclude from termination
        """
        session_ids = self.user_sessions.get(user_id, set()).copy()
        
        for session_id in session_ids:
            if session_id != exclude_session:
                self.terminate_session(session_id, "user_logout_all")
        
        logger.info(f"All sessions terminated for user: {user_id}")
    
    def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active sessions
        """
        session_ids = self.user_sessions.get(user_id, set())
        sessions = []
        
        for session_id in session_ids.copy():
            session = self.get_session(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    def cleanup_expired_sessions(self):
        """Clean up expired and terminated sessions."""
        now = datetime.utcnow()
        
        # Skip if cleanup was recent
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return
        
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if not session.is_active():
                expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            self.terminate_session(session_id, "cleanup")
        
        self.last_cleanup = now
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        now = datetime.utcnow()
        active_sessions = len(self.sessions)
        
        # Count sessions by status
        status_counts = {}
        for session in self.sessions.values():
            status = session.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count sessions by login method
        method_counts = {}
        for session in self.sessions.values():
            method = session.login_method
            method_counts[method] = method_counts.get(method, 0) + 1
        
        # Calculate average session duration
        total_duration = 0
        session_count = 0
        for session in self.sessions.values():
            if session.created_at:
                duration = (now - session.created_at).total_seconds()
                total_duration += duration
                session_count += 1
        
        avg_duration = total_duration / session_count if session_count > 0 else 0
        
        return {
            'active_sessions': active_sessions,
            'unique_users': len(self.user_sessions),
            'status_counts': status_counts,
            'method_counts': method_counts,
            'average_duration_seconds': avg_duration,
            'suspicious_sessions': sum(
                1 for s in self.sessions.values()
                if s.status == SessionStatus.SUSPICIOUS
            )
        }
    
    def _generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return f"sess_{secrets.token_urlsafe(32)}"
    
    def _enforce_session_limits(self, user_id: str):
        """Enforce maximum sessions per user."""
        user_session_ids = self.user_sessions.get(user_id, set())
        
        if len(user_session_ids) >= self.max_sessions_per_user:
            # Terminate oldest session
            oldest_session_id = None
            oldest_time = datetime.utcnow()
            
            for session_id in user_session_ids:
                session = self.sessions.get(session_id)
                if session and session.created_at < oldest_time:
                    oldest_time = session.created_at
                    oldest_session_id = session_id
            
            if oldest_session_id:
                self.terminate_session(oldest_session_id, "session_limit")
    
    def _extend_session(self, session: SessionInfo):
        """Extend session expiry (sliding window)."""
        now = datetime.utcnow()
        
        # Check if session is close to expiry
        if session.expires_at and (session.expires_at - now).total_seconds() < 300:  # 5 minutes
            # Extend by session timeout
            session.expires_at = now + timedelta(seconds=self.session_timeout)
            
            # But don't exceed absolute timeout
            absolute_expiry = session.created_at + timedelta(seconds=self.absolute_timeout)
            if session.expires_at > absolute_expiry:
                session.expires_at = absolute_expiry
    
    def _detect_suspicious_activity(
        self,
        session: SessionInfo,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> bool:
        """
        Detect suspicious session activity.
        
        Args:
            session: Session to check
            ip_address: Current IP address
            user_agent: Current user agent
            
        Returns:
            True if suspicious activity detected
        """
        now = datetime.utcnow()
        
        # Check request rate
        if session.last_request_time:
            time_diff = (now - session.last_request_time).total_seconds()
            if time_diff < 60:  # Within last minute
                requests_per_minute = session.request_count / max(time_diff / 60, 1)
                if requests_per_minute > self.max_requests_per_minute:
                    session.mark_suspicious("high_request_rate")
                    return True
        
        # Check IP address changes
        if ip_address and session.ip_address and ip_address != session.ip_address:
            ip_changes = session.metadata.get('ip_changes', 0) + 1
            session.metadata['ip_changes'] = ip_changes
            session.metadata['previous_ips'] = session.metadata.get('previous_ips', [])
            session.metadata['previous_ips'].append(session.ip_address)
            session.ip_address = ip_address
            
            if ip_changes > self.max_ip_changes:
                session.mark_suspicious("multiple_ip_changes")
                return True
        
        # Check user agent changes
        if user_agent and session.user_agent and user_agent != session.user_agent:
            ua_changes = session.metadata.get('user_agent_changes', 0) + 1
            session.metadata['user_agent_changes'] = ua_changes
            session.metadata['previous_user_agents'] = session.metadata.get('previous_user_agents', [])
            session.metadata['previous_user_agents'].append(session.user_agent)
            session.user_agent = user_agent
            
            if ua_changes > self.max_user_agent_changes:
                session.mark_suspicious("multiple_user_agent_changes")
                return True
        
        # Check for session hijacking indicators
        if self._detect_session_hijacking(session):
            session.mark_suspicious("possible_session_hijacking")
            return True
        
        return False
    
    def _detect_session_hijacking(self, session: SessionInfo) -> bool:
        """
        Detect potential session hijacking.
        
        Args:
            session: Session to check
            
        Returns:
            True if potential hijacking detected
        """
        # Check for rapid location changes (if location tracking is available)
        if session.location and 'previous_locations' in session.metadata:
            # This would require geolocation logic
            # For now, just a placeholder
            pass
        
        # Check for unusual activity patterns
        if session.suspicious_activity_count > 2:
            return True
        
        return False
    
    def force_session_refresh(self, session_id: str) -> bool:
        """
        Force session to require re-authentication.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was marked for refresh
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.metadata['requires_reauth'] = True
        session.metadata['reauth_required_at'] = datetime.utcnow().isoformat()
        
        logger.info(f"Session marked for re-authentication: {session_id}")
        return True
    
    def requires_reauth(self, session_id: str) -> bool:
        """
        Check if session requires re-authentication.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if re-authentication is required
        """
        session = self.sessions.get(session_id)
        if not session:
            return True
        
        return session.metadata.get('requires_reauth', False)


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager