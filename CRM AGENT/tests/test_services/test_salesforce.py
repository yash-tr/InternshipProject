"""
Integration tests for Salesforce service.
Tests OAuth authentication, CRUD operations, and error handling.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from app.services.salesforce import (
    SalesforceService,
    SalesforceContact,
    SalesforceTask,
    SalesforceLead,
    SalesforceAPIError,
    get_salesforce_service
)
from app.core.config import get_settings


class TestSalesforceService:
    """Test suite for SalesforceService class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.SALESFORCE_CLIENT_ID = "test_client_id"
        settings.SALESFORCE_CLIENT_SECRET = "test_client_secret"
        settings.SALESFORCE_USERNAME = "test@example.com"
        settings.SALESFORCE_PASSWORD = "test_password"
        settings.SALESFORCE_SECURITY_TOKEN = "test_token"
        settings.salesforce_base_url = "https://test.salesforce.com"
        return settings
    
    @pytest.fixture
    def salesforce_service(self, mock_settings):
        """Create SalesforceService instance with mocked settings."""
        with patch('app.services.salesforce.get_settings', return_value=mock_settings):
            return SalesforceService()
    
    @pytest.fixture
    def mock_auth_response(self):
        """Mock successful authentication response."""
        return {
            "access_token": "test_access_token",
            "instance_url": "https://test.my.salesforce.com",
            "token_type": "Bearer"
        }
    
    @pytest.fixture
    def mock_contact_record(self):
        """Mock contact record from Salesforce."""
        return {
            "Id": "003XX000004TmiQQAS",
            "FirstName": "John",
            "LastName": "Doe",
            "Phone": "+1234567890",
            "Email": "john.doe@example.com",
            "Account": {"Name": "Test Company"},
            "LeadSource": "AI_Calling_Agent",
            "Description": "Test contact"
        }
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, salesforce_service, mock_auth_response):
        """Test successful OAuth 2.0 authentication."""
        with patch.object(salesforce_service, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_auth_response)
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            token = await salesforce_service.authenticate()
            
            assert token.access_token == "test_access_token"
            assert token.instance_url == "https://test.my.salesforce.com"
            assert not token.is_expired
            
            # Verify authentication request
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert "grant_type" in call_args[1]["data"]
            assert call_args[1]["data"]["grant_type"] == "password"
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, salesforce_service):
        """Test authentication failure handling."""
        with patch.object(salesforce_service, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Invalid credentials")
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(SalesforceAPIError) as exc_info:
                await salesforce_service.authenticate()
            
            assert "Authentication failed" in str(exc_info.value)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_token_refresh_on_expiry(self, salesforce_service, mock_auth_response):
        """Test automatic token refresh when expired."""
        # Set up expired token
        from app.services.salesforce import SalesforceAuthToken
        expired_token = SalesforceAuthToken(
            access_token="old_token",
            instance_url="https://old.salesforce.com",
            expires_at=datetime.utcnow() - timedelta(minutes=10)
        )
        salesforce_service._auth_token = expired_token
        
        with patch.object(salesforce_service, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_auth_response)
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            token = await salesforce_service.authenticate()
            
            assert token.access_token == "test_access_token"
            assert not token.is_expired
    
    @pytest.mark.asyncio
    async def test_find_contact_by_phone_success(self, salesforce_service, mock_contact_record):
        """Test successful contact lookup by phone number."""
        query_response = {
            "records": [mock_contact_record]
        }
        
        with patch.object(salesforce_service, '_make_api_request', return_value=query_response):
            contact = await salesforce_service.find_contact_by_phone("+1234567890")
            
            assert contact is not None
            assert contact["Id"] == "003XX000004TmiQQAS"
            assert contact["Phone"] == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_find_contact_by_phone_not_found(self, salesforce_service):
        """Test contact lookup when no contact exists."""
        query_response = {"records": []}
        
        with patch.object(salesforce_service, '_make_api_request', return_value=query_response):
            contact = await salesforce_service.find_contact_by_phone("+1234567890")
            
            assert contact is None
    
    @pytest.mark.asyncio
    async def test_create_contact_success(self, salesforce_service, mock_contact_record):
        """Test successful contact creation."""
        create_response = {"id": "003XX000004TmiQQAS", "success": True}
        
        with patch.object(salesforce_service, '_make_api_request', return_value=create_response), \
             patch.object(salesforce_service, 'get_contact_by_id', return_value=mock_contact_record):
            
            contact_data = SalesforceContact(
                FirstName="John",
                LastName="Doe",
                Phone="+1234567890",
                Email="john.doe@example.com"
            )
            
            contact = await salesforce_service.create_contact(contact_data)
            
            assert contact["Id"] == "003XX000004TmiQQAS"
            assert contact["FirstName"] == "John"
    
    @pytest.mark.asyncio
    async def test_find_or_create_contact_existing(self, salesforce_service, mock_contact_record):
        """Test find_or_create_contact with existing contact."""
        with patch.object(salesforce_service, 'find_contact_by_phone', return_value=mock_contact_record):
            contact = await salesforce_service.find_or_create_contact("+1234567890")
            
            assert contact["Id"] == "003XX000004TmiQQAS"
            assert contact["Phone"] == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_find_or_create_contact_new(self, salesforce_service, mock_contact_record):
        """Test find_or_create_contact with new contact creation."""
        with patch.object(salesforce_service, 'find_contact_by_phone', return_value=None), \
             patch.object(salesforce_service, 'create_contact', return_value=mock_contact_record):
            
            contact = await salesforce_service.find_or_create_contact(
                "+1234567890",
                {"FirstName": "John", "LastName": "Doe"}
            )
            
            assert contact["Id"] == "003XX000004TmiQQAS"
    
    @pytest.mark.asyncio
    async def test_log_call_activity_success(self, salesforce_service):
        """Test successful call activity logging."""
        task_response = {"id": "00TXX000001234567", "success": True}
        
        with patch.object(salesforce_service, '_make_api_request', return_value=task_response):
            result = await salesforce_service.log_call_activity(
                contact_id="003XX000004TmiQQAS",
                call_summary="Discussed product features",
                call_outcome="Qualified Lead",
                call_duration=300,
                lead_score=85
            )
            
            assert result["id"] == "00TXX000001234567"
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_create_qualified_lead_high_score(self, salesforce_service):
        """Test qualified lead creation with high score."""
        lead_response = {"id": "00QXX000001234567", "success": True}
        task_response = {"id": "00TXX000001234568", "success": True}
        
        contact_data = {
            "FirstName": "John",
            "LastName": "Doe",
            "Phone": "+1234567890",
            "Email": "john.doe@example.com",
            "Company": "Test Company"
        }
        
        with patch.object(salesforce_service, '_make_api_request', return_value=lead_response), \
             patch.object(salesforce_service, 'create_follow_up_task', return_value=task_response):
            
            result = await salesforce_service.create_qualified_lead(
                contact_data=contact_data,
                qualification_score=85,
                qualification_details="High-value prospect with immediate need"
            )
            
            assert result["id"] == "00QXX000001234567"
    
    @pytest.mark.asyncio
    async def test_api_request_retry_logic(self, salesforce_service, mock_auth_response):
        """Test API request retry logic with exponential backoff."""
        # Mock authentication
        with patch.object(salesforce_service, 'authenticate') as mock_auth:
            mock_auth.return_value.access_token = "test_token"
            mock_auth.return_value.instance_url = "https://test.salesforce.com"
            mock_auth.return_value.token_type = "Bearer"
            
            # Mock session with failing then succeeding requests
            with patch('aiohttp.ClientSession.request') as mock_request:
                # First call fails, second succeeds
                mock_response_fail = AsyncMock()
                mock_response_fail.status = 500
                mock_response_fail.text = AsyncMock(return_value="Server Error")
                
                mock_response_success = AsyncMock()
                mock_response_success.status = 200
                mock_response_success.text = AsyncMock(return_value='{"success": true}')
                mock_response_success.json = AsyncMock(return_value={"success": True})
                
                mock_request.return_value.__aenter__.side_effect = [
                    mock_response_fail,
                    mock_response_success
                ]
                
                # Should succeed after retry
                result = await salesforce_service._make_api_request("GET", "/test")
                assert result["success"] is True
                
                # Verify retry was attempted
                assert mock_request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_api_request_max_retries_exceeded(self, salesforce_service):
        """Test API request failure after max retries."""
        with patch.object(salesforce_service, 'authenticate') as mock_auth:
            mock_auth.return_value.access_token = "test_token"
            mock_auth.return_value.instance_url = "https://test.salesforce.com"
            mock_auth.return_value.token_type = "Bearer"
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                # All requests fail
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.text = AsyncMock(return_value="Server Error")
                mock_request.return_value.__aenter__.return_value = mock_response
                
                with pytest.raises(SalesforceAPIError):
                    await salesforce_service._make_api_request("GET", "/test")
                
                # Verify max retries were attempted
                assert mock_request.call_count == salesforce_service.max_retries
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, salesforce_service):
        """Test successful health check."""
        with patch.object(salesforce_service, '_make_api_request', return_value={"records": []}):
            is_healthy = await salesforce_service.health_check()
            assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, salesforce_service):
        """Test health check failure."""
        with patch.object(salesforce_service, '_make_api_request', side_effect=SalesforceAPIError("Connection failed")):
            is_healthy = await salesforce_service.health_check()
            assert is_healthy is False


