"""
Tests for data anonymization functionality.
"""
import pytest
import re
from unittest.mock import patch

from app.security.anonymization import (
    DataAnonymizer,
    get_data_anonymizer,
    anonymize_data,
    pseudonymize_data,
    generate_synthetic_data
)


class TestDataAnonymizer:
    """Test data anonymizer functionality."""
    
    def test_init_with_salt(self):
        """Test initialization with custom salt."""
        salt = "custom_salt_123"
        anonymizer = DataAnonymizer(salt)
        
        assert anonymizer.salt == salt
        assert len(anonymizer.first_names) > 0
        assert len(anonymizer.last_names) > 0
        assert len(anonymizer.company_names) > 0
    
    def test_init_without_salt(self):
        """Test initialization without salt (auto-generated)."""
        anonymizer = DataAnonymizer()
        
        assert anonymizer.salt is not None
        assert len(anonymizer.salt) > 0
    
    def test_pseudonymize_string_preserve_format(self):
        """Test string pseudonymization with format preservation."""
        anonymizer = DataAnonymizer("test_salt")
        
        original = "John123"
        pseudo = anonymizer.pseudonymize_string(original, preserve_format=True)
        
        # Should preserve length and character types
        assert len(pseudo) == len(original)
        assert pseudo[0].isupper()  # First char should be uppercase
        assert pseudo[-3:].isdigit()  # Last 3 chars should be digits
        assert pseudo != original  # Should be different
        
        # Should be consistent
        pseudo2 = anonymizer.pseudonymize_string(original, preserve_format=True)
        assert pseudo == pseudo2
    
    def test_pseudonymize_string_no_format_preservation(self):
        """Test string pseudonymization without format preservation."""
        anonymizer = DataAnonymizer("test_salt")
        
        original = "John Doe"
        pseudo = anonymizer.pseudonymize_string(original, preserve_format=False)
        
        assert pseudo.startswith("pseudo_")
        assert len(pseudo) == 14  # "pseudo_" + 8 hex chars
        assert pseudo != original
        
        # Should be consistent
        pseudo2 = anonymizer.pseudonymize_string(original, preserve_format=False)
        assert pseudo == pseudo2
    
    def test_pseudonymize_phone(self):
        """Test phone number pseudonymization."""
        anonymizer = DataAnonymizer("test_salt")
        
        # Test various phone formats
        test_cases = [
            "555-123-4567",
            "(555) 123-4567",
            "555.123.4567",
            "15551234567",
            "+1-555-123-4567"
        ]
        
        for original in test_cases:
            pseudo = anonymizer.pseudonymize_phone(original)
            
            # Should preserve format
            assert len(pseudo) == len(original)
            
            # Should preserve non-digit characters
            for i, char in enumerate(original):
                if not char.isdigit():
                    assert pseudo[i] == char
            
            # Should change digits
            original_digits = re.sub(r'\D', '', original)
            pseudo_digits = re.sub(r'\D', '', pseudo)
            if len(original_digits) >= 10:  # Valid phone number
                assert pseudo_digits != original_digits
            
            # Should be consistent
            pseudo2 = anonymizer.pseudonymize_phone(original)
            assert pseudo == pseudo2
    
    def test_pseudonymize_email(self):
        """Test email pseudonymization."""
        anonymizer = DataAnonymizer("test_salt")
        
        original = "john.doe@example.com"
        pseudo = anonymizer.pseudonymize_email(original)
        
        # Should have email format
        assert "@" in pseudo
        local, domain = pseudo.split("@", 1)
        
        # Local part should be pseudonymized
        assert local != "john.doe"
        assert len(local) == len("john.doe")  # Preserve length
        
        # Domain should be handled appropriately
        assert domain != "example.com" or domain in anonymizer.email_domains
        
        # Should be consistent
        pseudo2 = anonymizer.pseudonymize_email(original)
        assert pseudo == pseudo2
    
    def test_pseudonymize_common_email_domains(self):
        """Test pseudonymization of common email domains."""
        anonymizer = DataAnonymizer("test_salt")
        
        common_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        
        for domain in common_domains:
            email = f"user@{domain}"
            pseudo = anonymizer.pseudonymize_email(email)
            
            _, pseudo_domain = pseudo.split("@", 1)
            # Should use synthetic domain for common providers
            assert pseudo_domain in anonymizer.email_domains
    
    def test_anonymize_string(self):
        """Test string anonymization."""
        anonymizer = DataAnonymizer()
        
        original = "sensitive data"
        anonymized = anonymizer.anonymize_string(original)
        
        assert anonymized == "[REDACTED]"
        
        # Test custom replacement
        custom = anonymizer.anonymize_string(original, "[HIDDEN]")
        assert custom == "[HIDDEN]"
    
    def test_anonymize_partial(self):
        """Test partial string anonymization."""
        anonymizer = DataAnonymizer()
        
        # Test with default parameters
        original = "sensitive"
        partial = anonymizer.anonymize_partial(original)
        assert partial == "se******ve"  # Keep 2 chars at start and end
        
        # Test with custom parameters
        partial = anonymizer.anonymize_partial(original, keep_chars=1, mask_char='X')
        assert partial == "sXXXXXXXe"
        
        # Test short strings
        short = "ab"
        partial = anonymizer.anonymize_partial(short, keep_chars=2)
        assert partial == "**"  # Should mask completely if too short
    
    def test_generate_synthetic_name(self):
        """Test synthetic name generation."""
        anonymizer = DataAnonymizer()
        
        name = anonymizer.generate_synthetic_name()
        
        assert "first_name" in name
        assert "last_name" in name
        assert name["first_name"] in anonymizer.first_names
        assert name["last_name"] in anonymizer.last_names
    
    def test_generate_synthetic_phone(self):
        """Test synthetic phone generation."""
        anonymizer = DataAnonymizer()
        
        phone = anonymizer.generate_synthetic_phone()
        
        # Should match phone format
        assert re.match(r'\(\d{3}\) \d{3}-\d{4}', phone)
        
        # Test with custom area code
        phone_custom = anonymizer.generate_synthetic_phone("212")
        assert phone_custom.startswith("(212)")
    
    def test_generate_synthetic_email(self):
        """Test synthetic email generation."""
        anonymizer = DataAnonymizer()
        
        # Without name parts
        email = anonymizer.generate_synthetic_email()
        assert "@" in email
        assert email.split("@")[1] in anonymizer.email_domains
        
        # With name parts
        name_parts = {"first_name": "John", "last_name": "Doe"}
        email_with_name = anonymizer.generate_synthetic_email(name_parts)
        assert email_with_name.startswith("john.doe@")
    
    def test_generate_synthetic_company(self):
        """Test synthetic company generation."""
        anonymizer = DataAnonymizer()
        
        company = anonymizer.generate_synthetic_company()
        assert company in anonymizer.company_names
    
    def test_anonymize_data_redact(self):
        """Test data anonymization with redaction method."""
        anonymizer = DataAnonymizer()
        
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "company": "TechCorp",
            "public_info": "Not sensitive"
        }
        
        fields_to_anonymize = {"first_name", "last_name", "email"}
        anonymized = anonymizer.anonymize_data(data, fields_to_anonymize, "redact")
        
        # Specified fields should be redacted
        assert anonymized["first_name"] == "[REDACTED]"
        assert anonymized["last_name"] == "[REDACTED]"
        assert anonymized["email"] == "[REDACTED]"
        
        # Other fields should remain unchanged
        assert anonymized["company"] == "TechCorp"
        assert anonymized["public_info"] == "Not sensitive"
    
    def test_anonymize_data_mask(self):
        """Test data anonymization with masking method."""
        anonymizer = DataAnonymizer()
        
        data = {
            "first_name": "John",
            "email": "john@example.com"
        }
        
        fields_to_anonymize = {"first_name", "email"}
        anonymized = anonymizer.anonymize_data(data, fields_to_anonymize, "mask")
        
        # Should be partially masked
        assert anonymized["first_name"] == "J**n"
        assert "@" in anonymized["email"]  # Email format preserved
        assert anonymized["email"] != data["email"]
    
    def test_anonymize_data_synthetic(self):
        """Test data anonymization with synthetic method."""
        anonymizer = DataAnonymizer()
        
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp"
        }
        
        fields_to_anonymize = {"first_name", "email", "company"}
        anonymized = anonymizer.anonymize_data(data, fields_to_anonymize, "synthetic")
        
        # Should generate synthetic values
        assert anonymized["first_name"] in anonymizer.first_names
        assert "@" in anonymized["email"]
        assert anonymized["company"] in anonymizer.company_names
        
        # Should be different from original
        assert anonymized["first_name"] != data["first_name"]
        assert anonymized["email"] != data["email"]
        assert anonymized["company"] != data["company"]
    
    def test_anonymize_nested_data(self):
        """Test anonymization of nested data structures."""
        anonymizer = DataAnonymizer()
        
        data = {
            "user": {
                "first_name": "John",
                "email": "john@example.com"
            },
            "contacts": [
                {"name": "Jane", "email": "jane@example.com"},
                {"name": "Bob", "email": "bob@example.com"}
            ]
        }
        
        fields_to_anonymize = {"first_name", "email", "name"}
        anonymized = anonymizer.anonymize_data(data, fields_to_anonymize, "redact")
        
        # Nested dictionary
        assert anonymized["user"]["first_name"] == "[REDACTED]"
        assert anonymized["user"]["email"] == "[REDACTED]"
        
        # List of dictionaries
        assert anonymized["contacts"][0]["name"] == "[REDACTED]"
        assert anonymized["contacts"][0]["email"] == "[REDACTED]"
    
    def test_pseudonymize_data(self):
        """Test data pseudonymization."""
        anonymizer = DataAnonymizer("test_salt")
        
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "company": "TechCorp"
        }
        
        pseudonymized = anonymizer.pseudonymize_data(data)
        
        # Should be pseudonymized but consistent
        assert pseudonymized["first_name"] != data["first_name"]
        assert pseudonymized["email"] != data["email"]
        assert pseudonymized["phone"] != data["phone"]
        
        # Should be consistent across calls
        pseudonymized2 = anonymizer.pseudonymize_data(data)
        assert pseudonymized == pseudonymized2
        
        # Phone should preserve format
        assert len(pseudonymized["phone"]) == len(data["phone"])
        
        # Email should preserve @ symbol
        assert "@" in pseudonymized["email"]
    
    def test_create_anonymization_report(self):
        """Test anonymization report creation."""
        anonymizer = DataAnonymizer()
        
        original_data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp"
        }
        
        anonymized_data = {
            "first_name": "[REDACTED]",
            "email": "[REDACTED]",
            "company": "TechCorp"
        }
        
        fields_processed = {"first_name", "email"}
        
        report = anonymizer.create_anonymization_report(
            original_data, anonymized_data, fields_processed
        )
        
        assert "timestamp" in report
        assert report["fields_processed"] == ["first_name", "email"]
        assert report["total_fields"] == 3
        assert report["anonymized_fields"] == 2
        assert report["anonymization_rate"] == 2/3
        assert report["method"] == "anonymization"
    
    def test_generate_synthetic_value(self):
        """Test synthetic value generation by field type."""
        anonymizer = DataAnonymizer()
        
        # Test different field types
        test_cases = [
            ("first_name", "John"),
            ("last_name", "Doe"),
            ("email", "john@example.com"),
            ("phone", "555-1234"),
            ("company", "TechCorp"),
            ("unknown_field", "some_value")
        ]
        
        for field_name, original_value in test_cases:
            synthetic = anonymizer._generate_synthetic_value(field_name, original_value)
            
            assert isinstance(synthetic, str)
            assert len(synthetic) > 0
            assert synthetic != original_value
            
            # Check type-specific generation
            if "first_name" in field_name:
                assert synthetic in anonymizer.first_names
            elif "last_name" in field_name:
                assert synthetic in anonymizer.last_names
            elif "email" in field_name:
                assert "@" in synthetic
            elif "company" in field_name:
                assert synthetic in anonymizer.company_names


