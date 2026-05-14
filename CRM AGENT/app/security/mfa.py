"""
Multi-Factor Authentication (MFA) system using TOTP.
"""
import secrets
import qrcode
import io
import base64
from typing import Optional, Tuple, Dict, Any
import pyotp
from datetime import datetime, timedelta
import structlog

from .access_control import User

logger = structlog.get_logger()


class MFAManager:
    """Manages multi-factor authentication using TOTP (Time-based One-Time Password)."""
    
    def __init__(self, issuer_name: str = "AI Calling Agent"):
        """
        Initialize MFA manager.
        
        Args:
            issuer_name: Name of the service for TOTP apps
        """
        self.issuer_name = issuer_name
        self.backup_codes_count = 10
        self.backup_code_length = 8
        
    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret key.
        
        Returns:
            Base32 encoded secret key
        """
        return pyotp.random_base32()
    
    def generate_qr_code(self, user: User, secret: str) -> str:
        """
        Generate QR code for TOTP setup.
        
        Args:
            user: User object
            secret: TOTP secret key
            
        Returns:
            Base64 encoded QR code image
        """
        # Create TOTP URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=self.issuer_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_totp_code(self, secret: str, code: str, window: int = 1) -> bool:
        """
        Verify TOTP code.
        
        Args:
            secret: TOTP secret key
            code: 6-digit TOTP code
            window: Time window tolerance (default 1 = ±30 seconds)
            
        Returns:
            True if code is valid
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=window)
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False
    
    def generate_backup_codes(self) -> list[str]:
        """
        Generate backup codes for MFA recovery.
        
        Returns:
            List of backup codes
        """
        codes = []
        for _ in range(self.backup_codes_count):
            # Generate random alphanumeric code
            code = ''.join(
                secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                for _ in range(self.backup_code_length)
            )
            codes.append(code)
        
        return codes
    
    def setup_mfa_for_user(self, user: User) -> Tuple[str, str, list[str]]:
        """
        Set up MFA for a user.
        
        Args:
            user: User object
            
        Returns:
            Tuple of (secret, qr_code_base64, backup_codes)
        """
        # Generate secret
        secret = self.generate_secret()
        
        # Generate QR code
        qr_code = self.generate_qr_code(user, secret)
        
        # Generate backup codes
        backup_codes = self.generate_backup_codes()
        
        # Store secret in user (would be encrypted in real implementation)
        user.mfa_secret = secret
        user.mfa_enabled = False  # Will be enabled after verification
        
        logger.info(f"MFA setup initiated for user: {user.username}")
        
        return secret, qr_code, backup_codes
    
    def enable_mfa_for_user(self, user: User, verification_code: str) -> bool:
        """
        Enable MFA for user after verifying setup.
        
        Args:
            user: User object
            verification_code: TOTP code for verification
            
        Returns:
            True if MFA was enabled successfully
        """
        if not user.mfa_secret:
            logger.error(f"No MFA secret found for user: {user.username}")
            return False
        
        # Verify the code
        if not self.verify_totp_code(user.mfa_secret, verification_code):
            logger.warning(f"Invalid MFA verification code for user: {user.username}")
            return False
        
        # Enable MFA
        user.mfa_enabled = True
        user.updated_at = datetime.utcnow()
        
        logger.info(f"MFA enabled for user: {user.username}")
        return True
    
    def disable_mfa_for_user(self, user: User) -> bool:
        """
        Disable MFA for user.
        
        Args:
            user: User object
            
        Returns:
            True if MFA was disabled successfully
        """
        user.mfa_enabled = False
        user.mfa_secret = None
        user.updated_at = datetime.utcnow()
        
        logger.info(f"MFA disabled for user: {user.username}")
        return True
    
    def verify_mfa_code(self, user: User, code: str) -> bool:
        """
        Verify MFA code for user.
        
        Args:
            user: User object
            code: TOTP code or backup code
            
        Returns:
            True if code is valid
        """
        if not user.mfa_enabled or not user.mfa_secret:
            return False
        
        # Try TOTP code first
        if self.verify_totp_code(user.mfa_secret, code):
            logger.info(f"TOTP code verified for user: {user.username}")
            return True
        
        # Try backup codes (if implemented)
        # This would require storing backup codes securely
        # For now, we'll just use TOTP
        
        logger.warning(f"Invalid MFA code for user: {user.username}")
        return False
    
    def get_mfa_status(self, user: User) -> Dict[str, Any]:
        """
        Get MFA status for user.
        
        Args:
            user: User object
            
        Returns:
            Dictionary with MFA status information
        """
        return {
            'mfa_enabled': user.mfa_enabled,
            'has_secret': bool(user.mfa_secret),
            'setup_required': bool(user.mfa_secret and not user.mfa_enabled)
        }


