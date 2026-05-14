"""
Pytest configuration for schema tests only.
"""
import os
import pytest

# Set minimal test environment variables to avoid import errors
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SALESFORCE_CLIENT_ID", "test-client-id")
os.environ.setdefault("SALESFORCE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("SALESFORCE_USERNAME", "test@example.com")
os.environ.setdefault("SALESFORCE_PASSWORD", "test-password")
os.environ.setdefault("SALESFORCE_SECURITY_TOKEN", "test-token")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test-account-sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15551234567")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ENVIRONMENT", "test")