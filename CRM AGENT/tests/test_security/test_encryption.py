"""
Tests for encryption and data protection functionality.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet

from app.security.encryption import (
    EncryptionManager,
    get_encryption_manager,
    encrypt_pii_data,
    decrypt_pii_data,
    mask_pii_for_logging,
    generate_encryption_key,
    encrypt_field,
    decrypt_field,
    EncryptedField,
    PII_FIELDS
)


class TestEncryptionManager:
    """Test encryption manager functionality."""
    
    def test_init_with_valid_key(self):
        """Test initialization with valid encryption key."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        assert len(manager.keys) == 1
        assert len(manager.key_ids) == 1
        assert manager.primary_key_id == "key_0"
    
    def test_init_with_multiple_keys(self):
        """Test initialization with multiple keys for rotation."""
        keys = [Fernet.generate_key().decode('utf-8') for _ in range(3)]
        manager = EncryptionManager(keys)
        
        assert len(manager.keys) == 3
        assert len(manager.key_ids) == 3
        assert manager.primary_key_id == "key_0"
    
    def test_init_with_invalid_key(self):
        """Test initialization with invalid key raises error."""
        with pytest.raises(ValueError, match="Invalid encryption key format"):
            EncryptionManager(["invalid-key"])
    
    def test_encrypt_decrypt_string(self):
        """Test string encryption and decryption."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        plaintext = "sensitive data"
        encrypted = manager.encrypt_string(plaintext)
        decrypted = manager.decrypt_string(encrypted)
        
        assert encrypted != plaintext
        assert decrypted == plaintext
        assert "key_0:" in encrypted  # Key ID prefix
    
    def test_encrypt_decrypt_empty_string(self):
        """Test encryption of empty strings."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        assert manager.encrypt_string("") == ""
        assert manager.decrypt_string("") == ""
        assert manager.encrypt_string(None) is None
        assert manager.decrypt_string(None) is None
    
    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-1234",
            "non_pii": "public data"
        }
        
        encrypted = manager.encrypt_dict(data)
        decrypted = manager.decrypt_dict(encrypted)
        
        # PII fields should be encrypted
        assert encrypted["first_name"] != data["first_name"]
        assert encrypted["email"] != data["email"]
        
        # Non-PII fields should remain unchanged
        assert encrypted["non_pii"] == data["non_pii"]
        
        # Decryption should restore original data
        assert decrypted["first_name"] == data["first_name"]
        assert decrypted["email"] == data["email"]
        
        # Should include encryption metadata
        assert "_encryption_metadata" in encrypted
        assert "encrypted_fields" in encrypted["_encryption_metadata"]
    
    def test_encrypt_decrypt_nested_dict(self):
        """Test encryption of nested dictionaries."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        data = {
            "contact": {
                "first_name": "Jane",
                "email": "jane@example.com"
            },
            "metadata": {
                "source": "web"
            }
        }
        
        encrypted = manager.encrypt_dict(data)
        decrypted = manager.decrypt_dict(encrypted)
        
        assert encrypted["contact"]["first_name"] != data["contact"]["first_name"]
        assert decrypted["contact"]["first_name"] == data["contact"]["first_name"]
        assert encrypted["metadata"]["source"] == data["metadata"]["source"]
    
    def test_encrypt_decrypt_list(self):
        """Test encryption of lists."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        data = {
            "conversation_history": [
                "Hello, my name is John",
                "I'm interested in your product"
            ]
        }
        
        encrypted = manager.encrypt_dict(data)
        decrypted = manager.decrypt_dict(encrypted)
        
        assert encrypted["conversation_history"][0] != data["conversation_history"][0]
        assert decrypted["conversation_history"][0] == data["conversation_history"][0]
    
    def test_key_rotation(self):
        """Test key rotation functionality."""
        old_key = Fernet.generate_key().decode('utf-8')
        new_key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([old_key])
        
        # Encrypt with old key
        plaintext = "test data"
        encrypted_old = manager.encrypt_string(plaintext)
        
        # Rotate key
        success = manager.rotate_key(new_key)
        assert success
        assert len(manager.keys) == 2
        
        # Should be able to decrypt old data
        decrypted = manager.decrypt_string(encrypted_old)
        assert decrypted == plaintext
        
        # New encryptions should use new key
        encrypted_new = manager.encrypt_string(plaintext)
        assert encrypted_new != encrypted_old
    
    def test_hash_for_indexing(self):
        """Test hashing for indexing purposes."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        value = "john@example.com"
        hash1 = manager.hash_for_indexing(value)
        hash2 = manager.hash_for_indexing(value)
        
        assert hash1 == hash2  # Consistent hashing
        assert hash1 != value  # Different from original
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_mask_pii(self):
        """Test PII masking for logging."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567",
            "ssn": "123-45-6789",
            "non_pii": "public data"
        }
        
        masked = manager.mask_pii(data)
        
        # Names should be partially masked
        assert masked["first_name"] == "J**n"
        assert masked["last_name"] == "D*e"
        
        # Email should show first letter and domain
        assert masked["email"] == "j*******@example.com"
        
        # Phone should show last 4 digits
        assert masked["phone"] == "*******4567"
        
        # SSN should be completely masked
        assert masked["ssn"] == "********"
        
        # Non-PII should remain unchanged
        assert masked["non_pii"] == "public data"
    
    def test_get_key_info(self):
        """Test key information retrieval."""
        keys = [Fernet.generate_key().decode('utf-8') for _ in range(2)]
        manager = EncryptionManager(keys)
        
        info = manager.get_key_info()
        
        assert info["total_keys"] == 2
        assert info["primary_key_id"] == "key_0"
        assert len(info["key_ids"]) == 2
        assert info["rotation_supported"] is True


