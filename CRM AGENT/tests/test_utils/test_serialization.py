"""
Unit tests for serialization utilities.
"""
import pytest
import json
from datetime import datetime, date
from pydantic import BaseModel

from app.utils.serialization import (
    CustomJSONEncoder, serialize_to_json, deserialize_from_json,
    serialize_for_database, deserialize_from_database,
    serialize_for_api_response, serialize_for_logging,
    batch_serialize, batch_deserialize, validate_and_serialize,
    safe_serialize
)
from app.schemas.base import BaseSchema
from app.schemas.call_session import CallSessionCreate


class TestModel(BaseSchema):
    """Test model for serialization tests."""
    name: str
    phone: str
    created_at: datetime


class TestCustomJSONEncoder:
    """Test CustomJSONEncoder class."""
    
    def test_datetime_encoding(self):
        """Test datetime encoding."""
        encoder = CustomJSONEncoder()
        dt = datetime(2024, 1, 1, 12, 0, 0)
        
        result = encoder.default(dt)
        assert result == "2024-01-01T12:00:00"
    
    def test_date_encoding(self):
        """Test date encoding."""
        encoder = CustomJSONEncoder()
        d = date(2024, 1, 1)
        
        result = encoder.default(d)
        assert result == "2024-01-01"
    
    def test_pydantic_model_encoding(self):
        """Test Pydantic model encoding."""
        encoder = CustomJSONEncoder()
        model = TestModel(
            name="John Doe",
            phone="+15551234567",
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        result = encoder.default(model)
        expected = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        assert result == expected
    
    def test_object_with_dict_encoding(self):
        """Test object with __dict__ encoding."""
        encoder = CustomJSONEncoder()
        
        class TestObject:
            def __init__(self):
                self.name = "test"
                self.value = 123
        
        obj = TestObject()
        result = encoder.default(obj)
        
        assert result == {"name": "test", "value": 123}


class TestSerializeToJson:
    """Test serialize_to_json function."""
    
    def test_serialize_pydantic_model(self):
        """Test serializing Pydantic model to JSON."""
        model = TestModel(
            name="John Doe",
            phone="+15551234567",
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        result = serialize_to_json(model, encrypt_pii=False)
        data = json.loads(result)
        
        assert data["name"] == "John Doe"
        assert data["phone"] == "+15551234567"
        assert data["created_at"] == "2024-01-01T12:00:00"
    
    def test_serialize_dict(self):
        """Test serializing dictionary to JSON."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        result = serialize_to_json(data, encrypt_pii=False)
        parsed = json.loads(result)
        
        assert parsed["name"] == "John Doe"
        assert parsed["phone"] == "+15551234567"
        assert parsed["created_at"] == "2024-01-01T12:00:00"
    
    def test_serialize_list(self):
        """Test serializing list to JSON."""
        models = [
            TestModel(name="John", phone="+15551234567", created_at=datetime(2024, 1, 1)),
            TestModel(name="Jane", phone="+15559876543", created_at=datetime(2024, 1, 2))
        ]
        
        result = serialize_to_json(models, encrypt_pii=False)
        data = json.loads(result)
        
        assert len(data) == 2
        assert data[0]["name"] == "John"
        assert data[1]["name"] == "Jane"
    
    def test_serialize_with_encryption(self):
        """Test serializing with PII encryption."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "public_field": "public data"
        }
        
        result = serialize_to_json(data, encrypt_pii=True)
        parsed = json.loads(result)
        
        # PII fields should be encrypted (different from original)
        assert parsed["phone"] != "+15551234567"
        assert parsed["name"] != "John Doe"
        
        # Non-PII fields should remain unchanged
        assert parsed["public_field"] == "public data"
    
    def test_serialize_pretty_format(self):
        """Test serializing with pretty formatting."""
        data = {"name": "John", "phone": "+15551234567"}
        
        result = serialize_to_json(data, encrypt_pii=False, pretty=True)
        
        # Pretty format should include indentation
        assert "  " in result
        assert "\n" in result
    
    def test_serialize_invalid_data(self):
        """Test serializing invalid data raises error."""
        # Create an object that can't be serialized
        class UnserializableObject:
            def __init__(self):
                self.circular_ref = self
        
        obj = UnserializableObject()
        
        with pytest.raises(ValueError, match="Failed to serialize data"):
            serialize_to_json(obj)


class TestDeserializeFromJson:
    """Test deserialize_from_json function."""
    
    def test_deserialize_to_pydantic_model(self):
        """Test deserializing JSON to Pydantic model."""
        json_data = json.dumps({
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": "2024-01-01T12:00:00"
        })
        
        result = deserialize_from_json(json_data, TestModel, decrypt_pii=False)
        
        assert isinstance(result, TestModel)
        assert result.name == "John Doe"
        assert result.phone == "+15551234567"
        assert result.created_at == datetime(2024, 1, 1, 12, 0, 0)
    
    def test_deserialize_with_decryption(self):
        """Test deserializing with PII decryption."""
        # First encrypt some data
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": "2024-01-01T12:00:00"
        }
        
        encrypted_json = serialize_to_json(data, encrypt_pii=True)
        result = deserialize_from_json(encrypted_json, TestModel, decrypt_pii=True)
        
        assert result.name == "John Doe"
        assert result.phone == "+15551234567"
    
    def test_deserialize_invalid_json(self):
        """Test deserializing invalid JSON raises error."""
        invalid_json = "{ invalid json }"
        
        with pytest.raises(ValueError, match="Invalid JSON format"):
            deserialize_from_json(invalid_json, TestModel)
    
    def test_deserialize_invalid_model_data(self):
        """Test deserializing data that doesn't match model."""
        json_data = json.dumps({"invalid_field": "value"})
        
        with pytest.raises(ValueError, match="Failed to deserialize data"):
            deserialize_from_json(json_data, TestModel)


