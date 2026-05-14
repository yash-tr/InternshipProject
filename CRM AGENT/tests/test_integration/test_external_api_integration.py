"""
Integration tests for External API Management System.

Tests circuit breakers, rate limiting, health monitoring, caching,
cost tracking, and failover logic for all external API integrations.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import httpx

from app.services.external_api_manager import (
    ExternalAPIManager,
    APIProvider,
    CircuitBreakerState,
    APICallResult,
    APIEndpoint,
    CircuitBreaker,
    RateLimiter,
    APIMetrics,
    external_api_manager
)


class TestExternalAPIManager:
    """Test external API manager functionality."""
    
    @pytest.fixture
    async def api_manager(self):
        """Create API manager for testing."""
        manager = ExternalAPIManager()
        
        # Mock Redis client
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.redis_client.get.return_value = None
        manager.redis_client.setex.return_value = True
        manager.redis_client.hgetall.return_value = {}
        manager.redis_client.hset.return_value = True
        manager.redis_client.expire.return_value = True
        
        # Mock HTTP client
        manager.http_client = AsyncMock()
        
        # Mock audit service
        manager.audit_service = AsyncMock()
        manager.audit_service.log_api_call.return_value = None
        manager.audit_service.log_api_call_error.return_value = None
        
        await manager.initialize()
        return manager
    
    @pytest.fixture
    def mock_successful_response(self):
        """Mock successful HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True, "data": "test_data"}
        response.text = '{"success": true, "data": "test_data"}'
        return response
    
    @pytest.fixture
    def mock_error_response(self):
        """Mock error HTTP response."""
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        return response
    
    @pytest.mark.asyncio
    async def test_successful_api_call(self, api_manager, mock_successful_response):
        """Test successful API call with all features."""
        # Setup mock response
        api_manager.http_client.request.return_value = mock_successful_response
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead",
            cache_key="leads_list"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["data"]["success"] is True
        assert result["cached"] is False
        assert "request_id" in result
        assert "response_time" in result
        
        # Verify HTTP client was called
        api_manager.http_client.request.assert_called_once()
        
        # Verify audit logging
        api_manager.audit_service.log_api_call.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cached_response(self, api_manager):
        """Test cached response handling."""
        # Setup cached response
        cached_data = {"cached": True, "data": "cached_data"}
        api_manager.redis_client.get.return_value = json.dumps(cached_data)
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead",
            cache_key="leads_list"
        )
        
        # Verify cached response
        assert result["success"] is True
        assert result["cached"] is True
        assert result["data"] == cached_data
        
        # Verify HTTP client was NOT called
        api_manager.http_client.request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self, api_manager):
        """Test circuit breaker in open state blocking requests."""
        # Set circuit breaker to open state
        cb = api_manager.circuit_breakers["salesforce_api"]
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 10
        cb.next_attempt_time = datetime.utcnow() + timedelta(minutes=5)
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify request was blocked
        assert result["success"] is False
        assert "Circuit breaker is open" in result["error"]
        assert result["circuit_state"] == "open"
        
        # Verify HTTP client was NOT called
        api_manager.http_client.request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_transition(self, api_manager, mock_successful_response):
        """Test circuit breaker transition from open to half-open to closed."""
        # Set circuit breaker to open state with expired timeout
        cb = api_manager.circuit_breakers["salesforce_api"]
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 5
        cb.next_attempt_time = datetime.utcnow() - timedelta(seconds=1)  # Expired
        
        # Setup successful response
        api_manager.http_client.request.return_value = mock_successful_response
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify request succeeded
        assert result["success"] is True
        
        # Verify circuit breaker transitioned to half-open
        assert cb.state == CircuitBreakerState.HALF_OPEN
        
        # Make more successful calls to close circuit breaker
        for _ in range(2):  # Need 3 total successes
            await api_manager.make_api_call(
                endpoint_name="salesforce_api",
                method="GET",
                path="/services/data/v52.0/sobjects/Lead"
            )
        
        # Verify circuit breaker is now closed
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, api_manager):
        """Test rate limiting functionality."""
        # Get rate limiter
        rl = api_manager.rate_limiters["salesforce_api"]
        
        # Set low limits for testing
        rl.requests_per_minute = 2
        rl.current_minute_count = 2  # At limit
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify request was rate limited
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        assert "rate_limit_info" in result
        
        # Verify HTTP client was NOT called
        api_manager.http_client.request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_api_call_with_retries(self, api_manager, mock_error_response, mock_successful_response):
        """Test API call retry logic."""
        # Setup responses: first call fails, second succeeds
        api_manager.http_client.request.side_effect = [
            mock_error_response,
            mock_successful_response
        ]
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify eventual success
        assert result["success"] is True
        assert result["data"]["success"] is True
        
        # Verify retry was attempted
        assert api_manager.http_client.request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, api_manager):
        """Test timeout handling."""
        # Setup timeout exception
        api_manager.http_client.request.side_effect = httpx.TimeoutException("Request timeout")
        
        # Make API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify timeout was handled
        assert result["success"] is False
        assert "Request timeout" in result["error"]
        
        # Verify circuit breaker recorded failure
        cb = api_manager.circuit_breakers["salesforce_api"]
        assert cb.failure_count > 0
    
    @pytest.mark.asyncio
    async def test_cost_tracking(self, api_manager, mock_successful_response):
        """Test API cost tracking."""
        # Setup successful response
        api_manager.http_client.request.return_value = mock_successful_response
        
        # Get initial cost
        initial_metrics = api_manager.metrics["salesforce_api"]
        initial_cost = initial_metrics.total_cost
        
        # Make API call
        await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify cost was tracked
        endpoint_config = api_manager.endpoints["salesforce_api"]
        expected_cost = initial_cost + endpoint_config.cost_per_request
        
        assert initial_metrics.total_cost == expected_cost
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, api_manager, mock_successful_response):
        """Test comprehensive metrics collection."""
        # Setup successful response
        api_manager.http_client.request.return_value = mock_successful_response
        
        # Get initial metrics
        metrics = api_manager.metrics["salesforce_api"]
        initial_requests = metrics.total_requests
        initial_successes = metrics.successful_requests
        
        # Make API call
        await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead"
        )
        
        # Verify metrics were updated
        assert metrics.total_requests == initial_requests + 1
        assert metrics.successful_requests == initial_successes + 1
        assert metrics.last_success_time is not None
        assert metrics.average_response_time > 0
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, api_manager):
        """Test API health monitoring."""
        # Mock health check response
        health_response = MagicMock()
        health_response.status_code = 200
        api_manager.http_client.get.return_value = health_response
        
        # Perform health check
        await api_manager._perform_health_check(
            "salesforce_auth",
            api_manager.endpoints["salesforce_auth"]
        )
        
        # Verify health status was updated
        health_status = api_manager.health_status.get("salesforce_auth")
        assert health_status is not None
        assert health_status["status"] == "healthy"
        assert "response_time" in health_status
        assert "last_check" in health_status
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, api_manager):
        """Test manual circuit breaker reset."""
        # Set circuit breaker to open state
        cb = api_manager.circuit_breakers["salesforce_api"]
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 10
        
        # Reset circuit breaker
        success = await api_manager.reset_circuit_breaker("salesforce_api")
        
        # Verify reset was successful
        assert success is True
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
    
    @pytest.mark.asyncio
    async def test_endpoint_configuration_update(self, api_manager):
        """Test dynamic endpoint configuration updates."""
        # Update configuration
        config_updates = {
            "timeout_seconds": 45.0,
            "max_retries": 5,
            "rate_limit_per_minute": 120,
            "cost_per_request": 0.005
        }
        
        success = await api_manager.update_endpoint_configuration(
            "salesforce_api",
            config_updates
        )
        
        # Verify update was successful
        assert success is True
        
        # Verify configuration was updated
        endpoint = api_manager.endpoints["salesforce_api"]
        assert endpoint.timeout_seconds == 45.0
        assert endpoint.max_retries == 5
        assert endpoint.rate_limit_per_minute == 120
        assert endpoint.cost_per_request == 0.005
        
        # Verify rate limiter was updated
        rl = api_manager.rate_limiters["salesforce_api"]
        assert rl.requests_per_minute == 120
    
    @pytest.mark.asyncio
    async def test_get_api_metrics(self, api_manager):
        """Test API metrics retrieval."""
        # Setup some test metrics
        metrics = api_manager.metrics["salesforce_api"]
        metrics.total_requests = 100
        metrics.successful_requests = 85
        metrics.failed_requests = 15
        metrics.total_cost = 2.50
        metrics.average_response_time = 1.5
        
        # Get metrics for specific endpoint
        endpoint_metrics = await api_manager.get_api_metrics("salesforce_api")
        
        assert endpoint_metrics["total_requests"] == 100
        assert endpoint_metrics["success_rate"] == 0.85
        assert endpoint_metrics["total_cost"] == 2.50
        assert endpoint_metrics["average_response_time"] == 1.5
        
        # Get metrics for all endpoints
        all_metrics = await api_manager.get_api_metrics()
        
        assert "endpoints" in all_metrics
        assert "totals" in all_metrics
        assert "timestamp" in all_metrics
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_status(self, api_manager):
        """Test circuit breaker status retrieval."""
        # Setup circuit breaker state
        cb = api_manager.circuit_breakers["salesforce_api"]
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.failure_count = 3
        
        # Get status for specific endpoint
        cb_status = await api_manager.get_circuit_breaker_status("salesforce_api")
        
        assert cb_status["state"] == "half_open"
        assert cb_status["failure_count"] == 3
        assert cb_status["failure_threshold"] == cb.failure_threshold
        
        # Get status for all endpoints
        all_cb_status = await api_manager.get_circuit_breaker_status()
        
        assert "circuit_breakers" in all_cb_status
        assert "timestamp" in all_cb_status
    
    @pytest.mark.asyncio
    async def test_health_status_retrieval(self, api_manager):
        """Test health status retrieval."""
        # Setup health status
        api_manager.health_status["salesforce_api"] = {
            "status": "healthy",
            "response_time": 0.5,
            "last_check": datetime.utcnow().isoformat()
        }
        
        # Get health status for specific endpoint
        health_status = await api_manager.get_api_health_status("salesforce_api")
        
        assert health_status["status"] == "healthy"
        assert "response_time" in health_status
        
        # Get health status for all endpoints
        all_health = await api_manager.get_api_health_status()
        
        assert "endpoints" in all_health
        assert "overall_health" in all_health
        assert "timestamp" in all_health


