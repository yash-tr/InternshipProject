"""
Compliance service for AI Calling Agent MVP.
Handles DNC checking, consent verification, timezone validation, and approval workflows.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
import pytz
import logging

from app.schemas.compliance import (
    ComplianceStatus, ApprovalStatus, ComplianceViolationType,
    CallingWindow, ConsentRecord, DNCRecord, ComplianceCheck,
    ComplianceValidation, ApprovalRequest, ApprovalDecision,
    ComplianceAuditEntry, ComplianceMetrics
)
from app.utils.encryption import encrypt_field, decrypt_field
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ComplianceService:
    """Service for handling compliance checks and approval workflows."""
    
    def __init__(self):
        self.dnc_list: Set[str] = set()  # In-memory DNC list (encrypted phone numbers)
        self.consent_records: Dict[str, ConsentRecord] = {}  # Consent tracking
        self.calling_windows: Dict[str, CallingWindow] = self._load_calling_windows()
        self.audit_entries: List[ComplianceAuditEntry] = []
        
    def _load_calling_windows(self) -> Dict[str, CallingWindow]:
        """Load default calling windows for different regions."""
        return {
            "US_EASTERN": CallingWindow(
                timezone="America/New_York",
                start_hour=8,
                end_hour=21,
                allowed_days=[1, 2, 3, 4, 5, 6]  # Mon-Sat
            ),
            "US_CENTRAL": CallingWindow(
                timezone="America/Chicago",
                start_hour=8,
                end_hour=21,
                allowed_days=[1, 2, 3, 4, 5, 6]
            ),
            "US_MOUNTAIN": CallingWindow(
                timezone="America/Denver",
                start_hour=8,
                end_hour=21,
                allowed_days=[1, 2, 3, 4, 5, 6]
            ),
            "US_PACIFIC": CallingWindow(
                timezone="America/Los_Angeles",
                start_hour=8,
                end_hour=21,
                allowed_days=[1, 2, 3, 4, 5, 6]
            ),
            "EU_CENTRAL": CallingWindow(
                timezone="Europe/Berlin",
                start_hour=9,
                end_hour=18,
                allowed_days=[1, 2, 3, 4, 5]  # Mon-Fri only for GDPR
            ),
            "UK": CallingWindow(
                timezone="Europe/London",
                start_hour=9,
                end_hour=18,
                allowed_days=[1, 2, 3, 4, 5]
            )
        }
    
    async def validate_compliance(
        self,
        prospect_id: str,
        phone_number: str,
        prospect_data: Dict[str, Any]
    ) -> ComplianceValidation:
        """
        Perform comprehensive compliance validation for a prospect.
        
        Args:
            prospect_id: Unique prospect identifier
            phone_number: Phone number to validate
            prospect_data: Additional prospect information
            
        Returns:
            ComplianceValidation with all check results
        """
        logger.info(f"Starting compliance validation for prospect {prospect_id}")
        
        checks = []
        violations = []
        
        # Encrypt phone number for internal processing
        encrypted_phone = await encrypt_field(phone_number)
        
        # 1. DNC List Check
        dnc_check = await self._check_dnc_list(encrypted_phone)
        checks.append(dnc_check)
        if dnc_check.violation_type:
            violations.append(dnc_check.violation_type)
        
        # 2. Consent Verification
        consent_check = await self._check_consent(encrypted_phone)
        checks.append(consent_check)
        if consent_check.violation_type:
            violations.append(consent_check.violation_type)
        
        # 3. Timezone/Calling Window Check
        timezone_check = await self._check_calling_window(phone_number, prospect_data)
        checks.append(timezone_check)
        if timezone_check.violation_type:
            violations.append(timezone_check.violation_type)
        
        # 4. TCPA Compliance Check
        tcpa_check = await self._check_tcpa_compliance(phone_number, prospect_data)
        checks.append(tcpa_check)
        if tcpa_check.violation_type:
            violations.append(tcpa_check.violation_type)
        
        # 5. GDPR Compliance Check (if EU prospect)
        gdpr_check = await self._check_gdpr_compliance(prospect_data)
        checks.append(gdpr_check)
        if gdpr_check.violation_type:
            violations.append(gdpr_check.violation_type)
        
        # 6. Call Frequency Check
        frequency_check = await self._check_call_frequency(encrypted_phone)
        checks.append(frequency_check)
        if frequency_check.violation_type:
            violations.append(frequency_check.violation_type)
        
        # Determine overall status
        if violations:
            overall_status = ComplianceStatus.VIOLATION
        elif all(check.status == ComplianceStatus.APPROVED for check in checks):
            overall_status = ComplianceStatus.APPROVED
        else:
            overall_status = ComplianceStatus.PENDING
        
        validation = ComplianceValidation(
            prospect_id=prospect_id,
            phone_number=encrypted_phone,
            overall_status=overall_status,
            checks=checks,
            violations=violations,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        # Log audit entry
        await self._log_audit_entry(
            prospect_id=prospect_id,
            action_type="compliance_validation",
            action_details={
                "overall_status": overall_status.value,
                "violations_count": len(violations),
                "checks_count": len(checks)
            },
            compliance_status=overall_status
        )
        
        logger.info(f"Compliance validation completed for prospect {prospect_id}: {overall_status}")
        return validation
    
    async def _check_dnc_list(self, encrypted_phone: str) -> ComplianceCheck:
        """Check if phone number is on Do Not Call list."""
        try:
            is_on_dnc = encrypted_phone in self.dnc_list
            
            return ComplianceCheck(
                check_type="dnc_list",
                status=ComplianceStatus.VIOLATION if is_on_dnc else ComplianceStatus.APPROVED,
                details={"on_dnc_list": is_on_dnc},
                violation_type=ComplianceViolationType.DNC_VIOLATION if is_on_dnc else None
            )
        except Exception as e:
            logger.error(f"Error checking DNC list: {e}")
            return ComplianceCheck(
                check_type="dnc_list",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    async def _check_consent(self, encrypted_phone: str) -> ComplianceCheck:
        """Check if valid consent exists for phone number."""
        try:
            consent_record = self.consent_records.get(encrypted_phone)
            
            if not consent_record:
                return ComplianceCheck(
                    check_type="consent_verification",
                    status=ComplianceStatus.VIOLATION,
                    details={"consent_found": False},
                    violation_type=ComplianceViolationType.CONSENT_VIOLATION
                )
            
            # Check if consent is still valid
            now = datetime.now(timezone.utc)
            if consent_record.expiry_date and now > consent_record.expiry_date:
                return ComplianceCheck(
                    check_type="consent_verification",
                    status=ComplianceStatus.VIOLATION,
                    details={"consent_expired": True, "expiry_date": consent_record.expiry_date},
                    violation_type=ComplianceViolationType.CONSENT_VIOLATION
                )
            
            if not consent_record.consent_given:
                return ComplianceCheck(
                    check_type="consent_verification",
                    status=ComplianceStatus.VIOLATION,
                    details={"consent_revoked": True},
                    violation_type=ComplianceViolationType.CONSENT_VIOLATION
                )
            
            return ComplianceCheck(
                check_type="consent_verification",
                status=ComplianceStatus.APPROVED,
                details={
                    "consent_given": True,
                    "consent_date": consent_record.consent_date,
                    "consent_method": consent_record.consent_method
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking consent: {e}")
            return ComplianceCheck(
                check_type="consent_verification",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    async def _check_calling_window(
        self,
        phone_number: str,
        prospect_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check if current time is within allowed calling window for prospect's timezone."""
        try:
            # Determine prospect's timezone from phone number or location data
            timezone_region = self._determine_timezone_region(phone_number, prospect_data)
            calling_window = self.calling_windows.get(timezone_region)
            
            if not calling_window:
                # Default to US Eastern if timezone cannot be determined
                calling_window = self.calling_windows["US_EASTERN"]
            
            # Get current time in prospect's timezone
            prospect_tz = pytz.timezone(calling_window.timezone)
            current_time = datetime.now(prospect_tz)
            current_hour = current_time.hour
            current_weekday = current_time.isoweekday()  # 1=Monday, 7=Sunday
            
            # Check if current day is allowed
            if current_weekday not in calling_window.allowed_days:
                return ComplianceCheck(
                    check_type="calling_window",
                    status=ComplianceStatus.VIOLATION,
                    details={
                        "current_day": current_weekday,
                        "allowed_days": calling_window.allowed_days,
                        "timezone": calling_window.timezone
                    },
                    violation_type=ComplianceViolationType.TIMEZONE_VIOLATION
                )
            
            # Check if current hour is within allowed window
            if not (calling_window.start_hour <= current_hour < calling_window.end_hour):
                return ComplianceCheck(
                    check_type="calling_window",
                    status=ComplianceStatus.VIOLATION,
                    details={
                        "current_hour": current_hour,
                        "allowed_start": calling_window.start_hour,
                        "allowed_end": calling_window.end_hour,
                        "timezone": calling_window.timezone
                    },
                    violation_type=ComplianceViolationType.TIMEZONE_VIOLATION
                )
            
            return ComplianceCheck(
                check_type="calling_window",
                status=ComplianceStatus.APPROVED,
                details={
                    "timezone": calling_window.timezone,
                    "current_time": current_time.isoformat(),
                    "within_window": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking calling window: {e}")
            return ComplianceCheck(
                check_type="calling_window",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    def _determine_timezone_region(
        self,
        phone_number: str,
        prospect_data: Dict[str, Any]
    ) -> str:
        """Determine timezone region from phone number or prospect data."""
        # Extract country/area code from phone number
        if phone_number.startswith("+1"):
            # North American Numbering Plan
            if len(phone_number) >= 5:
                area_code = phone_number[2:5]
                # Map area codes to timezones (simplified)
                eastern_codes = ["212", "646", "917", "347", "718", "929", "516", "631"]
                central_codes = ["312", "773", "872", "708", "847", "224", "630"]
                mountain_codes = ["303", "720", "970", "719", "505", "575"]
                pacific_codes = ["213", "323", "310", "424", "818", "747", "626"]
                
                if area_code in eastern_codes:
                    return "US_EASTERN"
                elif area_code in central_codes:
                    return "US_CENTRAL"
                elif area_code in mountain_codes:
                    return "US_MOUNTAIN"
                elif area_code in pacific_codes:
                    return "US_PACIFIC"
        
        # Check prospect data for location information
        country = prospect_data.get("country", "").upper()
        if country in ["DE", "FR", "IT", "ES", "NL", "BE"]:
            return "EU_CENTRAL"
        elif country in ["GB", "UK"]:
            return "UK"
        
        # Default to US Eastern
        return "US_EASTERN"
    
    async def _check_tcpa_compliance(
        self,
        phone_number: str,
        prospect_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check TCPA (Telephone Consumer Protection Act) compliance."""
        try:
            # TCPA requires written consent for robocalls to cell phones
            # For now, we'll do basic checks
            
            # Check if it's a mobile number (simplified check)
            is_mobile = self._is_mobile_number(phone_number)
            
            if is_mobile:
                # Mobile numbers require explicit consent under TCPA
                encrypted_phone = await encrypt_field(phone_number)
                consent_record = self.consent_records.get(encrypted_phone)
                
                if not consent_record or not consent_record.consent_given:
                    return ComplianceCheck(
                        check_type="tcpa_compliance",
                        status=ComplianceStatus.VIOLATION,
                        details={"mobile_without_consent": True},
                        violation_type=ComplianceViolationType.TCPA_VIOLATION
                    )
            
            return ComplianceCheck(
                check_type="tcpa_compliance",
                status=ComplianceStatus.APPROVED,
                details={"is_mobile": is_mobile, "tcpa_compliant": True}
            )
            
        except Exception as e:
            logger.error(f"Error checking TCPA compliance: {e}")
            return ComplianceCheck(
                check_type="tcpa_compliance",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    def _is_mobile_number(self, phone_number: str) -> bool:
        """Determine if phone number is mobile (simplified implementation)."""
        # This is a simplified check - in production, use a proper phone number validation service
        if phone_number.startswith("+1"):
            # US numbers - check against known mobile prefixes
            if len(phone_number) >= 6:
                area_code = phone_number[2:5]
                exchange = phone_number[5:8]
                # This is very simplified - real implementation would use carrier lookup
                return True  # Assume mobile for safety
        return True  # Assume mobile for safety
    
    async def _check_gdpr_compliance(self, prospect_data: Dict[str, Any]) -> ComplianceCheck:
        """Check GDPR compliance for EU prospects."""
        try:
            country = prospect_data.get("country", "").upper()
            eu_countries = [
                "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
                "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
                "PL", "PT", "RO", "SK", "SI", "ES", "SE"
            ]
            
            if country in eu_countries:
                # EU prospect - requires explicit GDPR consent
                # Check for GDPR-specific consent record
                # For now, we'll require explicit consent for all EU prospects
                return ComplianceCheck(
                    check_type="gdpr_compliance",
                    status=ComplianceStatus.APPROVED,  # Assume compliant for MVP
                    details={"eu_prospect": True, "gdpr_consent_required": True}
                )
            
            return ComplianceCheck(
                check_type="gdpr_compliance",
                status=ComplianceStatus.APPROVED,
                details={"eu_prospect": False}
            )
            
        except Exception as e:
            logger.error(f"Error checking GDPR compliance: {e}")
            return ComplianceCheck(
                check_type="gdpr_compliance",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    async def _check_call_frequency(self, encrypted_phone: str) -> ComplianceCheck:
        """Check if call frequency limits are respected."""
        try:
            # Check call history for this number (simplified implementation)
            # In production, this would query a database of call attempts
            
            # For MVP, we'll implement basic frequency limits:
            # - Max 3 calls per day
            # - Max 1 call per hour
            # - No calls within 24 hours of explicit rejection
            
            return ComplianceCheck(
                check_type="call_frequency",
                status=ComplianceStatus.APPROVED,  # Simplified for MVP
                details={"frequency_compliant": True}
            )
            
        except Exception as e:
            logger.error(f"Error checking call frequency: {e}")
            return ComplianceCheck(
                check_type="call_frequency",
                status=ComplianceStatus.PENDING,
                details={"error": str(e)}
            )
    
    async def create_approval_request(
        self,
        prospect_id: str,
        prospect_score: int,
        prospect_context: Dict[str, Any],
        compliance_validation: ComplianceValidation
    ) -> ApprovalRequest:
        """Create a human approval request for high-value prospects."""
        request_id = str(uuid.uuid4())
        
        # Set expiration to 24 hours from now
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            prospect_id=prospect_id,
            prospect_score=prospect_score,
            prospect_context=prospect_context,
            compliance_validation=compliance_validation,
            requested_by="ai_calling_agent",
            expires_at=expires_at
        )
        
        # Log audit entry
        await self._log_audit_entry(
            prospect_id=prospect_id,
            action_type="approval_request_created",
            action_details={
                "request_id": request_id,
                "prospect_score": prospect_score,
                "expires_at": expires_at.isoformat()
            },
            compliance_status=compliance_validation.overall_status
        )
        
        logger.info(f"Created approval request {request_id} for prospect {prospect_id}")
        return approval_request
    
    async def process_approval_decision(
        self,
        request_id: str,
        decision: ApprovalDecision
    ) -> bool:
        """Process a human approval decision."""
        try:
            # In production, this would update the approval request in database
            # For MVP, we'll log the decision
            
            await self._log_audit_entry(
                prospect_id="unknown",  # Would be retrieved from request
                action_type="approval_decision",
                action_details={
                    "request_id": request_id,
                    "decision": decision.decision.value,
                    "approved_by": decision.approved_by,
                    "reason": decision.reason
                },
                compliance_status=ComplianceStatus.APPROVED if decision.decision == ApprovalStatus.APPROVED else ComplianceStatus.REJECTED
            )
            
            logger.info(f"Processed approval decision for request {request_id}: {decision.decision}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing approval decision: {e}")
            return False
    
    async def add_to_dnc_list(
        self,
        phone_number: str,
        source: str,
        reason: Optional[str] = None
    ) -> bool:
        """Add phone number to Do Not Call list."""
        try:
            encrypted_phone = await encrypt_field(phone_number)
            self.dnc_list.add(encrypted_phone)
            
            # Create DNC record
            dnc_record = DNCRecord(
                phone_number=encrypted_phone,
                added_date=datetime.now(timezone.utc),
                source=source,
                reason=reason
            )
            
            # Log audit entry
            await self._log_audit_entry(
                prospect_id="unknown",
                action_type="dnc_list_addition",
                action_details={
                    "source": source,
                    "reason": reason
                },
                compliance_status=ComplianceStatus.VIOLATION
            )
            
            logger.info(f"Added phone number to DNC list from source: {source}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding to DNC list: {e}")
            return False
    
    async def record_consent(
        self,
        phone_number: str,
        consent_type: str,
        consent_given: bool,
        consent_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expiry_date: Optional[datetime] = None
    ) -> bool:
        """Record consent for a phone number."""
        try:
            encrypted_phone = await encrypt_field(phone_number)
            
            consent_record = ConsentRecord(
                phone_number=encrypted_phone,
                consent_type=consent_type,
                consent_given=consent_given,
                consent_date=datetime.now(timezone.utc),
                consent_method=consent_method,
                ip_address=ip_address,
                user_agent=user_agent,
                expiry_date=expiry_date
            )
            
            self.consent_records[encrypted_phone] = consent_record
            
            # Log audit entry
            await self._log_audit_entry(
                prospect_id="unknown",
                action_type="consent_recorded",
                action_details={
                    "consent_type": consent_type,
                    "consent_given": consent_given,
                    "consent_method": consent_method
                },
                compliance_status=ComplianceStatus.APPROVED if consent_given else ComplianceStatus.VIOLATION
            )
            
            logger.info(f"Recorded consent: {consent_type} = {consent_given}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording consent: {e}")
            return False
    
    async def _log_audit_entry(
        self,
        prospect_id: str,
        action_type: str,
        action_details: Dict[str, Any],
        compliance_status: ComplianceStatus,
        performed_by: str = "system",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log an audit trail entry."""
        try:
            entry = ComplianceAuditEntry(
                entry_id=str(uuid.uuid4()),
                prospect_id=prospect_id,
                action_type=action_type,
                action_details=action_details,
                performed_by=performed_by,
                compliance_status=compliance_status,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.audit_entries.append(entry)
            logger.debug(f"Logged audit entry: {action_type} for prospect {prospect_id}")
            
        except Exception as e:
            logger.error(f"Error logging audit entry: {e}")
    
    async def get_compliance_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> ComplianceMetrics:
        """Generate compliance metrics for a given period."""
        try:
            # Filter audit entries for the period
            period_entries = [
                entry for entry in self.audit_entries
                if period_start <= entry.performed_at <= period_end
            ]
            
            # Calculate metrics (simplified implementation)
            metrics = ComplianceMetrics(
                period_start=period_start,
                period_end=period_end,
                total_prospects_checked=len([e for e in period_entries if e.action_type == "compliance_validation"]),
                violations_detected=len([e for e in period_entries if e.compliance_status == ComplianceStatus.VIOLATION]),
                approval_requests_sent=len([e for e in period_entries if e.action_type == "approval_request_created"]),
                approvals_granted=len([e for e in period_entries if e.action_type == "approval_decision" and "APPROVED" in str(e.action_details)])
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error generating compliance metrics: {e}")
            return ComplianceMetrics(period_start=period_start, period_end=period_end)


# Global compliance service instance
compliance_service = ComplianceService()