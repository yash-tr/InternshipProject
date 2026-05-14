"""
Tests for authentication middleware and dependencies.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.security.authentication import (
    AuthenticationError,
    AuthorizationError,
    get_current_user_from_token,
    get_current_user_from_api_key,
    get_current_user,
    require_permission,
    require_role,
    require_any_role,
    get_optional_user,
    IPWhitelistChecker,
    RateLimiter,
    create_default_admin_user,
    get_user_context
)
from app.security.access_control import (
    AccessControlManager,
    User,
    Role,
    Permission
)


class TestAuthenticationErrors:
    """Test custom authentication exceptions."""
    
    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Test auth error")
        
        assert error.status_code == 401
        assert error.detail == "Test auth error"
        assert "WWW-Authenticate" in error.headers
    
    def test_authorization_error(self):
        """Test AuthorizationError creation."""
        error = AuthorizationError("Test auth error")
        
        assert error.status_code == 403
        assert error.detail == "Test auth error"


class TestGetCurrentUserFromToken:
    """Test JWT token authentication."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_token_success(self):
        """Test successful token authentication."""
        # Mock request
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        
        # Mock credentials
        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "valid_jwt_token"
        
        # Mock access control manager
        access_control = Mock(spec=AccessControlManager)
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        
        access_control.validate_jwt_token.return_value = (True, {"user_id": "user_123"}, test_user)
        
        # Test
        user = await get_current_user_from_token(request, credentials, access_control)
        
        assert user == test_user
        access_control.validate_jwt_token.assert_called_once_with("valid_jwt_token")
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_token_missing_credentials(self):
        """Test token authentication with missing credentials."""
        request = Mock(spec=Request)
        
        with pytest.raises(AuthenticationError, match="Missing authentication token"):
            await get_current_user_from_token(request, None, Mock())
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_token_invalid_token(self):
        """Test token authentication with invalid token."""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        
        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "invalid_jwt_token"
        
        access_control = Mock(spec=AccessControlManager)
        access_control.validate_jwt_token.return_value = (False, None, None)
        
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            await get_current_user_from_token(request, credentials, access_control)


class TestGetCurrentUserFromApiKey:
    """Test API key authentication."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_success(self):
        """Test successful API key authentication."""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        
        api_key = "valid_api_key"
        
        access_control = Mock(spec=AccessControlManager)
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        
        access_control.validate_api_key.return_value = (True, test_user)
        
        user = await get_current_user_from_api_key(request, api_key, access_control)
        
        assert user == test_user
        access_control.validate_api_key.assert_called_once_with("valid_api_key")
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_missing_key(self):
        """Test API key authentication with missing key."""
        request = Mock(spec=Request)
        
        with pytest.raises(AuthenticationError, match="Missing API key"):
            await get_current_user_from_api_key(request, None, Mock())
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_invalid_key(self):
        """Test API key authentication with invalid key."""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        
        access_control = Mock(spec=AccessControlManager)
        access_control.validate_api_key.return_value = (False, None)
        
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await get_current_user_from_api_key(request, "invalid_key", access_control)


class TestGetCurrentUser:
    """Test combined authentication."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_token_auth(self):
        """Test authentication via token."""
        request = Mock(spec=Request)
        test_user = Mock(spec=User)
        
        user = await get_current_user(request, test_user, None)
        
        assert user == test_user
    
    @pytest.mark.asyncio
    async def test_get_current_user_api_key_auth(self):
        """Test authentication via API key."""
        request = Mock(spec=Request)
        test_user = Mock(spec=User)
        
        user = await get_current_user(request, None, test_user)
        
        assert user == test_user
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_auth(self):
        """Test authentication with no valid method."""
        request = Mock(spec=Request)
        
        with pytest.raises(AuthenticationError, match="Authentication required"):
            await get_current_user(request, None, None)


class TestRequirePermission:
    """Test permission requirement decorator."""
    
    @pytest.mark.asyncio
    async def test_require_permission_success(self):
        """Test successful permission check."""
        test_user = Mock(spec=User)
        access_control = Mock(spec=AccessControlManager)
        access_control.check_permission.return_value = True
        
        permission_dep = require_permission(Permission.MANAGE_USERS)
        user = await permission_dep(test_user, access_control)
        
        assert user == test_user
        access_control.check_permission.assert_called_once_with(test_user, Permission.MANAGE_USERS)
    
    @pytest.mark.asyncio
    async def test_require_permission_denied(self):
        """Test permission denied."""
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        
        access_control = Mock(spec=AccessControlManager)
        access_control.check_permission.return_value = False
        
        permission_dep = require_permission(Permission.MANAGE_USERS)
        
        with pytest.raises(AuthorizationError, match="Permission required"):
            await permission_dep(test_user, access_control)