class TestEncryptionUtilities:
    """Test encryption utility functions."""
    
    @pytest.mark.asyncio
    async def test_encrypt_decrypt_pii_data(self):
        """Test PII data encryption utilities."""
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "public_info": "not sensitive"
        }
        
        encrypted = await encrypt_pii_data(data)
        decrypted = await decrypt_pii_data(encrypted)
        
        assert encrypted["first_name"] != data["first_name"]
        assert decrypted["first_name"] == data["first_name"]
        assert encrypted["public_info"] == data["public_info"]
    
    @pytest.mark.asyncio
    async def test_encrypt_decrypt_field(self):
        """Test single field encryption utilities."""
        value = "sensitive information"
        
        encrypted = await encrypt_field(value)
        decrypted = await decrypt_field(encrypted)
        
        assert encrypted != value
        assert decrypted == value
    
    def test_mask_pii_for_logging_utility(self):
        """Test PII masking utility function."""
        data = {
            "email": "test@example.com",
            "phone": "555-1234"
        }
        
        masked = mask_pii_for_logging(data)
        
        assert masked["email"] == "t***@example.com"
        assert masked["phone"] == "****1234"
    
    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        key = generate_encryption_key()
        
        assert isinstance(key, str)
        assert len(key) == 44  # Base64 encoded 32-byte key
        
        # Should be valid Fernet key
        Fernet(key.encode())


class TestEncryptedField:
    """Test encrypted field descriptor."""
    
    def test_encrypted_field_descriptor(self):
        """Test encrypted field descriptor functionality."""
        
        class TestModel:
            def __init__(self):
                self.name = EncryptedField("name")
        
        model = TestModel()
        
        # Set value
        model.name = "John Doe"
        
        # Should have encrypted storage
        assert hasattr(model, "_name_encrypted")
        assert model._name_encrypted is not None
        assert model._name_encrypted != "John Doe"
        
        # Should decrypt when accessed
        assert model.name == "John Doe"
    
    def test_encrypted_field_empty_value(self):
        """Test encrypted field with empty values."""
        
        class TestModel:
            def __init__(self):
                self.name = EncryptedField("name")
        
        model = TestModel()
        
        # Set empty value
        model.name = ""
        assert model._name_encrypted is None
        assert model.name is None
        
        # Set None value
        model.name = None
        assert model._name_encrypted is None
        assert model.name is None


class TestEncryptionIntegration:
    """Test encryption integration scenarios."""
    
    def test_environment_key_loading(self):
        """Test loading encryption keys from environment."""
        test_key = Fernet.generate_key().decode('utf-8')
        
        with patch.dict(os.environ, {'ENCRYPTION_KEY': test_key}):
            manager = EncryptionManager()
            assert len(manager.keys) >= 1
    
    def test_multiple_environment_keys(self):
        """Test loading multiple keys from environment."""
        key1 = Fernet.generate_key().decode('utf-8')
        key2 = Fernet.generate_key().decode('utf-8')
        
        env_vars = {
            'ENCRYPTION_KEY': key1,
            'ENCRYPTION_KEY_1': key2
        }
        
        with patch.dict(os.environ, env_vars):
            manager = EncryptionManager()
            assert len(manager.keys) >= 2
    
    def test_password_based_key_derivation(self):
        """Test key derivation from password."""
        password = "test-password-123"
        
        with patch.dict(os.environ, {'ENCRYPTION_KEY': password}):
            manager = EncryptionManager()
            
            # Should work with derived key
            plaintext = "test data"
            encrypted = manager.encrypt_string(plaintext)
            decrypted = manager.decrypt_string(encrypted)
            
            assert decrypted == plaintext
    
    def test_encryption_error_handling(self):
        """Test encryption error handling."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        # Test decryption of invalid data
        with pytest.raises(ValueError, match="Failed to decrypt data"):
            manager.decrypt_string("invalid-encrypted-data")
    
    def test_concurrent_encryption_operations(self):
        """Test thread safety of encryption operations."""
        import threading
        import time
        
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        results = []
        errors = []
        
        def encrypt_decrypt_worker(worker_id):
            try:
                for i in range(10):
                    plaintext = f"worker-{worker_id}-data-{i}"
                    encrypted = manager.encrypt_string(plaintext)
                    decrypted = manager.decrypt_string(encrypted)
                    results.append((worker_id, i, decrypted == plaintext))
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=encrypt_decrypt_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Encryption errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations
        assert all(success for _, _, success in results)
    
    def test_large_data_encryption(self):
        """Test encryption of large data sets."""
        key = Fernet.generate_key().decode('utf-8')
        manager = EncryptionManager([key])
        
        # Create large data structure
        large_data = {
            f"field_{i}": f"sensitive_data_{i}" * 100
            for i in range(100)
        }
        
        # Should handle large data without issues
        encrypted = manager.encrypt_dict(large_data, fields_to_encrypt=set(large_data.keys()))
        decrypted = manager.decrypt_dict(encrypted, fields_to_decrypt=set(large_data.keys()))
        
        assert len(encrypted) == len(large_data)
        assert len(decrypted) == len(large_data)
        
        # Verify a few fields
        for i in range(0, 100, 10):
            field = f"field_{i}"
            assert decrypted[field] == large_data[field]
            assert encrypted[field] != large_data[field]


@pytest.fixture
def sample_pii_data():
    """Sample PII data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "ssn": "123-45-6789",
        "address": "123 Main St, Anytown, USA",
        "conversation_history": [
            "Hello, I'm interested in your product",
            "My budget is around $10,000"
        ],
        "metadata": {
            "source": "website",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    }


@pytest.fixture
def encryption_manager():
    """Encryption manager fixture."""
    key = Fernet.generate_key().decode('utf-8')
    return EncryptionManager([key])