"""
Data anonymization and pseudonymization utilities for privacy protection.
"""
import hashlib
import secrets
import string
import random
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)


class DataAnonymizer:
    """Provides data anonymization and pseudonymization capabilities."""
    
    def __init__(self, salt: Optional[str] = None):
        """
        Initialize data anonymizer.
        
        Args:
            salt: Optional salt for consistent pseudonymization
        """
        self.salt = salt or secrets.token_hex(16)
        
        # Common first names for synthetic data
        self.first_names = [
            'John', 'Jane', 'Michael', 'Sarah', 'David', 'Lisa', 'Robert', 'Mary',
            'James', 'Patricia', 'William', 'Jennifer', 'Richard', 'Linda', 'Joseph',
            'Elizabeth', 'Thomas', 'Barbara', 'Christopher', 'Susan', 'Daniel', 'Jessica'
        ]
        
        # Common last names for synthetic data
        self.last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
            'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez',
            'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'
        ]
        
        # Common company names for synthetic data
        self.company_names = [
            'TechCorp', 'DataSystems', 'InnovateLLC', 'GlobalSolutions', 'NextGen',
            'SmartTech', 'FutureSoft', 'ProServices', 'EliteConsulting', 'PrimeTech',
            'AlphaSystems', 'BetaWorks', 'GammaLabs', 'DeltaCorp', 'OmegaSoft'
        ]
        
        # Email domains for synthetic data
        self.email_domains = [
            'example.com', 'test.org', 'sample.net', 'demo.co', 'placeholder.io'
        ]
    
    def pseudonymize_string(self, value: str, preserve_format: bool = True) -> str:
        """
        Create a consistent pseudonym for a string value.
        
        Args:
            value: Original string value
            preserve_format: Whether to preserve the original format
            
        Returns:
            Pseudonymized string
        """
        if not value:
            return value
        
        # Create consistent hash
        hash_input = f"{self.salt}:{value}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        
        if preserve_format:
            # Preserve length and character types
            result = ""
            for i, char in enumerate(value):
                hash_char = hash_value[i % len(hash_value)]
                if char.isalpha():
                    # Convert hash char to letter, preserving case
                    letter_index = int(hash_char, 16) % 26
                    if char.isupper():
                        result += chr(ord('A') + letter_index)
                    else:
                        result += chr(ord('a') + letter_index)
                elif char.isdigit():
                    # Convert hash char to digit
                    result += str(int(hash_char, 16) % 10)
                else:
                    # Keep special characters as-is
                    result += char
            return result
        else:
            # Return hash-based pseudonym
            return f"pseudo_{hash_value[:8]}"
    
    def pseudonymize_phone(self, phone: str) -> str:
        """
        Pseudonymize a phone number while preserving format.
        
        Args:
            phone: Original phone number
            
        Returns:
            Pseudonymized phone number
        """
        if not phone:
            return phone
        
        # Extract digits only
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 10:
            return self.pseudonymize_string(phone)
        
        # Create consistent pseudonym based on original
        hash_input = f"{self.salt}:phone:{digits}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Generate new digits
        pseudo_digits = ""
        for i in range(len(digits)):
            pseudo_digits += str(int(hash_value[i % len(hash_value)], 16) % 10)
        
        # Preserve original format
        result = phone
        digit_index = 0
        for i, char in enumerate(phone):
            if char.isdigit() and digit_index < len(pseudo_digits):
                result = result[:i] + pseudo_digits[digit_index] + result[i+1:]
                digit_index += 1
        
        return result
    
    def pseudonymize_email(self, email: str) -> str:
        """
        Pseudonymize an email address while preserving domain structure.
        
        Args:
            email: Original email address
            
        Returns:
            Pseudonymized email address
        """
        if not email or '@' not in email:
            return self.pseudonymize_string(email)
        
        local_part, domain = email.split('@', 1)
        
        # Pseudonymize local part
        pseudo_local = self.pseudonymize_string(local_part, preserve_format=True)
        
        # Keep domain or use synthetic one
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
            # Use synthetic domain for common providers
            hash_input = f"{self.salt}:domain:{domain}"
            hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
            domain_index = int(hash_value[:2], 16) % len(self.email_domains)
            pseudo_domain = self.email_domains[domain_index]
        else:
            # Pseudonymize custom domains
            pseudo_domain = self.pseudonymize_string(domain, preserve_format=True)
        
        return f"{pseudo_local}@{pseudo_domain}"
    
    def anonymize_string(self, value: str, replacement: str = "[REDACTED]") -> str:
        """
        Anonymize a string by replacing it with a generic value.
        
        Args:
            value: Original string value
            replacement: Replacement string
            
        Returns:
            Anonymized string
        """
        if not value:
            return value
        return replacement
    
    def anonymize_partial(self, value: str, keep_chars: int = 2, mask_char: str = '*') -> str:
        """
        Partially anonymize a string by masking most characters.
        
        Args:
            value: Original string value
            keep_chars: Number of characters to keep at start and end
            mask_char: Character to use for masking
            
        Returns:
            Partially anonymized string
        """
        if not value or len(value) <= keep_chars * 2:
            return mask_char * len(value) if value else value
        
        start = value[:keep_chars]
        end = value[-keep_chars:]
        middle = mask_char * (len(value) - keep_chars * 2)
        
        return f"{start}{middle}{end}"
    
    def generate_synthetic_name(self, gender_hint: Optional[str] = None) -> Dict[str, str]:
        """
        Generate synthetic first and last names.
        
        Args:
            gender_hint: Optional gender hint for name selection
            
        Returns:
            Dictionary with 'first_name' and 'last_name'
        """
        # Use consistent randomization based on salt
        random.seed(hash(self.salt) % (2**32))
        
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        
        return {
            'first_name': first_name,
            'last_name': last_name
        }
    
    def generate_synthetic_phone(self, area_code: Optional[str] = None) -> str:
        """
        Generate a synthetic phone number.
        
        Args:
            area_code: Optional area code to use
            
        Returns:
            Synthetic phone number
        """
        if area_code is None:
            # Use common area codes
            area_codes = ['555', '123', '456', '789']
            area_code = random.choice(area_codes)
        
        # Generate exchange and number
        exchange = f"{random.randint(200, 999)}"
        number = f"{random.randint(1000, 9999)}"
        
        return f"({area_code}) {exchange}-{number}"
    
    def generate_synthetic_email(self, name_parts: Optional[Dict[str, str]] = None) -> str:
        """
        Generate a synthetic email address.
        
        Args:
            name_parts: Optional dictionary with 'first_name' and 'last_name'
            
        Returns:
            Synthetic email address
        """
        if name_parts:
            first = name_parts.get('first_name', 'user').lower()
            last = name_parts.get('last_name', 'test').lower()
            local_part = f"{first}.{last}"
        else:
            local_part = f"user{random.randint(1000, 9999)}"
        
        domain = random.choice(self.email_domains)
        return f"{local_part}@{domain}"
    
    def generate_synthetic_company(self) -> str:
        """
        Generate a synthetic company name.
        
        Returns:
            Synthetic company name
        """
        return random.choice(self.company_names)
    
    def anonymize_data(
        self,
        data: Dict[str, Any],
        fields_to_anonymize: Optional[Set[str]] = None,
        anonymization_method: str = "redact"
    ) -> Dict[str, Any]:
        """
        Anonymize specified fields in a data dictionary.
        
        Args:
            data: Dictionary containing data to anonymize
            fields_to_anonymize: Set of field names to anonymize
            anonymization_method: Method to use ('redact', 'mask', 'synthetic')
            
        Returns:
            Dictionary with anonymized fields
        """
        if not data:
            return data
        
        if fields_to_anonymize is None:
            # Default PII fields to anonymize
            fields_to_anonymize = {
                'first_name', 'last_name', 'email', 'phone', 'caller_phone',
                'address', 'ssn', 'credit_card', 'bank_account'
            }
        
        anonymized_data = data.copy()
        
        for field in fields_to_anonymize:
            if field in anonymized_data and anonymized_data[field]:
                value = anonymized_data[field]
                
                if isinstance(value, str):
                    if anonymization_method == "redact":
                        anonymized_data[field] = "[REDACTED]"
                    elif anonymization_method == "mask":
                        anonymized_data[field] = self.anonymize_partial(value)
                    elif anonymization_method == "synthetic":
                        anonymized_data[field] = self._generate_synthetic_value(field, value)
                    else:
                        anonymized_data[field] = "[ANONYMIZED]"
                elif isinstance(value, dict):
                    # Recursively anonymize nested dictionaries
                    anonymized_data[field] = self.anonymize_data(
                        value, fields_to_anonymize, anonymization_method
                    )
                elif isinstance(value, list):
                    # Handle lists of strings or dictionaries
                    anonymized_list = []
                    for item in value:
                        if isinstance(item, str):
                            if anonymization_method == "redact":
                                anonymized_list.append("[REDACTED]")
                            elif anonymization_method == "mask":
                                anonymized_list.append(self.anonymize_partial(item))
                            else:
                                anonymized_list.append("[ANONYMIZED]")
                        elif isinstance(item, dict):
                            anonymized_list.append(
                                self.anonymize_data(item, fields_to_anonymize, anonymization_method)
                            )
                        else:
                            anonymized_list.append(item)
                    anonymized_data[field] = anonymized_list
        
        return anonymized_data
    
    def pseudonymize_data(
        self,
        data: Dict[str, Any],
        fields_to_pseudonymize: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Pseudonymize specified fields in a data dictionary.
        
        Args:
            data: Dictionary containing data to pseudonymize
            fields_to_pseudonymize: Set of field names to pseudonymize
            
        Returns:
            Dictionary with pseudonymized fields
        """
        if not data:
            return data
        
        if fields_to_pseudonymize is None:
            # Default PII fields to pseudonymize
            fields_to_pseudonymize = {
                'first_name', 'last_name', 'email', 'phone', 'caller_phone',
                'company', 'title'
            }
        
        pseudonymized_data = data.copy()
        
        for field in fields_to_pseudonymize:
            if field in pseudonymized_data and pseudonymized_data[field]:
                value = pseudonymized_data[field]
                
                if isinstance(value, str):
                    if field in ['phone', 'caller_phone']:
                        pseudonymized_data[field] = self.pseudonymize_phone(value)
                    elif field == 'email':
                        pseudonymized_data[field] = self.pseudonymize_email(value)
                    else:
                        pseudonymized_data[field] = self.pseudonymize_string(value)
                elif isinstance(value, dict):
                    # Recursively pseudonymize nested dictionaries
                    pseudonymized_data[field] = self.pseudonymize_data(value, fields_to_pseudonymize)
                elif isinstance(value, list):
                    # Handle lists of strings or dictionaries
                    pseudonymized_list = []
                    for item in value:
                        if isinstance(item, str):
                            if field in ['phone', 'caller_phone']:
                                pseudonymized_list.append(self.pseudonymize_phone(item))
                            elif field == 'email':
                                pseudonymized_list.append(self.pseudonymize_email(item))
                            else:
                                pseudonymized_list.append(self.pseudonymize_string(item))
                        elif isinstance(item, dict):
                            pseudonymized_list.append(
                                self.pseudonymize_data(item, fields_to_pseudonymize)
                            )
                        else:
                            pseudonymized_list.append(item)
                    pseudonymized_data[field] = pseudonymized_list
        
        return pseudonymized_data
    
    def _generate_synthetic_value(self, field_name: str, original_value: str) -> str:
        """
        Generate synthetic value based on field type.
        
        Args:
            field_name: Name of the field
            original_value: Original value for context
            
        Returns:
            Synthetic value
        """
        field_lower = field_name.lower()
        
        if 'first_name' in field_lower:
            return random.choice(self.first_names)
        elif 'last_name' in field_lower:
            return random.choice(self.last_names)
        elif 'email' in field_lower:
            return self.generate_synthetic_email()
        elif 'phone' in field_lower:
            return self.generate_synthetic_phone()
        elif 'company' in field_lower:
            return self.generate_synthetic_company()
        else:
            # Generic synthetic value
            return f"synthetic_{random.randint(1000, 9999)}"
    
    def create_anonymization_report(
        self,
        original_data: Dict[str, Any],
        anonymized_data: Dict[str, Any],
        fields_processed: Set[str]
    ) -> Dict[str, Any]:
        """
        Create a report of anonymization operations performed.
        
        Args:
            original_data: Original data dictionary
            anonymized_data: Anonymized data dictionary
            fields_processed: Set of fields that were processed
            
        Returns:
            Anonymization report
        """
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'fields_processed': list(fields_processed),
            'total_fields': len(original_data),
            'anonymized_fields': len(fields_processed),
            'anonymization_rate': len(fields_processed) / len(original_data) if original_data else 0,
            'method': 'anonymization',
            'salt_used': bool(self.salt)
        }


# Global anonymizer instance
_data_anonymizer = None


def get_data_anonymizer() -> DataAnonymizer:
    """Get the global data anonymizer instance."""
    global _data_anonymizer
    if _data_anonymizer is None:
        _data_anonymizer = DataAnonymizer()
    return _data_anonymizer


def anonymize_data(
    data: Dict[str, Any],
    fields_to_anonymize: Optional[Set[str]] = None,
    method: str = "redact"
) -> Dict[str, Any]:
    """
    Anonymize specified fields in a data dictionary.
    
    Args:
        data: Dictionary containing data to anonymize
        fields_to_anonymize: Set of field names to anonymize
        method: Anonymization method ('redact', 'mask', 'synthetic')
        
    Returns:
        Dictionary with anonymized fields
    """
    return get_data_anonymizer().anonymize_data(data, fields_to_anonymize, method)


def pseudonymize_data(
    data: Dict[str, Any],
    fields_to_pseudonymize: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Pseudonymize specified fields in a data dictionary.
    
    Args:
        data: Dictionary containing data to pseudonymize
        fields_to_pseudonymize: Set of field names to pseudonymize
        
    Returns:
        Dictionary with pseudonymized fields
    """
    return get_data_anonymizer().pseudonymize_data(data, fields_to_pseudonymize)


def generate_synthetic_data(data_type: str, **kwargs) -> Any:
    """
    Generate synthetic data of specified type.
    
    Args:
        data_type: Type of data to generate ('name', 'email', 'phone', 'company')
        **kwargs: Additional parameters for data generation
        
    Returns:
        Generated synthetic data
    """
    anonymizer = get_data_anonymizer()
    
    if data_type == 'name':
        return anonymizer.generate_synthetic_name(kwargs.get('gender_hint'))
    elif data_type == 'email':
        return anonymizer.generate_synthetic_email(kwargs.get('name_parts'))
    elif data_type == 'phone':
        return anonymizer.generate_synthetic_phone(kwargs.get('area_code'))
    elif data_type == 'company':
        return anonymizer.generate_synthetic_company()
    else:
        raise ValueError(f"Unsupported data type: {data_type}")