class TestRequireRole:
    """Test role requirement decorator."""
    
    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test successful role check."""
        test_user = Mock(spec=User)
        test_user.has_role.return_value = True
        
        role_dep = require_role(Role.ADMIN)
        user = await role_dep(test_user)
        
        assert user == test_user
        test_user.has_role.assert_called_once_with(Role.ADMIN)
    
    @pytest.mark.asyncio
    async def test_require_role_denied(self):
        """Test role requirement denied."""
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        test_user.roles = [Role.VIEWER]
        test_user.has_role.return_value = False
        
        role_dep = require_role(Role.ADMIN)
        
        with pytest.raises(AuthorizationError, match="Role required"):
            await role_dep(test_user)


class TestRequireAnyRole:
    """Test any role requirement decorator."""
    
    @pytest.mark.asyncio
    async def test_require_any_role_success(self):
        """Test successful any role check."""
        test_user = Mock(spec=User)
        test_user.has_role.side_effect = lambda role: role == Role.MANAGER
        
        any_role_dep = require_any_role(Role.ADMIN, Role.MANAGER)
        user = await any_role_dep(test_user)
        
        assert user == test_user
    
    @pytest.mark.asyncio
    async def test_require_any_role_denied(self):
        """Test any role requirement denied."""
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        test_user.roles = [Role.VIEWER]
        test_user.has_role.return_value = False
        
        any_role_dep = require_any_role(Role.ADMIN, Role.MANAGER)
        
        with pytest.raises(AuthorizationError, match="One of these roles required"):
            await any_role_dep(test_user)


class TestGetOptionalUser:
    """Test optional user authentication."""
    
    @pytest.mark.asyncio
    async def test_get_optional_user_with_token(self):
        """Test optional authentication with valid token."""
        request = Mock(spec=Request)
        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "valid_token"
        
        access_control = Mock(spec=AccessControlManager)
        test_user = Mock(spec=User)
        access_control.validate_jwt_token.return_value = (True, {}, test_user)
        
        user = await get_optional_user(request, credentials, None, access_control)
        
        assert user == test_user
    
    @pytest.mark.asyncio
    async def test_get_optional_user_with_api_key(self):
        """Test optional authentication with valid API key."""
        request = Mock(spec=Request)
        api_key = "valid_api_key"
        
        access_control = Mock(spec=AccessControlManager)
        test_user = Mock(spec=User)
        access_control.validate_jwt_token.return_value = (False, None, None)
        access_control.validate_api_key.return_value = (True, test_user)
        
        user = await get_optional_user(request, None, api_key, access_control)
        
        assert user == test_user
    
    @pytest.mark.asyncio
    async def test_get_optional_user_no_auth(self):
        """Test optional authentication with no credentials."""
        request = Mock(spec=Request)
        access_control = Mock(spec=AccessControlManager)
        
        user = await get_optional_user(request, None, None, access_control)
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_auth(self):
        """Test optional authentication with invalid credentials."""
        request = Mock(spec=Request)
        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "invalid_token"
        
        access_control = Mock(spec=AccessControlManager)
        access_control.validate_jwt_token.side_effect = Exception("Invalid token")
        
        user = await get_optional_user(request, credentials, None, access_control)
        
        assert user is None


class TestIPWhitelistChecker:
    """Test IP whitelist functionality."""
    
    def test_ip_whitelist_no_restrictions(self):
        """Test IP whitelist with no restrictions."""
        checker = IPWhitelistChecker()
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        ip = checker(request)
        assert ip == "192.168.1.1"
    
    def test_ip_whitelist_allowed_ip(self):
        """Test IP whitelist with allowed IP."""
        checker = IPWhitelistChecker(["192.168.1.1", "10.0.0.1"])
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        ip = checker(request)
        assert ip == "192.168.1.1"
    
    def test_ip_whitelist_denied_ip(self):
        """Test IP whitelist with denied IP."""
        checker = IPWhitelistChecker(["192.168.1.1"])
        request = Mock(spec=Request)
        request.client.host = "10.0.0.1"
        request.headers = {}
        
        with pytest.raises(HTTPException) as exc_info:
            checker(request)
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
    
    def test_ip_whitelist_forwarded_header(self):
        """Test IP extraction from forwarded headers."""
        checker = IPWhitelistChecker(["203.0.113.1"])
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"  # Internal proxy IP
        request.headers = {"X-Forwarded-For": "203.0.113.1, 192.168.1.1"}
        
        ip = checker(request)
        assert ip == "203.0.113.1"
    
    def test_ip_whitelist_real_ip_header(self):
        """Test IP extraction from X-Real-IP header."""
        checker = IPWhitelistChecker(["203.0.113.1"])
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {"X-Real-IP": "203.0.113.1"}
        
        ip = checker(request)
        assert ip == "203.0.113.1"
    
    @patch.dict('os.environ', {'ALLOWED_IPS': '192.168.1.1,10.0.0.1'})
    def test_ip_whitelist_from_environment(self):
        """Test IP whitelist loading from environment."""
        checker = IPWhitelistChecker()
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        ip = checker(request)
        assert ip == "192.168.1.1"


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_within_limits(self):
        """Test rate limiter within limits."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        # Should allow requests within limit
        for _ in range(5):
            result = limiter(request)
            assert result is True
    
    def test_rate_limiter_exceeded(self):
        """Test rate limiter when exceeded."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        # First two requests should pass
        assert limiter(request) is True
        assert limiter(request) is True
        
        # Third request should fail
        with pytest.raises(HTTPException) as exc_info:
            limiter(request)
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
    
    def test_rate_limiter_different_clients(self):
        """Test rate limiter with different clients."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        request1 = Mock(spec=Request)
        request1.client.host = "192.168.1.1"
        request1.headers = {}
        
        request2 = Mock(spec=Request)
        request2.client.host = "192.168.1.2"
        request2.headers = {}
        
        # Each client should have separate limits
        assert limiter(request1) is True
        assert limiter(request1) is True
        assert limiter(request2) is True
        assert limiter(request2) is True
        
        # Both should be at limit now
        with pytest.raises(HTTPException):
            limiter(request1)
        
        with pytest.raises(HTTPException):
            limiter(request2)