class TestSalesforceModels:
    """Test suite for Salesforce data models."""
    
    def test_salesforce_contact_model(self):
        """Test SalesforceContact model validation."""
        contact = SalesforceContact(
            FirstName="John",
            LastName="Doe",
            Phone="+1234567890",
            Email="john.doe@example.com",
            Company="Test Company"
        )
        
        assert contact.FirstName == "John"
        assert contact.LastName == "Doe"
        assert contact.Phone == "+1234567890"
        assert contact.LeadSource == "AI_Calling_Agent"
    
    def test_salesforce_task_model(self):
        """Test SalesforceTask model validation."""
        task = SalesforceTask(
            WhoId="003XX000004TmiQQAS",
            Subject="AI Agent Call - Qualified Lead",
            Description="Call summary and details"
        )
        
        assert task.WhoId == "003XX000004TmiQQAS"
        assert task.Type == "Call"
        assert task.TaskSubtype == "Call"
        assert task.CallType == "Inbound"
        assert task.Status == "Completed"
    
    def test_salesforce_lead_model(self):
        """Test SalesforceLead model validation."""
        lead = SalesforceLead(
            FirstName="John",
            LastName="Doe",
            Phone="+1234567890",
            Email="john.doe@example.com",
            Company="Test Company",
            Rating="Hot"
        )
        
        assert lead.FirstName == "John"
        assert lead.LastName == "Doe"
        assert lead.LeadSource == "AI_Agent_Qualification"
        assert lead.Status == "Open - Not Contacted"
        assert lead.Rating == "Hot"


