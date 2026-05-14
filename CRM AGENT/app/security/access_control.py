"""
Role-Based Access Control (RBAC) system for AI Calling Agent.
"""
import hashlib
import secrets
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import jwt
import bcrypt
import logging

logger = logging.getLogger(__name__)


class Role(Enum):
    """System roles with hierarchical permissions."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(Enum):
    """System permissions."""
    # System administration
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    
    # Data access
    READ_ALL_DATA = "read_all_data"
    WRITE_ALL_DATA = "write_all_data"
    DELETE_DATA = "delete_data"
    EXPORT_DATA = "export_data"
    
    # Call management
    MANAGE_CALLS = "manage_calls"
    VIEW_CALLS = "view_calls"
    INITIATE_CALLS = "initiate_calls"
    
    # Lead management
    MANAGE_LEADS = "manage_leads"
    VIEW_LEADS = "view_leads"
    QUALIFY_LEADS = "qualify_leads"
    
    # Campaign management
    MANAGE_CAMPAIGNS = "manage_campaigns"
    VIEW_CAMPAIGNS = "view_campaigns"
    
    # API access
    API_READ = "api_read"
    API_WRITE = "api_write"
    API_ADMIN = "api_admin"
    
    # Approval workflows
    APPROVE_HIGH_VALUE = "approve_high_value"
    APPROVE_CAMPAIGNS = "approve_campaigns"
    
    # Monitoring and analytics
    VIEW_ANALYTICS = "view_analytics"
    VIEW_PERFORMANCE = "view_performance"


@dataclass
class User:
    """User account with authentication and authorization data."""
    user_id: str
    username: str
    email: str
    password_hash: str
    roles: Set[Role] = field(default_factory=set)
    is_active: bool = True
    is_locked: bool = False
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    password_expires_at: Optional[datetime] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    api_key: Optional[str] = None
    api_key_expires_at: Optional[datetime] = None
    session_timeout: int = 3600  # 1 hour default
    allowed_ips: Set[str] = field(default_factory=set)
    
    def has_role(self, role: Role) -> bool:
        """Check if user has specific role."""
        return role in self.roles
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission through their roles."""
        return any(
            permission in ROLE_PERMISSIONS.get(role, set())
            for role in self.roles
        )
    
    def add_role(self, role: Role):
        """Add role to user."""
        self.roles.add(role)
        self.updated_at = datetime.utcnow()
    
    def remove_role(self, role: Role):
        """Remove role from user."""
        self.roles.discard(role)
        self.updated_at = datetime.utcnow()
    
    def is_password_expired(self) -> bool:
        """Check if password has expired."""
        if not self.password_expires_at:
            return False
        return datetime.utcnow() > self.password_expires_at
    
    def is_api_key_expired(self) -> bool:
        """Check if API key has expired."""
        if not self.api_key_expires_at:
            return False
        return datetime.utcnow() > self.api_key_expires_at


@dataclass
class Session:
    """User session data."""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()


