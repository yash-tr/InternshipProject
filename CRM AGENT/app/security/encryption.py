"""
Enhanced data encryption and decryption utilities for PII protection.
Implements AES-256 encryption with key rotation and secure key management.
"""
import os
import base64
import hashlib
import secrets
from typing import Any, Dict, List, Optional, Union
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# PII fields that require encryption
PII_FIELDS = {
    'phone', 'caller_phone', 'email', 'first_name', 'last_name', 
    'company', 'title', 'description', 'content', 'conversation_history',
    'extracted_data', 'conversation_summary', 'address', 'ssn', 'credit_card',
    'bank_account', 'passport', 'driver_license', 'medical_record'
}

# Sensitive fields that require special handling
HIGHLY_SENSITIVE_FIELDS = {
    'ssn', 'credit_card', 'bank_account', 'passport', 'driver_license', 
    'medical_record', 'password', 'api_key', 'token'
}


class EncryptionManager:
    """Enhanced encryption manager with key rotation and secure key management."""
    
    def __init__(self, encryption_keys: Optional[List[str]] = None):
        """
        Initialize encryption manager with multiple keys for rotation.
        
        Args:
            encryption_keys: List of base64 encoded encryption keys. First key is primary.
        """
        self.keys = []
        self.key_ids = []
        
        if encryption_keys:
            for i, key in enumerate(encryption_keys):
                try:
                    # Validate key format
                    decoded_key = base64.urlsafe_b64decode(key.encode())
                    if len(decoded_key) == 32:
                        self.keys.append(key.encode())
                        self.key_ids.append(f"key_{i}")
                    else:
                        raise ValueError(f"Invalid key length: {len(decoded_key)}")
                except Exception as e:
                    logger.error(f"Invalid encryption key {i}: {e}")
                    raise ValueError(f"Invalid encryption key format: {e}")
        else:
            # Load keys from environment
            self._load_keys_from_env()
        
        if not self.keys:
            raise ValueError("No valid encryption keys provided")
        
        # Create Fernet instances
        self.fernet_keys = [Fernet(key) for key in self.keys]
        self.multi_fernet = MultiFernet(self.fernet_keys)
        
        # Primary key for new encryptions
        self.primary_fernet = self.fernet_keys[0]
        self.primary_key_id = self.key_ids[0]
        
        logger.info(f"Encryption manager initialized with {len(self.keys)} keys")
    
    def _load_keys_from_env(self):
        """Load encryption keys from environment variables."""
        # Primary key
        primary_key = os.getenv('ENCRYPTION_KEY')
        if primary_key:
            try:
                # Validate and add primary key
                if self._is_valid_fernet_key(primary_key):
                    self.keys.append(primary_key.encode())
                    self.key_ids.append("primary")
                else:
                    # Derive key from password
                    derived_key = self._derive_key_from_password(primary_key)
                    self.keys.append(derived_key)
                    self.key_ids.append("primary")
            except Exception as e:
                logger.error(f"Failed to load primary encryption key: {e}")
                raise
        
        # Additional rotation keys
        for i in range(1, 10):  # Support up to 10 rotation keys
            key_env = f'ENCRYPTION_KEY_{i}'
            key = os.getenv(key_env)
            if key:
                try:
                    if self._is_valid_fernet_key(key):
                        self.keys.append(key.encode())
                        self.key_ids.append(f"rotation_{i}")
                    else:
                        derived_key = self._derive_key_from_password(key, salt=f"salt_{i}".encode())
                        self.keys.append(derived_key)
                        self.key_ids.append(f"rotation_{i}")
                except Exception as e:
                    logger.warning(f"Failed to load rotation key {i}: {e}")
        
        # If no keys loaded, generate a default one (development only)
        if not self.keys:
            if os.getenv('ENVIRONMENT', 'development').lower() == 'development':
                logger.warning("No encryption keys found, generating default key for development")
                default_key = Fernet.generate_key()
                self.keys.append(default_key)
                self.key_ids.append("default")
            else:
                raise ValueError("No encryption keys configured for production environment")
    
    def _is_valid_fernet_key(self, key: str) -> bool:
        """Check if a string is a valid Fernet key."""
        try:
            decoded = base64.urlsafe_b64decode(key.encode())
            return len(decoded) == 32
        except:
            return False
    
    def _derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = os.getenv('ENCRYPTION_SALT', 'default-salt').encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def encrypt_string(self, plaintext: str, include_key_id: bool = True) -> str:
        """
        Encrypt a string value with key rotation support.
        
        Args:
            plaintext: String to encrypt
            include_key_id: Whether to include key ID in encrypted data
            
        Returns:
            Base64 encoded encrypted string with optional key ID prefix
        """
        if not plaintext:
            return plaintext
        
        try:
            encrypted_bytes = self.primary_fernet.encrypt(plaintext.encode('utf-8'))
            encrypted_b64 = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            
            if include_key_id:
                return f"{self.primary_key_id}:{encrypted_b64}"
            else:
                return encrypted_b64
                
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt_string(self, ciphertext: str) -> str:
        """
        Decrypt a string value with key rotation support.
        
        Args:
            ciphertext: Base64 encoded encrypted string with optional key ID prefix
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext
        
        try:
            # Check if ciphertext has key ID prefix
            if ':' in ciphertext and not ciphertext.startswith('gAAAAA'):  # Not a Fernet token
                key_id, encrypted_data = ciphertext.split(':', 1)
                # Try specific key first if we have it
                if key_id in self.key_ids:
                    key_index = self.key_ids.index(key_id)
                    try:
                        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
                        decrypted_bytes = self.fernet_keys[key_index].decrypt(encrypted_bytes)
                        return decrypted_bytes.decode('utf-8')
                    except:
                        pass  # Fall back to multi-key decryption
                
                # Use the encrypted data part for multi-key decryption
                ciphertext = encrypted_data
            
            # Try multi-key decryption (handles key rotation)
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted_bytes = self.multi_fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Dict[str, Any], fields_to_encrypt: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Encrypt specified fields in a dictionary with enhanced security.
        
        Args:
            data: Dictionary containing data to encrypt
            fields_to_encrypt: List of field names to encrypt. If None, uses PII_FIELDS.
            
        Returns:
            Dictionary with encrypted fields and metadata
        """
        if not data:
            return data
        
        if fields_to_encrypt is None:
            fields_to_encrypt = PII_FIELDS
        
        encrypted_data = data.copy()
        encryption_metadata = {
            'encrypted_fields': [],
            'encryption_timestamp': datetime.utcnow().isoformat(),
            'key_id': self.primary_key_id
        }
        
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field]:
                value = encrypted_data[field]
                
                try:
                    if isinstance(value, str):
                        encrypted_data[field] = self.encrypt_string(value)
                        encryption_metadata['encrypted_fields'].append(field)
                    elif isinstance(value, dict):
                        # Recursively encrypt nested dictionaries
                        nested_result = self.encrypt_dict(value, fields_to_encrypt)
                        encrypted_data[field] = nested_result
                        if 'encryption_metadata' in nested_result:
                            encryption_metadata['encrypted_fields'].append(field)
                    elif isinstance(value, list):
                        # Handle lists of strings or dictionaries
                        encrypted_list = []
                        for item in value:
                            if isinstance(item, str):
                                encrypted_list.append(self.encrypt_string(item))
                            elif isinstance(item, dict):
                                encrypted_list.append(self.encrypt_dict(item, fields_to_encrypt))
                            else:
                                encrypted_list.append(item)
                        encrypted_data[field] = encrypted_list
                        encryption_metadata['encrypted_fields'].append(field)
                except Exception as e:
                    logger.error(f"Failed to encrypt field {field}: {e}")
                    # Continue with other fields
        
        # Add metadata if any fields were encrypted
        if encryption_metadata['encrypted_fields']:
            encrypted_data['_encryption_metadata'] = encryption_metadata
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields_to_decrypt: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Decrypt specified fields in a dictionary with metadata handling.
        
        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt. If None, uses PII_FIELDS.
            
        Returns:
            Dictionary with decrypted fields
        """
        if not data:
            return data
        
        if fields_to_decrypt is None:
            fields_to_decrypt = PII_FIELDS
        
        decrypted_data = data.copy()
        
        # Remove encryption metadata from result
        encryption_metadata = decrypted_data.pop('_encryption_metadata', None)
        
        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field]:
                value = decrypted_data[field]
                
                try:
                    if isinstance(value, str):
                        decrypted_data[field] = self.decrypt_string(value)
                    elif isinstance(value, dict):
                        # Recursively decrypt nested dictionaries
                        decrypted_data[field] = self.decrypt_dict(value, fields_to_decrypt)
                    elif isinstance(value, list):
                        # Handle lists of strings or dictionaries
                        decrypted_list = []
                        for item in value:
                            if isinstance(item, str):
                                decrypted_list.append(self.decrypt_string(item))
                            elif isinstance(item, dict):
                                decrypted_list.append(self.decrypt_dict(item, fields_to_decrypt))
                            else:
                                decrypted_list.append(item)
                        decrypted_data[field] = decrypted_list
                except ValueError:
                    # If decryption fails, assume data is not encrypted
                    logger.warning(f"Failed to decrypt field {field}, assuming plaintext")
                    pass
                except Exception as e:
                    logger.error(f"Unexpected error decrypting field {field}: {e}")
        
        return decrypted_data
    
    def hash_for_indexing(self, value: str, salt: Optional[str] = None) -> str:
        """
        Create a secure hash of sensitive data for indexing purposes.
        
        Args:
            value: Value to hash
            salt: Optional salt for hashing
            
        Returns:
            SHA-256 hash of the value with salt
        """
        if not value:
            return value
        
        if salt is None:
            salt = os.getenv('HASH_SALT', 'default-hash-salt')
        
        salted_value = f"{salt}:{value}"
        return hashlib.sha256(salted_value.encode('utf-8')).hexdigest()
    
    def mask_pii(self, data: Dict[str, Any], mask_char: str = '*') -> Dict[str, Any]:
        """
        Enhanced PII masking for logging and display purposes.
        
        Args:
            data: Dictionary containing data to mask
            mask_char: Character to use for masking
            
        Returns:
            Dictionary with masked PII fields
        """
        if not data:
            return data
        
        masked_data = data.copy()
        
        # Remove encryption metadata from masked output
        masked_data.pop('_encryption_metadata', None)
        
        for field in PII_FIELDS:
            if field in masked_data and masked_data[field]:
                value = masked_data[field]
                
                if isinstance(value, str):
                    if field in ['phone', 'caller_phone']:
                        # Show last 4 digits of phone numbers
                        masked_data[field] = f"{mask_char * max(0, len(value) - 4)}{value[-4:]}" if len(value) > 4 else mask_char * len(value)
                    elif field == 'email':
                        # Show first letter and domain
                        if '@' in value:
                            local, domain = value.split('@', 1)
                            masked_data[field] = f"{local[0]}{mask_char * max(0, len(local) - 1)}@{domain}"
                        else:
                            masked_data[field] = mask_char * len(value)
                    elif field in HIGHLY_SENSITIVE_FIELDS:
                        # Completely mask highly sensitive fields
                        masked_data[field] = mask_char * 8
                    else:
                        # Mask other fields partially
                        if len(value) <= 2:
                            masked_data[field] = mask_char * len(value)
                        else:
                            masked_data[field] = f"{value[0]}{mask_char * (len(value) - 2)}{value[-1]}"
                elif isinstance(value, dict):
                    masked_data[field] = self.mask_pii(value, mask_char)
                elif isinstance(value, list):
                    masked_list = []
                    for item in value:
                        if isinstance(item, str):
                            masked_list.append(mask_char * min(len(item), 10))
                        elif isinstance(item, dict):
                            masked_list.append(self.mask_pii(item, mask_char))
                        else:
                            masked_list.append(item)
                    masked_data[field] = masked_list
        
        return masked_data
    
    def rotate_key(self, new_key: str) -> bool:
        """
        Add a new encryption key for rotation.
        
        Args:
            new_key: New encryption key to add
            
        Returns:
            True if key rotation successful
        """
        try:
            if self._is_valid_fernet_key(new_key):
                # Add new key as primary
                self.keys.insert(0, new_key.encode())
                self.key_ids.insert(0, f"rotated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
                
                # Recreate Fernet instances
                self.fernet_keys = [Fernet(key) for key in self.keys]
                self.multi_fernet = MultiFernet(self.fernet_keys)
                self.primary_fernet = self.fernet_keys[0]
                self.primary_key_id = self.key_ids[0]
                
                logger.info(f"Key rotation successful, now have {len(self.keys)} keys")
                return True
            else:
                logger.error("Invalid key format for rotation")
                return False
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False
    
    def get_key_info(self) -> Dict[str, Any]:
        """
        Get information about current encryption keys.
        
        Returns:
            Dictionary with key information (no sensitive data)
        """
        return {
            'total_keys': len(self.keys),
            'primary_key_id': self.primary_key_id,
            'key_ids': self.key_ids,
            'rotation_supported': len(self.keys) > 1
        }


# Global encryption manager instance
_encryption_manager = None


def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


async def encrypt_pii_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to encrypt PII data.
    
    Args:
        data: Dictionary containing data to encrypt
        
    Returns:
        Dictionary with encrypted PII fields
    """
    return get_encryption_manager().encrypt_dict(data)