class TestSalesforceServiceIntegration:
    """Integration tests with real Salesforce sandbox (if configured)."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_salesforce_authentication(self):
        """Test authentication with real Salesforce sandbox."""
        # Skip if not configured for integration testing
        settings = get_settings()
        if not all([
            settings.SALESFORCE_CLIENT_ID,
            settings.SALESFORCE_CLIENT_SECRET,
            settings.SALESFORCE_USERNAME,
            settings.SALESFORCE_PASSWORD,
            settings.SALESFORCE_SECURITY_TOKEN
        ]):
            pytest.skip("Salesforce credentials not configured for integration testing")
        
        async with SalesforceService() as sf_service:
            try:
                token = await sf_service.authenticate()
                assert token.access_token
                assert token.instance_url
                assert not token.is_expired
            except SalesforceAPIError as e:
                pytest.fail(f"Authentication failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_contact_operations(self):
        """Test contact CRUD operations with real Salesforce sandbox."""
        settings = get_settings()
        if not all([
            settings.SALESFORCE_CLIENT_ID,
            settings.SALESFORCE_CLIENT_SECRET,
            settings.SALESFORCE_USERNAME,
            settings.SALESFORCE_PASSWORD,
            settings.SALESFORCE_SECURITY_TOKEN
        ]):
            pytest.skip("Salesforce credentials not configured for integration testing")
        
        async with SalesforceService() as sf_service:
            try:
                # Test phone number for integration testing
                test_phone = "+15551234567"
                
                # Find or create contact
                contact = await sf_service.find_or_create_contact(
                    phone=test_phone,
                    additional_data={
                        "FirstName": "Test",
                        "LastName": "Integration",
                        "Email": "test.integration@example.com"
                    }
                )
                
                assert contact["Phone"] == test_phone
                assert "Id" in contact
                
                # Log call activity
                await sf_service.log_call_activity(
                    contact_id=contact["Id"],
                    call_summary="Integration test call",
                    call_outcome="Test Completed",
                    lead_score=75
                )
                
                # Create qualified lead if score is high enough
                if 75 >= 60:
                    lead = await sf_service.create_qualified_lead(
                        contact_data=contact,
                        qualification_score=75,
                        qualification_details="Integration test qualification"
                    )
                    assert "id" in lead
                
            except SalesforceAPIError as e:
                pytest.fail(f"Integration test failed: {e}")


def test_get_salesforce_service():
    """Test service factory function."""
    service1 = asyncio.run(get_salesforce_service())
    service2 = asyncio.run(get_salesforce_service())
    
    # Should return the same instance (singleton pattern)
    assert service1 is service2
    assert isinstance(service1, SalesforceService)