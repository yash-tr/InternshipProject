"""
Tests for data classification functionality.
"""
import pytest
from datetime import timedelta

from app.security.data_classification import (
    DataClassifier,
    DataSensitivityLevel,
    DataCategory,
    RetentionPolicy,
    get_data_classifier,
    classify_data_sensitivity,
    get_retention_policy,
    should_encrypt_field
)


class TestDataClassifier:
    """Test data classifier functionality."""
    
    def test_classify_field_by_name(self):
        """Test field classification by name."""
        classifier = DataClassifier()
        
        # PII fields
        sensitivity, category = classifier.classify_field("first_name")
        assert sensitivity == DataSensitivityLevel.CONFIDENTIAL
        assert category == DataCategory.PII
        
        sensitivity, category = classifier.classify_field("email")
        assert sensitivity == DataSensitivityLevel.CONFIDENTIAL
        assert category == DataCategory.PII
        
        sensitivity, category = classifier.classify_field("ssn")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.PII
        
        # Financial fields
        sensitivity, category = classifier.classify_field("credit_card")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.FINANCIAL
        
        # Business fields
        sensitivity, category = classifier.classify_field("company")
        assert sensitivity == DataSensitivityLevel.INTERNAL
        assert category == DataCategory.BUSINESS
        
        # Technical fields
        sensitivity, category = classifier.classify_field("api_key")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.TECHNICAL
    
    def test_classify_field_by_content(self):
        """Test field classification by content."""
        classifier = DataClassifier()
        
        # SSN in content
        sensitivity, category = classifier.classify_field("user_input", "My SSN is 123-45-6789")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.PII
        
        # Email in content
        sensitivity, category = classifier.classify_field("message", "Contact me at john@example.com")
        assert sensitivity == DataSensitivityLevel.CONFIDENTIAL
        assert category == DataCategory.PII
        
        # Credit card in content
        sensitivity, category = classifier.classify_field("payment", "Card number: 4111 1111 1111 1111")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.FINANCIAL
        
        # Phone number in content
        sensitivity, category = classifier.classify_field("contact", "Call me at 555-123-4567")
        assert sensitivity == DataSensitivityLevel.CONFIDENTIAL
        assert category == DataCategory.PII
    
    def test_classify_content_patterns(self):
        """Test content pattern classification."""
        classifier = DataClassifier()
        
        # Test various PII patterns
        test_cases = [
            ("123-45-6789", DataSensitivityLevel.RESTRICTED, DataCategory.PII),  # SSN
            ("4111-1111-1111-1111", DataSensitivityLevel.RESTRICTED, DataCategory.FINANCIAL),  # Credit card
            ("john@example.com", DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),  # Email
            ("555-123-4567", DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),  # Phone
            ("192.168.1.1", DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII),  # IP address
        ]
        
        for content, expected_sensitivity, expected_category in test_cases:
            sensitivity, category = classifier.classify_content(content)
            assert sensitivity == expected_sensitivity, f"Failed for content: {content}"
            assert category == expected_category, f"Failed for content: {content}"
    
    def test_classify_data_dict(self):
        """Test classification of data dictionary."""
        classifier = DataClassifier()
        
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-1234",
            "company": "TechCorp",
            "api_key": "secret-key-123",
            "metadata": {
                "source": "web",
                "ip_address": "192.168.1.1"
            },
            "conversation_history": [
                "Hello, I'm interested in your product",
                "My SSN is 123-45-6789"
            ]
        }
        
        classifications = classifier.classify_data_dict(data)
        
        # Check direct field classifications
        assert classifications["first_name"] == (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII)
        assert classifications["email"] == (DataSensitivityLevel.CONFIDENTIAL, DataCategory.PII)
        assert classifications["company"] == (DataSensitivityLevel.INTERNAL, DataCategory.BUSINESS)
        assert classifications["api_key"] == (DataSensitivityLevel.RESTRICTED, DataCategory.TECHNICAL)
        
        # Check nested field classifications
        assert "metadata.ip_address" in classifications
        assert classifications["metadata.ip_address"] == (DataSensitivityLevel.INTERNAL, DataCategory.TECHNICAL)
        
        # Check list field classification
        assert "conversation_history" in classifications
        # Should detect SSN in conversation content
        assert classifications["conversation_history"][0] == DataSensitivityLevel.RESTRICTED
    
    def test_get_retention_policy(self):
        """Test retention policy retrieval."""
        classifier = DataClassifier()
        
        # Test specific policy combinations
        policy = classifier.get_retention_policy(
            DataSensitivityLevel.RESTRICTED, 
            DataCategory.PII
        )
        assert policy.retention_period == timedelta(days=730)  # 2 years
        assert policy.encryption_required is True
        assert policy.access_logging_required is True
        
        policy = classifier.get_retention_policy(
            DataSensitivityLevel.RESTRICTED, 
            DataCategory.FINANCIAL
        )
        assert policy.retention_period == timedelta(days=2555)  # 7 years
        assert policy.encryption_required is True
        
        # Test fallback policy
        policy = classifier.get_retention_policy(
            DataSensitivityLevel.CONFIDENTIAL, 
            DataCategory.BUSINESS  # No specific policy defined
        )
        assert policy.retention_period == timedelta(days=1095)  # 3 years fallback
        assert policy.encryption_required is True
    
    def test_should_encrypt_field(self):
        """Test field encryption determination."""
        classifier = DataClassifier()
        
        # PII fields should be encrypted
        assert classifier.should_encrypt_field("first_name") is True
        assert classifier.should_encrypt_field("email") is True
        assert classifier.should_encrypt_field("ssn") is True
        
        # Some business fields may not require encryption
        # (depends on specific policy configuration)
        company_encrypt = classifier.should_encrypt_field("company")
        assert isinstance(company_encrypt, bool)
        
        # Technical secrets should be encrypted
        assert classifier.should_encrypt_field("api_key") is True
        assert classifier.should_encrypt_field("password") is True
    
    def test_get_fields_requiring_encryption(self):
        """Test identification of fields requiring encryption."""
        classifier = DataClassifier()
        
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp",
            "public_info": "This is public",
            "nested": {
                "ssn": "123-45-6789",
                "description": "Some description"
            }
        }
        
        encryption_fields = classifier.get_fields_requiring_encryption(data)
        
        # Should include PII fields
        assert "first_name" in encryption_fields
        assert "email" in encryption_fields
        assert "nested" in encryption_fields  # Contains SSN
        
        # May or may not include business fields depending on policy
        # assert "company" in encryption_fields or "company" not in encryption_fields
    
    def test_get_data_handling_requirements(self):
        """Test comprehensive data handling requirements."""
        classifier = DataClassifier()
        
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp",
            "ssn": "123-45-6789"
        }
        
        requirements = classifier.get_data_handling_requirements(data)
        
        # Check structure
        assert isinstance(requirements, dict)
        assert "first_name" in requirements
        assert "email" in requirements
        assert "ssn" in requirements
        
        # Check SSN requirements (most restrictive)
        ssn_req = requirements["ssn"]
        assert ssn_req["sensitivity_level"] == DataSensitivityLevel.RESTRICTED.value
        assert ssn_req["category"] == DataCategory.PII.value
        assert ssn_req["encryption_required"] is True
        assert ssn_req["access_logging_required"] is True
        assert ssn_req["retention_days"] == 730  # 2 years
        
        # Check email requirements
        email_req = requirements["email"]
        assert email_req["sensitivity_level"] == DataSensitivityLevel.CONFIDENTIAL.value
        assert email_req["encryption_required"] is True
    
    def test_pattern_matching_edge_cases(self):
        """Test edge cases in pattern matching."""
        classifier = DataClassifier()
        
        # Test partial matches that shouldn't trigger
        sensitivity, category = classifier.classify_content("This is not a 123-45-678 SSN")
        assert sensitivity == DataSensitivityLevel.PUBLIC  # Incomplete SSN
        
        # Test valid patterns in context
        sensitivity, category = classifier.classify_content("My social security number is 123-45-6789")
        assert sensitivity == DataSensitivityLevel.RESTRICTED
        assert category == DataCategory.PII
        
        # Test multiple patterns in same content
        content = "Contact john@example.com or call 555-123-4567"
        sensitivity, category = classifier.classify_content(content)
        # Should classify as the most sensitive pattern found
        assert sensitivity == DataSensitivityLevel.CONFIDENTIAL
        assert category == DataCategory.PII
    
    def test_nested_data_classification(self):
        """Test classification of deeply nested data."""
        classifier = DataClassifier()
        
        data = {
            "user": {
                "profile": {
                    "personal": {
                        "first_name": "John",
                        "ssn": "123-45-6789"
                    },
                    "contact": {
                        "email": "john@example.com",
                        "phone": "555-1234"
                    }
                },
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            }
        }
        
        classifications = classifier.classify_data_dict(data)
        
        # Check nested field classifications
        assert "user.profile.personal.first_name" in classifications
        assert "user.profile.personal.ssn" in classifications
        assert "user.profile.contact.email" in classifications
        
        # Verify sensitivity levels
        ssn_classification = classifications["user.profile.personal.ssn"]
        assert ssn_classification[0] == DataSensitivityLevel.RESTRICTED
        
        email_classification = classifications["user.profile.contact.email"]
        assert email_classification[0] == DataSensitivityLevel.CONFIDENTIAL
    
    def test_list_data_classification(self):
        """Test classification of list data."""
        classifier = DataClassifier()
        
        data = {
            "emails": [
                "john@example.com",
                "jane@example.com"
            ],
            "conversation_history": [
                {"role": "user", "content": "My name is John"},
                {"role": "assistant", "content": "Hello John"}
            ],
            "tags": ["customer", "vip", "enterprise"]
        }
        
        classifications = classifier.classify_data_dict(data)
        
        # Check list classifications
        assert "emails" in classifications
        assert "conversation_history" in classifications
        
        # Email list should be classified as PII
        email_classification = classifications["emails"]
        assert email_classification[0] == DataSensitivityLevel.CONFIDENTIAL
        assert email_classification[1] == DataCategory.PII
        
        # Conversation history should be classified as communication data
        conv_classification = classifications["conversation_history"]
        assert conv_classification[1] == DataCategory.COMMUNICATION


