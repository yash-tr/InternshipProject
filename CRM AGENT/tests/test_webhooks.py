"""
Tests for webhook endpoints.
"""
import pytest
from fastapi.testclient import TestClient


def test_twilio_webhook_endpoint(client: TestClient, mock_twilio_request):
    """Test Twilio incoming call webhook."""
    response = client.post(
        "/api/v1/webhooks/twilio/incoming-call",
        data=mock_twilio_request
    )
    
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    
    # Check TwiML response structure
    content = response.content.decode()
    assert "<?xml version=" in content
    assert "<Response>" in content
    assert "<Say" in content
    assert "</Response>" in content


def test_salesforce_webhook_endpoint(client: TestClient, mock_salesforce_lead):
    """Test Salesforce lead creation webhook."""
    response = client.post(
        "/api/v1/webhooks/salesforce/lead-created",
        json=mock_salesforce_lead
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "message" in data


def test_webhook_test_endpoint(client: TestClient):
    """Test webhook test endpoint."""
    response = client.get("/api/v1/webhooks/test")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["version"] == "0.1.0"


def test_twilio_webhook_missing_fields(client: TestClient):
    """Test Twilio webhook with missing required fields."""
    incomplete_data = {
        "From": "+1234567890",
        # Missing CallSid, To, CallStatus
    }
    
    response = client.post(
        "/api/v1/webhooks/twilio/incoming-call",
        data=incomplete_data
    )
    
    assert response.status_code == 422  # Validation error