class TestDataAnonymizationUtilities:
    """Test data anonymization utility functions."""
    
    def test_anonymize_data_utility(self):
        """Test anonymize data utility function."""
        data = {
            "first_name": "John",
            "email": "john@example.com",
            "company": "TechCorp"
        }
        
        anonymized = anonymize_data(data, {"first_name", "email"}, "redact")
        
        assert anonymized["first_name"] == "[REDACTED]"
        assert anonymized["email"] == "[REDACTED]"
        assert anonymized["company"] == "TechCorp"
    
    def test_pseudonymize_data_utility(self):
        """Test pseudonymize data utility function."""
        data = {
            "first_name": "John",
            "email": "john@example.com"
        }
        
        pseudonymized = pseudonymize_data(data, {"first_name", "email"})
        
        assert pseudonymized["first_name"] != data["first_name"]
        assert pseudonymized["email"] != data["email"]
        assert "@" in pseudonymized["email"]
    
    def test_generate_synthetic_data_utility(self):
        """Test synthetic data generation utility."""
        # Test name generation
        name = generate_synthetic_data("name")
        assert "first_name" in name
        assert "last_name" in name
        
        # Test email generation
        email = generate_synthetic_data("email")
        assert "@" in email
        
        # Test phone generation
        phone = generate_synthetic_data("phone")
        assert re.match(r'\(\d{3}\) \d{3}-\d{4}', phone)
        
        # Test company generation
        company = generate_synthetic_data("company")
        assert isinstance(company, str)
        assert len(company) > 0
        
        # Test invalid type
        with pytest.raises(ValueError, match="Unsupported data type"):
            generate_synthetic_data("invalid_type")