async def decrypt_pii_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to decrypt PII data.
    
    Args:
        data: Dictionary containing encrypted data
        
    Returns:
        Dictionary with decrypted PII fields
    """
    return get_encryption_manager().decrypt_dict(data)


def mask_pii_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to mask PII data for logging.
    
    Args:
        data: Dictionary containing data to mask
        
    Returns:
        Dictionary with masked PII fields
    """
    return get_encryption_manager().mask_pii(data)


def generate_encryption_key() -> str:
    """
    Generate a new encryption key for development/testing.
    
    Returns:
        Base64 encoded encryption key
    """
    return Fernet.generate_key().decode('utf-8')


async def encrypt_field(value: str) -> str:
    """
    Convenience function to encrypt a single field value.
    
    Args:
        value: String value to encrypt
        
    Returns:
        Encrypted string value
    """
    if not value:
        return value
    return get_encryption_manager().encrypt_string(value)


async def decrypt_field(value: str) -> str:
    """
    Convenience function to decrypt a single field value.
    
    Args:
        value: Encrypted string value to decrypt
        
    Returns:
        Decrypted string value
    """
    if not value:
        return value
    return get_encryption_manager().decrypt_string(value)


class EncryptedField:
    """
    Enhanced descriptor for automatically encrypting/decrypting model fields.
    """
    
    def __init__(self, field_name: str, required: bool = False):
        self.field_name = field_name
        self.encrypted_field_name = f"_{field_name}_encrypted"
        self.required = required
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        encrypted_value = getattr(obj, self.encrypted_field_name, None)
        if encrypted_value:
            try:
                return get_encryption_manager().decrypt_string(encrypted_value)
            except ValueError:
                logger.warning(f"Failed to decrypt field {self.field_name}, returning None")
                return None
        return None
    
    def __set__(self, obj, value):
        if value:
            try:
                encrypted_value = get_encryption_manager().encrypt_string(value)
                setattr(obj, self.encrypted_field_name, encrypted_value)
            except ValueError as e:
                logger.error(f"Failed to encrypt field {self.field_name}: {e}")
                if self.required:
                    raise
                setattr(obj, self.encrypted_field_name, None)
        else:
            setattr(obj, self.encrypted_field_name, None)