# Role-Permission mapping
ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: {
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.MANAGE_SYSTEM,
        Permission.VIEW_AUDIT_LOGS,
        Permission.READ_ALL_DATA,
        Permission.WRITE_ALL_DATA,
        Permission.DELETE_DATA,
        Permission.EXPORT_DATA,
        Permission.MANAGE_CALLS,
        Permission.VIEW_CALLS,
        Permission.INITIATE_CALLS,
        Permission.MANAGE_LEADS,
        Permission.VIEW_LEADS,
        Permission.QUALIFY_LEADS,
        Permission.MANAGE_CAMPAIGNS,
        Permission.VIEW_CAMPAIGNS,
        Permission.API_READ,
        Permission.API_WRITE,
        Permission.API_ADMIN,
        Permission.APPROVE_HIGH_VALUE,
        Permission.APPROVE_CAMPAIGNS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PERFORMANCE,
    },
    Role.ADMIN: {
        Permission.MANAGE_USERS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.READ_ALL_DATA,
        Permission.WRITE_ALL_DATA,
        Permission.EXPORT_DATA,
        Permission.MANAGE_CALLS,
        Permission.VIEW_CALLS,
        Permission.INITIATE_CALLS,
        Permission.MANAGE_LEADS,
        Permission.VIEW_LEADS,
        Permission.QUALIFY_LEADS,
        Permission.MANAGE_CAMPAIGNS,
        Permission.VIEW_CAMPAIGNS,
        Permission.API_READ,
        Permission.API_WRITE,
        Permission.APPROVE_HIGH_VALUE,
        Permission.APPROVE_CAMPAIGNS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PERFORMANCE,
    },
    Role.MANAGER: {
        Permission.READ_ALL_DATA,
        Permission.VIEW_CALLS,
        Permission.INITIATE_CALLS,
        Permission.MANAGE_LEADS,
        Permission.VIEW_LEADS,
        Permission.QUALIFY_LEADS,
        Permission.VIEW_CAMPAIGNS,
        Permission.API_READ,
        Permission.APPROVE_HIGH_VALUE,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PERFORMANCE,
    },
    Role.AGENT: {
        Permission.VIEW_CALLS,
        Permission.INITIATE_CALLS,
        Permission.VIEW_LEADS,
        Permission.QUALIFY_LEADS,
        Permission.API_READ,
    },
    Role.VIEWER: {
        Permission.VIEW_CALLS,
        Permission.VIEW_LEADS,
        Permission.VIEW_CAMPAIGNS,
        Permission.VIEW_ANALYTICS,
    },
    Role.API_USER: {
        Permission.API_READ,
        Permission.API_WRITE,
    },
}


