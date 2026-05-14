"""
Tests for approval workflow service functionality.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from app.services.approval_workflow import ApprovalWorkflowService, NotificationService
from app.schemas.compliance import (
    ApprovalRequest, ApprovalDecision, ApprovalStatus,
    ComplianceValidation, ComplianceStatus
)


class TestNotificationService:
    """Test notification service functionality."""
    
    @pytest.fixture
    def notification_service(self):
        """Create notification service instance for testing."""
        return NotificationService()
    
    @pytest.fixture
    def sample_approval_request(self):
        """Sample approval request for testing."""
        return ApprovalRequest(
            request_id="test_request_123",
            prospect_id="test_prospect_456",
            prospect_score=85,
            prospect_context={
                "company_name": "Test Company Inc",
                "contact_name": "John Doe",
                "industry": "Technology",
                "revenue_range": "$10M-$50M"
            },
            compliance_validation=ComplianceValidation(
                prospect_id="test_prospect_456",
                phone_number="encrypted_phone",
                overall_status=ComplianceStatus.APPROVED,
                checks=[],
                violations=[]
            ),
            requested_by="ai_calling_agent",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
    
    @pytest.mark.asyncio
    async def test_send_slack_notification_success(self, notification_service, sample_approval_request):
        """Test successful Slack notification sending."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            # Mock webhook URL
            notification_service.slack_webhook_url = "https://hooks.slack.com/test"
            
            result = await notification_service.send_slack_notification(sample_approval_request)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_send_slack_notification_no_webhook(self, notification_service, sample_approval_request):
        """Test Slack notification when webhook URL not configured."""
        notification_service.slack_webhook_url = None
        
        result = await notification_service.send_slack_notification(sample_approval_request)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_slack_notification_failure(self, notification_service, sample_approval_request):
        """Test Slack notification failure."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 500
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            notification_service.slack_webhook_url = "https://hooks.slack.com/test"
            
            result = await notification_service.send_slack_notification(sample_approval_request)
            
            assert result is False
    
    def test_create_slack_message(self, notification_service, sample_approval_request):
        """Test Slack message creation."""
        message = notification_service._create_slack_message(sample_approval_request)
        
        assert "text" in message
        assert "blocks" in message
        assert "High-Value Prospect Approval Required" in message["text"]
        
        # Check that prospect information is included
        blocks = message["blocks"]
        assert any("Test Company Inc" in str(block) for block in blocks)
        assert any("John Doe" in str(block) for block in blocks)
        assert any("85/100" in str(block) for block in blocks)
    
    @pytest.mark.asyncio
    async def test_send_email_notification_success(self, notification_service, sample_approval_request):
        """Test successful email notification sending."""
        # Configure email settings
        notification_service.smtp_server = "smtp.test.com"
        notification_service.smtp_username = "test@test.com"
        notification_service.smtp_password = "password"
        notification_service.from_email = "test@test.com"
        
        with patch.object(notification_service, '_send_single_email', return_value=True):
            result = await notification_service.send_email_notification(
                sample_approval_request,
                ["approver1@test.com", "approver2@test.com"]
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_send_email_notification_no_config(self, notification_service, sample_approval_request):
        """Test email notification when not configured."""
        notification_service.smtp_server = None
        
        result = await notification_service.send_email_notification(
            sample_approval_request,
            ["approver@test.com"]
        )
        
        assert result is False
    
    def test_create_email_html(self, notification_service, sample_approval_request):
        """Test HTML email creation."""
        html = notification_service._create_email_html(sample_approval_request)
        
        assert "High-Value Prospect Approval Required" in html
        assert "Test Company Inc" in html
        assert "John Doe" in html
        assert "85/100" in html
        assert "✅ Approve" in html
        assert "❌ Reject" in html
    
    def test_create_email_text(self, notification_service, sample_approval_request):
        """Test plain text email creation."""
        text = notification_service._create_email_text(sample_approval_request)
        
        assert "HIGH-VALUE PROSPECT APPROVAL REQUIRED" in text
        assert "Test Company Inc" in text
        assert "John Doe" in text
        assert "85/100" in text
        assert sample_approval_request.request_id in text


class TestApprovalWorkflowService:
    """Test approval workflow service functionality."""
    
    @pytest.fixture
    def workflow_service(self):
        """Create approval workflow service instance for testing."""
        return ApprovalWorkflowService()
    
    @pytest.fixture
    def sample_prospect_context(self):
        """Sample prospect context for testing."""
        return {
            "company_name": "Test Company Inc",
            "contact_name": "Jane Smith",
            "industry": "Healthcare",
            "revenue_range": "$50M-$100M",
            "phone_number": "+15551234567"
        }
    
    @pytest.fixture
    def sample_compliance_validation(self):
        """Sample compliance validation for testing."""
        return ComplianceValidation(
            prospect_id="test_prospect_789",
            phone_number="encrypted_phone",
            overall_status=ComplianceStatus.APPROVED,
            checks=[],
            violations=[]
        )
    
    @pytest.mark.asyncio
    async def test_submit_approval_request(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test submitting an approval request."""
        prospect_id = "test_prospect_789"
        prospect_score = 90
        
        with patch.object(workflow_service, '_send_approval_notifications') as mock_notify:
            mock_notify.return_value = None
            
            approval_request = await workflow_service.submit_approval_request(
                prospect_id=prospect_id,
                prospect_score=prospect_score,
                prospect_context=sample_prospect_context,
                compliance_validation=sample_compliance_validation
            )
            
            assert approval_request.prospect_id == prospect_id
            assert approval_request.prospect_score == prospect_score
            assert approval_request.status == ApprovalStatus.PENDING
            assert approval_request.request_id in workflow_service.pending_requests
            
            # Verify notification was attempted
            mock_notify.assert_called_once_with(approval_request)
    
    @pytest.mark.asyncio
    async def test_process_approval_decision_approve(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test processing an approval decision (approve)."""
        # First create an approval request
        approval_request = await workflow_service.submit_approval_request(
            prospect_id="test_prospect_approve",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation
        )
        
        # Create approval decision
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.APPROVED,
            approved_by="test_approver",
            reason="High-value prospect with good compliance"
        )
        
        with patch.object(workflow_service, '_send_decision_confirmation') as mock_confirm:
            mock_confirm.return_value = None
            
            result = await workflow_service.process_approval_decision(
                approval_request.request_id,
                decision
            )
            
            assert result is True
            assert approval_request.request_id not in workflow_service.pending_requests
            assert approval_request.request_id in workflow_service.completed_requests
            
            completed_request = workflow_service.completed_requests[approval_request.request_id]
            assert completed_request.status == ApprovalStatus.APPROVED
            assert completed_request.approved_by == "test_approver"
            assert completed_request.approved_at is not None
    
    @pytest.mark.asyncio
    async def test_process_approval_decision_reject(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test processing an approval decision (reject)."""
        # First create an approval request
        approval_request = await workflow_service.submit_approval_request(
            prospect_id="test_prospect_reject",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation
        )
        
        # Create rejection decision
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.REJECTED,
            approved_by="test_approver",
            reason="Compliance concerns"
        )
        
        result = await workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        assert result is True
        completed_request = workflow_service.completed_requests[approval_request.request_id]
        assert completed_request.status == ApprovalStatus.REJECTED
        assert completed_request.rejection_reason == "Compliance concerns"
    
    @pytest.mark.asyncio
    async def test_process_approval_decision_not_found(self, workflow_service):
        """Test processing decision for non-existent request."""
        decision = ApprovalDecision(
            request_id="non_existent_request",
            decision=ApprovalStatus.APPROVED,
            approved_by="test_approver"
        )
        
        result = await workflow_service.process_approval_decision(
            "non_existent_request",
            decision
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_approval_decision_expired(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test processing decision for expired request."""
        # Create an approval request that's already expired
        approval_request = ApprovalRequest(
            request_id="expired_request",
            prospect_id="test_prospect_expired",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="ai_calling_agent",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)  # Already expired
        )
        
        workflow_service.pending_requests[approval_request.request_id] = approval_request
        
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.APPROVED,
            approved_by="test_approver"
        )
        
        result = await workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        assert result is False
        completed_request = workflow_service.completed_requests[approval_request.request_id]
        assert completed_request.status == ApprovalStatus.TIMEOUT
    
    def test_get_pending_requests(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test getting pending requests."""
        # Add some mock requests
        request1 = ApprovalRequest(
            request_id="request1",
            prospect_id="prospect1",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        request2 = ApprovalRequest(
            request_id="request2",
            prospect_id="prospect2",
            prospect_score=90,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        workflow_service.pending_requests["request1"] = request1
        workflow_service.pending_requests["request2"] = request2
        
        pending = workflow_service.get_pending_requests()
        
        assert len(pending) == 2
        assert request1 in pending
        assert request2 in pending
    
    def test_get_request_by_id(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test getting request by ID."""
        request = ApprovalRequest(
            request_id="test_request_id",
            prospect_id="test_prospect",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        workflow_service.pending_requests["test_request_id"] = request
        
        found_request = workflow_service.get_request_by_id("test_request_id")
        assert found_request == request
        
        not_found = workflow_service.get_request_by_id("non_existent")
        assert not_found is None
    
    def test_get_approval_metrics(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test getting approval metrics."""
        period_start = datetime.now(timezone.utc) - timedelta(days=7)
        period_end = datetime.now(timezone.utc)
        
        # Add some mock requests with different statuses
        approved_request = ApprovalRequest(
            request_id="approved",
            prospect_id="prospect1",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=period_end,
            status=ApprovalStatus.APPROVED,
            approved_at=period_start + timedelta(hours=2)
        )
        approved_request.requested_at = period_start + timedelta(hours=1)
        
        rejected_request = ApprovalRequest(
            request_id="rejected",
            prospect_id="prospect2",
            prospect_score=90,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=period_end,
            status=ApprovalStatus.REJECTED,
            approved_at=period_start + timedelta(hours=3)
        )
        rejected_request.requested_at = period_start + timedelta(hours=1)
        
        timeout_request = ApprovalRequest(
            request_id="timeout",
            prospect_id="prospect3",
            prospect_score=80,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="system",
            expires_at=period_start + timedelta(hours=24),
            status=ApprovalStatus.TIMEOUT
        )
        timeout_request.requested_at = period_start + timedelta(hours=1)
        
        workflow_service.completed_requests["approved"] = approved_request
        workflow_service.completed_requests["rejected"] = rejected_request
        workflow_service.completed_requests["timeout"] = timeout_request
        
        metrics = workflow_service.get_approval_metrics(period_start, period_end)
        
        assert metrics["total_requests"] == 3
        assert metrics["approved"] == 1
        assert metrics["rejected"] == 1
        assert metrics["timeouts"] == 1
        assert metrics["approval_rate"] == 33.33333333333333  # 1 approved out of 3 total
        assert metrics["average_approval_time_hours"] == 1.5  # Average of 1 and 2 hours
    
    @pytest.mark.asyncio
    async def test_timeout_check(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test timeout check functionality."""
        # Create a request that expires very soon
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=0.1)
        
        approval_request = ApprovalRequest(
            request_id="timeout_test",
            prospect_id="test_prospect_timeout",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="ai_calling_agent",
            expires_at=expires_at
        )
        
        workflow_service.pending_requests["timeout_test"] = approval_request
        
        with patch.object(workflow_service, '_send_timeout_notification') as mock_timeout:
            mock_timeout.return_value = None
            
            # Start timeout check
            await workflow_service._schedule_timeout_check("timeout_test", expires_at)
            
            # Request should be moved to completed with timeout status
            assert "timeout_test" not in workflow_service.pending_requests
            assert "timeout_test" in workflow_service.completed_requests
            
            completed_request = workflow_service.completed_requests["timeout_test"]
            assert completed_request.status == ApprovalStatus.TIMEOUT
            
            # Timeout notification should have been sent
            mock_timeout.assert_called_once_with(approval_request)
    
    @pytest.mark.asyncio
    async def test_send_approval_notifications(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test sending approval notifications."""
        approval_request = ApprovalRequest(
            request_id="notification_test",
            prospect_id="test_prospect_notify",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="ai_calling_agent",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        # Mock notification service methods
        with patch.object(workflow_service.notification_service, 'send_slack_notification', return_value=True) as mock_slack:
            with patch.object(workflow_service.notification_service, 'send_email_notification', return_value=True) as mock_email:
                workflow_service.approver_emails = ["approver@test.com"]
                
                await workflow_service._send_approval_notifications(approval_request)
                
                mock_slack.assert_called_once_with(approval_request)
                mock_email.assert_called_once_with(approval_request, ["approver@test.com"])
    
    @pytest.mark.asyncio
    async def test_send_approval_notifications_no_channels(
        self,
        workflow_service,
        sample_prospect_context,
        sample_compliance_validation
    ):
        """Test sending notifications when no channels are configured."""
        approval_request = ApprovalRequest(
            request_id="no_channels_test",
            prospect_id="test_prospect_no_channels",
            prospect_score=85,
            prospect_context=sample_prospect_context,
            compliance_validation=sample_compliance_validation,
            requested_by="ai_calling_agent",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        # Mock notification service methods to return False (not configured)
        with patch.object(workflow_service.notification_service, 'send_slack_notification', return_value=False):
            with patch.object(workflow_service.notification_service, 'send_email_notification', return_value=False):
                workflow_service.approver_emails = []
                
                # Should not raise an exception, just log a warning
                await workflow_service._send_approval_notifications(approval_request)