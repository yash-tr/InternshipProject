"""
Simple tests for Salesforce service to verify basic functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.salesforce import (
    SalesforceService,
    SalesforceContact,
    SalesforceTask,
    SalesforceLead,
    SalesforceAuthToken,
    SalesforceAPIError
)


class TestSalesforceBasics:
    """Basic tests for Salesforce service components."""
    
    def test_salesforce_contact_model(self):
        """Test SalesforceContact model creation and validation."""
        contact = SalesforceContact(
            FirstName="John",
            LastName="Doe",
            Phone="+1234567890",
            Email="john.doe@example.com"
        )
        
        assert contact.FirstName == "John"
        assert contact.LastName == "Doe"
        assert contact.Phone == "+1234567890"
        assert contact.Email == "john.doe@example.com"
        assert contact.LeadSource == "AI_Calling_Agent"
    
    def test_salesforce_task_model(self):
        """Test SalesforceTask model creation and validation."""
        task = SalesforceTask(
            WhoId="003XX000004TmiQQAS",
            Subject="AI Agent Call",
            Description="Test call description",
            ActivityDate="2024-01-15"
        )
        
        assert task.WhoId == "003XX000004TmiQQAS"
        assert task.Subject == "AI Agent Call"
        assert task.Type == "Call"
        assert task.TaskSubtype == "Call"
        assert task.CallType == "Inbound"
        assert task.Status == "Completed"
        assert task.ActivityDate == "2024-01-15"
    
    def test_salesforce_lead_model(self):
        """Test SalesforceLead model creation and validation."""
        lead = SalesforceLead(
            LastName="Doe",
            Phone="+1234567890",
            Company="Test Company",
            Rating="Hot"
        )
        
        assert lead.LastName == "Doe"
        assert lead.Phone == "+1234567890"
        assert lead.Company == "Test Company"
        assert lead.Rating == "Hot"
        assert lead.LeadSource == "AI_Agent_Qualification"
        assert lead.Status == "Open - Not Contacted"
    
    def test_salesforce_auth_token_expiry(self):
        """Test SalesforceAuthToken expiry logic."""
        # Test non-expired token
        future_time = datetime.utcnow() + timedelta(hours=1)
        token = SalesforceAuthToken(
            access_token="test_token",
            instance_url="https://test.salesforce.com",
            expires_at=future_time
        )
        assert not token.is_expired
        
        # Test expired token
        past_time = datetime.utcnow() - timedelta(hours=1)
        expired_token = SalesforceAuthToken(
            access_token="test_token",
            instance_url="https://test.salesforce.com",
            expires_at=past_time
        )
        assert expired_token.is_expired
    
    def test_salesforce_api_error(self):
        """Test SalesforceAPIError exception."""
        error = SalesforceAPIError(
            message="Test error",
            status_code=400,
            error_code="INVALID_LOGIN"
        )
        
        assert str(error) == "Test error"
        assert error.status_code == 400
        assert error.error_code == "INVALID_LOGIN"
    
    @pytest.mark.asyncio
    async def test_salesforce_service_initialization(self):
        """Test SalesforceService initialization."""
        with patch('app.services.salesforce.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            service = SalesforceService()
            
            assert service._auth_token is None
            assert service._session is None
            assert service.max_retries == 3
            assert service.base_backoff_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test SalesforceService as async context manager."""
        with patch('app.services.salesforce.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            with patch('aiohttp.ClientSession') as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session
                
                async with SalesforceService() as service:
                    assert service._session is not None
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        with patch('app.services.salesforce.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            service = SalesforceService()
            
            # Mock successful API request
            with patch.object(service, '_make_api_request', return_value={"records": []}):
                result = await service.health_check()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        with patch('app.services.salesforce.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            service = SalesforceService()
            
            # Mock failed API request
            with patch.object(service, '_make_api_request', side_effect=SalesforceAPIError("Connection failed")):
                result = await service.health_check()
                assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])