class TestRetentionPolicy:
    """Test retention policy functionality."""
    
    def test_retention_policy_creation(self):
        """Test retention policy creation."""
        policy = RetentionPolicy(
            retention_period=timedelta(days=365),
            archive_after=timedelta(days=90),
            purge_after=timedelta(days=730),
            encryption_required=True,
            access_logging_required=True
        )
        
        assert policy.retention_period == timedelta(days=365)
        assert policy.archive_after == timedelta(days=90)
        assert policy.purge_after == timedelta(days=730)
        assert policy.encryption_required is True
        assert policy.access_logging_required is True
    
    def test_retention_policy_defaults(self):
        """Test retention policy default values."""
        policy = RetentionPolicy(retention_period=timedelta(days=365))
        
        assert policy.retention_period == timedelta(days=365)
        assert policy.archive_after == timedelta(days=365)  # Default to retention_period
        assert policy.purge_after == timedelta(days=730)  # Default to retention_period * 2
        assert policy.encryption_required is True  # Default
        assert policy.access_logging_required is True  # Default


class TestDataClassificationUtilities:
    """Test data classification utility functions."""
    
    def test_classify_data_sensitivity_utility(self):
        """Test data sensitivity classification utility."""
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp"
        }
        
        classifications = classify_data_sensitivity(data)
        
        assert isinstance(classifications, dict)
        assert "first_name" in classifications
        assert "email" in classifications
        assert "company" in classifications
        
        # Check classification tuples
        first_name_class = classifications["first_name"]
        assert isinstance(first_name_class, tuple)
        assert len(first_name_class) == 2
        assert isinstance(first_name_class[0], DataSensitivityLevel)
        assert isinstance(first_name_class[1], DataCategory)
    
    def test_get_retention_policy_utility(self):
        """Test retention policy utility function."""
        policy = get_retention_policy(
            DataSensitivityLevel.CONFIDENTIAL,
            DataCategory.PII
        )
        
        assert isinstance(policy, RetentionPolicy)
        assert policy.encryption_required is True
        assert policy.access_logging_required is True
    
    def test_should_encrypt_field_utility(self):
        """Test field encryption utility function."""
        # PII field should be encrypted
        assert should_encrypt_field("first_name") is True
        assert should_encrypt_field("email") is True
        
        # Test with content
        assert should_encrypt_field("user_input", "My SSN is 123-45-6789") is True
        
        # Non-sensitive field may not require encryption
        result = should_encrypt_field("public_info")
        assert isinstance(result, bool)