class TestDataAnonymizationIntegration:
    """Test data anonymization integration scenarios."""
    
    def test_consistent_pseudonymization(self):
        """Test that pseudonymization is consistent across sessions."""
        salt = "consistent_salt"
        
        data = {
            "first_name": "John",
            "email": "john@example.com"
        }
        
        # Create two anonymizers with same salt
        anonymizer1 = DataAnonymizer(salt)
        anonymizer2 = DataAnonymizer(salt)
        
        pseudo1 = anonymizer1.pseudonymize_data(data)
        pseudo2 = anonymizer2.pseudonymize_data(data)
        
        # Should produce identical results
        assert pseudo1 == pseudo2
    
    def test_different_salt_different_results(self):
        """Test that different salts produce different pseudonymization."""
        data = {
            "first_name": "John",
            "email": "john@example.com"
        }
        
        anonymizer1 = DataAnonymizer("salt1")
        anonymizer2 = DataAnonymizer("salt2")
        
        pseudo1 = anonymizer1.pseudonymize_data(data)
        pseudo2 = anonymizer2.pseudonymize_data(data)
        
        # Should produce different results
        assert pseudo1 != pseudo2
    
    def test_real_world_data_anonymization(self):
        """Test anonymization of realistic data structures."""
        anonymizer = DataAnonymizer()
        
        # Simulate customer data
        customer_data = {
            "customer_id": "CUST-12345",
            "personal_info": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@techcorp.com",
                "phone": "+1-555-123-4567",
                "address": "123 Main St, Anytown, USA"
            },
            "company_info": {
                "company": "TechCorp Inc.",
                "title": "CTO",
                "industry": "Technology"
            },
            "interaction_history": [
                {
                    "date": "2024-01-01",
                    "type": "call",
                    "notes": "Discussed AI implementation needs",
                    "agent": "Sarah Johnson"
                },
                {
                    "date": "2024-01-15", 
                    "type": "email",
                    "notes": "Sent pricing proposal",
                    "agent": "Mike Smith"
                }
            ],
            "sensitive_data": {
                "ssn": "123-45-6789",
                "credit_score": "750",
                "bank_account": "1234567890"
            }
        }
        
        # Define fields to anonymize
        fields_to_anonymize = {
            "first_name", "last_name", "email", "phone", "address",
            "ssn", "credit_score", "bank_account", "notes", "agent"
        }
        
        # Test different anonymization methods
        redacted = anonymizer.anonymize_data(customer_data, fields_to_anonymize, "redact")
        masked = anonymizer.anonymize_data(customer_data, fields_to_anonymize, "mask")
        synthetic = anonymizer.anonymize_data(customer_data, fields_to_anonymize, "synthetic")
        
        # Verify redaction
        assert redacted["personal_info"]["first_name"] == "[REDACTED]"
        assert redacted["sensitive_data"]["ssn"] == "[REDACTED]"
        
        # Verify masking preserves some structure
        assert len(masked["personal_info"]["first_name"]) == len("John")
        assert "@" in masked["personal_info"]["email"]
        
        # Verify synthetic data is realistic
        assert synthetic["personal_info"]["first_name"] in anonymizer.first_names
        assert "@" in synthetic["personal_info"]["email"]
        
        # Non-sensitive data should remain unchanged
        assert redacted["customer_id"] == "CUST-12345"
        assert redacted["company_info"]["industry"] == "Technology"
    
    def test_performance_with_large_datasets(self):
        """Test anonymization performance with large datasets."""
        anonymizer = DataAnonymizer()
        
        # Create large dataset
        large_data = {}
        for i in range(1000):
            large_data[f"field_{i}"] = f"value_{i}"
            if i % 10 == 0:
                large_data[f"email_{i}"] = f"user{i}@example.com"
            if i % 20 == 0:
                large_data[f"phone_{i}"] = f"555-{i:04d}"
        
        fields_to_anonymize = {f"email_{i}" for i in range(0, 1000, 10)}
        fields_to_anonymize.update({f"phone_{i}" for i in range(0, 1000, 20)})
        
        # Should handle large datasets efficiently
        import time
        start_time = time.time()
        
        anonymized = anonymizer.anonymize_data(large_data, fields_to_anonymize, "redact")
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        assert processing_time < 5.0, f"Anonymization took too long: {processing_time}s"
        
        # Verify results
        assert len(anonymized) == len(large_data)
        
        # Check that specified fields were anonymized
        for field in fields_to_anonymize:
            if field in anonymized:
                assert anonymized[field] == "[REDACTED]"
    
    def test_edge_cases(self):
        """Test edge cases in anonymization."""
        anonymizer = DataAnonymizer()
        
        # Empty data
        assert anonymizer.anonymize_data({}) == {}
        assert anonymizer.pseudonymize_data({}) == {}
        
        # None values
        data_with_none = {
            "first_name": None,
            "email": "",
            "phone": "555-1234"
        }
        
        anonymized = anonymizer.anonymize_data(data_with_none, {"first_name", "email", "phone"})
        
        # None and empty values should be handled gracefully
        assert anonymized["first_name"] is None
        assert anonymized["email"] == ""
        assert anonymized["phone"] == "[REDACTED]"
        
        # Very short strings
        short_data = {"name": "A", "code": "XY"}
        masked = anonymizer.anonymize_data(short_data, {"name", "code"}, "mask")
        
        # Should handle short strings appropriately
        assert len(masked["name"]) == 1
        assert len(masked["code"]) == 2
    
    def test_thread_safety(self):
        """Test thread safety of anonymization operations."""
        import threading
        import time
        
        anonymizer = DataAnonymizer("thread_test_salt")
        
        data = {
            "first_name": "John",
            "email": "john@example.com"
        }
        
        results = []
        errors = []
        
        def anonymize_worker(worker_id):
            try:
                for i in range(10):
                    result = anonymizer.pseudonymize_data(data)
                    results.append((worker_id, i, result))
                    time.sleep(0.001)
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=anonymize_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Anonymization errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations
        
        # All results should be identical (same salt, same data)
        first_result = results[0][2]
        for _, _, result in results:
            assert result == first_result


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
        "company": "TechCorp Inc.",
        "title": "Software Engineer"
    }


@pytest.fixture
def data_anonymizer():
    """Data anonymizer fixture."""
    return DataAnonymizer("test_salt_123")