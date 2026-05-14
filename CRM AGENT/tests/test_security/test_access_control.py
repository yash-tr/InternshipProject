"""
Tests for access control functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import jwt
import bcrypt

from app.security.access_control import (
    AccessControlManager,
    User,
    Session,
    Role,
    Permission,
    ROLE_PERMISSIONS,
    get_access_control_manager
)


class TestUser:
    """Test User class functionality."""
    
    def test_user_creation(self):
        """Test user creation with default values."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        assert user.user_id == "test_user_1"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_locked is False
        assert user.failed_login_attempts == 0
        assert user.mfa_enabled is False
        assert len(user.roles) == 0
    
    def test_user_has_role(self):
        """Test role checking."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            roles={Role.ADMIN, Role.MANAGER}
        )
        
        assert user.has_role(Role.ADMIN) is True
        assert user.has_role(Role.MANAGER) is True
        assert user.has_role(Role.VIEWER) is False
    
    def test_user_has_permission(self):
        """Test permission checking through roles."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            roles={Role.ADMIN}
        )
        
        # Admin should have user management permission
        assert user.has_permission(Permission.MANAGE_USERS) is True
        assert user.has_permission(Permission.VIEW_CALLS) is True
        
        # Admin should not have super admin only permissions
        assert user.has_permission(Permission.MANAGE_SYSTEM) is False
    
    def test_user_add_remove_role(self):
        """Test adding and removing roles."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Add role
        user.add_role(Role.VIEWER)
        assert user.has_role(Role.VIEWER) is True
        
        # Remove role
        user.remove_role(Role.VIEWER)
        assert user.has_role(Role.VIEWER) is False
    
    def test_password_expiry(self):
        """Test password expiry checking."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # No expiry set
        assert user.is_password_expired() is False
        
        # Future expiry
        user.password_expires_at = datetime.utcnow() + timedelta(days=30)
        assert user.is_password_expired() is False
        
        # Past expiry
        user.password_expires_at = datetime.utcnow() - timedelta(days=1)
        assert user.is_password_expired() is True
    
    def test_api_key_expiry(self):
        """Test API key expiry checking."""
        user = User(
            user_id="test_user_1",
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # No API key
        assert user.is_api_key_expired() is False
        
        # Future expiry
        user.api_key = "test_key"
        user.api_key_expires_at = datetime.utcnow() + timedelta(days=30)
        assert user.is_api_key_expired() is False
        
        # Past expiry
        user.api_key_expires_at = datetime.utcnow() - timedelta(days=1)
        assert user.is_api_key_expired() is True


class TestSession:
    """Test Session class functionality."""
    
    def test_session_creation(self):
        """Test session creation."""
        session = Session(
            session_id="test_session_1",
            user_id="test_user_1"
        )
        
        assert session.session_id == "test_session_1"
        assert session.user_id == "test_user_1"
        assert session.is_active is True
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
    
    def test_session_expiry(self):
        """Test session expiry checking."""
        session = Session(
            session_id="test_session_1",
            user_id="test_user_1"
        )
        
        # No expiry set
        assert session.is_expired() is False
        
        # Future expiry
        session.expires_at = datetime.utcnow() + timedelta(hours=1)
        assert session.is_expired() is False
        
        # Past expiry
        session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        assert session.is_expired() is True
    
    def test_session_update_activity(self):
        """Test session activity update."""
        session = Session(
            session_id="test_session_1",
            user_id="test_user_1"
        )
        
        original_activity = session.last_activity
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        session.update_activity()
        
        assert session.last_activity > original_activity


class TestAccessControlManager:
    """Test AccessControlManager functionality."""
    
    def test_init(self):
        """Test access control manager initialization."""
        manager = AccessControlManager("test_secret_key")
        
        assert manager.secret_key == "test_secret_key"
        assert manager.jwt_algorithm == "HS256"
        assert isinstance(manager.users, dict)
        assert isinstance(manager.sessions, dict)
    
    def test_hash_password(self):
        """Test password hashing."""
        manager = AccessControlManager("test_secret_key")
        
        password = "test_password_123"
        hashed = manager.hash_password(password)
        
        assert hashed != password
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_verify_password(self):
        """Test password verification."""
        manager = AccessControlManager("test_secret_key")
        
        password = "test_password_123"
        hashed = manager.hash_password(password)
        
        # Correct password
        assert manager.verify_password(password, hashed) is True
        
        # Incorrect password
        assert manager.verify_password("wrong_password", hashed) is False
    
    def test_validate_password_strength(self):
        """Test password strength validation."""
        manager = AccessControlManager("test_secret_key")
        
        # Strong password
        is_valid, issues = manager.validate_password_strength("StrongPassword123!")
        assert is_valid is True
        assert len(issues) == 0
        
        # Weak password - too short
        is_valid, issues = manager.validate_password_strength("weak")
        assert is_valid is False
        assert any("at least" in issue for issue in issues)
        
        # Weak password - no uppercase
        is_valid, issues = manager.validate_password_strength("weakpassword123!")
        assert is_valid is False
        assert any("uppercase" in issue for issue in issues)
        
        # Common weak password
        is_valid, issues = manager.validate_password_strength("password123")
        assert is_valid is False
        assert any("common" in issue for issue in issues)
    
    def test_create_user_success(self):
        """Test successful user creation."""
        manager = AccessControlManager("test_secret_key")
        
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            roles={Role.VIEWER}
        )
        
        assert success is True
        assert "successfully" in message
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.has_role(Role.VIEWER) is True
        assert "testuser" in manager.users
    
    def test_create_user_duplicate_username(self):
        """Test user creation with duplicate username."""
        manager = AccessControlManager("test_secret_key")
        
        # Create first user
        manager.create_user(
            username="testuser",
            email="test1@example.com",
            password="StrongPassword123!"
        )
        
        # Try to create user with same username
        success, message, user = manager.create_user(
            username="testuser",
            email="test2@example.com",
            password="StrongPassword123!"
        )
        
        assert success is False
        assert "already exists" in message
        assert user is None
    
    def test_create_user_weak_password(self):
        """Test user creation with weak password."""
        manager = AccessControlManager("test_secret_key")
        
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="weak"
        )
        
        assert success is False
        assert "at least" in message
        assert user is None
    
    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Authenticate
        success, message, user = manager.authenticate_user(
            username="testuser",
            password="StrongPassword123!",
            ip_address="192.168.1.1"
        )
        
        assert success is True
        assert "successful" in message
        assert user is not None
        assert user.username == "testuser"
        assert user.failed_login_attempts == 0
        assert user.last_login is not None
    
    def test_authenticate_user_invalid_credentials(self):
        """Test authentication with invalid credentials."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Wrong password
        success, message, user = manager.authenticate_user(
            username="testuser",
            password="WrongPassword123!"
        )
        
        assert success is False
        assert "Invalid credentials" in message
        assert user is None
        
        # Check failed attempt was recorded
        stored_user = manager.users["testuser"]
        assert stored_user.failed_login_attempts == 1
    
    def test_authenticate_user_account_lockout(self):
        """Test account lockout after failed attempts."""
        manager = AccessControlManager("test_secret_key")
        manager.max_failed_attempts = 3
        
        # Create user
        manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Make failed attempts
        for _ in range(3):
            manager.authenticate_user(
                username="testuser",
                password="WrongPassword123!"
            )
        
        # Check user is locked
        user = manager.users["testuser"]
        assert user.is_locked is True
        
        # Try to authenticate with correct password
        success, message, user = manager.authenticate_user(
            username="testuser",
            password="StrongPassword123!"
        )
        
        assert success is False
        assert "locked" in message
    
    def test_authenticate_user_inactive(self):
        """Test authentication with inactive user."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Deactivate user
        user.is_active = False
        
        # Try to authenticate
        success, message, auth_user = manager.authenticate_user(
            username="testuser",
            password="StrongPassword123!"
        )
        
        assert success is False
        assert "disabled" in message
    
    def test_create_session(self):
        """Test session creation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Create session
        session = manager.create_session(
            user=user,
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        
        assert session.user_id == user.user_id
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Test Browser"
        assert session.expires_at is not None
        assert session.session_id in manager.sessions
    
    def test_validate_session(self):
        """Test session validation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and session
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        session = manager.create_session(user)
        
        # Validate session
        is_valid, validated_session, validated_user = manager.validate_session(session.session_id)
        
        assert is_valid is True
        assert validated_session.session_id == session.session_id
        assert validated_user.user_id == user.user_id
    
    def test_validate_session_expired(self):
        """Test validation of expired session."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and session
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        session = manager.create_session(user)
        
        # Expire session
        session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Validate session
        is_valid, validated_session, validated_user = manager.validate_session(session.session_id)
        
        assert is_valid is False
        assert validated_session is None
        assert validated_user is None
        assert session.session_id not in manager.sessions
    
    def test_invalidate_session(self):
        """Test session invalidation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and session
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        session = manager.create_session(user)
        
        # Invalidate session
        manager.invalidate_session(session.session_id)
        
        assert session.session_id not in manager.sessions
    
    def test_create_jwt_token(self):
        """Test JWT token creation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and session
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            roles={Role.ADMIN}
        )
        session = manager.create_session(user)
        
        # Create JWT token
        token = manager.create_jwt_token(user, session)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode token to verify contents
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        assert payload["user_id"] == user.user_id
        assert payload["username"] == user.username
        assert payload["session_id"] == session.session_id
        assert Role.ADMIN.value in payload["roles"]
    
    def test_validate_jwt_token(self):
        """Test JWT token validation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and session
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        session = manager.create_session(user)
        
        # Create and validate token
        token = manager.create_jwt_token(user, session)
        is_valid, payload, validated_user = manager.validate_jwt_token(token)
        
        assert is_valid is True
        assert payload["user_id"] == user.user_id
        assert validated_user.user_id == user.user_id
    
    def test_validate_jwt_token_invalid(self):
        """Test validation of invalid JWT token."""
        manager = AccessControlManager("test_secret_key")
        
        # Invalid token
        is_valid, payload, user = manager.validate_jwt_token("invalid_token")
        
        assert is_valid is False
        assert payload is None
        assert user is None
    
    def test_generate_api_key(self):
        """Test API key generation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        # Generate API key
        api_key = manager.generate_api_key(user)
        
        assert api_key.startswith("ak_")
        assert len(api_key) > 10
        assert user.api_key == api_key
        assert user.api_key_expires_at is not None
    
    def test_validate_api_key(self):
        """Test API key validation."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and API key
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        api_key = manager.generate_api_key(user)
        
        # Validate API key
        is_valid, validated_user = manager.validate_api_key(api_key)
        
        assert is_valid is True
        assert validated_user.user_id == user.user_id
    
    def test_validate_api_key_invalid(self):
        """Test validation of invalid API key."""
        manager = AccessControlManager("test_secret_key")
        
        # Invalid API key
        is_valid, user = manager.validate_api_key("invalid_api_key")
        
        assert is_valid is False
        assert user is None
    
    def test_check_permission(self):
        """Test permission checking."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user with admin role
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            roles={Role.ADMIN}
        )
        
        # Check permissions
        assert manager.check_permission(user, Permission.MANAGE_USERS) is True
        assert manager.check_permission(user, Permission.MANAGE_SYSTEM) is False
    
    def test_require_permission(self):
        """Test permission requirement."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user with admin role
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            roles={Role.ADMIN}
        )
        
        # Should pass for allowed permission
        assert manager.require_permission(user, Permission.MANAGE_USERS) is True
        
        # Should raise exception for disallowed permission
        with pytest.raises(PermissionError):
            manager.require_permission(user, Permission.MANAGE_SYSTEM)
    
    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user and sessions
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!"
        )
        
        session1 = manager.create_session(user)
        session2 = manager.create_session(user)
        
        # Expire one session
        session1.expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Cleanup
        manager.cleanup_expired_sessions()
        
        # Check results
        assert session1.session_id not in manager.sessions
        assert session2.session_id in manager.sessions
    
    def test_get_user_info(self):
        """Test getting user information."""
        manager = AccessControlManager("test_secret_key")
        
        # Create user
        success, message, user = manager.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            roles={Role.ADMIN}
        )
        
        # Get user info
        info = manager.get_user_info("testuser")
        
        assert info is not None
        assert info["username"] == "testuser"
        assert info["email"] == "test@example.com"
        assert Role.ADMIN.value in info["roles"]
        assert info["is_active"] is True
        assert "password_hash" not in info  # Should not expose sensitive data
    
    def test_list_active_sessions(self):
        """Test listing active sessions."""
        manager = AccessControlManager("test_secret_key")
        
        # Create users and sessions
        success, message, user1 = manager.create_user(
            username="user1",
            email="user1@example.com",
            password="StrongPassword123!"
        )
        success, message, user2 = manager.create_user(
            username="user2",
            email="user2@example.com",
            password="StrongPassword123!"
        )
        
        session1 = manager.create_session(user1)
        session2 = manager.create_session(user2)
        
        # List all sessions
        all_sessions = manager.list_active_sessions()
        assert len(all_sessions) == 2
        
        # List sessions for specific user
        user1_sessions = manager.list_active_sessions(user1.user_id)
        assert len(user1_sessions) == 1
        assert user1_sessions[0]["user_id"] == user1.user_id


