"""
Authentication middleware and FastAPI dependencies for secure API access.
"""
import os
from typing import Optional, Tuple, Dict, Any
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import structlog

from .access_control import (
    AccessControlManager,
    get_access_control_manager,
    User,
    Role,
    Permission
)

logger = structlog.get_logger()

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticationError(HTTPException):
    """Custom authentication error."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Custom authorization error."""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


async def get_current_user_from_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_control: AccessControlManager = Depends(get_access_control_manager)
) -> User:
    """
    Get current user from JWT token.
    
    Args:
        request: FastAPI request object
        credentials: Bearer token credentials
        access_control: Access control manager
        
    Returns:
        Authenticated user object
        
    Raises:
        AuthenticationError: If authentication fails
    """
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    # Validate JWT token
    is_valid, payload, user = access_control.validate_jwt_token(credentials.credentials)
    
    if not is_valid or not user:
        logger.warning(
            "Invalid JWT token",
            token_prefix=credentials.credentials[:20] + "..." if len(credentials.credentials) > 20 else credentials.credentials,
            client_ip=request.client.host if request.client else "unknown"
        )
        raise AuthenticationError("Invalid or expired token")
    
    # Log successful authentication
    logger.info(
        "User authenticated via JWT",
        user_id=user.user_id,
        username=user.username,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    return user


async def get_current_user_from_api_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    access_control: AccessControlManager = Depends(get_access_control_manager)
) -> User:
    """
    Get current user from API key.
    
    Args:
        request: FastAPI request object
        api_key: API key from header
        access_control: Access control manager
        
    Returns:
        Authenticated user object
        
    Raises:
        AuthenticationError: If authentication fails
    """
    if not api_key:
        raise AuthenticationError("Missing API key")
    
    # Validate API key
    is_valid, user = access_control.validate_api_key(api_key)
    
    if not is_valid or not user:
        logger.warning(
            "Invalid API key",
            api_key_prefix=api_key[:10] + "..." if len(api_key) > 10 else api_key,
            client_ip=request.client.host if request.client else "unknown"
        )
        raise AuthenticationError("Invalid API key")
    
    # Log successful authentication
    logger.info(
        "User authenticated via API key",
        user_id=user.user_id,
        username=user.username,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    return user


async def get_current_user(
    request: Request,
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_user: Optional[User] = Depends(get_current_user_from_api_key)
) -> User:
    """
    Get current user from either JWT token or API key.
    
    Args:
        request: FastAPI request object
        token_user: User from JWT token (if provided)
        api_key_user: User from API key (if provided)
        
    Returns:
        Authenticated user object
        
    Raises:
        AuthenticationError: If no valid authentication method provided
    """
    # Try JWT token first, then API key
    user = token_user or api_key_user
    
    if not user:
        raise AuthenticationError("Authentication required")
    
    return user


def require_permission(permission: Permission):
    """
    Dependency factory to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(
        current_user: User = Depends(get_current_user),
        access_control: AccessControlManager = Depends(get_access_control_manager)
    ) -> User:
        """Check if current user has required permission."""
        if not access_control.check_permission(current_user, permission):
            logger.warning(
                "Permission denied",
                user_id=current_user.user_id,
                username=current_user.username,
                required_permission=permission.value
            )
            raise AuthorizationError(f"Permission required: {permission.value}")
        
        return current_user
    
    return permission_dependency


def require_role(role: Role):
    """
    Dependency factory to require specific role.
    
    Args:
        role: Required role
        
    Returns:
        FastAPI dependency function
    """
    async def role_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        """Check if current user has required role."""
        if not current_user.has_role(role):
            logger.warning(
                "Role requirement not met",
                user_id=current_user.user_id,
                username=current_user.username,
                required_role=role.value,
                user_roles=[r.value for r in current_user.roles]
            )
            raise AuthorizationError(f"Role required: {role.value}")
        
        return current_user
    
    return role_dependency


def require_any_role(*roles: Role):
    """
    Dependency factory to require any of the specified roles.
    
    Args:
        roles: Any of these roles is acceptable
        
    Returns:
        FastAPI dependency function
    """
    async def any_role_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        """Check if current user has any of the required roles."""
        if not any(current_user.has_role(role) for role in roles):
            logger.warning(
                "Role requirement not met",
                user_id=current_user.user_id,
                username=current_user.username,
                required_roles=[r.value for r in roles],
                user_roles=[r.value for r in current_user.roles]
            )
            raise AuthorizationError(f"One of these roles required: {[r.value for r in roles]}")
        
        return current_user
    
    return any_role_dependency


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    access_control: AccessControlManager = Depends(get_access_control_manager)
) -> Optional[User]:
    """
    Get current user if authentication is provided, but don't require it.
    
    Args:
        request: FastAPI request object
        credentials: Optional bearer token credentials
        api_key: Optional API key
        access_control: Access control manager
        
    Returns:
        User object if authenticated, None otherwise
    """
    try:
        # Try JWT token first
        if credentials:
            is_valid, payload, user = access_control.validate_jwt_token(credentials.credentials)
            if is_valid and user:
                return user
        
        # Try API key
        if api_key:
            is_valid, user = access_control.validate_api_key(api_key)
            if is_valid and user:
                return user
        
        return None
        
    except Exception as e:
        logger.warning(f"Optional authentication failed: {e}")
        return None


class IPWhitelistChecker:
    """Check if request comes from whitelisted IP addresses."""
    
    def __init__(self, allowed_ips: Optional[list] = None):
        """
        Initialize IP whitelist checker.
        
        Args:
            allowed_ips: List of allowed IP addresses/CIDR blocks
        """
        self.allowed_ips = set(allowed_ips or [])
        
        # Add IPs from environment
        env_ips = os.getenv('ALLOWED_IPS', '')
        if env_ips:
            self.allowed_ips.update(ip.strip() for ip in env_ips.split(','))
    
    def __call__(self, request: Request) -> str:
        """
        Check if request IP is whitelisted.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address
            
        Raises:
            HTTPException: If IP is not whitelisted
        """
        # Get client IP (handle proxy headers)
        client_ip = self._get_client_ip(request)
        
        # If no whitelist configured, allow all
        if not self.allowed_ips:
            return client_ip
        
        # Check if IP is whitelisted
        if client_ip not in self.allowed_ips and not self._check_cidr_match(client_ip):
            logger.warning(f"Access denied for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied from this IP address"
            )
        
        return client_ip
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers (proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"
    
    def _check_cidr_match(self, ip: str) -> bool:
        """Check if IP matches any CIDR blocks in whitelist."""
        try:
            import ipaddress
            
            ip_obj = ipaddress.ip_address(ip)
            
            for allowed in self.allowed_ips:
                if '/' in allowed:  # CIDR notation
                    network = ipaddress.ip_network(allowed, strict=False)
                    if ip_obj in network:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"CIDR matching error: {e}")
            return False


class RateLimiter:
    """Rate limiting for API endpoints."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
    
    def __call__(self, request: Request) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if within limits
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if not self._check_rate_limit(client_id):
            logger.warning(f"Rate limit exceeded for: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        return True
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use IP address as identifier
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limits."""
        import time
        
        now = time.time()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests outside the window
        cutoff = now - self.window_seconds
        self.requests[client_id] = [
            timestamp for timestamp in self.requests[client_id]
            if timestamp > cutoff
        ]
        
        # Check if within limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[client_id].append(now)
        return True


# Common dependency instances
ip_whitelist = IPWhitelistChecker()
rate_limiter = RateLimiter()

# Admin-only dependencies
require_admin = require_any_role(Role.ADMIN, Role.SUPER_ADMIN)
require_manager = require_any_role(Role.MANAGER, Role.ADMIN, Role.SUPER_ADMIN)

# Permission-based dependencies
require_user_management = require_permission(Permission.MANAGE_USERS)
require_system_management = require_permission(Permission.MANAGE_SYSTEM)
require_data_export = require_permission(Permission.EXPORT_DATA)
require_audit_access = require_permission(Permission.VIEW_AUDIT_LOGS)


async def create_default_admin_user():
    """Create default admin user if none exists."""
    access_control = get_access_control_manager()
    
    # Check if any admin users exist
    admin_exists = any(
        user.has_role(Role.ADMIN) or user.has_role(Role.SUPER_ADMIN)
        for user in access_control.users.values()
    )
    
    if not admin_exists:
        # Create default admin user
        default_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'AdminPassword123!')
        
        success, message, user = access_control.create_user(
            username="admin",
            email="admin@example.com",
            password=default_password,
            roles={Role.SUPER_ADMIN}
        )
        
        if success:
            logger.info("Default admin user created")
        else:
            logger.error(f"Failed to create default admin user: {message}")


def get_user_context(user: User) -> Dict[str, Any]:
    """
    Get user context for logging and audit purposes.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with user context information
    """
    return {
        'user_id': user.user_id,
        'username': user.username,
        'roles': [role.value for role in user.roles],
        'is_active': user.is_active
    }