"""
Unit tests for encryption utilities.
"""
import pytest
import os
from unittest.mock import patch

from app.utils.encryption import (
    EncryptionManager, get_encryption_manager, encrypt_pii_data,
    decrypt_pii_data, mask_pii_for_logging, generate_encryption_key,
    EncryptedField, PII_FIELDS
)


class TestEncryptionManager:
    """Test EncryptionManager class."""
    
    def test_encryption_manager_init_with_key(self):
        """Test EncryptionManager initialization with provided key."""
        test_key = generate_encryption_key()
        manager = EncryptionManager(encryption_key=test_key)
        
        assert manager.key == test_key.encode()
        assert manager.fernet is not None
    
    def test_encryption_manager_init_from_env(self):
        """Test EncryptionManager initialization from environment."""
        test_key = generate_encryption_key()
        
        with patch.dict(os.environ, {'ENCRYPTION_KEY': test_key}):
            manager = EncryptionManager()
            assert manager.key == test_key.encode()
    
    def test_encryption_manager_init_default(self):
        """Test EncryptionManager initialization with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            manager = EncryptionManager()
            assert manager.key is not None
            assert manager.fernet is not None
    
    def test_encrypt_decrypt_string(self):
        """Test string encryption and decryption."""
        manager = EncryptionManager()
        
        plaintext = "sensitive information"
        encrypted = manager.encrypt_string(plaintext)
        decrypted = manager.decrypt_string(encrypted)
        
        assert encrypted != plaintext
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_empty_string(self):
        """Test encryption/decryption of empty strings."""
        manager = EncryptionManager()
        
        assert manager.encrypt_string("") == ""
        assert manager.decrypt_string("") == ""
        assert manager.encrypt_string(None) is None
        assert manager.decrypt_string(None) is None
    
    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        manager = EncryptionManager()
        
        data = {
            "phone": "+15551234567",
            "email": "test@example.com",
            "first_name": "John",
            "non_pii_field": "public data"
        }
        
        encrypted_data = manager.encrypt_dict(data)
        decrypted_data = manager.decrypt_dict(encrypted_data)
        
        # PII fields should be encrypted
        assert encrypted_data["phone"] != data["phone"]
        assert encrypted_data["email"] != data["email"]
        assert encrypted_data["first_name"] != data["first_name"]
        
        # Non-PII fields should remain unchanged
        assert encrypted_data["non_pii_field"] == data["non_pii_field"]
        
        # Decryption should restore original data
        assert decrypted_data == data
    
    def test_encrypt_decrypt_nested_dict(self):
        """Test encryption/decryption of nested dictionaries."""
        manager = EncryptionManager()
        
        data = {
            "contact": {
                "phone": "+15551234567",
                "email": "test@example.com"
            },
            "metadata": {
                "source": "web_form",
                "description": "Lead from website"
            }
        }
        
        encrypted_data = manager.encrypt_dict(data)
        decrypted_data = manager.decrypt_dict(encrypted_data)
        
        # Nested PII should be encrypted
        assert encrypted_data["contact"]["phone"] != data["contact"]["phone"]
        assert encrypted_data["contact"]["email"] != data["contact"]["email"]
        assert encrypted_data["metadata"]["description"] != data["metadata"]["description"]
        
        # Non-PII should remain unchanged
        assert encrypted_data["metadata"]["source"] == data["metadata"]["source"]
        
        # Decryption should restore original data
        assert decrypted_data == data
    
    def test_encrypt_decrypt_list_of_strings(self):
        """Test encryption/decryption of lists containing strings."""
        manager = EncryptionManager()
        
        data = {
            "conversation_history": [
                "Hello, how can I help you?",
                "I'm interested in your services",
                "Great! Let me get your information"
            ]
        }
        
        encrypted_data = manager.encrypt_dict(data)
        decrypted_data = manager.decrypt_dict(encrypted_data)
        
        # List items should be encrypted
        for i, item in enumerate(encrypted_data["conversation_history"]):
            assert item != data["conversation_history"][i]
        
        # Decryption should restore original data
        assert decrypted_data == data
    
    def test_encrypt_decrypt_list_of_dicts(self):
        """Test encryption/decryption of lists containing dictionaries."""
        manager = EncryptionManager()
        
        data = {
            "extracted_data": [
                {"phone": "+15551234567", "name": "John Doe"},
                {"phone": "+15559876543", "name": "Jane Smith"}
            ]
        }
        
        encrypted_data = manager.encrypt_dict(data)
        decrypted_data = manager.decrypt_dict(encrypted_data)
        
        # Dictionary items in list should be encrypted
        for i, item in enumerate(encrypted_data["extracted_data"]):
            assert item["phone"] != data["extracted_data"][i]["phone"]
        
        # Decryption should restore original data
        assert decrypted_data == data
    
    def test_encrypt_decrypt_custom_fields(self):
        """Test encryption/decryption with custom field list."""
        manager = EncryptionManager()
        
        data = {
            "phone": "+15551234567",
            "email": "test@example.com",
            "custom_field": "sensitive data",
            "public_field": "public data"
        }
        
        custom_fields = ["phone", "custom_field"]
        
        encrypted_data = manager.encrypt_dict(data, fields_to_encrypt=custom_fields)
        decrypted_data = manager.decrypt_dict(encrypted_data, fields_to_decrypt=custom_fields)
        
        # Only specified fields should be encrypted
        assert encrypted_data["phone"] != data["phone"]
        assert encrypted_data["custom_field"] != data["custom_field"]
        assert encrypted_data["email"] == data["email"]  # Not in custom fields
        assert encrypted_data["public_field"] == data["public_field"]
        
        # Decryption should restore specified fields
        assert decrypted_data["phone"] == data["phone"]
        assert decrypted_data["custom_field"] == data["custom_field"]
        assert decrypted_data["email"] == data["email"]
        assert decrypted_data["public_field"] == data["public_field"]
    
    def test_hash_for_indexing(self):
        """Test hash generation for indexing."""
        manager = EncryptionManager()
        
        value = "+15551234567"
        hash1 = manager.hash_for_indexing(value)
        hash2 = manager.hash_for_indexing(value)
        
        # Same value should produce same hash
        assert hash1 == hash2
        
        # Different values should produce different hashes
        different_value = "+15559876543"
        hash3 = manager.hash_for_indexing(different_value)
        assert hash1 != hash3
        
        # Hash should be deterministic and not equal to original
        assert hash1 != value
        assert len(hash1) == 64  # SHA-256 hex digest length
    
    def test_hash_for_indexing_empty(self):
        """Test hash generation for empty values."""
        manager = EncryptionManager()
        
        assert manager.hash_for_indexing("") == ""
        assert manager.hash_for_indexing(None) is None
    
    def test_mask_pii(self):
        """Test PII masking for logging."""
        manager = EncryptionManager()
        
        data = {
            "phone": "+15551234567",
            "caller_phone": "+15559876543",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "company": "Acme Corporation",
            "non_pii": "public data"
        }
        
        masked_data = manager.mask_pii(data)
        
        # Phone numbers should show last 4 digits
        assert masked_data["phone"] == "*******4567"
        assert masked_data["caller_phone"] == "*******6543"
        
        # Email should show first letter and domain
        assert masked_data["email"] == "t***@example.com"
        
        # Other PII should be masked
        assert masked_data["first_name"] == "****"
        assert masked_data["last_name"] == "***"
        assert masked_data["company"] == "**********"
        
        # Non-PII should remain unchanged
        assert masked_data["non_pii"] == "public data"
    
    def test_mask_pii_nested(self):
        """Test PII masking for nested data."""
        manager = EncryptionManager()
        
        data = {
            "contact": {
                "phone": "+15551234567",
                "email": "test@example.com"
            },
            "conversation_history": [
                "Hello, my name is John Doe",
                "My phone number is 555-123-4567"
            ]
        }
        
        masked_data = manager.mask_pii(data)
        
        # Nested PII should be masked
        assert masked_data["contact"]["phone"] == "*******4567"
        assert masked_data["contact"]["email"] == "t***@example.com"
        
        # List items should be masked
        for item in masked_data["conversation_history"]:
            assert len(item) <= 10  # Should be truncated to max 10 chars
            assert item == "**********"
    
    def test_mask_pii_custom_char(self):
        """Test PII masking with custom mask character."""
        manager = EncryptionManager()
        
        data = {"phone": "+15551234567"}
        masked_data = manager.mask_pii(data, mask_char='X')
        
        assert masked_data["phone"] == "XXXXXXX4567"
    
    def test_decrypt_non_encrypted_data(self):
        """Test decryption gracefully handles non-encrypted data."""
        manager = EncryptionManager()
        
        # Data that looks like it might be encrypted but isn't
        data = {
            "phone": "+15551234567",  # Plain phone number
            "email": "test@example.com"  # Plain email
        }
        
        # Should not raise exception and should return original data
        result = manager.decrypt_dict(data)
        assert result == data


class TestGlobalFunctions:
    """Test global utility functions."""
    
    def test_get_encryption_manager_singleton(self):
        """Test that get_encryption_manager returns singleton."""
        manager1 = get_encryption_manager()
        manager2 = get_encryption_manager()
        
        assert manager1 is manager2
    
    def test_encrypt_pii_data(self):
        """Test encrypt_pii_data convenience function."""
        data = {
            "phone": "+15551234567",
            "email": "test@example.com",
            "public_field": "public data"
        }
        
        encrypted_data = encrypt_pii_data(data)
        
        assert encrypted_data["phone"] != data["phone"]
        assert encrypted_data["email"] != data["email"]
        assert encrypted_data["public_field"] == data["public_field"]
    
    def test_decrypt_pii_data(self):
        """Test decrypt_pii_data convenience function."""
        data = {
            "phone": "+15551234567",
            "email": "test@example.com"
        }
        
        encrypted_data = encrypt_pii_data(data)
        decrypted_data = decrypt_pii_data(encrypted_data)
        
        assert decrypted_data == data
    
    def test_mask_pii_for_logging(self):
        """Test mask_pii_for_logging convenience function."""
        data = {
            "phone": "+15551234567",
            "email": "test@example.com"
        }
        
        masked_data = mask_pii_for_logging(data)
        
        assert masked_data["phone"] == "*******4567"
        assert masked_data["email"] == "t***@example.com"
    
    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        
        # Keys should be different
        assert key1 != key2
        
        # Keys should be valid base64
        import base64
        try:
            base64.urlsafe_b64decode(key1)
            base64.urlsafe_b64decode(key2)
        except Exception:
            pytest.fail("Generated keys are not valid base64")


class TestEncryptedField:
    """Test EncryptedField descriptor."""
    
    def test_encrypted_field_descriptor(self):
        """Test EncryptedField descriptor functionality."""
        
        class TestModel:
            def __init__(self):
                self._phone_encrypted = None
            
            phone = EncryptedField('phone')
        
        model = TestModel()
        
        # Test setting value
        model.phone = "+15551234567"
        assert model._phone_encrypted is not None
        assert model._phone_encrypted != "+15551234567"
        
        # Test getting value
        retrieved_phone = model.phone
        assert retrieved_phone == "+15551234567"
    
    def test_encrypted_field_none_value(self):
        """Test EncryptedField with None value."""
        
        class TestModel:
            def __init__(self):
                self._phone_encrypted = None
            
            phone = EncryptedField('phone')
        
        model = TestModel()
        
        # Test setting None
        model.phone = None
        assert model._phone_encrypted is None
        
        # Test getting None
        assert model.phone is None
    
    def test_encrypted_field_empty_string(self):
        """Test EncryptedField with empty string."""
        
        class TestModel:
            def __init__(self):
                self._phone_encrypted = None
            
            phone = EncryptedField('phone')
        
        model = TestModel()
        
        # Test setting empty string
        model.phone = ""
        assert model._phone_encrypted is None
        
        # Test getting empty string
        assert model.phone is None


class TestPIIFields:
    """Test PII_FIELDS constant."""
    
    def test_pii_fields_contains_expected(self):
        """Test that PII_FIELDS contains expected sensitive fields."""
        expected_fields = {
            'phone', 'caller_phone', 'email', 'first_name', 'last_name',
            'company', 'title', 'description', 'content', 'conversation_history',
            'extracted_data', 'conversation_summary'
        }
        
        assert expected_fields.issubset(PII_FIELDS)
    
    def test_pii_fields_is_set(self):
        """Test that PII_FIELDS is a set for efficient lookup."""
        assert isinstance(PII_FIELDS, set)