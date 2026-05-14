"""
Tests for audit trail and compliance reporting functionality.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.audit_trail import (
    AuditTrailService, AuditEventType, DataRetentionPolicy, RetentionRule
)
from app.schemas.compliance import (
    ComplianceAuditEntry, ComplianceStatus, ComplianceViolationType
)


class TestAuditTrailService:
    """Test audit trail service functionality."""
    
    @pytest.fixture
    def audit_service(self):
        """Create audit trail service instance for testing."""
        return AuditTrailService()
    
    @pytest.fixture
    def sample_action_details(self):
        """Sample action details for testing."""
        return {
            "prospect_id": "test_prospect_123",
            "phone_number": "+15551234567",
            "company_name": "Test Company Inc",
            "action_result": "success",
            "compliance_checks": ["dnc_list", "consent", "timezone"]
        }
    
    @pytest.mark.asyncio
    async def test_log_audit_event_basic(self, audit_service, sample_action_details):
        """Test basic audit event logging."""
        entry_id = await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            prospect_id="test_prospect_123",
            user_id="test_user",
            action_details=sample_action_details,
            compliance_status=ComplianceStatus.APPROVED,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0"
        )
        
        assert entry_id is not None
        assert len(audit_service.audit_entries) == 1
        
        entry = audit_service.audit_entries[0]
        assert entry.entry_id == entry_id
        assert entry.prospect_id == "test_prospect_123"
        assert entry.action_type == AuditEventType.COMPLIANCE_VALIDATION.value
        assert entry.performed_by == "test_user"
        assert entry.compliance_status == ComplianceStatus.APPROVED
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "TestAgent/1.0"
    
    @pytest.mark.asyncio
    async def test_log_audit_event_with_encryption(self, audit_service):
        """Test audit event logging with sensitive data encryption."""
        sensitive_details = {
            "phone_number": "+15551234567",
            "email": "test@example.com",
            "name": "John Doe",
            "company_name": "Secret Corp",
            "non_sensitive": "public_data"
        }
        
        with patch('app.utils.encryption.encrypt_field') as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
            
            entry_id = await audit_service.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action_details=sensitive_details,
                compliance_status=ComplianceStatus.APPROVED
            )
        
        entry = audit_service.audit_entries[0]
        
        # Verify sensitive fields were encrypted
        assert entry.action_details["phone_number"] == "encrypted_+15551234567"
        assert entry.action_details["email"] == "encrypted_test@example.com"
        assert entry.action_details["name"] == "encrypted_John Doe"
        assert entry.action_details["company_name"] == "encrypted_Secret Corp"
        
        # Non-sensitive data should remain unchanged
        assert entry.action_details["non_sensitive"] == "public_data"
    
    @pytest.mark.asyncio
    async def test_log_audit_event_violation_detection(self, audit_service):
        """Test automatic violation detection during audit logging."""
        # Log a security violation event
        entry_id = await audit_service.log_audit_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action_details={"violation_type": "unauthorized_access"},
            compliance_status=ComplianceStatus.VIOLATION
        )
        
        # Verify violation was detected and recorded
        assert len(audit_service.compliance_violations) == 1
        
        violation = audit_service.compliance_violations[0]
        assert violation["audit_entry_id"] == entry_id
        assert violation["violation_type"] == "security_violation"
        assert violation["severity"] == "high"
        assert not violation["resolved"]
    
    @pytest.mark.asyncio
    async def test_search_audit_entries_by_event_type(self, audit_service):
        """Test searching audit entries by event type."""
        # Create multiple audit entries of different types
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            prospect_id="prospect1"
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.CALL_INITIATED,
            prospect_id="prospect2"
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            prospect_id="prospect3"
        )
        
        # Search for compliance validation events only
        results = await audit_service.search_audit_entries(
            event_types=[AuditEventType.COMPLIANCE_VALIDATION]
        )
        
        assert len(results) == 2
        assert all(entry.action_type == AuditEventType.COMPLIANCE_VALIDATION.value for entry in results)
    
    @pytest.mark.asyncio
    async def test_search_audit_entries_by_prospect(self, audit_service):
        """Test searching audit entries by prospect ID."""
        # Create entries for different prospects
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            prospect_id="target_prospect"
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.CALL_INITIATED,
            prospect_id="other_prospect"
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.APPROVAL_REQUEST_CREATED,
            prospect_id="target_prospect"
        )
        
        # Search for specific prospect
        results = await audit_service.search_audit_entries(
            prospect_id="target_prospect"
        )
        
        assert len(results) == 2
        assert all(entry.prospect_id == "target_prospect" for entry in results)
    
    @pytest.mark.asyncio
    async def test_search_audit_entries_by_date_range(self, audit_service):
        """Test searching audit entries by date range."""
        base_time = datetime.now(timezone.utc)
        
        # Create entries at different times
        with patch('app.services.audit_trail.datetime') as mock_datetime:
            # Entry 1: 2 days ago
            mock_datetime.now.return_value = base_time - timedelta(days=2)
            await audit_service.log_audit_event(
                event_type=AuditEventType.COMPLIANCE_VALIDATION,
                prospect_id="prospect1"
            )
            
            # Entry 2: 1 day ago
            mock_datetime.now.return_value = base_time - timedelta(days=1)
            await audit_service.log_audit_event(
                event_type=AuditEventType.CALL_INITIATED,
                prospect_id="prospect2"
            )
            
            # Entry 3: Now
            mock_datetime.now.return_value = base_time
            await audit_service.log_audit_event(
                event_type=AuditEventType.APPROVAL_DECISION,
                prospect_id="prospect3"
            )
        
        # Search for entries from last 1.5 days
        start_date = base_time - timedelta(days=1, hours=12)
        results = await audit_service.search_audit_entries(
            start_date=start_date
        )
        
        # Should find the last 2 entries
        assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_search_audit_entries_pagination(self, audit_service):
        """Test audit entry search with pagination."""
        # Create multiple entries
        for i in range(25):
            await audit_service.log_audit_event(
                event_type=AuditEventType.COMPLIANCE_VALIDATION,
                prospect_id=f"prospect_{i}"
            )
        
        # Test first page
        page1 = await audit_service.search_audit_entries(limit=10, offset=0)
        assert len(page1) == 10
        
        # Test second page
        page2 = await audit_service.search_audit_entries(limit=10, offset=10)
        assert len(page2) == 10
        
        # Test third page
        page3 = await audit_service.search_audit_entries(limit=10, offset=20)
        assert len(page3) == 5
        
        # Verify no overlap between pages
        page1_ids = {entry.entry_id for entry in page1}
        page2_ids = {entry.entry_id for entry in page2}
        assert page1_ids.isdisjoint(page2_ids)
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report_summary(self, audit_service):
        """Test generating summary compliance report."""
        # Create test data
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            compliance_status=ComplianceStatus.APPROVED
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            compliance_status=ComplianceStatus.VIOLATION
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.CALL_INITIATED,
            compliance_status=ComplianceStatus.APPROVED
        )
        
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        report = await audit_service.generate_compliance_report(
            report_type="summary",
            start_date=start_date,
            end_date=end_date
        )
        
        assert report["report_type"] == "summary"
        assert "period" in report
        assert "metrics" in report
        assert "summary" in report
        
        metrics = report["metrics"]
        assert metrics["total_entries"] == 3
        assert metrics["violation_count"] == 1
        assert metrics["compliance_rate"] == 66.67  # 2 approved out of 3 total
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report_violations(self, audit_service):
        """Test generating violations compliance report."""
        # Create violation entries
        await audit_service.log_audit_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            compliance_status=ComplianceStatus.VIOLATION,
            action_details={"violation_type": "unauthorized_access"}
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.POLICY_VIOLATION,
            compliance_status=ComplianceStatus.VIOLATION,
            action_details={"violation_type": "data_breach"}
        )
        
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        report = await audit_service.generate_compliance_report(
            report_type="violations",
            start_date=start_date,
            end_date=end_date
        )
        
        assert "violations" in report
        violations_report = report["violations"]
        assert violations_report["total_violations"] == 2
        assert "violations_by_type" in violations_report
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report_detailed(self, audit_service):
        """Test generating detailed compliance report."""
        # Create test entries
        for i in range(5):
            await audit_service.log_audit_event(
                event_type=AuditEventType.COMPLIANCE_VALIDATION,
                prospect_id=f"prospect_{i}",
                user_id=f"user_{i % 2}",  # Alternate between 2 users
                compliance_status=ComplianceStatus.APPROVED
            )
        
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        report = await audit_service.generate_compliance_report(
            report_type="detailed",
            start_date=start_date,
            end_date=end_date
        )
        
        assert "detailed_entries" in report
        assert "user_activity" in report
        assert "system_health" in report
        
        # Check user activity report
        user_activity = report["user_activity"]
        assert "user_0" in user_activity
        assert "user_1" in user_activity
        assert user_activity["user_0"]["total_actions"] == 3  # user_0 appears at indices 0, 2, 4
        assert user_activity["user_1"]["total_actions"] == 2  # user_1 appears at indices 1, 3
    
    @pytest.mark.asyncio
    async def test_detect_suspicious_patterns_rapid_actions(self, audit_service):
        """Test detection of suspicious rapid action patterns."""
        # Create many rapid actions from same user
        for i in range(15):
            await audit_service.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                user_id="suspicious_user",
                action_details={"attempt": i}
            )
        
        # The last entry should trigger suspicious pattern detection
        last_entry = audit_service.audit_entries[-1]
        is_suspicious = await audit_service._detect_suspicious_patterns(last_entry)
        
        assert is_suspicious is True
    
    @pytest.mark.asyncio
    async def test_detect_suspicious_patterns_failed_attempts(self, audit_service):
        """Test detection of suspicious failed access attempts."""
        # Create multiple failed access attempts
        for i in range(8):
            await audit_service.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                user_id="failing_user",
                action_details={"success": False, "attempt": i}
            )
        
        # The pattern should be detected
        last_entry = audit_service.audit_entries[-1]
        is_suspicious = await audit_service._detect_suspicious_patterns(last_entry)
        
        assert is_suspicious is True
    
    def test_retention_rules_configuration(self, audit_service):
        """Test data retention rules configuration."""
        retention_rules = audit_service.retention_rules
        
        # Check that critical compliance events have long-term retention
        compliance_rule = retention_rules[AuditEventType.COMPLIANCE_VALIDATION]
        assert compliance_rule.retention_policy == DataRetentionPolicy.LONG_TERM
        assert compliance_rule.retention_days == 2555  # 7 years
        assert compliance_rule.requires_approval_for_deletion is True
        
        # Check that DNC events have permanent retention
        dnc_rule = retention_rules[AuditEventType.DNC_LIST_ADDITION]
        assert dnc_rule.retention_policy == DataRetentionPolicy.PERMANENT
        assert dnc_rule.retention_days == -1  # Never delete
        assert dnc_rule.requires_approval_for_deletion is True
        
        # Check that system errors have short-term retention
        error_rule = retention_rules[AuditEventType.SYSTEM_ERROR]
        assert error_rule.retention_policy == DataRetentionPolicy.SHORT_TERM
        assert error_rule.retention_days == 30
    
    @pytest.mark.asyncio
    async def test_apply_data_retention_policy(self, audit_service):
        """Test application of data retention policies."""
        # Create old entries that should be subject to retention
        old_date = datetime.now(timezone.utc) - timedelta(days=400)  # Very old
        
        with patch('app.services.audit_trail.datetime') as mock_datetime:
            mock_datetime.now.return_value = old_date
            
            # Create an old system error (short retention)
            await audit_service.log_audit_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                action_details={"error": "test_error"}
            )
            
            # Create an old compliance validation (long retention)
            await audit_service.log_audit_event(
                event_type=AuditEventType.COMPLIANCE_VALIDATION,
                action_details={"validation": "test"}
            )
        
        # Apply retention policy
        results = await audit_service.apply_data_retention_policy()
        
        assert "entries_reviewed" in results
        assert "entries_archived" in results
        assert "entries_deleted" in results
        assert results["entries_reviewed"] >= 2
    
    @pytest.mark.asyncio
    async def test_compliance_recommendations_generation(self, audit_service):
        """Test generation of compliance recommendations."""
        # Create entries with low compliance rate
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            compliance_status=ComplianceStatus.VIOLATION
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            compliance_status=ComplianceStatus.VIOLATION
        )
        await audit_service.log_audit_event(
            event_type=AuditEventType.COMPLIANCE_VALIDATION,
            compliance_status=ComplianceStatus.APPROVED
        )
        
        # Calculate metrics
        metrics = await audit_service._calculate_compliance_metrics(audit_service.audit_entries)
        
        # Generate recommendations
        recommendations = await audit_service._generate_compliance_recommendations(metrics)
        
        # Should recommend improving compliance rate (66.67% < 95%)
        assert len(recommendations) > 0
        compliance_rec = next(
            (rec for rec in recommendations if rec["category"] == "Compliance Rate"),
            None
        )
        assert compliance_rec is not None
        assert compliance_rec["priority"] == "High"
    
    @pytest.mark.asyncio
    async def test_violation_alert_system(self, audit_service):
        """Test compliance violation alert system."""
        with patch.object(audit_service, '_send_violation_alert') as mock_alert:
            # Log a high-severity violation
            await audit_service.log_audit_event(
                event_type=AuditEventType.SECURITY_VIOLATION,
                compliance_status=ComplianceStatus.VIOLATION,
                action_details={"severity": "critical"}
            )
            
            # Verify alert was sent for high-severity violation
            mock_alert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_audit_entry_encryption_nested_data(self, audit_service):
        """Test encryption of nested sensitive data in audit entries."""
        nested_details = {
            "prospect_info": {
                "phone_number": "+15551234567",
                "name": "John Doe",
                "company_name": "Secret Corp"
            },
            "call_data": {
                "conversation_content": "Sensitive conversation",
                "duration": 300
            },
            "metadata": {
                "timestamp": "2024-01-01T00:00:00Z",
                "public_field": "not_sensitive"
            }
        }
        
        with patch('app.utils.encryption.encrypt_field') as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
            
            encrypted_data = await audit_service._encrypt_sensitive_data(nested_details)
        
        # Check nested encryption
        assert encrypted_data["prospect_info"]["phone_number"] == "encrypted_+15551234567"
        assert encrypted_data["prospect_info"]["name"] == "encrypted_John Doe"
        assert encrypted_data["prospect_info"]["company_name"] == "encrypted_Secret Corp"
        assert encrypted_data["call_data"]["conversation_content"] == "encrypted_Sensitive conversation"
        
        # Non-sensitive fields should remain unchanged
        assert encrypted_data["call_data"]["duration"] == 300
        assert encrypted_data["metadata"]["public_field"] == "not_sensitive"
    
    @pytest.mark.asyncio
    async def test_compliance_metrics_calculation(self, audit_service):
        """Test comprehensive compliance metrics calculation."""
        # Create diverse audit entries
        test_entries = [
            (AuditEventType.COMPLIANCE_VALIDATION, ComplianceStatus.APPROVED, "user1", "prospect1"),
            (AuditEventType.COMPLIANCE_VALIDATION, ComplianceStatus.VIOLATION, "user1", "prospect2"),
            (AuditEventType.CALL_INITIATED, ComplianceStatus.APPROVED, "user2", "prospect1"),
            (AuditEventType.APPROVAL_DECISION, ComplianceStatus.APPROVED, "user2", "prospect3"),
            (AuditEventType.SYSTEM_ERROR, ComplianceStatus.PENDING, "system", "system")
        ]
        
        for event_type, status, user, prospect in test_entries:
            await audit_service.log_audit_event(
                event_type=event_type,
                compliance_status=status,
                user_id=user,
                prospect_id=prospect
            )
        
        metrics = await audit_service._calculate_compliance_metrics(audit_service.audit_entries)
        
        assert metrics["total_entries"] == 5
        assert metrics["violation_count"] == 1
        assert metrics["compliance_rate"] == 60.0  # 3 approved out of 5 total
        assert metrics["unique_users"] == 3  # user1, user2, system
        assert metrics["unique_prospects"] == 3  # prospect1, prospect2, prospect3 (excluding system)
        
        # Check event type counts
        assert metrics["event_type_counts"][AuditEventType.COMPLIANCE_VALIDATION.value] == 2
        assert metrics["event_type_counts"][AuditEventType.CALL_INITIATED.value] == 1
    
    @pytest.mark.asyncio
    async def test_audit_search_complex_filters(self, audit_service):
        """Test audit search with multiple complex filters."""
        base_time = datetime.now(timezone.utc)
        
        # Create test entries with specific characteristics
        test_cases = [
            {
                "event_type": AuditEventType.COMPLIANCE_VALIDATION,
                "prospect_id": "target_prospect",
                "user_id": "target_user",
                "status": ComplianceStatus.APPROVED,
                "time_offset": timedelta(hours=1)
            },
            {
                "event_type": AuditEventType.COMPLIANCE_VALIDATION,
                "prospect_id": "other_prospect",
                "user_id": "target_user",
                "status": ComplianceStatus.VIOLATION,
                "time_offset": timedelta(hours=2)
            },
            {
                "event_type": AuditEventType.CALL_INITIATED,
                "prospect_id": "target_prospect",
                "user_id": "other_user",
                "status": ComplianceStatus.APPROVED,
                "time_offset": timedelta(hours=3)
            }
        ]
        
        for case in test_cases:
            with patch('app.services.audit_trail.datetime') as mock_datetime:
                mock_datetime.now.return_value = base_time - case["time_offset"]
                
                await audit_service.log_audit_event(
                    event_type=case["event_type"],
                    prospect_id=case["prospect_id"],
                    user_id=case["user_id"],
                    compliance_status=case["status"]
                )
        
        # Search with multiple filters
        results = await audit_service.search_audit_entries(
            event_types=[AuditEventType.COMPLIANCE_VALIDATION],
            prospect_id="target_prospect",
            user_id="target_user",
            compliance_status=ComplianceStatus.APPROVED,
            start_date=base_time - timedelta(hours=4),
            end_date=base_time
        )
        
        # Should find only the first entry that matches all criteria
        assert len(results) == 1
        result = results[0]
        assert result.action_type == AuditEventType.COMPLIANCE_VALIDATION.value
        assert result.prospect_id == "target_prospect"
        assert result.performed_by == "target_user"
        assert result.compliance_status == ComplianceStatus.APPROVED