class TestSpecificAPIIntegrations:
    """Test specific API integrations."""
    
    @pytest.fixture
    async def api_manager(self):
        """Create API manager for testing."""
        manager = ExternalAPIManager()
        
        # Mock dependencies
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.redis_client.get.return_value = None
        manager.redis_client.setex.return_value = True
        manager.redis_client.hgetall.return_value = {}
        manager.redis_client.hset.return_value = True
        manager.redis_client.expire.return_value = True
        
        manager.http_client = AsyncMock()
        manager.audit_service = AsyncMock()
        
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_salesforce_api_integration(self, api_manager):
        """Test Salesforce API integration."""
        # Mock successful Salesforce response
        sf_response = MagicMock()
        sf_response.status_code = 200
        sf_response.json.return_value = {
            "records": [
                {"Id": "00Q123", "Name": "Test Lead", "Phone": "+1234567890"}
            ]
        }
        
        api_manager.http_client.request.return_value = sf_response
        
        # Make Salesforce API call
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead",
            params={"limit": 10},
            cache_key="leads_recent"
        )
        
        # Verify Salesforce-specific handling
        assert result["success"] is True
        assert "records" in result["data"]
        assert len(result["data"]["records"]) == 1
        
        # Verify caching was attempted
        api_manager.redis_client.setex.assert_called()
    
    @pytest.mark.asyncio
    async def test_elevenlabs_tts_integration(self, api_manager):
        """Test ElevenLabs TTS API integration."""
        # Mock TTS response
        tts_response = MagicMock()
        tts_response.status_code = 200
        tts_response.json.return_value = {
            "audio_url": "https://api.elevenlabs.io/audio/123.mp3",
            "duration": 5.2
        }
        
        api_manager.http_client.request.return_value = tts_response
        
        # Make TTS API call
        result = await api_manager.make_api_call(
            endpoint_name="elevenlabs_tts",
            method="POST",
            path="/text-to-speech/voice-id",
            data={
                "text": "Hello, this is a test message",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
            }
        )
        
        # Verify TTS-specific handling
        assert result["success"] is True
        assert "audio_url" in result["data"]
        assert "duration" in result["data"]
        
        # Verify ElevenLabs headers were included
        call_args = api_manager.http_client.request.call_args
        headers = call_args[1]["headers"]
        assert "xi-api-key" in headers
    
    @pytest.mark.asyncio
    async def test_openrouter_llm_integration(self, api_manager):
        """Test OpenRouter LLM API integration."""
        # Mock LLM response
        llm_response = MagicMock()
        llm_response.status_code = 200
        llm_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "This is a test response from the LLM."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 15,
                "total_tokens": 35
            }
        }
        
        api_manager.http_client.request.return_value = llm_response
        
        # Make LLM API call
        result = await api_manager.make_api_call(
            endpoint_name="openrouter_llm",
            method="POST",
            path="/chat/completions",
            data={
                "model": "mistralai/mistral-nemo:free",
                "messages": [
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "max_tokens": 100
            }
        )
        
        # Verify LLM-specific handling
        assert result["success"] is True
        assert "choices" in result["data"]
        assert "usage" in result["data"]
        
        # Verify OpenRouter headers were included
        call_args = api_manager.http_client.request.call_args
        headers = call_args[1]["headers"]
        assert "Authorization" in headers
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers
    
    @pytest.mark.asyncio
    async def test_twilio_voice_integration(self, api_manager):
        """Test Twilio Voice API integration."""
        # Mock Twilio response
        twilio_response = MagicMock()
        twilio_response.status_code = 201
        twilio_response.json.return_value = {
            "sid": "CA123456789",
            "status": "queued",
            "to": "+1234567890",
            "from": "+0987654321"
        }
        
        api_manager.http_client.request.return_value = twilio_response
        
        # Make Twilio API call
        result = await api_manager.make_api_call(
            endpoint_name="twilio_voice",
            method="POST",
            path="/Calls.json",
            data={
                "To": "+1234567890",
                "From": "+0987654321",
                "Url": "https://example.com/twiml"
            }
        )
        
        # Verify Twilio-specific handling
        assert result["success"] is True
        assert "sid" in result["data"]
        assert "status" in result["data"]
        
        # Verify status code handling (201 for created)
        assert result["status_code"] == 201


class TestAPIFailoverAndRecovery:
    """Test API failover and recovery mechanisms."""
    
    @pytest.fixture
    async def api_manager(self):
        """Create API manager for testing."""
        manager = ExternalAPIManager()
        
        # Mock dependencies
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.redis_client.get.return_value = None
        manager.redis_client.setex.return_value = True
        manager.redis_client.hgetall.return_value = {}
        manager.redis_client.hset.return_value = True
        manager.redis_client.expire.return_value = True
        
        manager.http_client = AsyncMock()
        manager.audit_service = AsyncMock()
        
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self, api_manager):
        """Test circuit breaker opens after failure threshold."""
        # Mock error responses
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        
        api_manager.http_client.request.return_value = error_response
        
        # Get circuit breaker
        cb = api_manager.circuit_breakers["salesforce_api"]
        initial_threshold = cb.failure_threshold
        
        # Make multiple failing requests
        for i in range(initial_threshold):
            result = await api_manager.make_api_call(
                endpoint_name="salesforce_api",
                method="GET",
                path="/test"
            )
            assert result["success"] is False
        
        # Verify circuit breaker opened
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count >= initial_threshold
        
        # Next request should be blocked by circuit breaker
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/test"
        )
        
        assert result["success"] is False
        assert "Circuit breaker is open" in result["error"]
    
    @pytest.mark.asyncio
    async def test_automatic_recovery_after_timeout(self, api_manager):
        """Test automatic recovery after circuit breaker timeout."""
        # Set circuit breaker to open with expired timeout
        cb = api_manager.circuit_breakers["salesforce_api"]
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 10
        cb.next_attempt_time = datetime.utcnow() - timedelta(seconds=1)  # Expired
        
        # Mock successful response for recovery
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}
        
        api_manager.http_client.request.return_value = success_response
        
        # Make API call (should transition to half-open)
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/test"
        )
        
        # Verify request succeeded and circuit breaker transitioned
        assert result["success"] is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_rate_limit_recovery(self, api_manager):
        """Test rate limit recovery after window reset."""
        # Get rate limiter and set to limit
        rl = api_manager.rate_limiters["salesforce_api"]
        rl.requests_per_minute = 1
        rl.current_minute_count = 1
        rl.minute_window_start = datetime.utcnow() - timedelta(seconds=30)
        
        # First request should be rate limited
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/test"
        )
        
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        
        # Simulate window reset
        rl.minute_window_start = datetime.utcnow() - timedelta(minutes=2)
        
        # Mock successful response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}
        
        api_manager.http_client.request.return_value = success_response
        
        # Next request should succeed
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/test"
        )
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_cache_fallback_on_api_failure(self, api_manager):
        """Test cache fallback when API fails."""
        # Setup cached response
        cached_data = {"fallback": True, "data": "cached_fallback_data"}
        api_manager.redis_client.get.return_value = json.dumps(cached_data)
        
        # Mock API failure
        api_manager.http_client.request.side_effect = Exception("API unavailable")
        
        # Make API call with cache key
        result = await api_manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/test",
            cache_key="test_data"
        )
        
        # Should return cached data instead of failing
        assert result["success"] is True
        assert result["cached"] is True
        assert result["data"] == cached_data


