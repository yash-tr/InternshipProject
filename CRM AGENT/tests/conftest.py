"""
Test configuration and fixtures.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

# Set test environment variables before importing app modules
os.environ.update({
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-secret-key-32-characters-long",
    "SALESFORCE_CLIENT_ID": "test_client_id",
    "SALESFORCE_CLIENT_SECRET": "test_client_secret", 
    "SALESFORCE_USERNAME": "test@example.com",
    "SALESFORCE_PASSWORD": "test_password",
    "SALESFORCE_SECURITY_TOKEN": "test_token",
    "TWILIO_ACCOUNT_SID": "test_account_sid",
    "TWILIO_AUTH_TOKEN": "test_auth_token",
    "TWILIO_PHONE_NUMBER": "+1234567890",
    "ELEVENLABS_API_KEY": "test_elevenlabs_key",
    "OPENROUTER_API_KEY": "test_openrouter_key",
    "ENCRYPTION_KEY": "test-encryption-key-32-chars-long"
})

from app.main import app
from app.core.config import get_settings
from fastapi.testclient import TestClient


@pytest.fixture
def test_app():
    """FastAPI test application."""
    return app


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    return get_settings()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services for all tests."""
    with patch('app.services.salesforce.aiohttp.ClientSession'), \
         patch('app.utils.encryption.get_encryption_manager'):
        yield