"""
Data encryption and decryption utilities for PII protection.
Implements AES-256 encryption for sensitive data fields.
"""
import os
import base64
import hashlib
from typing import Any, Dict, List, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import json
import logging

logger = logging.getLogger(__name__)

# PII fields that require encryption
PII_FIELDS = {
    'phone', 'caller_phone', 'email', 'first_name', 'last_name', 
    'company', 'title', 'description', 'content', 'conversation_history',
    'extracted_data', 'conversation_summary'
}


class EncryptionManager:
    """Manages encryption and decryption of sensitive data."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption manager with key.
        
        Args:
            encryption_key: Base64 encoded encryption key. If None, generates from environment.
        """
        if encryption_key:
            # Try to use as base64 key first, if that fails, derive from password
            try:
                self.key = base64.urlsafe_b64decode(encryption_key.encode())
                if len(self.key) != 32:
                    raise ValueError("Key must be 32 bytes")
                self.key = encryption_key.encode()
            except:
                # Derive key from the provided string as password
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'default-salt',
                    iterations=100000,
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        else:
            # Get key from environment or generate one
            env_key = os.getenv('ENCRYPTION_KEY')
            if env_key:
                try:
                    # Try as base64 key first
                    test_key = base64.urlsafe_b64decode(env_key.encode())
                    if len(test_key) == 32:
                        self.key = env_key.encode()
                    else:
                        raise ValueError("Invalid key length")
                except:
                    # Derive key from the env value as password
                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=b'default-salt',
                        iterations=100000,
                    )
                    self.key = base64.urlsafe_b64encode(kdf.derive(env_key.encode()))
            else:
                # Generate key from default password and salt
                password = os.getenv('ENCRYPTION_PASSWORD', 'default-dev-password').encode()
                salt = os.getenv('ENCRYPTION_SALT', 'default-dev-salt').encode()
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(password))
        
        self.fernet = Fernet(self.key)
    
    def encrypt_string(self, plaintext: str) -> str:
        """
        Encrypt a string value.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not plaintext:
            return plaintext
        
        try:
            encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt_string(self, ciphertext: str) -> str:
        """
        Decrypt a string value.
        
        Args:
            ciphertext: Base64 encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Dict[str, Any], fields_to_encrypt: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Encrypt specified fields in a dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            fields_to_encrypt: List of field names to encrypt. If None, uses PII_FIELDS.
            
        Returns:
            Dictionary with encrypted fields
        """
        if not data:
            return data
        
        if fields_to_encrypt is None:
            fields_to_encrypt = PII_FIELDS
        
        encrypted_data = data.copy()
        
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field]:
                value = encrypted_data[field]
                
                if isinstance(value, str):
                    encrypted_data[field] = self.encrypt_string(value)
                elif isinstance(value, dict):
                    # Recursively encrypt nested dictionaries
                    encrypted_data[field] = self.encrypt_dict(value, fields_to_encrypt)
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
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields_to_decrypt: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Decrypt specified fields in a dictionary.
        
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
        
        return decrypted_data
    
    def hash_for_indexing(self, value: str) -> str:
        """
        Create a hash of sensitive data for indexing purposes.
        
        Args:
            value: Value to hash
            
        Returns:
            SHA-256 hash of the value
        """
        if not value:
            return value
        
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    
    def mask_pii(self, data: Dict[str, Any], mask_char: str = '*') -> Dict[str, Any]:
        """
        Mask PII fields for logging and display purposes.
        
        Args:
            data: Dictionary containing data to mask
            mask_char: Character to use for masking
            
        Returns:
            Dictionary with masked PII fields
        """
        if not data:
            return data
        
        masked_data = data.copy()
        
        for field in PII_FIELDS:
            if field in masked_data and masked_data[field]:
                value = masked_data[field]
                
                if isinstance(value, str):
                    if field in ['phone', 'caller_phone']:
                        # Show last 4 digits of phone numbers
                        masked_data[field] = f"{mask_char * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else mask_char * len(value)
                    elif field == 'email':
                        # Show first letter and domain
                        if '@' in value:
                            local, domain = value.split('@', 1)
                            masked_data[field] = f"{local[0]}{mask_char * (len(local) - 1)}@{domain}"
                        else:
                            masked_data[field] = mask_char * len(value)
                    else:
                        # Mask other fields completely
                        masked_data[field] = mask_char * min(len(value), 10)
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
    Descriptor for automatically encrypting/decrypting model fields.
    """
    
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.encrypted_field_name = f"_{field_name}_encrypted"
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        encrypted_value = getattr(obj, self.encrypted_field_name, None)
        if encrypted_value:
            return get_encryption_manager().decrypt_string(encrypted_value)
        return None
    
    def __set__(self, obj, value):
        if value:
            encrypted_value = get_encryption_manager().encrypt_string(value)
            setattr(obj, self.encrypted_field_name, encrypted_value)
        else:
            setattr(obj, self.encrypted_field_name, None)