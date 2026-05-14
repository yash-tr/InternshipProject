"""
Compliance and approval workflow schemas for AI Calling Agent MVP.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
import pytz


class ComplianceStatus(str, Enum):
    """Compliance check status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    VIOLATION = "violation"


class ApprovalStatus(str, Enum):
    """Human approval status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ComplianceViolationType(str, Enum):
    """Types of compliance violations."""
    DNC_VIOLATION = "dnc_violation"
    TIMEZONE_VIOLATION = "timezone_violation"
    CONSENT_VIOLATION = "consent_violation"
    TCPA_VIOLATION = "tcpa_violation"
    GDPR_VIOLATION = "gdpr_violation"
    FREQUENCY_VIOLATION = "frequency_violation"


class CallingWindow(BaseModel):
    """Calling window configuration for timezone compliance."""
    timezone: str = Field(..., description="Timezone identifier (e.g., 'America/New_York')")
    start_hour: int = Field(8, ge=0, le=23, description="Start hour in 24-hour format")
    end_hour: int = Field(21, ge=0, le=23, description="End hour in 24-hour format")
    allowed_days: List[int] = Field(
        default=[1, 2, 3, 4, 5], 
        description="Allowed days (1=Monday, 7=Sunday)"
    )
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone string."""
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")
    
    @validator('end_hour')
    def validate_hours(cls, v, values):
        """Ensure end hour is after start hour."""
        if 'start_hour' in values and v <= values['start_hour']:
            raise ValueError("End hour must be after start hour")
        return v


class ConsentRecord(BaseModel):
    """Consent tracking record."""
    phone_number: str = Field(..., description="Phone number (encrypted)")
    consent_type: str = Field(..., description="Type of consent (marketing, sales, etc.)")
    consent_given: bool = Field(..., description="Whether consent was given")
    consent_date: datetime = Field(..., description="When consent was given/revoked")
    consent_method: str = Field(..., description="How consent was obtained")
    ip_address: Optional[str] = Field(None, description="IP address when consent given")
    user_agent: Optional[str] = Field(None, description="User agent when consent given")
    expiry_date: Optional[datetime] = Field(None, description="When consent expires")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DNCRecord(BaseModel):
    """Do Not Call list record."""
    phone_number: str = Field(..., description="Phone number (encrypted)")
    added_date: datetime = Field(..., description="When number was added to DNC")
    source: str = Field(..., description="Source of DNC request")
    reason: Optional[str] = Field(None, description="Reason for DNC request")
    expiry_date: Optional[datetime] = Field(None, description="When DNC expires (if applicable)")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComplianceCheck(BaseModel):
    """Individual compliance check result."""
    check_type: str = Field(..., description="Type of compliance check")
    status: ComplianceStatus = Field(..., description="Check result status")
    details: Dict[str, Any] = Field(default_factory=dict, description="Check details")
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    violation_type: Optional[ComplianceViolationType] = Field(None, description="Type of violation if any")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComplianceValidation(BaseModel):
    """Complete compliance validation result."""
    prospect_id: str = Field(..., description="Prospect identifier")
    phone_number: str = Field(..., description="Phone number being validated")
    overall_status: ComplianceStatus = Field(..., description="Overall compliance status")
    checks: List[ComplianceCheck] = Field(..., description="Individual compliance checks")
    violations: List[ComplianceViolationType] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When validation expires")
    
    @property
    def is_compliant(self) -> bool:
        """Check if prospect is compliant for calling."""
        return self.overall_status == ComplianceStatus.APPROVED and not self.violations
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ApprovalRequest(BaseModel):
    """Human approval request."""
    request_id: str = Field(..., description="Unique request identifier")
    prospect_id: str = Field(..., description="Prospect requiring approval")
    prospect_score: int = Field(..., ge=0, le=100, description="Prospect qualification score")
    prospect_context: Dict[str, Any] = Field(..., description="Prospect information for approval")
    compliance_validation: ComplianceValidation = Field(..., description="Compliance check results")
    requested_by: str = Field(..., description="System/user requesting approval")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="When approval request expires")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    approved_by: Optional[str] = Field(None, description="Who approved/rejected")
    approved_at: Optional[datetime] = Field(None, description="When decision was made")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")
    
    @property
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_pending(self) -> bool:
        """Check if approval is still pending."""
        return self.status == ApprovalStatus.PENDING and not self.is_expired
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ApprovalDecision(BaseModel):
    """Human approval decision."""
    request_id: str = Field(..., description="Approval request identifier")
    decision: ApprovalStatus = Field(..., description="Approval decision")
    approved_by: str = Field(..., description="Who made the decision")
    reason: Optional[str] = Field(None, description="Reason for decision")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Any conditions for approval")
    
    @validator('decision')
    def validate_decision(cls, v):
        """Ensure decision is valid."""
        if v not in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
            raise ValueError("Decision must be APPROVED or REJECTED")
        return v


class ComplianceAuditEntry(BaseModel):
    """Audit trail entry for compliance actions."""
    entry_id: str = Field(..., description="Unique audit entry identifier")
    prospect_id: str = Field(..., description="Prospect identifier")
    action_type: str = Field(..., description="Type of action taken")
    action_details: Dict[str, Any] = Field(..., description="Details of the action")
    performed_by: str = Field(..., description="Who performed the action")
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    compliance_status: ComplianceStatus = Field(..., description="Compliance status at time of action")
    ip_address: Optional[str] = Field(None, description="IP address of action")
    user_agent: Optional[str] = Field(None, description="User agent of action")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComplianceMetrics(BaseModel):
    """Compliance metrics and KPIs."""
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")
    total_prospects_checked: int = Field(0, description="Total prospects checked")
    compliant_prospects: int = Field(0, description="Number of compliant prospects")
    violations_detected: int = Field(0, description="Number of violations detected")
    violations_by_type: Dict[str, int] = Field(default_factory=dict)
    approval_requests_sent: int = Field(0, description="Number of approval requests sent")
    approvals_granted: int = Field(0, description="Number of approvals granted")
    approvals_rejected: int = Field(0, description="Number of approvals rejected")
    approval_timeouts: int = Field(0, description="Number of approval timeouts")
    average_approval_time_hours: float = Field(0.0, description="Average approval time in hours")
    
    @property
    def compliance_rate(self) -> float:
        """Calculate compliance rate percentage."""
        if self.total_prospects_checked == 0:
            return 0.0
        return (self.compliant_prospects / self.total_prospects_checked) * 100
    
    @property
    def approval_rate(self) -> float:
        """Calculate approval rate percentage."""
        if self.approval_requests_sent == 0:
            return 0.0
        return (self.approvals_granted / self.approval_requests_sent) * 100
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }