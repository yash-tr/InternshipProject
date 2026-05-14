"""
Serialization and deserialization utilities for data models.
Handles conversion between Pydantic models, database models, and API responses.
"""
import json
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
import logging

from .encryption import encrypt_pii_data, decrypt_pii_data, mask_pii_for_logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling datetime and other special types."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif hasattr(obj, 'dict'):
            # Handle Pydantic models
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            # Handle other objects with __dict__
            return obj.__dict__
        return super().default(obj)


def serialize_to_json(data: Union[BaseModel, Dict, List], encrypt_pii: bool = True, pretty: bool = False) -> str:
    """
    Serialize data to JSON string with optional PII encryption.
    
    Args:
        data: Data to serialize
        encrypt_pii: Whether to encrypt PII fields before serialization
        pretty: Whether to format JSON with indentation
        
    Returns:
        JSON string representation of the data
    """
    try:
        # Convert Pydantic models to dict
        if isinstance(data, BaseModel):
            data_dict = data.dict()
        elif isinstance(data, list):
            data_dict = [item.dict() if isinstance(item, BaseModel) else item for item in data]
        else:
            data_dict = data
        
        # Encrypt PII fields if requested
        if encrypt_pii and isinstance(data_dict, dict):
            data_dict = encrypt_pii_data(data_dict)
        elif encrypt_pii and isinstance(data_dict, list):
            data_dict = [encrypt_pii_data(item) if isinstance(item, dict) else item for item in data_dict]
        
        # Serialize to JSON
        indent = 2 if pretty else None
        return json.dumps(data_dict, cls=CustomJSONEncoder, indent=indent, ensure_ascii=False)
    
    except Exception as e:
        logger.error(f"Serialization failed: {e}")
        raise ValueError(f"Failed to serialize data: {e}")


def deserialize_from_json(json_str: str, model_class: Type[T], decrypt_pii: bool = True) -> T:
    """
    Deserialize JSON string to Pydantic model with optional PII decryption.
    
    Args:
        json_str: JSON string to deserialize
        model_class: Pydantic model class to deserialize to
        decrypt_pii: Whether to decrypt PII fields after deserialization
        
    Returns:
        Instance of the specified Pydantic model
    """
    try:
        # Parse JSON
        data_dict = json.loads(json_str)
        
        # Decrypt PII fields if requested
        if decrypt_pii and isinstance(data_dict, dict):
            data_dict = decrypt_pii_data(data_dict)
        
        # Create model instance
        return model_class(**data_dict)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        logger.error(f"Deserialization failed: {e}")
        raise ValueError(f"Failed to deserialize data: {e}")


def serialize_for_database(data: Union[BaseModel, Dict], encrypt_pii: bool = True) -> Dict[str, Any]:
    """
    Serialize data for database storage with PII encryption.
    
    Args:
        data: Data to serialize
        encrypt_pii: Whether to encrypt PII fields
        
    Returns:
        Dictionary suitable for database storage
    """
    try:
        # Convert to dict if Pydantic model
        if isinstance(data, BaseModel):
            data_dict = data.dict(exclude_unset=True, exclude_none=True)
        else:
            data_dict = data.copy()
        
        # Encrypt PII fields
        if encrypt_pii:
            data_dict = encrypt_pii_data(data_dict)
        
        # Convert datetime objects to ISO strings for JSON fields
        for key, value in data_dict.items():
            if isinstance(value, datetime):
                data_dict[key] = value.isoformat()
            elif isinstance(value, date):
                data_dict[key] = value.isoformat()
            elif isinstance(value, dict):
                data_dict[key] = json.dumps(value, cls=CustomJSONEncoder)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                data_dict[key] = json.dumps(value, cls=CustomJSONEncoder)
        
        return data_dict
    
    except Exception as e:
        logger.error(f"Database serialization failed: {e}")
        raise ValueError(f"Failed to serialize for database: {e}")