@pytest.mark.integration
class TestExternalAPIIntegrationEndToEnd:
    """End-to-end integration tests for external API system."""
    
    @pytest.mark.asyncio
    async def test_complete_api_workflow_with_all_features(self):
        """Test complete API workflow with all features enabled."""
        # This test would simulate a complete workflow:
        # 1. API call with caching
        # 2. Circuit breaker monitoring
        # 3. Rate limiting
        # 4. Health checking
        # 5. Metrics collection
        # 6. Cost tracking
        # 7. Error handling and recovery
        
        manager = ExternalAPIManager()
        
        # Mock all dependencies
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.redis_client.get.return_value = None
        manager.redis_client.setex.return_value = True
        manager.redis_client.hgetall.return_value = {}
        manager.redis_client.hset.return_value = True
        manager.redis_client.expire.return_value = True
        
        manager.http_client = AsyncMock()
        manager.audit_service = AsyncMock()
        
        await manager.initialize()
        
        # Mock successful response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "id": "test123",
            "name": "Test Record",
            "status": "active"
        }
        
        manager.http_client.request.return_value = success_response
        
        # Make API call
        result = await manager.make_api_call(
            endpoint_name="salesforce_api",
            method="GET",
            path="/services/data/v52.0/sobjects/Lead/test123",
            cache_key="lead_test123"
        )
        
        # Verify all features worked
        assert result["success"] is True
        assert "request_id" in result
        assert "response_time" in result
        assert result["cached"] is False
        
        # Verify metrics were updated
        metrics = manager.metrics["salesforce_api"]
        assert metrics.total_requests > 0
        assert metrics.successful_requests > 0
        assert metrics.total_cost > 0
        
        # Verify circuit breaker is still closed
        cb = manager.circuit_breakers["salesforce_api"]
        assert cb.state == CircuitBreakerState.CLOSED
        
        # Verify audit logging
        manager.audit_service.log_api_call.assert_called()
    
    @pytest.mark.asyncio
    async def test_concurrent_api_calls_with_rate_limiting(self):
        """Test concurrent API calls with rate limiting."""
        manager = ExternalAPIManager()
        
        # Mock dependencies
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.redis_client.get.return_value = None
        manager.redis_client.setex.return_value = True
        manager.redis_client.hgetall.return_value = {}
        manager.redis_client.hset.return_value = True
        manager.redis_client.expire.return_value = True
        
        manager.http_client = AsyncMock()
        manager.audit_service = AsyncMock()
        
        await manager.initialize()
        
        # Set low rate limit for testing
        rl = manager.rate_limiters["salesforce_api"]
        rl.requests_per_minute = 3
        
        # Mock successful response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}
        
        manager.http_client.request.return_value = success_response
        
        # Make concurrent API calls
        tasks = [
            manager.make_api_call(
                endpoint_name="salesforce_api",
                method="GET",
                path=f"/test/{i}"
            )
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should succeed, some should be rate limited
        successful_calls = [r for r in results if isinstance(r, dict) and r.get("success")]
        rate_limited_calls = [r for r in results if isinstance(r, dict) and not r.get("success") and "Rate limit" in r.get("error", "")]
        
        assert len(successful_calls) <= 3  # Rate limit
        assert len(rate_limited_calls) >= 2  # Excess calls
    
    @pytest.mark.asyncio
    async def test_api_health_monitoring_and_alerting(self):
        """Test API health monitoring and alerting."""
        manager = ExternalAPIManager()
        
        # Mock dependencies
        manager.redis_client = AsyncMock()
        manager.redis_client.ping.return_value = True
        manager.http_client = AsyncMock()
        manager.audit_service = AsyncMock()
        
        await manager.initialize()
        
        # Mock health check responses
        healthy_response = MagicMock()
        healthy_response.status_code = 200
        
        unhealthy_response = MagicMock()
        unhealthy_response.status_code = 503
        
        # Test healthy endpoint
        manager.http_client.get.return_value = healthy_response
        
        await manager._perform_health_check(
            "salesforce_auth",
            manager.endpoints["salesforce_auth"]
        )
        
        health_status = manager.health_status.get("salesforce_auth")
        assert health_status["status"] == "healthy"
        
        # Test unhealthy endpoint
        manager.http_client.get.return_value = unhealthy_response
        
        await manager._perform_health_check(
            "salesforce_auth",
            manager.endpoints["salesforce_auth"]
        )
        
        health_status = manager.health_status.get("salesforce_auth")
        assert health_status["status"] == "unhealthy"
        
        # Test overall health calculation
        overall_health = manager._calculate_overall_health()
        assert overall_health in ["healthy", "degraded", "unhealthy"]