class TestSerializeForDatabase:
    """Test serialize_for_database function."""
    
    def test_serialize_pydantic_model_for_db(self):
        """Test serializing Pydantic model for database."""
        model = TestModel(
            name="John Doe",
            phone="+15551234567",
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        result = serialize_for_database(model, encrypt_pii=False)
        
        assert result["name"] == "John Doe"
        assert result["phone"] == "+15551234567"
        assert result["created_at"] == "2024-01-01T12:00:00"
    
    def test_serialize_dict_for_db(self):
        """Test serializing dictionary for database."""
        data = {
            "name": "John Doe",
            "metadata": {"key": "value"},
            "tags": [{"name": "tag1"}, {"name": "tag2"}],
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        result = serialize_for_database(data, encrypt_pii=False)
        
        assert result["name"] == "John Doe"
        assert result["created_at"] == "2024-01-01T12:00:00"
        
        # Complex objects should be JSON strings
        assert isinstance(result["metadata"], str)
        assert isinstance(result["tags"], str)
        
        # Verify JSON parsing
        assert json.loads(result["metadata"]) == {"key": "value"}
        assert json.loads(result["tags"]) == [{"name": "tag1"}, {"name": "tag2"}]
    
    def test_serialize_for_db_with_encryption(self):
        """Test serializing for database with encryption."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "public_field": "public data"
        }
        
        result = serialize_for_database(data, encrypt_pii=True)
        
        # PII should be encrypted
        assert result["name"] != "John Doe"
        assert result["phone"] != "+15551234567"
        
        # Non-PII should remain unchanged
        assert result["public_field"] == "public data"


class TestDeserializeFromDatabase:
    """Test deserialize_from_database function."""
    
    def test_deserialize_from_db(self):
        """Test deserializing from database."""
        db_data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": "2024-01-01T12:00:00"
        }
        
        result = deserialize_from_database(db_data, TestModel, decrypt_pii=False)
        
        assert isinstance(result, TestModel)
        assert result.name == "John Doe"
        assert result.phone == "+15551234567"
    
    def test_deserialize_from_db_with_json_fields(self):
        """Test deserializing from database with JSON fields."""
        db_data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": "2024-01-01T12:00:00",
            "metadata": '{"key": "value"}',
            "tags": '[{"name": "tag1"}]'
        }
        
        # Create a model that accepts these fields
        class ExtendedTestModel(TestModel):
            metadata: dict = {}
            tags: list = []
        
        result = deserialize_from_database(db_data, ExtendedTestModel, decrypt_pii=False)
        
        assert result.metadata == {"key": "value"}
        assert result.tags == [{"name": "tag1"}]
    
    def test_deserialize_from_db_with_decryption(self):
        """Test deserializing from database with decryption."""
        # First serialize with encryption
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        encrypted_data = serialize_for_database(data, encrypt_pii=True)
        result = deserialize_from_database(encrypted_data, TestModel, decrypt_pii=True)
        
        assert result.name == "John Doe"
        assert result.phone == "+15551234567"


class TestSerializeForApiResponse:
    """Test serialize_for_api_response function."""
    
    def test_serialize_model_for_api(self):
        """Test serializing model for API response."""
        model = TestModel(
            name="John Doe",
            phone="+15551234567",
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        result = serialize_for_api_response(model, mask_pii=False)
        
        assert result["name"] == "John Doe"
        assert result["phone"] == "+15551234567"
    
    def test_serialize_for_api_with_masking(self):
        """Test serializing for API with PII masking."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "email": "john@example.com"
        }
        
        result = serialize_for_api_response(data, mask_pii=True)
        
        # PII should be masked
        assert result["phone"] == "*******4567"
        assert result["email"] == "j***@example.com"
        assert result["name"] == "********"
    
    def test_serialize_list_for_api(self):
        """Test serializing list for API response."""
        models = [
            TestModel(name="John", phone="+15551234567", created_at=datetime(2024, 1, 1)),
            TestModel(name="Jane", phone="+15559876543", created_at=datetime(2024, 1, 2))
        ]
        
        result = serialize_for_api_response(models, mask_pii=False)
        
        assert len(result) == 2
        assert result[0]["name"] == "John"
        assert result[1]["name"] == "Jane"


class TestSerializeForLogging:
    """Test serialize_for_logging function."""
    
    def test_serialize_for_logging(self):
        """Test serializing for logging with PII masking."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "email": "john@example.com",
            "public_field": "public data"
        }
        
        result = serialize_for_logging(data)
        
        # PII should be masked
        assert result["phone"] == "*******4567"
        assert result["email"] == "j***@example.com"
        assert result["name"] == "********"
        
        # Non-PII should remain unchanged
        assert result["public_field"] == "public data"


class TestBatchSerialization:
    """Test batch serialization functions."""
    
    def test_batch_serialize_json(self):
        """Test batch serialization to JSON."""
        models = [
            TestModel(name="John", phone="+15551234567", created_at=datetime(2024, 1, 1)),
            TestModel(name="Jane", phone="+15559876543", created_at=datetime(2024, 1, 2))
        ]
        
        results = batch_serialize(models, target_format='json', encrypt_pii=False)
        
        assert len(results) == 2
        
        # Each result should be a JSON string
        for result in results:
            assert isinstance(result, str)
            data = json.loads(result)
            assert "name" in data
            assert "phone" in data
    
    def test_batch_serialize_database(self):
        """Test batch serialization for database."""
        models = [
            TestModel(name="John", phone="+15551234567", created_at=datetime(2024, 1, 1)),
            TestModel(name="Jane", phone="+15559876543", created_at=datetime(2024, 1, 2))
        ]
        
        results = batch_serialize(models, target_format='database', encrypt_pii=False)
        
        assert len(results) == 2
        
        # Each result should be a dictionary
        for result in results:
            assert isinstance(result, dict)
            assert "name" in result
            assert "phone" in result
    
    def test_batch_serialize_with_error(self):
        """Test batch serialization handles errors gracefully."""
        # Mix valid and invalid items
        items = [
            TestModel(name="John", phone="+15551234567", created_at=datetime(2024, 1, 1)),
            {"invalid": "data that will cause error"}
        ]
        
        results = batch_serialize(items, target_format='json', encrypt_pii=False)
        
        # Should have one successful result (errors are skipped)
        assert len(results) == 1
    
    def test_batch_deserialize_json(self):
        """Test batch deserialization from JSON."""
        json_items = [
            json.dumps({"name": "John", "phone": "+15551234567", "created_at": "2024-01-01T00:00:00"}),
            json.dumps({"name": "Jane", "phone": "+15559876543", "created_at": "2024-01-02T00:00:00"})
        ]
        
        results = batch_deserialize(json_items, TestModel, source_format='json', decrypt_pii=False)
        
        assert len(results) == 2
        assert all(isinstance(r, TestModel) for r in results)
        assert results[0].name == "John"
        assert results[1].name == "Jane"
    
    def test_batch_deserialize_with_error(self):
        """Test batch deserialization handles errors gracefully."""
        json_items = [
            json.dumps({"name": "John", "phone": "+15551234567", "created_at": "2024-01-01T00:00:00"}),
            "invalid json"
        ]
        
        results = batch_deserialize(json_items, TestModel, source_format='json', decrypt_pii=False)
        
        # Should have one successful result (errors are skipped)
        assert len(results) == 1
        assert results[0].name == "John"


class TestValidateAndSerialize:
    """Test validate_and_serialize function."""
    
    def test_validate_and_serialize_valid_data(self):
        """Test validating and serializing valid data."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        result = validate_and_serialize(data, TestModel, target_format='json', encrypt_pii=False)
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["name"] == "John Doe"
        assert parsed["phone"] == "+15551234567"
    
    def test_validate_and_serialize_invalid_data(self):
        """Test validating and serializing invalid data."""
        data = {
            "invalid_field": "value"
        }
        
        with pytest.raises(ValueError, match="Failed to validate and serialize data"):
            validate_and_serialize(data, TestModel, target_format='json')
    
    def test_validate_and_serialize_database_format(self):
        """Test validating and serializing for database format."""
        data = {
            "name": "John Doe",
            "phone": "+15551234567",
            "created_at": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        result = validate_and_serialize(data, TestModel, target_format='database', encrypt_pii=False)
        
        assert isinstance(result, dict)
        assert result["name"] == "John Doe"
        assert result["phone"] == "+15551234567"


class TestSafeSerialization:
    """Test safe_serialize function."""
    
    def test_safe_serialize_pydantic_model(self):
        """Test safe serialization of Pydantic model."""
        model = TestModel(
            name="John Doe",
            phone="+15551234567",
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        result = safe_serialize(model)
        
        assert isinstance(result, dict)
        assert result["name"] == "John Doe"
    
    def test_safe_serialize_basic_types(self):
        """Test safe serialization of basic types."""
        assert safe_serialize("string") == "string"
        assert safe_serialize(123) == 123
        assert safe_serialize([1, 2, 3]) == [1, 2, 3]
        assert safe_serialize({"key": "value"}) == {"key": "value"}
        assert safe_serialize(True) is True
    
    def test_safe_serialize_object_with_dict(self):
        """Test safe serialization of object with __dict__."""
        class TestObject:
            def __init__(self):
                self.name = "test"
                self.value = 123
        
        obj = TestObject()
        result = safe_serialize(obj)
        
        assert result == {"name": "test", "value": 123}
    
    def test_safe_serialize_fallback(self):
        """Test safe serialization with fallback."""
        class UnserializableObject:
            def __init__(self):
                self.circular_ref = self
        
        obj = UnserializableObject()
        result = safe_serialize(obj, fallback_value="fallback")
        
        # Should return string representation or fallback
        assert result is not None
    
    def test_safe_serialize_none_fallback(self):
        """Test safe serialization with None fallback."""
        class UnserializableObject:
            def __init__(self):
                self.circular_ref = self
        
        obj = UnserializableObject()
        result = safe_serialize(obj, fallback_value=None)
        
        # Should return string representation or None
        assert result is not None  # String representation should work