class TestCreateDefaultAdminUser:
    """Test default admin user creation."""
    
    @pytest.mark.asyncio
    @patch('app.security.authentication.get_access_control_manager')
    @patch.dict('os.environ', {'DEFAULT_ADMIN_PASSWORD': 'TestAdminPass123!'})
    async def test_create_default_admin_user_success(self, mock_get_manager):
        """Test successful default admin user creation."""
        mock_manager = Mock(spec=AccessControlManager)
        mock_manager.users = {}  # No existing users
        mock_manager.create_user.return_value = (True, "User created", Mock())
        mock_get_manager.return_value = mock_manager
        
        await create_default_admin_user()
        
        mock_manager.create_user.assert_called_once_with(
            username="admin",
            email="admin@example.com",
            password="TestAdminPass123!",
            roles={Role.SUPER_ADMIN}
        )
    
    @pytest.mark.asyncio
    @patch('app.security.authentication.get_access_control_manager')
    async def test_create_default_admin_user_exists(self, mock_get_manager):
        """Test default admin user creation when admin already exists."""
        mock_admin = Mock(spec=User)
        mock_admin.has_role.return_value = True
        
        mock_manager = Mock(spec=AccessControlManager)
        mock_manager.users = {"admin": mock_admin}
        mock_get_manager.return_value = mock_manager
        
        await create_default_admin_user()
        
        # Should not create user if admin already exists
        mock_manager.create_user.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.security.authentication.get_access_control_manager')
    async def test_create_default_admin_user_failure(self, mock_get_manager):
        """Test default admin user creation failure."""
        mock_manager = Mock(spec=AccessControlManager)
        mock_manager.users = {}
        mock_manager.create_user.return_value = (False, "Creation failed", None)
        mock_get_manager.return_value = mock_manager
        
        # Should not raise exception on failure
        await create_default_admin_user()
        
        mock_manager.create_user.assert_called_once()


class TestGetUserContext:
    """Test user context extraction."""
    
    def test_get_user_context(self):
        """Test user context extraction."""
        test_user = Mock(spec=User)
        test_user.user_id = "user_123"
        test_user.username = "testuser"
        test_user.roles = {Role.ADMIN, Role.MANAGER}
        test_user.is_active = True
        
        context = get_user_context(test_user)
        
        assert context["user_id"] == "user_123"
        assert context["username"] == "testuser"
        assert Role.ADMIN.value in context["roles"]
        assert Role.MANAGER.value in context["roles"]
        assert context["is_active"] is True


@pytest.fixture
def mock_request():
    """Mock FastAPI request fixture."""
    request = Mock(spec=Request)
    request.client.host = "192.168.1.1"
    request.headers = {}
    return request


@pytest.fixture
def mock_user():
    """Mock user fixture."""
    user = Mock(spec=User)
    user.user_id = "user_123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.roles = {Role.ADMIN}
    user.is_active = True
    user.has_role.return_value = True
    return user


@pytest.fixture
def mock_access_control():
    """Mock access control manager fixture."""
    return Mock(spec=AccessControlManager)