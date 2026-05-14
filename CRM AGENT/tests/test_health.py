"""
Tests for health check functionality.
"""
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_exists(client: TestClient):
    """Test that health endpoint is accessible."""
    response = client.get("/health")
    assert response.status_code in [200, 503]  # Either healthy or unhealthy
    
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "timestamp" in data
    assert "version" in data


def test_health_endpoint_structure(client: TestClient):
    """Test health endpoint response structure."""
    response = client.get("/health")
    data = response.json()
    
    # Check main structure
    assert isinstance(data["status"], str)
    assert isinstance(data["services"], dict)
    assert isinstance(data["timestamp"], (int, float))
    assert isinstance(data["version"], str)
    
    # Check services structure
    services = data["services"]
    expected_services = ["database", "salesforce", "elevenlabs", "openrouter", "twilio", "llm_service"]
    
    for service in expected_services:
        assert service in services
        service_data = services[service]
        assert "status" in service_data
        assert service_data["status"] in ["healthy", "unhealthy"]


def test_metrics_endpoint_exists(client: TestClient):
    """Test that metrics endpoint is accessible."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_database_health_check():
    """Test database health check function."""
    from app.core.health import check_database_health
    
    result = await check_database_health()
    assert "status" in result
    assert result["status"] in ["healthy", "unhealthy"]
    
    if result["status"] == "healthy":
        assert "response_time_ms" in result
        assert isinstance(result["response_time_ms"], (int, float))