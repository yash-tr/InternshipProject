"""
Integration tests for the complete approval workflow system.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.compliance import compliance_service
from app.services.approval_workflow import approval_workflow_service
from app.services.audit_trail import audit_trail_service, AuditEventType
from app.schemas.compliance import (
    ComplianceStatus, ApprovalStatus, ComplianceViolationType
)


class TestApprovalWorkflowIntegration:
    """Integration tests for the complete approval workflow."""
    
    @pytest.fixture
    def sample_prospect_data(self):
        """Sample prospect data for testing."""
        return {
            "company_name": "Test Company Inc",
            "contact_name": "John Doe",
            "industry": "Technology",
            "revenue_range": "$10M-$50M",
            "country": "US",
            "phone_number": "+15551234567"
        }
    
    @pytest.mark.asyncio
    async def test_complete_approval_workflow_compliant_prospect(self, sample_prospect_data):
        """Test complete approval workflow for compliant high-value prospect."""
        prospect_id = "test_prospect_compliant"
        prospect_score = 85
        phone_number = "+15551234567"
        
        # Step 1: Validate compliance
        compliance_validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        assert compliance_validation.is_compliant
        assert compliance_validation.overall_status == ComplianceStatus.APPROVED
        
        # Step 2: Create approval request for high-value prospect
        with patch.object(approval_workflow_service, '_send_approval_notifications') as mock_notify:
            mock_notify.return_value = None
            
            approval_request = await approval_workflow_service.submit_approval_request(
                prospect_id=prospect_id,
                prospect_score=prospect_score,
                prospect_context=sample_prospect_data,
                compliance_validation=compliance_validation
            )
        
        assert approval_request.prospect_id == prospect_id
        assert approval_request.status == ApprovalStatus.PENDING
        assert approval_request.is_pending
        
        # Verify notification was attempted
        mock_notify.assert_called_once()
        
        # Step 3: Process approval decision
        from app.schemas.compliance import ApprovalDecision
        
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.APPROVED,
            approved_by="test_approver",
            reason="High-value compliant prospect"
        )
        
        success = await approval_workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        assert success is True
        
        # Verify request was moved to completed
        completed_request = approval_workflow_service.get_request_by_id(approval_request.request_id)
        assert completed_request.status == ApprovalStatus.APPROVED
        assert completed_request.approved_by == "test_approver"
        
        # Step 4: Verify audit trail was created
        audit_entries = await audit_trail_service.search_audit_entries(
            prospect_id=prospect_id
        )
        
        # Should have entries for compliance validation and approval request creation
        assert len(audit_entries) >= 2
        event_types = [entry.action_type for entry in audit_entries]
        assert AuditEventType.COMPLIANCE_VALIDATION.value in event_types
        assert AuditEventType.APPROVAL_REQUEST_CREATED.value in event_types
    
    @pytest.mark.asyncio
    async def test_complete_approval_workflow_non_compliant_prospect(self, sample_prospect_data):
        """Test approval workflow for non-compliant prospect."""
        prospect_id = "test_prospect_non_compliant"
        phone_number = "+15551234567"
        
        # Add phone to DNC list to create violation
        await compliance_service.add_to_dnc_list(
            phone_number=phone_number,
            source="test_setup",
            reason="Testing non-compliance"
        )
        
        # Step 1: Validate compliance (should fail)
        compliance_validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        assert not compliance_validation.is_compliant
        assert compliance_validation.overall_status == ComplianceStatus.VIOLATION
        assert ComplianceViolationType.DNC_VIOLATION in compliance_validation.violations
        
        # Step 2: Attempt to create approval request (should still work but flag violations)
        approval_request = await approval_workflow_service.submit_approval_request(
            prospect_id=prospect_id,
            prospect_score=85,
            prospect_context=sample_prospect_data,
            compliance_validation=compliance_validation
        )
        
        # Request should be created but compliance violations should be noted
        assert approval_request.compliance_validation.violations
        assert not approval_request.compliance_validation.is_compliant
        
        # Step 3: Automatic rejection due to compliance violations
        # In a real system, this might be handled automatically
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.REJECTED,
            approved_by="system",
            reason="Compliance violations detected"
        )
        
        success = await approval_workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        assert success is True
        
        completed_request = approval_workflow_service.get_request_by_id(approval_request.request_id)
        assert completed_request.status == ApprovalStatus.REJECTED
        assert "compliance" in completed_request.rejection_reason.lower()
    
    @pytest.mark.asyncio
    async def test_approval_workflow_timeout(self, sample_prospect_data):
        """Test approval workflow timeout handling."""
        prospect_id = "test_prospect_timeout"
        phone_number = "+15551234567"
        
        # Create compliance validation
        compliance_validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        # Create approval request with very short timeout
        approval_request = await approval_workflow_service.submit_approval_request(
            prospect_id=prospect_id,
            prospect_score=85,
            prospect_context=sample_prospect_data,
            compliance_validation=compliance_validation
        )
        
        # Manually expire the request
        approval_request.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Attempt to process decision on expired request
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.APPROVED,
            approved_by="late_approver"
        )
        
        success = await approval_workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        # Should fail due to timeout
        assert success is False
        
        completed_request = approval_workflow_service.get_request_by_id(approval_request.request_id)
        assert completed_request.status == ApprovalStatus.TIMEOUT
    
    @pytest.mark.asyncio
    async def test_compliance_metrics_generation(self, sample_prospect_data):
        """Test compliance metrics generation across the workflow."""
        # Create multiple prospects with different compliance outcomes
        prospects = [
            ("compliant_1", 85, True),
            ("compliant_2", 90, True),
            ("violation_1", 80, False),
            ("violation_2", 75, False)
        ]
        
        for prospect_id, score, is_compliant in prospects:
            phone_number = f"+1555123{prospect_id[-1:]}000"
            
            if not is_compliant:
                # Add to DNC list to create violation
                await compliance_service.add_to_dnc_list(
                    phone_number=phone_number,
                    source="test_setup"
                )
            
            # Validate compliance
            compliance_validation = await compliance_service.validate_compliance(
                prospect_id=prospect_id,
                phone_number=phone_number,
                prospect_data=sample_prospect_data
            )
            
            # Create approval request
            await approval_workflow_service.submit_approval_request(
                prospect_id=prospect_id,
                prospect_score=score,
                prospect_context=sample_prospect_data,
                compliance_validation=compliance_validation
            )
        
        # Generate compliance metrics
        period_start = datetime.now(timezone.utc) - timedelta(hours=1)
        period_end = datetime.now(timezone.utc) + timedelta(hours=1)
        
        compliance_metrics = await compliance_service.get_compliance_metrics(
            period_start, period_end
        )
        
        # Verify metrics
        assert compliance_metrics.total_prospects_checked == 4
        assert compliance_metrics.violations_detected == 2
        assert compliance_metrics.compliance_rate == 50.0  # 2 compliant out of 4
        
        # Generate approval metrics
        approval_metrics = approval_workflow_service.get_approval_metrics(
            period_start, period_end
        )
        
        assert approval_metrics["total_requests"] == 4
        assert approval_metrics["pending"] == 4  # All still pending
    
    @pytest.mark.asyncio
    async def test_audit_trail_comprehensive_logging(self, sample_prospect_data):
        """Test that all workflow steps are properly logged in audit trail."""
        prospect_id = "test_prospect_audit"
        phone_number = "+15551234567"
        
        # Clear existing audit entries for clean test
        audit_trail_service.audit_entries.clear()
        
        # Step 1: Compliance validation (should create audit entry)
        compliance_validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        # Step 2: Create approval request (should create audit entry)
        approval_request = await approval_workflow_service.submit_approval_request(
            prospect_id=prospect_id,
            prospect_score=85,
            prospect_context=sample_prospect_data,
            compliance_validation=compliance_validation
        )
        
        # Step 3: Process approval decision (should create audit entry)
        decision = ApprovalDecision(
            request_id=approval_request.request_id,
            decision=ApprovalStatus.APPROVED,
            approved_by="test_approver"
        )
        
        await approval_workflow_service.process_approval_decision(
            approval_request.request_id,
            decision
        )
        
        # Verify audit entries were created
        audit_entries = await audit_trail_service.search_audit_entries(
            prospect_id=prospect_id
        )
        
        # Should have entries for compliance validation and approval request
        assert len(audit_entries) >= 2
        
        event_types = [entry.action_type for entry in audit_entries]
        assert AuditEventType.COMPLIANCE_VALIDATION.value in event_types
        assert AuditEventType.APPROVAL_REQUEST_CREATED.value in event_types
        
        # Verify audit entries contain relevant information
        for entry in audit_entries:
            assert entry.prospect_id == prospect_id
            assert entry.performed_by in ["ai_calling_agent", "system"]
            assert entry.performed_at is not None
    
    @pytest.mark.asyncio
    async def test_data_retention_policy_application(self):
        """Test data retention policy application across all services."""
        # Create old audit entries that should be subject to retention
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        
        # Create system error entry (short-term retention - 30 days)
        entry_id = await audit_trail_service.log_audit_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            action_details={"error": "test_error"}
        )
        
        # Manually set old timestamp
        old_entry = next(e for e in audit_trail_service.audit_entries if e.entry_id == entry_id)
        old_entry.performed_at = old_timestamp
        
        # Create compliance entry (long-term retention - should not be deleted)
        compliance_entry_id = await audit_trail_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            action_details={"validation": "test"}
        )
        
        compliance_entry = next(e for e in audit_trail_service.audit_entries if e.entry_id == compliance_entry_id)
        compliance_entry.performed_at = old_timestamp
        
        initial_count = len(audit_trail_service.audit_entries)
        
        # Apply retention policy
        retention_result = await audit_trail_service.apply_data_retention_policy()
        
        # Verify results
        assert retention_result["entries_reviewed"] == initial_count
        assert retention_result["entries_deleted"] == 1  # System error entry deleted
        assert retention_result["entries_requiring_approval"] == 1  # Compliance entry requires approval
        
        # Verify correct entry was deleted
        remaining_ids = {entry.entry_id for entry in audit_trail_service.audit_entries}
        assert entry_id not in remaining_ids  # System error entry deleted
        assert compliance_entry_id in remaining_ids  # Compliance entry retained
    
    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, sample_prospect_data):
        """Test comprehensive compliance report generation."""
        # Create test data across all services
        prospects = [
            ("report_prospect_1", 85, True),
            ("report_prospect_2", 90, False),  # Will have violation
            ("report_prospect_3", 75, True)
        ]
        
        for prospect_id, score, is_compliant in prospects:
            phone_number = f"+1555999{prospect_id[-1:]}000"
            
            if not is_compliant:
                await compliance_service.add_to_dnc_list(phone_number, "test_setup")
            
            compliance_validation = await compliance_service.validate_compliance(
                prospect_id=prospect_id,
                phone_number=phone_number,
                prospect_data=sample_prospect_data
            )
            
            await approval_workflow_service.submit_approval_request(
                prospect_id=prospect_id,
                prospect_score=score,
                prospect_context=sample_prospect_data,
                compliance_validation=compliance_validation
            )
        
        # Generate comprehensive compliance report
        period_start = datetime.now(timezone.utc) - timedelta(hours=1)
        period_end = datetime.now(timezone.utc) + timedelta(hours=1)
        
        report = await audit_trail_service.generate_compliance_report(
            report_type="detailed",
            start_date=period_start,
            end_date=period_end,
            include_details=True
        )
        
        # Verify report structure
        assert report["report_type"] == "detailed"
        assert "metrics" in report
        assert "summary" in report
        assert "detailed_entries" in report
        assert "user_activity" in report
        assert "system_health" in report
        assert "recommendations" in report
        
        # Verify metrics
        metrics = report["metrics"]
        assert metrics["total_entries"] >= 3  # At least compliance validations
        assert metrics["violation_count"] >= 1  # At least one violation
        
        # Verify recommendations are provided
        assert len(report["recommendations"]) > 0
    
    @pytest.mark.asyncio
    async def test_violation_detection_and_alerting(self, sample_prospect_data):
        """Test violation detection and alerting across the system."""
        prospect_id = "violation_test_prospect"
        phone_number = "+15551234567"
        
        # Create multiple violations
        await compliance_service.add_to_dnc_list(phone_number, "test_violation")
        
        # Log security violation
        await audit_trail_service.log_audit_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            prospect_id=prospect_id,
            compliance_status=ComplianceStatus.VIOLATION,
            action_details={"violation_type": "unauthorized_access"}
        )
        
        # Validate compliance (should detect DNC violation)
        compliance_validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        # Verify violations were detected
        assert not compliance_validation.is_compliant
        assert len(compliance_validation.violations) > 0
        
        # Verify violations were recorded in audit trail
        violations = audit_trail_service.compliance_violations
        assert len(violations) > 0
        
        # Find security violation
        security_violations = [v for v in violations if v.get("violation_type") == "security_violation"]
        assert len(security_violations) > 0
        assert security_violations[0]["severity"] == "high"
        assert security_violations[0]["resolved"] is False