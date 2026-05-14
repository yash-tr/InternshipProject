"""
Secure key management and rotation system for encryption keys.
"""
import os
import json
import secrets
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import logging

logger = logging.getLogger(__name__)


class KeyManager:
    """Manages encryption keys with rotation, validation, and secure storage."""
    
    def __init__(self, key_store_path: Optional[str] = None):
        """
        Initialize key manager.
        
        Args:
            key_store_path: Path to store key metadata (not the keys themselves)
        """
        self.key_store_path = key_store_path or os.getenv('KEY_STORE_PATH', '.keys/metadata.json')
        self.key_metadata = self._load_key_metadata()
        
    def _load_key_metadata(self) -> Dict:
        """Load key metadata from storage."""
        try:
            if os.path.exists(self.key_store_path):
                with open(self.key_store_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load key metadata: {e}")
        
        return {
            'keys': {},
            'current_key_id': None,
            'rotation_history': [],
            'created_at': datetime.utcnow().isoformat()
        }
    
    def _save_key_metadata(self):
        """Save key metadata to storage."""
        try:
            os.makedirs(os.path.dirname(self.key_store_path), exist_ok=True)
            with open(self.key_store_path, 'w') as f:
                json.dump(self.key_metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save key metadata: {e}")
    
    def generate_key(self, key_id: Optional[str] = None) -> str:
        """
        Generate a new encryption key.
        
        Args:
            key_id: Optional key identifier
            
        Returns:
            Base64 encoded encryption key
        """
        if key_id is None:
            key_id = f"key_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
        
        # Generate cryptographically secure key
        key = Fernet.generate_key()
        key_b64 = key.decode('utf-8')
        
        # Store metadata (not the key itself)
        self.key_metadata['keys'][key_id] = {
            'created_at': datetime.utcnow().isoformat(),
            'algorithm': 'Fernet',
            'key_length': 32,
            'status': 'active',
            'usage_count': 0,
            'last_used': None
        }
        
        # Set as current key if it's the first one
        if self.key_metadata['current_key_id'] is None:
            self.key_metadata['current_key_id'] = key_id
        
        self._save_key_metadata()
        logger.info(f"Generated new encryption key: {key_id}")
        
        return key_b64
    
    def rotate_key(self, new_key: Optional[str] = None) -> Tuple[str, str]:
        """
        Rotate to a new encryption key.
        
        Args:
            new_key: Optional new key to use, if None generates a new one
            
        Returns:
            Tuple of (new_key_id, new_key)
        """
        old_key_id = self.key_metadata['current_key_id']
        
        if new_key is None:
            new_key = self.generate_key()
            new_key_id = list(self.key_metadata['keys'].keys())[-1]  # Last added key
        else:
            # Validate provided key
            if not self.validate_key_strength(new_key):
                raise ValueError("Provided key does not meet security requirements")
            
            new_key_id = f"rotated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.key_metadata['keys'][new_key_id] = {
                'created_at': datetime.utcnow().isoformat(),
                'algorithm': 'Fernet',
                'key_length': 32,
                'status': 'active',
                'usage_count': 0,
                'last_used': None
            }
        
        # Update current key
        old_current = self.key_metadata['current_key_id']
        self.key_metadata['current_key_id'] = new_key_id
        
        # Mark old key as rotated but keep it for decryption
        if old_key_id and old_key_id in self.key_metadata['keys']:
            self.key_metadata['keys'][old_key_id]['status'] = 'rotated'
            self.key_metadata['keys'][old_key_id]['rotated_at'] = datetime.utcnow().isoformat()
        
        # Add to rotation history
        self.key_metadata['rotation_history'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'old_key_id': old_key_id,
            'new_key_id': new_key_id,
            'reason': 'manual_rotation'
        })
        
        self._save_key_metadata()
        logger.info(f"Key rotation completed: {old_key_id} -> {new_key_id}")
        
        return new_key_id, new_key
    
    def validate_key_strength(self, key: str) -> bool:
        """
        Validate encryption key strength and format.
        
        Args:
            key: Base64 encoded key to validate
            
        Returns:
            True if key meets security requirements
        """
        try:
            # Check if it's a valid Fernet key
            decoded_key = base64.urlsafe_b64decode(key.encode())
            
            # Check key length (32 bytes for Fernet)
            if len(decoded_key) != 32:
                logger.warning(f"Invalid key length: {len(decoded_key)}, expected 32")
                return False
            
            # Check entropy (basic check)
            entropy = self._calculate_entropy(decoded_key)
            if entropy < 7.0:  # Minimum entropy threshold
                logger.warning(f"Low key entropy: {entropy}")
                return False
            
            # Try to create Fernet instance
            Fernet(key.encode())
            
            return True
            
        except Exception as e:
            logger.error(f"Key validation failed: {e}")
            return False
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0
        
        # Count byte frequencies
        frequencies = {}
        for byte in data:
            frequencies[byte] = frequencies.get(byte, 0) + 1
        
        # Calculate entropy
        entropy = 0
        data_len = len(data)
        for count in frequencies.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    def get_key_info(self, key_id: str) -> Optional[Dict]:
        """
        Get information about a specific key.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Key metadata or None if not found
        """
        return self.key_metadata['keys'].get(key_id)
    
    def list_keys(self, include_rotated: bool = False) -> Dict[str, Dict]:
        """
        List all keys with their metadata.
        
        Args:
            include_rotated: Whether to include rotated keys
            
        Returns:
            Dictionary of key metadata
        """
        if include_rotated:
            return self.key_metadata['keys']
        else:
            return {
                key_id: metadata 
                for key_id, metadata in self.key_metadata['keys'].items()
                if metadata['status'] == 'active'
            }
    
    def mark_key_used(self, key_id: str):
        """
        Mark a key as used (for usage tracking).
        
        Args:
            key_id: Key identifier
        """
        if key_id in self.key_metadata['keys']:
            self.key_metadata['keys'][key_id]['usage_count'] += 1
            self.key_metadata['keys'][key_id]['last_used'] = datetime.utcnow().isoformat()
            self._save_key_metadata()
    
    def should_rotate_key(self, key_id: str) -> bool:
        """
        Check if a key should be rotated based on age and usage.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if key should be rotated
        """
        key_info = self.get_key_info(key_id)
        if not key_info:
            return True
        
        # Check key age (rotate after 90 days)
        created_at = datetime.fromisoformat(key_info['created_at'])
        age = datetime.utcnow() - created_at
        if age > timedelta(days=90):
            logger.info(f"Key {key_id} should be rotated due to age: {age.days} days")
            return True
        
        # Check usage count (rotate after 1M operations)
        if key_info['usage_count'] > 1000000:
            logger.info(f"Key {key_id} should be rotated due to usage: {key_info['usage_count']}")
            return True
        
        return False
    
    def cleanup_old_keys(self, retention_days: int = 365):
        """
        Clean up old rotated keys that are past retention period.
        
        Args:
            retention_days: Number of days to retain old keys
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        keys_to_remove = []
        
        for key_id, metadata in self.key_metadata['keys'].items():
            if metadata['status'] == 'rotated':
                rotated_at = metadata.get('rotated_at')
                if rotated_at:
                    rotated_date = datetime.fromisoformat(rotated_at)
                    if rotated_date < cutoff_date:
                        keys_to_remove.append(key_id)
        
        for key_id in keys_to_remove:
            del self.key_metadata['keys'][key_id]
            logger.info(f"Cleaned up old key: {key_id}")
        
        if keys_to_remove:
            self._save_key_metadata()
    
    def get_rotation_history(self) -> List[Dict]:
        """Get key rotation history."""
        return self.key_metadata['rotation_history']
    
    def export_key_metadata(self) -> Dict:
        """Export key metadata for backup (excludes sensitive data)."""
        return {
            'keys': {
                key_id: {
                    'created_at': metadata['created_at'],
                    'algorithm': metadata['algorithm'],
                    'status': metadata['status'],
                    'usage_count': metadata['usage_count']
                }
                for key_id, metadata in self.key_metadata['keys'].items()
            },
            'current_key_id': self.key_metadata['current_key_id'],
            'rotation_history': self.key_metadata['rotation_history']
        }


# Global key manager instance
_key_manager = None


def get_key_manager() -> KeyManager:
    """Get the global key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def rotate_encryption_key(new_key: Optional[str] = None) -> Tuple[str, str]:
    """
    Rotate the encryption key.
    
    Args:
        new_key: Optional new key to use
        
    Returns:
        Tuple of (new_key_id, new_key)
    """
    return get_key_manager().rotate_key(new_key)


def validate_key_strength(key: str) -> bool:
    """
    Validate encryption key strength.
    
    Args:
        key: Base64 encoded key to validate
        
    Returns:
        True if key meets security requirements
    """
    return get_key_manager().validate_key_strength(key)


def generate_secure_key() -> str:
    """
    Generate a cryptographically secure encryption key.
    
    Returns:
        Base64 encoded encryption key
    """
    return get_key_manager().generate_key()


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> str:
    """
    Derive an encryption key from a password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt for key derivation
        
    Returns:
        Base64 encoded derived key
    """
    if salt is None:
        # Use a consistent salt for the same password
        salt = hashlib.sha256(password.encode()).digest()[:16]
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    
    derived_key = kdf.derive(password.encode())
    return base64.urlsafe_b64encode(derived_key).decode('utf-8')