class TestDataClassificationIntegration:
    """Test data classification integration scenarios."""
    
    def test_real_world_data_classification(self):
        """Test classification of realistic data structures."""
        classifier = DataClassifier()
        
        # Simulate call session data
        call_data = {
            "call_sid": "CA1234567890",
            "caller_phone": "+1-555-123-4567",
            "contact_info": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@techcorp.com",
                "company": "TechCorp Inc.",
                "title": "CTO"
            },
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Hi, I'm interested in your AI solution",
                    "timestamp": "2024-01-01T10:00:00Z"
                },
                {
                    "role": "assistant", 
                    "content": "Great! Can you tell me about your company?",
                    "timestamp": "2024-01-01T10:00:05Z"
                },
                {
                    "role": "user",
                    "content": "We're a 500-person company with $50M revenue",
                    "timestamp": "2024-01-01T10:00:15Z"
                }
            ],
            "extracted_data": {
                "company_size": "500",
                "revenue": "$50M",
                "pain_points": ["scalability", "automation"],
                "budget": "up to $100K"
            },
            "lead_score": 85,
            "call_outcome": "qualified",
            "metadata": {
                "call_duration": 300,
                "transcription_confidence": 0.95,
                "created_at": "2024-01-01T10:00:00Z"
            }
        }
        
        classifications = classifier.classify_data_dict(call_data)
        requirements = classifier.get_data_handling_requirements(call_data)
        
        # Verify key classifications
        assert "caller_phone" in classifications
        assert classifications["caller_phone"][0] == DataSensitivityLevel.CONFIDENTIAL
        
        assert "contact_info.first_name" in classifications
        assert classifications["contact_info.first_name"][0] == DataSensitivityLevel.CONFIDENTIAL
        
        assert "conversation_history" in classifications
        assert classifications["conversation_history"][1] == DataCategory.COMMUNICATION
        
        # Verify encryption requirements
        encryption_fields = classifier.get_fields_requiring_encryption(call_data)
        assert "caller_phone" in encryption_fields
        assert "contact_info" in encryption_fields
        assert "conversation_history" in encryption_fields
        
        # Verify retention requirements
        phone_req = requirements["caller_phone"]
        assert phone_req["encryption_required"] is True
        assert phone_req["access_logging_required"] is True
        assert phone_req["retention_days"] > 0
    
    def test_compliance_data_classification(self):
        """Test classification for compliance scenarios."""
        classifier = DataClassifier()
        
        # Healthcare-related data
        healthcare_data = {
            "patient_name": "John Doe",
            "medical_record": "MRN-123456789",
            "insurance_id": "INS987654321",
            "diagnosis": "Hypertension",
            "treatment_notes": "Patient responding well to medication"
        }
        
        classifications = classifier.classify_data_dict(healthcare_data)
        
        # Medical data should be classified as PHI
        assert classifications["medical_record"][1] == DataCategory.PHI
        assert classifications["medical_record"][0] == DataSensitivityLevel.RESTRICTED
        
        # Financial data
        financial_data = {
            "account_number": "123456789012",
            "routing_number": "021000021",
            "credit_score": "750",
            "income": "$75000"
        }
        
        classifications = classifier.classify_data_dict(financial_data)
        
        # Financial data should have appropriate classification
        # Note: account_number might be classified as bank_account pattern
        for field, (sensitivity, category) in classifications.items():
            if category == DataCategory.FINANCIAL:
                assert sensitivity in [DataSensitivityLevel.CONFIDENTIAL, DataSensitivityLevel.RESTRICTED]
    
    def test_performance_with_large_datasets(self):
        """Test classification performance with large datasets."""
        classifier = DataClassifier()
        
        # Create large dataset
        large_data = {}
        for i in range(1000):
            large_data[f"field_{i}"] = f"value_{i}"
            if i % 10 == 0:
                large_data[f"email_{i}"] = f"user{i}@example.com"
            if i % 20 == 0:
                large_data[f"phone_{i}"] = f"555-{i:04d}"
        
        # Should handle large datasets efficiently
        import time
        start_time = time.time()
        
        classifications = classifier.classify_data_dict(large_data)
        requirements = classifier.get_data_handling_requirements(large_data)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 5.0, f"Classification took too long: {processing_time}s"
        
        # Verify results
        assert len(classifications) == len(large_data)
        assert len(requirements) == len(large_data)
        
        # Check that email fields were properly classified
        email_fields = [field for field in classifications if field.startswith("email_")]
        for field in email_fields:
            assert classifications[field][1] == DataCategory.PII


@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe", 
        "email": "john@example.com",
        "phone": "555-1234",
        "ssn": "123-45-6789",
        "company": "TechCorp",
        "api_key": "secret-123",
        "public_info": "This is public"
    }


@pytest.fixture
def data_classifier():
    """Data classifier fixture."""
    return DataClassifier()