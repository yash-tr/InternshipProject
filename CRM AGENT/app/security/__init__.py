"""
Security and data protection module for AI Calling Agent.
"""

from .encryption import (
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
from .key_management import (
    KeyManager,
    get_key_manager,
    rotate_encryption_key,
    validate_key_strength
)
from .data_classification import (
    DataClassifier,
    classify_data_sensitivity,
    get_retention_policy,
    should_encrypt_field
)
from .anonymization import (
    DataAnonymizer,
    anonymize_data,
    pseudonymize_data,
    generate_synthetic_data
)

__all__ = [
    "EncryptionManager",
    "get_encryption_manager", 
    "encrypt_pii_data",
    "decrypt_pii_data",
    "mask_pii_for_logging",
    "generate_encryption_key",
    "encrypt_field",
    "decrypt_field",
    "EncryptedField",
    "PII_FIELDS",
    "KeyManager",
    "get_key_manager",
    "rotate_encryption_key",
    "validate_key_strength",
    "DataClassifier",
    "classify_data_sensitivity",
    "get_retention_policy",
    "should_encrypt_field",
    "DataAnonymizer",
    "anonymize_data",
    "pseudonymize_data",
    "generate_synthetic_data"
]