def deserialize_from_database(data: Dict[str, Any], model_class: Type[T], decrypt_pii: bool = True) -> T:
    """
    Deserialize data from database with PII decryption.
    
    Args:
        data: Database record data
        model_class: Pydantic model class to deserialize to
        decrypt_pii: Whether to decrypt PII fields
        
    Returns:
        Instance of the specified Pydantic model
    """
    try:
        data_dict = data.copy()
        
        # Parse JSON fields back to objects
        for key, value in data_dict.items():
            if isinstance(value, str):
                # Try to parse as JSON if it looks like JSON
                if value.startswith(('{', '[')):
                    try:
                        data_dict[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # Not JSON, keep as string
                        pass
        
        # Decrypt PII fields
        if decrypt_pii:
            data_dict = decrypt_pii_data(data_dict)
        
        # Create model instance
        return model_class(**data_dict)
    
    except Exception as e:
        logger.error(f"Database deserialization failed: {e}")
        raise ValueError(f"Failed to deserialize from database: {e}")


def serialize_for_api_response(data: Union[BaseModel, Dict, List], mask_pii: bool = False) -> Dict[str, Any]:
    """
    Serialize data for API responses with optional PII masking.
    
    Args:
        data: Data to serialize
        mask_pii: Whether to mask PII fields for security
        
    Returns:
        Dictionary suitable for API response
    """
    try:
        # Convert to dict
        if isinstance(data, BaseModel):
            data_dict = data.dict()
        elif isinstance(data, list):
            data_dict = [item.dict() if isinstance(item, BaseModel) else item for item in data]
        else:
            data_dict = data
        
        # Mask PII fields if requested
        if mask_pii:
            if isinstance(data_dict, dict):
                data_dict = mask_pii_for_logging(data_dict)
            elif isinstance(data_dict, list):
                data_dict = [mask_pii_for_logging(item) if isinstance(item, dict) else item for item in data_dict]
        
        return data_dict
    
    except Exception as e:
        logger.error(f"API response serialization failed: {e}")
        raise ValueError(f"Failed to serialize for API response: {e}")


def serialize_for_logging(data: Union[BaseModel, Dict, List]) -> Dict[str, Any]:
    """
    Serialize data for logging with PII masking for security.
    
    Args:
        data: Data to serialize
        
    Returns:
        Dictionary with masked PII suitable for logging
    """
    return serialize_for_api_response(data, mask_pii=True)


def batch_serialize(items: List[Union[BaseModel, Dict]], 
                   target_format: str = 'json',
                   encrypt_pii: bool = True) -> List[Union[str, Dict]]:
    """
    Serialize a batch of items efficiently.
    
    Args:
        items: List of items to serialize
        target_format: Target format ('json', 'database', 'api')
        encrypt_pii: Whether to encrypt PII fields
        
    Returns:
        List of serialized items
    """
    serialized_items = []
    
    for item in items:
        try:
            if target_format == 'json':
                serialized_items.append(serialize_to_json(item, encrypt_pii=encrypt_pii))
            elif target_format == 'database':
                serialized_items.append(serialize_for_database(item, encrypt_pii=encrypt_pii))
            elif target_format == 'api':
                serialized_items.append(serialize_for_api_response(item, mask_pii=False))
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
        except Exception as e:
            logger.error(f"Failed to serialize item {item}: {e}")
            # Continue with other items, but log the error
            continue
    
    return serialized_items


def batch_deserialize(items: List[Union[str, Dict]], 
                     model_class: Type[T],
                     source_format: str = 'json',
                     decrypt_pii: bool = True) -> List[T]:
    """
    Deserialize a batch of items efficiently.
    
    Args:
        items: List of items to deserialize
        model_class: Pydantic model class to deserialize to
        source_format: Source format ('json', 'database')
        decrypt_pii: Whether to decrypt PII fields
        
    Returns:
        List of deserialized model instances
    """
    deserialized_items = []
    
    for item in items:
        try:
            if source_format == 'json':
                deserialized_items.append(deserialize_from_json(item, model_class, decrypt_pii=decrypt_pii))
            elif source_format == 'database':
                deserialized_items.append(deserialize_from_database(item, model_class, decrypt_pii=decrypt_pii))
            else:
                raise ValueError(f"Unsupported source format: {source_format}")
        except Exception as e:
            logger.error(f"Failed to deserialize item {item}: {e}")
            # Continue with other items, but log the error
            continue
    
    return deserialized_items


def validate_and_serialize(data: Dict[str, Any], 
                          model_class: Type[T],
                          target_format: str = 'json',
                          encrypt_pii: bool = True) -> Union[str, Dict]:
    """
    Validate data against a Pydantic model and serialize to target format.
    
    Args:
        data: Raw data to validate and serialize
        model_class: Pydantic model class for validation
        target_format: Target format ('json', 'database', 'api')
        encrypt_pii: Whether to encrypt PII fields
        
    Returns:
        Serialized and validated data
    """
    try:
        # Validate data by creating model instance
        validated_model = model_class(**data)
        
        # Serialize to target format
        if target_format == 'json':
            return serialize_to_json(validated_model, encrypt_pii=encrypt_pii)
        elif target_format == 'database':
            return serialize_for_database(validated_model, encrypt_pii=encrypt_pii)
        elif target_format == 'api':
            return serialize_for_api_response(validated_model, mask_pii=False)
        else:
            raise ValueError(f"Unsupported target format: {target_format}")
    
    except Exception as e:
        logger.error(f"Validation and serialization failed: {e}")
        raise ValueError(f"Failed to validate and serialize data: {e}")


def safe_serialize(data: Any, fallback_value: Any = None) -> Any:
    """
    Safely serialize data with fallback on error.
    
    Args:
        data: Data to serialize
        fallback_value: Value to return if serialization fails
        
    Returns:
        Serialized data or fallback value
    """
    try:
        if isinstance(data, BaseModel):
            return data.dict()
        elif isinstance(data, (dict, list, str, int, float, bool)):
            return data
        elif hasattr(data, '__dict__'):
            return data.__dict__
        else:
            return str(data)
    except Exception as e:
        logger.warning(f"Safe serialization failed, using fallback: {e}")
        return fallback_value