class TestRolePermissions:
    """Test role-permission mappings."""
    
    def test_role_permissions_defined(self):
        """Test that all roles have permissions defined."""
        for role in Role:
            assert role in ROLE_PERMISSIONS
            assert isinstance(ROLE_PERMISSIONS[role], set)
    
    def test_super_admin_has_all_permissions(self):
        """Test that super admin has all permissions."""
        super_admin_perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        
        # Should have all permissions
        for permission in Permission:
            assert permission in super_admin_perms
    
    def test_role_hierarchy(self):
        """Test role hierarchy - higher roles should have more permissions."""
        super_admin_perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        manager_perms = ROLE_PERMISSIONS[Role.MANAGER]
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        
        # Super admin should have more permissions than admin
        assert len(super_admin_perms) > len(admin_perms)
        
        # Admin should have more permissions than manager
        assert len(admin_perms) > len(manager_perms)
        
        # Manager should have more permissions than viewer
        assert len(manager_perms) > len(viewer_perms)
    
    def test_viewer_permissions_minimal(self):
        """Test that viewer has minimal permissions."""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        
        # Should only have view permissions
        assert Permission.VIEW_CALLS in viewer_perms
        assert Permission.VIEW_LEADS in viewer_perms
        assert Permission.VIEW_CAMPAIGNS in viewer_perms
        
        # Should not have management permissions
        assert Permission.MANAGE_USERS not in viewer_perms
        assert Permission.MANAGE_SYSTEM not in viewer_perms
        assert Permission.DELETE_DATA not in viewer_perms


@pytest.fixture
def access_control_manager():
    """Access control manager fixture."""
    return AccessControlManager("test_secret_key_123")


@pytest.fixture
def test_user(access_control_manager):
    """Test user fixture."""
    success, message, user = access_control_manager.create_user(
        username="testuser",
        email="test@example.com",
        password="StrongPassword123!",
        roles={Role.ADMIN}
    )
    return user