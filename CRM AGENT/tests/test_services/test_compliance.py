"""
Tests for compliance service functionality.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.compliance import ComplianceService, compliance_service
from app.schemas.compliance import (
    ComplianceStatus, ComplianceViolationType, ApprovalStatus,
    CallingWindow, ConsentRecord, DNCRecord, ComplianceCheck,
    ComplianceValidation, ApprovalRequest
)


class TestComplianceService:
    """Test compliance service functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh compliance service instance for testing."""
        return ComplianceService()
    
    @pytest.fixture
    def sample_prospect_data(self):
        """Sample prospect data for testing."""
        return {
            "company_name": "Test Company",
            "contact_name": "John Doe",
            "industry": "Technology",
            "country": "US",
            "revenue_range": "$10M-$50M"
        }
    
    @pytest.mark.asyncio
    async def test_validate_compliance_clean_prospect(self, service, sample_prospect_data):
        """Test compliance validation for a clean prospect."""
        prospect_id = "test_prospect_1"
        phone_number = "+15551234567"
        
        validation = await service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        assert validation.prospect_id == prospect_id
        assert validation.overall_status == ComplianceStatus.APPROVED
        assert len(validation.checks) == 6  # All compliance checks
        assert not validation.violations
        assert validation.is_compliant
    
    @pytest.mark.asyncio
    async def test_validate_compliance_with_violations(self, service, sample_prospect_data):
        """Test compliance validation with violations."""
        prospect_id = "test_prospect_2"
        phone_number = "+15551234567"
        
        # Add phone to DNC list
        encrypted_phone = await service._encrypt_phone_for_test(phone_number)
        service.dnc_list.add(encrypted_phone)
        
        validation = await service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=sample_prospect_data
        )
        
        assert validation.overall_status == ComplianceStatus.VIOLATION
        assert ComplianceViolationType.DNC_VIOLATION in validation.violations
        assert not validation.is_compliant
    
    @pytest.mark.asyncio
    async def test_dnc_list_check_clean_number(self, service):
        """Test DNC list check for clean number."""
        encrypted_phone = "encrypted_test_phone"
        
        check = await service._check_dnc_list(encrypted_phone)
        
        assert check.check_type == "dnc_list"
        assert check.status == ComplianceStatus.APPROVED
        assert check.violation_type is None
        assert not check.details["on_dnc_list"]
    
    @pytest.mark.asyncio
    async def test_dnc_list_check_blocked_number(self, service):
        """Test DNC list check for blocked number."""
        encrypted_phone = "encrypted_blocked_phone"
        service.dnc_list.add(encrypted_phone)
        
        check = await service._check_dnc_list(encrypted_phone)
        
        assert check.check_type == "dnc_list"
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.DNC_VIOLATION
        assert check.details["on_dnc_list"]
    
    @pytest.mark.asyncio
    async def test_consent_check_no_consent(self, service):
        """Test consent check when no consent record exists."""
        encrypted_phone = "encrypted_no_consent_phone"
        
        check = await service._check_consent(encrypted_phone)
        
        assert check.check_type == "consent_verification"
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.CONSENT_VIOLATION
        assert not check.details["consent_found"]
    
    @pytest.mark.asyncio
    async def test_consent_check_valid_consent(self, service):
        """Test consent check with valid consent."""
        encrypted_phone = "encrypted_consent_phone"
        
        # Add valid consent record
        consent_record = ConsentRecord(
            phone_number=encrypted_phone,
            consent_type="marketing",
            consent_given=True,
            consent_date=datetime.now(timezone.utc),
            consent_method="web_form"
        )
        service.consent_records[encrypted_phone] = consent_record
        
        check = await service._check_consent(encrypted_phone)
        
        assert check.check_type == "consent_verification"
        assert check.status == ComplianceStatus.APPROVED
        assert check.violation_type is None
        assert check.details["consent_given"]
    
    @pytest.mark.asyncio
    async def test_consent_check_expired_consent(self, service):
        """Test consent check with expired consent."""
        encrypted_phone = "encrypted_expired_consent_phone"
        
        # Add expired consent record
        consent_record = ConsentRecord(
            phone_number=encrypted_phone,
            consent_type="marketing",
            consent_given=True,
            consent_date=datetime.now(timezone.utc) - timedelta(days=30),
            consent_method="web_form",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=1)
        )
        service.consent_records[encrypted_phone] = consent_record
        
        check = await service._check_consent(encrypted_phone)
        
        assert check.check_type == "consent_verification"
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.CONSENT_VIOLATION
        assert check.details["consent_expired"]
    
    def test_determine_timezone_region_us_eastern(self, service):
        """Test timezone region determination for US Eastern."""
        phone_number = "+12125551234"  # NYC area code
        prospect_data = {}
        
        region = service._determine_timezone_region(phone_number, prospect_data)
        
        assert region == "US_EASTERN"
    
    def test_determine_timezone_region_eu_country(self, service):
        """Test timezone region determination for EU country."""
        phone_number = "+491234567890"
        prospect_data = {"country": "DE"}
        
        region = service._determine_timezone_region(phone_number, prospect_data)
        
        assert region == "EU_CENTRAL"
    
    def test_determine_timezone_region_uk(self, service):
        """Test timezone region determination for UK."""
        phone_number = "+441234567890"
        prospect_data = {"country": "GB"}
        
        region = service._determine_timezone_region(phone_number, prospect_data)
        
        assert region == "UK"
    
    @pytest.mark.asyncio
    async def test_calling_window_check_valid_time(self, service, sample_prospect_data):
        """Test calling window check during valid hours."""
        phone_number = "+15551234567"
        
        # Mock current time to be within calling window (10 AM EST on Tuesday)
        with patch('app.services.compliance.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 2, 15, 0, 0, tzinfo=timezone.utc)  # 10 AM EST
            mock_datetime.now.return_value = mock_now
            
            check = await service._check_calling_window(phone_number, sample_prospect_data)
        
        assert check.check_type == "calling_window"
        assert check.status == ComplianceStatus.APPROVED
        assert check.violation_type is None
        assert check.details["within_window"]
    
    @pytest.mark.asyncio
    async def test_calling_window_check_invalid_time(self, service, sample_prospect_data):
        """Test calling window check outside valid hours."""
        phone_number = "+15551234567"
        
        # Mock current time to be outside calling window (11 PM EST on Tuesday)
        with patch('app.services.compliance.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 3, 4, 0, 0, tzinfo=timezone.utc)  # 11 PM EST
            mock_datetime.now.return_value = mock_now
            
            check = await service._check_calling_window(phone_number, sample_prospect_data)
        
        assert check.check_type == "calling_window"
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.TIMEZONE_VIOLATION
    
    @pytest.mark.asyncio
    async def test_calling_window_check_invalid_day(self, service, sample_prospect_data):
        """Test calling window check on invalid day."""
        phone_number = "+15551234567"
        
        # Mock current time to be on Sunday (day 7)
        with patch('app.services.compliance.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 7, 15, 0, 0, tzinfo=timezone.utc)  # 10 AM EST on Sunday
            mock_datetime.now.return_value = mock_now
            
            check = await service._check_calling_window(phone_number, sample_prospect_data)
        
        assert check.check_type == "calling_window"
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.TIMEZONE_VIOLATION
        assert 7 not in check.details["allowed_days"]
    
    @pytest.mark.asyncio
    async def test_tcpa_compliance_check_mobile(self, service, sample_prospect_data):
        """Test TCPA compliance check for mobile number."""
        phone_number = "+15551234567"
        
        # Mock mobile number detection
        with patch.object(service, '_is_mobile_number', return_value=True):
            check = await service._check_tcpa_compliance(phone_number, sample_prospect_data)
        
        assert check.check_type == "tcpa_compliance"
        # Should be violation since no consent for mobile
        assert check.status == ComplianceStatus.VIOLATION
        assert check.violation_type == ComplianceViolationType.TCPA_VIOLATION
        assert check.details["mobile_without_consent"]
    
    @pytest.mark.asyncio
    async def test_gdpr_compliance_check_eu_prospect(self, service):
        """Test GDPR compliance check for EU prospect."""
        prospect_data = {"country": "DE"}
        
        check = await service._check_gdpr_compliance(prospect_data)
        
        assert check.check_type == "gdpr_compliance"
        assert check.status == ComplianceStatus.APPROVED  # Simplified for MVP
        assert check.details["eu_prospect"]
        assert check.details["gdpr_consent_required"]
    
    @pytest.mark.asyncio
    async def test_gdpr_compliance_check_non_eu_prospect(self, service):
        """Test GDPR compliance check for non-EU prospect."""
        prospect_data = {"country": "US"}
        
        check = await service._check_gdpr_compliance(prospect_data)
        
        assert check.check_type == "gdpr_compliance"
        assert check.status == ComplianceStatus.APPROVED
        assert not check.details["eu_prospect"]
    
    @pytest.mark.asyncio
    async def test_create_approval_request(self, service, sample_prospect_data):
        """Test creating an approval request."""
        prospect_id = "test_prospect_approval"
        prospect_score = 85
        
        # Create mock compliance validation
        compliance_validation = ComplianceValidation(
            prospect_id=prospect_id,
            phone_number="encrypted_phone",
            overall_status=ComplianceStatus.APPROVED,
            checks=[],
            violations=[]
        )
        
        approval_request = await service.create_approval_request(
            prospect_id=prospect_id,
            prospect_score=prospect_score,
            prospect_context=sample_prospect_data,
            compliance_validation=compliance_validation
        )
        
        assert approval_request.prospect_id == prospect_id
        assert approval_request.prospect_score == prospect_score
        assert approval_request.status == ApprovalStatus.PENDING
        assert approval_request.requested_by == "ai_calling_agent"
        assert not approval_request.is_expired
        assert approval_request.is_pending
    
    @pytest.mark.asyncio
    async def test_add_to_dnc_list(self, service):
        """Test adding phone number to DNC list."""
        phone_number = "+15551234567"
        source = "customer_request"
        reason = "No longer interested"
        
        with patch('app.utils.encryption.encrypt_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_phone"
            
            success = await service.add_to_dnc_list(phone_number, source, reason)
        
        assert success
        assert "encrypted_phone" in service.dnc_list
    
    @pytest.mark.asyncio
    async def test_record_consent(self, service):
        """Test recording consent for phone number."""
        phone_number = "+15551234567"
        consent_type = "marketing"
        consent_given = True
        consent_method = "web_form"
        
        with patch('app.utils.encryption.encrypt_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_phone"
            
            success = await service.record_consent(
                phone_number=phone_number,
                consent_type=consent_type,
                consent_given=consent_given,
                consent_method=consent_method
            )
        
        assert success
        assert "encrypted_phone" in service.consent_records
        consent_record = service.consent_records["encrypted_phone"]
        assert consent_record.consent_type == consent_type
        assert consent_record.consent_given == consent_given
        assert consent_record.consent_method == consent_method
    
    @pytest.mark.asyncio
    async def test_get_compliance_metrics(self, service):
        """Test getting compliance metrics."""
        period_start = datetime.now(timezone.utc) - timedelta(days=7)
        period_end = datetime.now(timezone.utc)
        
        # Add some mock audit entries
        await service._log_audit_entry(
            prospect_id="test1",
            action_type="compliance_validation",
            action_details={},
            compliance_status=ComplianceStatus.APPROVED
        )
        
        await service._log_audit_entry(
            prospect_id="test2",
            action_type="compliance_validation",
            action_details={},
            compliance_status=ComplianceStatus.VIOLATION
        )
        
        metrics = await service.get_compliance_metrics(period_start, period_end)
        
        assert metrics.period_start == period_start
        assert metrics.period_end == period_end
        assert metrics.total_prospects_checked == 2
        assert metrics.violations_detected == 1
        assert metrics.compliance_rate == 50.0  # 1 compliant out of 2 total
    
    def test_calling_window_validation(self):
        """Test calling window validation."""
        # Valid calling window
        window = CallingWindow(
            timezone="America/New_York",
            start_hour=8,
            end_hour=21,
            allowed_days=[1, 2, 3, 4, 5]
        )
        assert window.timezone == "America/New_York"
        assert window.start_hour == 8
        assert window.end_hour == 21
        
        # Invalid timezone should raise validation error
        with pytest.raises(ValueError, match="Invalid timezone"):
            CallingWindow(
                timezone="Invalid/Timezone",
                start_hour=8,
                end_hour=21
            )
        
        # Invalid hour range should raise validation error
        with pytest.raises(ValueError, match="End hour must be after start hour"):
            CallingWindow(
                timezone="America/New_York",
                start_hour=21,
                end_hour=8
            )
    
    def test_compliance_validation_properties(self):
        """Test compliance validation properties."""
        validation = ComplianceValidation(
            prospect_id="test",
            phone_number="encrypted_phone",
            overall_status=ComplianceStatus.APPROVED,
            checks=[],
            violations=[]
        )
        
        assert validation.is_compliant
        
        # Test with violations
        validation_with_violations = ComplianceValidation(
            prospect_id="test",
            phone_number="encrypted_phone",
            overall_status=ComplianceStatus.VIOLATION,
            checks=[],
            violations=[ComplianceViolationType.DNC_VIOLATION]
        )
        
        assert not validation_with_violations.is_compliant
    
    def test_approval_request_properties(self):
        """Test approval request properties."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        approval_request = ApprovalRequest(
            request_id="test_request",
            prospect_id="test_prospect",
            prospect_score=85,
            prospect_context={},
            compliance_validation=ComplianceValidation(
                prospect_id="test_prospect",
                phone_number="encrypted_phone",
                overall_status=ComplianceStatus.APPROVED,
                checks=[],
                violations=[]
            ),
            requested_by="system",
            expires_at=expires_at
        )
        
        assert not approval_request.is_expired
        assert approval_request.is_pending
        
        # Test expired request
        expired_request = ApprovalRequest(
            request_id="expired_request",
            prospect_id="test_prospect",
            prospect_score=85,
            prospect_context={},
            compliance_validation=ComplianceValidation(
                prospect_id="test_prospect",
                phone_number="encrypted_phone",
                overall_status=ComplianceStatus.APPROVED,
                checks=[],
                violations=[]
            ),
            requested_by="system",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        assert expired_request.is_expired
        assert not expired_request.is_pending


# Helper method for testing (would be added to ComplianceService)
async def _encrypt_phone_for_test(self, phone_number: str) -> str:
    """Helper method for testing phone encryption."""
    # In real implementation, this would use the actual encryption utility
    return f"encrypted_{phone_number}"

# Monkey patch for testing
ComplianceService._encrypt_phone_for_test = _encrypt_phone_for_test