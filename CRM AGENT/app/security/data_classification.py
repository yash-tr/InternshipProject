"""
Data classification and handling policies for sensitive information.
"""
import re
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataSensitivityLevel(Enum):
    """Data sensitivity classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataCategory(Enum):
    """Data category classifications."""
    PII = "personally_identifiable_information"
    PHI = "protected_health_information"
    FINANCIAL = "financial_information"
    BUSINESS = "business_information"
    TECHNICAL = "technical_information"
    COMMUNICATION = "communication_data"


class RetentionPolicy:
    """Data retention policy definition."""
    
    def __init__(
        self,
        retention_period: timedelta,
        archive_after: Optional[timedelta] = None,
        purge_after: Optional[timedelta] = None,
        encryption_required: bool = True,
        access_logging_required: bool = True
    ):
        self.retention_period = retention_period
        self.archive_after = archive_after or retention_period
        self.purge_after = purge_after or (retention_period * 2)
        self.encryption_required = encryption_required
        self.access_logging_required = access_logging_required


class DataClassifier:
    """Classifies data based on content and context for appropriate handling."""
    
    def __init__(self):
        self.pii_patterns = {
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'driver_license': re.compile(r'\b[A-Z]{1,2}[0-9]{6,8}\b'),
            'passport': re.compile(r'\b[A-Z]{1,2}[0-9]{6,9}\b'),
            'bank_account': re.compile(r'\b[0-9]{8,17}\b')
        }
        
        self.financial_patterns = {
            'routing_number': re.compile(r'\b[0-9]{9}\b'),
            'iban': re.compile(r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b'),
            'swift_code': re.compile(r'\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b')
        }
        
        self.health_patterns = {
            'medical_record': re.compile(r'\bMRN[-\s]?[0-9]{6,10}\b', re.IGNORECASE),
            'insurance_id': re.compile(r'\b[A-Z]{2,3}[0-9]{6,12}\b')
        }
        
        # Field-based classification
        self.field_classifications = {
            # PII Fields
            'first_name': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'last_name': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'full_name': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'email': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'phone': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'caller_phone': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),
            'address': (DataSensitivityLevel.RESTRICTED, DataCategory.PII),
            'ssn': (DataSensitivityLevel.RESTRICTED, DataCategory.PII),
            'driver_license': (DataSensitivityLevel.RESTRICTED, DataCategory.PII),
            'passport': (DataSensitivityLevel.RESTRICTED, DataCategory.PII),
            
            # Financial Information
            'credit_card': (DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL),
            'bank_account': (DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL),
            'routing_number': (DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL),
            'payment_info': (DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL),
            
            # Health Information
            'medical_record': (DataSensitivityLevel.RESTRICTED, DataCategory.PHI),
            'health_info': (DataSensitivityLevel.RESTRICTED, DataCategory.PHI),
            'insurance_id': (DataSensitivityLevel.RESTRICTED, DataCategory.PHI),
            
            # Communication Data
            'conversation_history': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.COMMUNICATION),
            'conversation_summary': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.COMMUNICATION),
            'call_recording': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.COMMUNICATION),
            'transcript': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.COMMUNICATION),
            
            # Business Information
            'company': (DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS),
            'title': (DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS),
            'lead_score': (DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS),
            'deal_value': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.BUSINESS),
            
            # Technical Information
            'api_key': (DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL),
            'password': (DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL),
            'token': (DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL),
            'session_id': (DataSensitivityLevel.CONFIDENTIAL, DataCategory.TECHNICAL),
            'ip_address': (DataSensitivityLevel.INTERNAL, DataCategory.TECHNICAL)
        }
        
        # Retention policies by category and sensitivity
        self.retention_policies = {
            (DataSensitivityLevel.PUBLIC, DataCategory.BUSINESS): RetentionPolicy(
                retention_period=timedelta(days=2555),  # 7 years
                encryption_required=False,
                access_logging_required=False
            ),
            (DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS): RetentionPolicy(
                retention_period=timedelta(days=1825),  # 5 years
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII): RetentionPolicy(
                retention_period=timedelta(days=1095),  # 3 years
                archive_after=timedelta(days=365),  # 1 year
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.RESTRICTED, DataCategory.PII): RetentionPolicy(
                retention_period=timedelta(days=730),  # 2 years
                archive_after=timedelta(days=180),  # 6 months
                purge_after=timedelta(days=730),  # 2 years
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL): RetentionPolicy(
                retention_period=timedelta(days=2555),  # 7 years (regulatory requirement)
                archive_after=timedelta(days=365),  # 1 year
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.RESTRICTED, DataCategory.PHI): RetentionPolicy(
                retention_period=timedelta(days=2190),  # 6 years (HIPAA requirement)
                archive_after=timedelta(days=365),  # 1 year
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.CONFIDENTIAL, DataCategory.COMMUNICATION): RetentionPolicy(
                retention_period=timedelta(days=1095),  # 3 years
                archive_after=timedelta(days=365),  # 1 year
                encryption_required=True,
                access_logging_required=True
            ),
            (DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL): RetentionPolicy(
                retention_period=timedelta(days=90),  # 3 months
                archive_after=timedelta(days=30),  # 1 month
                purge_after=timedelta(days=90),  # 3 months
                encryption_required=True,
                access_logging_required=True
            )
        }
    
    def classify_field(self, field_name: str, field_value: Optional[str] = None) -> Tuple[DataSensitivityLevel, DataCategory]:
        """
        Classify a data field based on name and optionally content.
        
        Args:
            field_name: Name of the field
            field_value: Optional field value for content-based classification
            
        Returns:
            Tuple of (sensitivity_level, category)
        """
        # Check field name classification first
        field_lower = field_name.lower()
        
        # Direct field name match
        if field_lower in self.field_classifications:
            return self.field_classifications[field_lower]
        
        # Pattern matching in field names
        for classified_field, (sensitivity, category) in self.field_classifications.items():
            if classified_field in field_lower:
                return sensitivity, category
        
        # Content-based classification if value provided
        if field_value:
            content_classification = self.classify_content(field_value)
            if content_classification != (DataSensitivityLevel.PUBLIC, DataCategory.BUSINESS):
                return content_classification
        
        # Default classification
        return DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS
    
    def classify_content(self, content: str) -> Tuple[DataSensitivityLevel, DataCategory]:
        """
        Classify content based on patterns found in the text.
        
        Args:
            content: Text content to classify
            
        Returns:
            Tuple of (sensitivity_level, category)
        """
        if not content:
            return DataSensitivityLevel.PUBLIC, DataCategory.BUSINESS
        
        # Check for PII patterns
        for pattern_name, pattern in self.pii_patterns.items():
            if pattern.search(content):
                if pattern_name in ['ssn', 'driver_license', 'passport']:
                    return DataSensitivityLevel.RESTRICTED, DataCategory.PII
                elif pattern_name == 'credit_card':
                    return DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL
                else:
                    return DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII
        
        # Check for financial patterns
        for pattern_name, pattern in self.financial_patterns.items():
            if pattern.search(content):
                return DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL
        
        # Check for health patterns
        for pattern_name, pattern in self.health_patterns.items():
            if pattern.search(content):
                return DataSensitivityLevel.RESTRICTED, DataCategory.PHI
        
        # Check for technical secrets
        if any(keyword in content.lower() for keyword in ['password', 'api_key', 'secret', 'token']):
            return DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL
        
        return DataSensitivityLevel.PUBLIC, DataCategory.BUSINESS
    
    def classify_data_dict(self, data: Dict) -> Dict[str, Tuple[DataSensitivityLevel, DataCategory]]:
        """
        Classify all fields in a data dictionary.
        
        Args:
            data: Dictionary of data to classify
            
        Returns:
            Dictionary mapping field names to (sensitivity_level, category) tuples
        """
        classifications = {}
        
        for field_name, field_value in data.items():
            if field_name.startswith('_'):  # Skip metadata fields
                continue
                
            if isinstance(field_value, str):
                classifications[field_name] = self.classify_field(field_name, field_value)
            elif isinstance(field_value, dict):
                # Recursively classify nested dictionaries
                nested_classifications = self.classify_data_dict(field_value)
                for nested_field, classification in nested_classifications.items():
                    classifications[f"{field_name}.{nested_field}"] = classification
            elif isinstance(field_value, list) and field_value:
                # Classify based on first item in list
                if isinstance(field_value[0], str):
                    classifications[field_name] = self.classify_field(field_name, field_value[0])
                elif isinstance(field_value[0], dict):
                    nested_classifications = self.classify_data_dict(field_value[0])
                    for nested_field, classification in nested_classifications.items():
                        classifications[f"{field_name}[].{nested_field}"] = classification
                else:
                    classifications[field_name] = self.classify_field(field_name)
            else:
                classifications[field_name] = self.classify_field(field_name)
        
        return classifications
    
    def get_retention_policy(self, sensitivity: DataSensitivityLevel, category: DataCategory) -> RetentionPolicy:
        """
        Get retention policy for given sensitivity and category.
        
        Args:
            sensitivity: Data sensitivity level
            category: Data category
            
        Returns:
            Applicable retention policy
        """
        # Try exact match first
        policy_key = (sensitivity, category)
        if policy_key in self.retention_policies:
            return self.retention_policies[policy_key]
        
        # Fall back to more restrictive policy
        if sensitivity == DataSensitivityLevel.RESTRICTED:
            return RetentionPolicy(
                retention_period=timedelta(days=730),  # 2 years
                archive_after=timedelta(days=180),  # 6 months
                purge_after=timedelta(days=730),  # 2 years
                encryption_required=True,
                access_logging_required=True
            )
        elif sensitivity == DataSensitivityLevel.CONFIDENTIAL:
            return RetentionPolicy(
                retention_period=timedelta(days=1095),  # 3 years
                archive_after=timedelta(days=365),  # 1 year
                encryption_required=True,
                access_logging_required=True
            )
        else:
            return RetentionPolicy(
                retention_period=timedelta(days=1825),  # 5 years
                encryption_required=True,
                access_logging_required=True
            )
    
    def should_encrypt_field(self, field_name: str, field_value: Optional[str] = None) -> bool:
        """
        Determine if a field should be encrypted based on classification.
        
        Args:
            field_name: Name of the field
            field_value: Optional field value
            
        Returns:
            True if field should be encrypted
        """
        sensitivity, category = self.classify_field(field_name, field_value)
        policy = self.get_retention_policy(sensitivity, category)
        return policy.encryption_required
    
    def get_fields_requiring_encryption(self, data: Dict) -> Set[str]:
        """
        Get set of field names that require encryption.
        
        Args:
            data: Dictionary of data to analyze
            
        Returns:
            Set of field names requiring encryption
        """
        classifications = self.classify_data_dict(data)
        encryption_fields = set()
        
        for field_name, (sensitivity, category) in classifications.items():
            policy = self.get_retention_policy(sensitivity, category)
            if policy.encryption_required:
                # Handle nested field names
                base_field = field_name.split('.')[0].split('[')[0]
                encryption_fields.add(base_field)
        
        return encryption_fields
    
    def get_data_handling_requirements(self, data: Dict) -> Dict[str, Dict]:
        """
        Get comprehensive data handling requirements for a dataset.
        
        Args:
            data: Dictionary of data to analyze
            
        Returns:
            Dictionary with handling requirements per field
        """
        classifications = self.classify_data_dict(data)
        requirements = {}
        
        for field_name, (sensitivity, category) in classifications.items():
            policy = self.get_retention_policy(sensitivity, category)
            
            requirements[field_name] = {
                'sensitivity_level': sensitivity.value,
                'category': category.value,
                'encryption_required': policy.encryption_required,
                'access_logging_required': policy.access_logging_required,
                'retention_days': policy.retention_period.days,
                'archive_after_days': policy.archive_after.days,
                'purge_after_days': policy.purge_after.days if policy.purge_after else None
            }
        
        return requirements


# Global classifier instance
_data_classifier = None


def get_data_classifier() -> DataClassifier:
    """Get the global data classifier instance."""
    global _data_classifier
    if _data_classifier is None:
        _data_classifier = DataClassifier()
    return _data_classifier


def classify_data_sensitivity(data: Dict) -> Dict[str, Tuple[DataSensitivityLevel, DataCategory]]:
    """
    Classify data sensitivity for all fields in a dictionary.
    
    Args:
        data: Dictionary of data to classify
        
    Returns:
        Dictionary mapping field names to (sensitivity_level, category) tuples
    """
    return get_data_classifier().classify_data_dict(data)


def get_retention_policy(sensitivity: DataSensitivityLevel, category: DataCategory) -> RetentionPolicy:
    """
    Get retention policy for given sensitivity and category.
    
    Args:
        sensitivity: Data sensitivity level
        category: Data category
        
    Returns:
        Applicable retention policy
    """
    return get_data_classifier().get_retention_policy(sensitivity, category)


def should_encrypt_field(field_name: str, field_value: Optional[str] = None) -> bool:
    """
    Determine if a field should be encrypted.
    
    Args:
        field_name: Name of the field
        field_value: Optional field value
        
    Returns:
        True if field should be encrypted
    """
    return get_data_classifier().should_encrypt_field(field_name, field_value)