class AccessControlManager:
    """Manages user authentication, authorization, and sessions."""
    
    def __init__(self, secret_key: str, jwt_algorithm: str = "HS256"):
        """
        Initialize access control manager.
        
        Args:
            secret_key: Secret key for JWT signing
            jwt_algorithm: JWT algorithm to use
        """
        self.secret_key = secret_key
        self.jwt_algorithm = jwt_algorithm
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.failed_login_tracking: Dict[str, List[datetime]] = {}
        
        # Security settings
        self.max_failed_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.password_min_length = 12
        self.password_complexity_required = True
        self.session_timeout = 3600  # 1 hour
        self.jwt_expiry = 3600  # 1 hour
        self.api_key_expiry = timedelta(days=90)
        
        # Rate limiting
        self.rate_limits: Dict[str, List[datetime]] = {}
        self.rate_limit_window = 60  # 1 minute
        self.rate_limit_max_requests = 100
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """
        Validate password strength.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if len(password) < self.password_min_length:
            issues.append(f"Password must be at least {self.password_min_length} characters long")
        
        if self.password_complexity_required:
            if not any(c.isupper() for c in password):
                issues.append("Password must contain at least one uppercase letter")
            
            if not any(c.islower() for c in password):
                issues.append("Password must contain at least one lowercase letter")
            
            if not any(c.isdigit() for c in password):
                issues.append("Password must contain at least one digit")
            
            if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                issues.append("Password must contain at least one special character")
        
        # Check for common weak passwords
        weak_passwords = {
            "password123", "admin123", "123456789", "qwerty123",
            "password1", "admin1234", "welcome123"
        }
        if password.lower() in weak_passwords:
            issues.append("Password is too common and easily guessable")
        
        return len(issues) == 0, issues
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: Optional[Set[Role]] = None,
        **kwargs
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Create a new user account.
        
        Returns:
            Tuple of (success, message, user_object)
        """
        # Validate inputs
        if not username or not email or not password:
            return False, "Username, email, and password are required", None
        
        if username in self.users:
            return False, "Username already exists", None
        
        if any(user.email == email for user in self.users.values()):
            return False, "Email already exists", None
        
        # Validate password strength
        is_valid, issues = self.validate_password_strength(password)
        if not is_valid:
            return False, "; ".join(issues), None
        
        # Create user
        user_id = self._generate_user_id()
        password_hash = self.hash_password(password)
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            roles=roles or {Role.VIEWER},
            password_expires_at=datetime.utcnow() + timedelta(days=90),
            **kwargs
        )
        
        self.users[username] = user
        logger.info(f"User created: {username} ({email})")
        
        return True, "User created successfully", user
    
    def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Authenticate user credentials.
        
        Returns:
            Tuple of (success, message, user_object)
        """
        # Check rate limiting
        if not self._check_rate_limit(ip_address or "unknown"):
            return False, "Too many requests, please try again later", None
        
        # Get user
        user = self.users.get(username)
        if not user:
            self._record_failed_login(username, ip_address)
            return False, "Invalid credentials", None
        
        # Check if user is active
        if not user.is_active:
            return False, "Account is disabled", None
        
        # Check if user is locked
        if user.is_locked:
            return False, "Account is locked due to too many failed attempts", None
        
        # Check IP restrictions
        if user.allowed_ips and ip_address not in user.allowed_ips:
            logger.warning(f"Login attempt from unauthorized IP: {ip_address} for user {username}")
            return False, "Access denied from this IP address", None
        
        # Verify password
        if not self.verify_password(password, user.password_hash):
            self._record_failed_login(username, ip_address)
            user.failed_login_attempts += 1
            
            if user.failed_login_attempts >= self.max_failed_attempts:
                user.is_locked = True
                logger.warning(f"User account locked due to failed attempts: {username}")
                return False, "Account locked due to too many failed attempts", None
            
            return False, "Invalid credentials", None
        
        # Check password expiry
        if user.is_password_expired():
            return False, "Password has expired, please reset", None
        
        # Successful authentication
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self._clear_failed_login_tracking(username)
        
        logger.info(f"User authenticated successfully: {username}")
        return True, "Authentication successful", user
    
    def create_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """Create a new user session."""
        session_id = self._generate_session_id()
        expires_at = datetime.utcnow() + timedelta(seconds=user.session_timeout)
        
        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        
        self.sessions[session_id] = session
        logger.info(f"Session created for user: {user.username}")
        
        return session
    
    def validate_session(self, session_id: str) -> Tuple[bool, Optional[Session], Optional[User]]:
        """
        Validate user session.
        
        Returns:
            Tuple of (is_valid, session, user)
        """
        session = self.sessions.get(session_id)
        if not session:
            return False, None, None
        
        if not session.is_active or session.is_expired():
            self.invalidate_session(session_id)
            return False, None, None
        
        # Get user
        user = next((u for u in self.users.values() if u.user_id == session.user_id), None)
        if not user or not user.is_active:
            self.invalidate_session(session_id)
            return False, None, None
        
        # Update session activity
        session.update_activity()
        
        return True, session, user
    
    def invalidate_session(self, session_id: str):
        """Invalidate a user session."""
        if session_id in self.sessions:
            self.sessions[session_id].is_active = False
            del self.sessions[session_id]
            logger.info(f"Session invalidated: {session_id}")
    
    def create_jwt_token(self, user: User, session: Session) -> str:
        """Create JWT token for user."""
        payload = {
            'user_id': user.user_id,
            'username': user.username,
            'session_id': session.session_id,
            'roles': [role.value for role in user.roles],
            'iat': int(time.time()),
            'exp': int(time.time()) + self.jwt_expiry
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.jwt_algorithm)
    
    def validate_jwt_token(self, token: str) -> Tuple[bool, Optional[Dict], Optional[User]]:
        """
        Validate JWT token.
        
        Returns:
            Tuple of (is_valid, payload, user)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.jwt_algorithm])
            
            # Get user
            user = next((u for u in self.users.values() if u.user_id == payload['user_id']), None)
            if not user or not user.is_active:
                return False, None, None
            
            # Validate session if present
            session_id = payload.get('session_id')
            if session_id:
                is_valid, session, _ = self.validate_session(session_id)
                if not is_valid:
                    return False, None, None
            
            return True, payload, user
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return False, None, None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return False, None, None
    
    def generate_api_key(self, user: User) -> str:
        """Generate API key for user."""
        api_key = f"ak_{secrets.token_urlsafe(32)}"
        user.api_key = api_key
        user.api_key_expires_at = datetime.utcnow() + self.api_key_expiry
        
        logger.info(f"API key generated for user: {user.username}")
        return api_key
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[User]]:
        """
        Validate API key.
        
        Returns:
            Tuple of (is_valid, user)
        """
        user = next((u for u in self.users.values() if u.api_key == api_key), None)
        if not user:
            return False, None
        
        if not user.is_active or user.is_api_key_expired():
            return False, None
        
        return True, user
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has specific permission."""
        return user.has_permission(permission)
    
    def require_permission(self, user: User, permission: Permission) -> bool:
        """Require user to have specific permission, raise exception if not."""
        if not self.check_permission(user, permission):
            raise PermissionError(f"User {user.username} lacks required permission: {permission.value}")
        return True
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if session.is_expired() or not session.is_active
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def _generate_user_id(self) -> str:
        """Generate unique user ID."""
        return f"user_{secrets.token_hex(8)}"
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"sess_{secrets.token_urlsafe(32)}"
    
    def _record_failed_login(self, username: str, ip_address: Optional[str]):
        """Record failed login attempt."""
        now = datetime.utcnow()
        
        # Track by username
        if username not in self.failed_login_tracking:
            self.failed_login_tracking[username] = []
        self.failed_login_tracking[username].append(now)
        
        # Track by IP if available
        if ip_address:
            if ip_address not in self.failed_login_tracking:
                self.failed_login_tracking[ip_address] = []
            self.failed_login_tracking[ip_address].append(now)
        
        logger.warning(f"Failed login attempt: {username} from {ip_address}")
    
    def _clear_failed_login_tracking(self, username: str):
        """Clear failed login tracking for user."""
        self.failed_login_tracking.pop(username, None)
    
    def _check_rate_limit(self, identifier: str) -> bool:
        """Check if identifier is within rate limits."""
        now = datetime.utcnow()
        
        if identifier not in self.rate_limits:
            self.rate_limits[identifier] = []
        
        # Remove old entries
        cutoff = now - timedelta(seconds=self.rate_limit_window)
        self.rate_limits[identifier] = [
            timestamp for timestamp in self.rate_limits[identifier]
            if timestamp > cutoff
        ]
        
        # Check limit
        if len(self.rate_limits[identifier]) >= self.rate_limit_max_requests:
            return False
        
        # Record this request
        self.rate_limits[identifier].append(now)
        return True
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information (safe for API responses)."""
        user = self.users.get(username)
        if not user:
            return None
        
        return {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'roles': [role.value for role in user.roles],
            'is_active': user.is_active,
            'is_locked': user.is_locked,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat(),
            'mfa_enabled': user.mfa_enabled,
            'api_key_expires_at': user.api_key_expires_at.isoformat() if user.api_key_expires_at else None
        }
    
    def list_active_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active sessions, optionally filtered by user."""
        sessions = []
        
        for session in self.sessions.values():
            if not session.is_active or session.is_expired():
                continue
            
            if user_id and session.user_id != user_id:
                continue
            
            sessions.append({
                'session_id': session.session_id,
                'user_id': session.user_id,
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'ip_address': session.ip_address,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None
            })
        
        return sessions


# Global access control manager instance
_access_control_manager = None


def get_access_control_manager() -> AccessControlManager:
    """Get the global access control manager instance."""
    global _access_control_manager
    if _access_control_manager is None:
        from app.core.config import get_settings
        settings = get_settings()
        _access_control_manager = AccessControlManager(settings.SECRET_KEY)
    return _access_control_manager


def require_permission(permission: Permission):
    """Decorator to require specific permission for endpoint access."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be implemented with FastAPI dependency injection
            # For now, it's a placeholder for the decorator pattern
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """Decorator to require specific role for endpoint access."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be implemented with FastAPI dependency injection
            # For now, it's a placeholder for the decorator pattern
            return func(*args, **kwargs)
        return wrapper
    return decorator