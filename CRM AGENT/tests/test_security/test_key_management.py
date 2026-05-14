"""
Tests for key management functionality.
"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from app.security.key_management import (
    KeyManager,
    get_key_manager,
    rotate_encryption_key,
    validate_key_strength,
    generate_secure_key,
    derive_key_from_password
)


class TestKeyManager:
    """Test key manager functionality."""
    
    def test_init_with_temp_store(self):
        """Test initialization with temporary key store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            assert manager.key_store_path == store_path
            assert isinstance(manager.key_metadata, dict)
            assert "keys" in manager.key_metadata
            assert "current_key_id" in manager.key_metadata
    
    def test_generate_key(self):
        """Test key generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            key = manager.generate_key("test_key")
            
            assert isinstance(key, str)
            assert len(key) == 44  # Base64 encoded 32-byte key
            assert "test_key" in manager.key_metadata["keys"]
            assert manager.key_metadata["current_key_id"] == "test_key"
            
            # Should be valid Fernet key
            Fernet(key.encode())
    
    def test_generate_key_auto_id(self):
        """Test key generation with automatic ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            key = manager.generate_key()
            
            assert isinstance(key, str)
            assert len(manager.key_metadata["keys"]) == 1
            
            # Key ID should be auto-generated
            key_id = list(manager.key_metadata["keys"].keys())[0]
            assert key_id.startswith("key_")
    
    def test_rotate_key(self):
        """Test key rotation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # Generate initial key
            old_key = manager.generate_key("old_key")
            old_key_id = manager.key_metadata["current_key_id"]
            
            # Rotate key
            new_key_id, new_key = manager.rotate_key()
            
            assert new_key_id != old_key_id
            assert new_key != old_key
            assert manager.key_metadata["current_key_id"] == new_key_id
            
            # Old key should be marked as rotated
            assert manager.key_metadata["keys"][old_key_id]["status"] == "rotated"
            assert "rotated_at" in manager.key_metadata["keys"][old_key_id]
            
            # Should have rotation history
            assert len(manager.key_metadata["rotation_history"]) == 1
            history_entry = manager.key_metadata["rotation_history"][0]
            assert history_entry["old_key_id"] == old_key_id
            assert history_entry["new_key_id"] == new_key_id
    
    def test_rotate_key_with_provided_key(self):
        """Test key rotation with provided key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # Generate initial key
            manager.generate_key("old_key")
            
            # Rotate with provided key
            new_key = Fernet.generate_key().decode('utf-8')
            new_key_id, returned_key = manager.rotate_key(new_key)
            
            assert returned_key == new_key
            assert manager.key_metadata["current_key_id"] == new_key_id
    
    def test_validate_key_strength(self):
        """Test key strength validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # Valid Fernet key
            valid_key = Fernet.generate_key().decode('utf-8')
            assert manager.validate_key_strength(valid_key) is True
            
            # Invalid keys
            assert manager.validate_key_strength("too_short") is False
            assert manager.validate_key_strength("") is False
            assert manager.validate_key_strength("not_base64_encoded!@#") is False
    
    def test_calculate_entropy(self):
        """Test entropy calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # High entropy data (random bytes)
            high_entropy = os.urandom(32)
            entropy = manager._calculate_entropy(high_entropy)
            assert entropy > 6.0
            
            # Low entropy data (repeated bytes)
            low_entropy = b'a' * 32
            entropy = manager._calculate_entropy(low_entropy)
            assert entropy < 1.0
            
            # Empty data
            assert manager._calculate_entropy(b'') == 0
    
    def test_get_key_info(self):
        """Test key information retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            manager.generate_key("test_key")
            info = manager.get_key_info("test_key")
            
            assert info is not None
            assert info["algorithm"] == "Fernet"
            assert info["key_length"] == 32
            assert info["status"] == "active"
            assert info["usage_count"] == 0
            assert "created_at" in info
    
    def test_list_keys(self):
        """Test key listing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # Generate multiple keys
            manager.generate_key("key1")
            manager.generate_key("key2")
            manager.rotate_key()  # This will mark key1 as rotated
            
            # List active keys only
            active_keys = manager.list_keys(include_rotated=False)
            assert len(active_keys) >= 1
            
            # List all keys
            all_keys = manager.list_keys(include_rotated=True)
            assert len(all_keys) >= 2
    
    def test_mark_key_used(self):
        """Test key usage tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            manager.generate_key("test_key")
            
            # Initially unused
            info = manager.get_key_info("test_key")
            assert info["usage_count"] == 0
            assert info["last_used"] is None
            
            # Mark as used
            manager.mark_key_used("test_key")
            
            info = manager.get_key_info("test_key")
            assert info["usage_count"] == 1
            assert info["last_used"] is not None
    
    def test_should_rotate_key(self):
        """Test key rotation recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            manager.generate_key("test_key")
            
            # New key should not need rotation
            assert manager.should_rotate_key("test_key") is False
            
            # Simulate old key
            old_date = (datetime.utcnow() - timedelta(days=100)).isoformat()
            manager.key_metadata["keys"]["test_key"]["created_at"] = old_date
            assert manager.should_rotate_key("test_key") is True
            
            # Simulate high usage
            manager.key_metadata["keys"]["test_key"]["created_at"] = datetime.utcnow().isoformat()
            manager.key_metadata["keys"]["test_key"]["usage_count"] = 1500000
            assert manager.should_rotate_key("test_key") is True
    
    def test_cleanup_old_keys(self):
        """Test cleanup of old rotated keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            # Generate and rotate keys
            manager.generate_key("old_key")
            manager.rotate_key()
            
            # Simulate old rotation
            old_date = (datetime.utcnow() - timedelta(days=400)).isoformat()
            manager.key_metadata["keys"]["old_key"]["rotated_at"] = old_date
            
            initial_count = len(manager.key_metadata["keys"])
            
            # Cleanup with 365 day retention
            manager.cleanup_old_keys(retention_days=365)
            
            # Old key should be removed
            assert len(manager.key_metadata["keys"]) < initial_count
            assert "old_key" not in manager.key_metadata["keys"]
    
    def test_get_rotation_history(self):
        """Test rotation history retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            manager.generate_key("key1")
            manager.rotate_key()
            manager.rotate_key()
            
            history = manager.get_rotation_history()
            assert len(history) == 2
            
            for entry in history:
                assert "timestamp" in entry
                assert "old_key_id" in entry
                assert "new_key_id" in entry
                assert "reason" in entry
    
    def test_export_key_metadata(self):
        """Test key metadata export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            manager = KeyManager(store_path)
            
            manager.generate_key("test_key")
            manager.rotate_key()
            
            exported = manager.export_key_metadata()
            
            assert "keys" in exported
            assert "current_key_id" in exported
            assert "rotation_history" in exported
            
            # Should not contain sensitive data
            for key_info in exported["keys"].values():
                assert "key_data" not in key_info
                assert "secret" not in key_info
    
    def test_persistence(self):
        """Test key metadata persistence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "test_keys.json")
            
            # Create manager and generate key
            manager1 = KeyManager(store_path)
            key_id = manager1.generate_key("persistent_key")
            
            # Create new manager instance
            manager2 = KeyManager(store_path)
            
            # Should load existing metadata
            assert "persistent_key" in manager2.key_metadata["keys"]
            assert manager2.key_metadata["current_key_id"] == "persistent_key"
    
    def test_corrupted_metadata_handling(self):
        """Test handling of corrupted metadata file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "corrupted_keys.json")
            
            # Create corrupted file
            with open(store_path, 'w') as f:
                f.write("invalid json content")
            
            # Should handle gracefully
            manager = KeyManager(store_path)
            assert isinstance(manager.key_metadata, dict)
            assert "keys" in manager.key_metadata


class TestKeyManagementUtilities:
    """Test key management utility functions."""
    
    def test_rotate_encryption_key(self):
        """Test key rotation utility."""
        with patch('app.security.key_management._key_manager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.rotate_key.return_value = ("new_key_id", "new_key")
            mock_manager = mock_instance
            
            # Mock the get_key_manager function
            with patch('app.security.key_management.get_key_manager', return_value=mock_instance):
                key_id, key = rotate_encryption_key("test_key")
                
                assert key_id == "new_key_id"
                assert key == "new_key"
                mock_instance.rotate_key.assert_called_once_with("test_key")
    
    def test_validate_key_strength_utility(self):
        """Test key strength validation utility."""
        valid_key = Fernet.generate_key().decode('utf-8')
        
        assert validate_key_strength(valid_key) is True
        assert validate_key_strength("invalid") is False
    
    def test_generate_secure_key(self):
        """Test secure key generation utility."""
        with patch('app.security.key_management._key_manager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.generate_key.return_value = "generated_key"
            mock_manager = mock_instance
            
            with patch('app.security.key_management.get_key_manager', return_value=mock_instance):
                key = generate_secure_key()
                
                assert key == "generated_key"
                mock_instance.generate_key.assert_called_once()
    
    def test_derive_key_from_password(self):
        """Test key derivation from password."""
        password = "test_password_123"
        
        key1 = derive_key_from_password(password)
        key2 = derive_key_from_password(password)
        
        # Should be consistent
        assert key1 == key2
        
        # Should be valid Fernet key
        assert len(key1) == 44
        Fernet(key1.encode())
        
        # Different passwords should produce different keys
        key3 = derive_key_from_password("different_password")
        assert key3 != key1
    
    def test_derive_key_with_custom_salt(self):
        """Test key derivation with custom salt."""
        password = "test_password"
        salt1 = b"salt1"
        salt2 = b"salt2"
        
        key1 = derive_key_from_password(password, salt1)
        key2 = derive_key_from_password(password, salt2)
        
        # Different salts should produce different keys
        assert key1 != key2
        
        # Same salt should produce same key
        key3 = derive_key_from_password(password, salt1)
        assert key1 == key3


class TestKeyManagerIntegration:
    """Test key manager integration scenarios."""
    
    def test_concurrent_key_operations(self):
        """Test thread safety of key operations."""
        import threading
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "concurrent_keys.json")
            manager = KeyManager(store_path)
            
            results = []
            errors = []
            
            def key_worker(worker_id):
                try:
                    for i in range(5):
                        key = manager.generate_key(f"worker_{worker_id}_key_{i}")
                        manager.mark_key_used(f"worker_{worker_id}_key_{i}")
                        results.append((worker_id, i, key is not None))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((worker_id, str(e)))
            
            # Start multiple threads
            threads = []
            for i in range(3):
                thread = threading.Thread(target=key_worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Check results
            assert len(errors) == 0, f"Key operation errors: {errors}"
            assert len(results) == 15  # 3 workers * 5 operations
            assert all(success for _, _, success in results)
    
    def test_key_manager_with_environment_config(self):
        """Test key manager with environment configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "env_keys.json")
            
            with patch.dict(os.environ, {'KEY_STORE_PATH': store_path}):
                manager = KeyManager()
                
                # Should use environment path
                assert manager.key_store_path == store_path
    
    def test_key_rotation_workflow(self):
        """Test complete key rotation workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = os.path.join(temp_dir, "rotation_keys.json")
            manager = KeyManager(store_path)
            
            # Initial setup
            key1 = manager.generate_key("initial_key")
            assert manager.key_metadata["current_key_id"] == "initial_key"
            
            # Simulate usage
            for _ in range(10):
                manager.mark_key_used("initial_key")
            
            # Check if rotation is needed (should be false for new key)
            assert manager.should_rotate_key("initial_key") is False
            
            # Force rotation
            key_id2, key2 = manager.rotate_key()
            assert key2 != key1
            assert manager.key_metadata["current_key_id"] == key_id2
            
            # Old key should still be available for decryption
            old_key_info = manager.get_key_info("initial_key")
            assert old_key_info["status"] == "rotated"
            
            # Rotation history should be updated
            history = manager.get_rotation_history()
            assert len(history) == 1
            assert history[0]["old_key_id"] == "initial_key"
            assert history[0]["new_key_id"] == key_id2


@pytest.fixture
def temp_key_store():
    """Temporary key store fixture."""
    with tempfile.TemporaryDirectory() as temp_dir:
        store_path = os.path.join(temp_dir, "test_keys.json")
        yield store_path


@pytest.fixture
def key_manager(temp_key_store):
    """Key manager fixture."""
    return KeyManager(temp_key_store)