class MFARequiredError(Exception):
    """Exception raised when MFA is required but not provided."""
    pass


class MFASession:
    """Manages MFA session state during authentication."""
    
    def __init__(self):
        self.pending_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 300  # 5 minutes
    
    def create_mfa_session(self, user: User, session_data: Dict[str, Any]) -> str:
        """
        Create a pending MFA session.
        
        Args:
            user: User object
            session_data: Session data to store
            
        Returns:
            MFA session ID
        """
        session_id = f"mfa_{secrets.token_urlsafe(32)}"
        
        self.pending_sessions[session_id] = {
            'user_id': user.user_id,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=self.session_timeout),
            'data': session_data
        }
        
        logger.info(f"MFA session created for user: {user.username}")
        return session_id
    
    def get_mfa_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get MFA session data.
        
        Args:
            session_id: MFA session ID
            
        Returns:
            Session data or None if not found/expired
        """
        session = self.pending_sessions.get(session_id)
        if not session:
            return None
        
        # Check expiry
        if datetime.utcnow() > session['expires_at']:
            del self.pending_sessions[session_id]
            return None
        
        return session
    
    def complete_mfa_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Complete MFA session and return data.
        
        Args:
            session_id: MFA session ID
            
        Returns:
            Session data or None if not found
        """
        session = self.get_mfa_session(session_id)
        if session:
            del self.pending_sessions[session_id]
            logger.info(f"MFA session completed: {session_id}")
        
        return session
    
    def cleanup_expired_sessions(self):
        """Clean up expired MFA sessions."""
        now = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, session in self.pending_sessions.items()
            if now > session['expires_at']
        ]
        
        for session_id in expired_sessions:
            del self.pending_sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired MFA sessions")


# Global instances
_mfa_manager = None
_mfa_session = None


def get_mfa_manager() -> MFAManager:
    """Get the global MFA manager instance."""
    global _mfa_manager
    if _mfa_manager is None:
        _mfa_manager = MFAManager()
    return _mfa_manager


def get_mfa_session() -> MFASession:
    """Get the global MFA session manager instance."""
    global _mfa_session
    if _mfa_session is None:
        _mfa_session = MFASession()
    return _mfa_session


def require_mfa_verification(user: User, mfa_code: Optional[str] = None) -> bool:
    """
    Check if user needs MFA verification and verify if code provided.
    
    Args:
        user: User object
        mfa_code: Optional MFA code
        
    Returns:
        True if MFA verification passed or not required
        
    Raises:
        MFARequiredError: If MFA is required but not provided/invalid
    """
    if not user.mfa_enabled:
        return True
    
    if not mfa_code:
        raise MFARequiredError("MFA code required")
    
    mfa_manager = get_mfa_manager()
    if not mfa_manager.verify_mfa_code(user, mfa_code):
        raise MFARequiredError("Invalid MFA code")
    
    return True


def generate_mfa_setup_data(user: User) -> Dict[str, Any]:
    """
    Generate MFA setup data for user.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with setup data
    """
    mfa_manager = get_mfa_manager()
    secret, qr_code, backup_codes = mfa_manager.setup_mfa_for_user(user)
    
    return {
        'secret': secret,
        'qr_code': qr_code,
        'backup_codes': backup_codes,
        'issuer': mfa_manager.issuer_name
    }