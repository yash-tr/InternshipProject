"""
Integration tests for approval API endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.schemas.compliance import (
    ApprovalRequest, ApprovalStatus, ComplianceValidation,
    ComplianceStatus, ComplianceCheck
)


class TestApprovalAPI:
    """Test approval API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_compliance_validation(self):
        """Sample compliance validation for testing."""
        return {
            "prospect_id": "test_prospect_123",
            "phone_number": "encrypted_phone",
            "overall_status": "approved",
            "checks": [
                {
                    "check_type": "dnc_list",
                    "status": "approved",
                    "details": {"on_dnc_list": False},
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            ],
            "violations": [],
            "validated_at": datetime.now(timezone.utc).isoformat()
        }
    
    @pytest.fixture
    def sample_approval_request_data(self, sample_compliance_validation):
        """Sample approval request data for testing."""
        return {
            "prospect_id": "test_prospect_123",
            "prospect_score": 85,
            "prospect_context": {
                "company_name": "Test Company Inc",
                "contact_name": "John Doe",
                "industry": "Technology",
                "revenue_range": "$10M-$50M"
            },
            "compliance_validation": sample_compliance_validation
        }
    
    def test_create_approval_request(self, client, sample_approval_request_data):
        """Test creating an approval request."""
        with patch('app.services.approval_workflow.approval_workflow_service.submit_approval_request') as mock_submit:
            # Mock the approval request response
            mock_approval_request = ApprovalRequest(
                request_id="test_request_123",
                prospect_id="test_prospect_123",
                prospect_score=85,
                prospect_context=sample_approval_request_data["prospect_context"],
                compliance_validation=ComplianceValidation(**sample_approval_request_data["compliance_validation"]),
                requested_by="ai_calling_agent",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            mock_submit.return_value = mock_approval_request
            
            response = client.post("/api/v1/approval/requests", json=sample_approval_request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["request_id"] == "test_request_123"
            assert data["prospect_id"] == "test_prospect_123"
            assert data["prospect_score"] == 85
            assert data["status"] == "pending"
    
    def test_create_approval_request_error(self, client, sample_approval_request_data):
        """Test creating approval request with error."""
        with patch('app.services.approval_workflow.approval_workflow_service.submit_approval_request') as mock_submit:
            mock_submit.side_effect = Exception("Service error")
            
            response = client.post("/api/v1/approval/requests", json=sample_approval_request_data)
            
            assert response.status_code == 500
            assert "Failed to create approval request" in response.json()["detail"]
    
    def test_get_pending_requests(self, client):
        """Test getting pending approval requests."""
        with patch('app.services.approval_workflow.approval_workflow_service.get_pending_requests') as mock_get:
            mock_requests = [
                ApprovalRequest(
                    request_id="request1",
                    prospect_id="prospect1",
                    prospect_score=85,
                    prospect_context={"company_name": "Company 1"},
                    compliance_validation=ComplianceValidation(
                        prospect_id="prospect1",
                        phone_number="encrypted_phone",
                        overall_status=ComplianceStatus.APPROVED,
                        checks=[],
                        violations=[]
                    ),
                    requested_by="system",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
                ),
                ApprovalRequest(
                    request_id="request2",
                    prospect_id="prospect2",
                    prospect_score=90,
                    prospect_context={"company_name": "Company 2"},
                    compliance_validation=ComplianceValidation(
                        prospect_id="prospect2",
                        phone_number="encrypted_phone",
                        overall_status=ComplianceStatus.APPROVED,
                        checks=[],
                        violations=[]
                    ),
                    requested_by="system",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
                )
            ]
            mock_get.return_value = mock_requests
            
            response = client.get("/api/v1/approval/requests")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["request_id"] == "request1"
            assert data[1]["request_id"] == "request2"
    
    def test_get_approval_request_by_id(self, client):
        """Test getting specific approval request by ID."""
        request_id = "test_request_123"
        
        with patch('app.services.approval_workflow.approval_workflow_service.get_request_by_id') as mock_get:
            mock_request = ApprovalRequest(
                request_id=request_id,
                prospect_id="test_prospect",
                prospect_score=85,
                prospect_context={"company_name": "Test Company"},
                compliance_validation=ComplianceValidation(
                    prospect_id="test_prospect",
                    phone_number="encrypted_phone",
                    overall_status=ComplianceStatus.APPROVED,
                    checks=[],
                    violations=[]
                ),
                requested_by="system",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            mock_get.return_value = mock_request
            
            response = client.get(f"/api/v1/approval/requests/{request_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["request_id"] == request_id
            assert data["prospect_score"] == 85
    
    def test_get_approval_request_not_found(self, client):
        """Test getting non-existent approval request."""
        request_id = "non_existent_request"
        
        with patch('app.services.approval_workflow.approval_workflow_service.get_request_by_id') as mock_get:
            mock_get.return_value = None
            
            response = client.get(f"/api/v1/approval/requests/{request_id}")
            
            assert response.status_code == 404
            assert "Approval request not found" in response.json()["detail"]
    
    def test_make_approval_decision_approve(self, client):
        """Test making an approval decision (approve)."""
        request_id = "test_request_123"
        decision_data = {
            "decision": "approved",
            "approved_by": "test_approver",
            "reason": "High-value prospect with good compliance"
        }
        
        with patch('app.services.approval_workflow.approval_workflow_service.process_approval_decision') as mock_process:
            mock_process.return_value = True
            
            response = client.post(f"/api/v1/approval/requests/{request_id}/decision", json=decision_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "approved" in data["message"]
            assert data["request_id"] == request_id
    
    def test_make_approval_decision_reject(self, client):
        """Test making an approval decision (reject)."""
        request_id = "test_request_123"
        decision_data = {
            "decision": "rejected",
            "approved_by": "test_approver",
            "reason": "Compliance concerns"
        }
        
        with patch('app.services.approval_workflow.approval_workflow_service.process_approval_decision') as mock_process:
            mock_process.return_value = True
            
            response = client.post(f"/api/v1/approval/requests/{request_id}/decision", json=decision_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "rejected" in data["message"]
    
    def test_make_approval_decision_failure(self, client):
        """Test making approval decision with failure."""
        request_id = "test_request_123"
        decision_data = {
            "decision": "approved",
            "approved_by": "test_approver"
        }
        
        with patch('app.services.approval_workflow.approval_workflow_service.process_approval_decision') as mock_process:
            mock_process.return_value = False
            
            response = client.post(f"/api/v1/approval/requests/{request_id}/decision", json=decision_data)
            
            assert response.status_code == 400
            assert "Failed to process approval decision" in response.json()["detail"]
    
    def test_get_approval_ui(self, client):
        """Test getting approval UI."""
        request_id = "test_request_123"
        
        with patch('app.services.approval_workflow.approval_workflow_service.get_request_by_id') as mock_get:
            mock_request = ApprovalRequest(
                request_id=request_id,
                prospect_id="test_prospect",
                prospect_score=85,
                prospect_context={
                    "company_name": "Test Company Inc",
                    "contact_name": "John Doe",
                    "industry": "Technology",
                    "revenue_range": "$10M-$50M"
                },
                compliance_validation=ComplianceValidation(
                    prospect_id="test_prospect",
                    phone_number="encrypted_phone",
                    overall_status=ComplianceStatus.APPROVED,
                    checks=[],
                    violations=[]
                ),
                requested_by="system",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            mock_get.return_value = mock_request
            
            response = client.get(f"/api/v1/approval/requests/{request_id}/ui")
            
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "High-Value Prospect Approval" in response.text
            assert "Test Company Inc" in response.text
            assert "John Doe" in response.text
    
    def test_get_approval_ui_not_found(self, client):
        """Test getting approval UI for non-existent request."""
        request_id = "non_existent_request"
        
        with patch('app.services.approval_workflow.approval_workflow_service.get_request_by_id') as mock_get:
            mock_get.return_value = None
            
            response = client.get(f"/api/v1/approval/requests/{request_id}/ui")
            
            assert response.status_code == 200
            assert "Approval Request Not Found" in response.text
    
    def test_get_approval_ui_with_action(self, client):
        """Test getting approval UI with action parameter."""
        request_id = "test_request_123"
        
        with patch('app.services.approval_workflow.approval_workflow_service.get_request_by_id') as mock_get:
            mock_request = ApprovalRequest(
                request_id=request_id,
                prospect_id="test_prospect",
                prospect_score=85,
                prospect_context={"company_name": "Test Company"},
                compliance_validation=ComplianceValidation(
                    prospect_id="test_prospect",
                    phone_number="encrypted_phone",
                    overall_status=ComplianceStatus.APPROVED,
                    checks=[],
                    violations=[]
                ),
                requested_by="system",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            mock_get.return_value = mock_request
            
            response = client.get(f"/api/v1/approval/requests/{request_id}/ui?action=approve")
            
            assert response.status_code == 200
            assert "Confirm Approve" in response.text
    
    def test_get_approval_metrics(self, client):
        """Test getting approval metrics."""
        with patch('app.services.approval_workflow.approval_workflow_service.get_approval_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "total_requests": 10,
                "approved": 7,
                "rejected": 2,
                "timeouts": 1,
                "pending": 0,
                "approval_rate": 70.0,
                "average_approval_time_hours": 2.5
            }
            
            response = client.get("/api/v1/approval/metrics?days=7")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_requests"] == 10
            assert data["approved"] == 7
            assert data["approval_rate"] == 70.0
    
    def test_get_compliance_metrics(self, client):
        """Test getting compliance metrics."""
        with patch('app.services.compliance.compliance_service.get_compliance_metrics') as mock_metrics:
            from app.schemas.compliance import ComplianceMetrics
            
            mock_metrics.return_value = ComplianceMetrics(
                period_start=datetime.now(timezone.utc) - timedelta(days=7),
                period_end=datetime.now(timezone.utc),
                total_prospects_checked=50,
                compliant_prospects=45,
                violations_detected=5,
                approval_requests_sent=10,
                approvals_granted=8
            )
            
            response = client.get("/api/v1/approval/compliance/metrics?days=7")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_prospects_checked"] == 50
            assert data["compliant_prospects"] == 45
            assert data["violations_detected"] == 5
            assert data["compliance_rate"] == 90.0
    
    def test_validate_compliance(self, client):
        """Test compliance validation endpoint."""
        request_data = {
            "prospect_id": "test_prospect_123",
            "phone_number": "+15551234567",
            "prospect_data": {
                "company_name": "Test Company",
                "industry": "Technology",
                "country": "US"
            }
        }
        
        with patch('app.services.compliance.compliance_service.validate_compliance') as mock_validate:
            mock_validation = ComplianceValidation(
                prospect_id="test_prospect_123",
                phone_number="encrypted_phone",
                overall_status=ComplianceStatus.APPROVED,
                checks=[
                    ComplianceCheck(
                        check_type="dnc_list",
                        status=ComplianceStatus.APPROVED,
                        details={"on_dnc_list": False}
                    )
                ],
                violations=[]
            )
            mock_validate.return_value = mock_validation
            
            response = client.post("/api/v1/approval/compliance/validate", params=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["prospect_id"] == "test_prospect_123"
            assert data["overall_status"] == "approved"
            assert len(data["checks"]) == 1
    
    def test_add_to_dnc_list(self, client):
        """Test adding phone number to DNC list."""
        request_data = {
            "phone_number": "+15551234567",
            "source": "customer_request",
            "reason": "No longer interested"
        }
        
        with patch('app.services.compliance.compliance_service.add_to_dnc_list') as mock_add:
            mock_add.return_value = True
            
            response = client.post("/api/v1/approval/compliance/dnc", params=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["phone_number"] == "+15551234567"
    
    def test_add_to_dnc_list_failure(self, client):
        """Test adding to DNC list with failure."""
        request_data = {
            "phone_number": "+15551234567",
            "source": "customer_request"
        }
        
        with patch('app.services.compliance.compliance_service.add_to_dnc_list') as mock_add:
            mock_add.return_value = False
            
            response = client.post("/api/v1/approval/compliance/dnc", params=request_data)
            
            assert response.status_code == 500
            assert "Failed to add to DNC list" in response.json()["detail"]
    
    def test_record_consent(self, client):
        """Test recording consent."""
        request_data = {
            "phone_number": "+15551234567",
            "consent_type": "marketing",
            "consent_given": True,
            "consent_method": "web_form"
        }
        
        with patch('app.services.compliance.compliance_service.record_consent') as mock_record:
            mock_record.return_value = True
            
            response = client.post("/api/v1/approval/compliance/consent", params=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["consent_given"] is True
    
    def test_record_consent_failure(self, client):
        """Test recording consent with failure."""
        request_data = {
            "phone_number": "+15551234567",
            "consent_type": "marketing",
            "consent_given": True,
            "consent_method": "web_form"
        }
        
        with patch('app.services.compliance.compliance_service.record_consent') as mock_record:
            mock_record.return_value = False
            
            response = client.post("/api/v1/approval/compliance/consent", params=request_data)
            
            assert response.status_code == 500
            assert "Failed to record consent" in response.json()["detail"]