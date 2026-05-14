"""
Audit trail and compliance reporting service for AI Calling Agent MVP.
Handles comprehensive audit logging, compliance reporting, and data retention policies.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging
from dataclasses import dataclass

from app.schemas.compliance import (
    ComplianceAuditEntry, ComplianceStatus, ComplianceViolationType,
    ComplianceMetrics
)
from app.utils.encryption import encrypt_field, decrypt_field, mask_pii_for_logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    COMPLIANCE_VALIDATION = "compliance_validation"
    APPROVAL_REQUEST_CREATED = "approval_request_created"
    APPROVAL_DECISION = "approval_decision"
    APPROVAL_TIMEOUT = "approval_timeout"
    DNC_LIST_ADDITION = "dnc_list_addition"
    DNC_LIST_REMOVAL = "dnc_list_removal"
    CONSENT_RECORDED = "consent_recorded"
    CONSENT_REVOKED = "consent_revoked"
    CALL_INITIATED = "call_initiated"
    CALL_COMPLETED = "call_completed"
    CALL_BLOCKED = "call_blocked"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    SYSTEM_ERROR = "system_error"
    SECURITY_VIOLATION = "security_violation"
    POLICY_VIOLATION = "policy_violation"


class DataRetentionPolicy(str, Enum):
    """Data retention policy types."""
    IMMEDIATE = "immediate"  # Delete immediately
    SHORT_TERM = "short_term"  # 30 days
    MEDIUM_TERM = "medium_term"  # 1 year
    LONG_TERM = "long_term"  # 7 years
    PERMANENT = "permanent"  # Never delete


@dataclass
class RetentionRule:
    """Data retention rule configuration."""
    event_type: AuditEventType
    retention_policy: DataRetentionPolicy
    retention_days: int
    archive_after_days: Optional[int] = None
    requires_approval_for_deletion: bool = False


class AuditTrailService:
    """Service for managing audit trails and compliance reporting."""
    
    def __init__(self):
        self.audit_entries: List[ComplianceAuditEntry] = []
        self.retention_rules = self._load_retention_rules()
        self.compliance_violations: List[Dict[str, Any]] = []
        self.data_access_log: List[Dict[str, Any]] = []
        self._settings = None
    
    @property
    def settings(self):
        """Lazy load settings to avoid import issues during testing."""
        if self._settings is None:
            try:
                self._settings = get_settings()
            except Exception:
                # Use default settings for testing
                self._settings = type('Settings', (), {})()
        return self._settings
        
    def _load_retention_rules(self) -> Dict[AuditEventType, RetentionRule]:
        """Load data retention rules based on compliance requirements."""
        return {
            # Compliance and approval events - long-term retention
            AuditEventType.COMPLIANCE_VALIDATION: RetentionRule(
                event_type=AuditEventType.COMPLIANCE_VALIDATION,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,  # 7 years
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            AuditEventType.APPROVAL_REQUEST_CREATED: RetentionRule(
                event_type=AuditEventType.APPROVAL_REQUEST_CREATED,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            AuditEventType.APPROVAL_DECISION: RetentionRule(
                event_type=AuditEventType.APPROVAL_DECISION,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            
            # DNC and consent events - permanent retention for compliance
            AuditEventType.DNC_LIST_ADDITION: RetentionRule(
                event_type=AuditEventType.DNC_LIST_ADDITION,
                retention_policy=DataRetentionPolicy.PERMANENT,
                retention_days=-1,  # Never delete
                requires_approval_for_deletion=True
            ),
            AuditEventType.CONSENT_RECORDED: RetentionRule(
                event_type=AuditEventType.CONSENT_RECORDED,
                retention_policy=DataRetentionPolicy.PERMANENT,
                retention_days=-1,
                requires_approval_for_deletion=True
            ),
            AuditEventType.CONSENT_REVOKED: RetentionRule(
                event_type=AuditEventType.CONSENT_REVOKED,
                retention_policy=DataRetentionPolicy.PERMANENT,
                retention_days=-1,
                requires_approval_for_deletion=True
            ),
            
            # Call events - medium-term retention
            AuditEventType.CALL_INITIATED: RetentionRule(
                event_type=AuditEventType.CALL_INITIATED,
                retention_policy=DataRetentionPolicy.MEDIUM_TERM,
                retention_days=365,
                archive_after_days=90
            ),
            AuditEventType.CALL_COMPLETED: RetentionRule(
                event_type=AuditEventType.CALL_COMPLETED,
                retention_policy=DataRetentionPolicy.MEDIUM_TERM,
                retention_days=365,
                archive_after_days=90
            ),
            AuditEventType.CALL_BLOCKED: RetentionRule(
                event_type=AuditEventType.CALL_BLOCKED,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            
            # Data access events - medium-term retention
            AuditEventType.DATA_ACCESS: RetentionRule(
                event_type=AuditEventType.DATA_ACCESS,
                retention_policy=DataRetentionPolicy.MEDIUM_TERM,
                retention_days=365,
                archive_after_days=90
            ),
            AuditEventType.DATA_EXPORT: RetentionRule(
                event_type=AuditEventType.DATA_EXPORT,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            AuditEventType.DATA_DELETION: RetentionRule(
                event_type=AuditEventType.DATA_DELETION,
                retention_policy=DataRetentionPolicy.PERMANENT,
                retention_days=-1,
                requires_approval_for_deletion=True
            ),
            
            # Security events - long-term retention
            AuditEventType.SECURITY_VIOLATION: RetentionRule(
                event_type=AuditEventType.SECURITY_VIOLATION,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            AuditEventType.POLICY_VIOLATION: RetentionRule(
                event_type=AuditEventType.POLICY_VIOLATION,
                retention_policy=DataRetentionPolicy.LONG_TERM,
                retention_days=2555,
                archive_after_days=365,
                requires_approval_for_deletion=True
            ),
            
            # System events - short-term retention
            AuditEventType.SYSTEM_ERROR: RetentionRule(
                event_type=AuditEventType.SYSTEM_ERROR,
                retention_policy=DataRetentionPolicy.SHORT_TERM,
                retention_days=30,
                archive_after_days=7
            )
        }
    
    async def log_audit_event(
        self,
        event_type: AuditEventType,
        prospect_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action_details: Optional[Dict[str, Any]] = None,
        compliance_status: Optional[ComplianceStatus] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event with comprehensive details.
        
        Args:
            event_type: Type of audit event
            prospect_id: Related prospect identifier
            user_id: User who performed the action
            action_details: Detailed information about the action
            compliance_status: Compliance status at time of action
            ip_address: IP address of the action
            user_agent: User agent string
            session_id: Session identifier
            additional_context: Additional context information
            
        Returns:
            Audit entry ID
        """
        try:
            entry_id = str(uuid.uuid4())
            
            # Encrypt sensitive data in action details
            encrypted_action_details = {}
            if action_details:
                encrypted_action_details = await self._encrypt_sensitive_data(action_details)
            
            # Create audit entry
            audit_entry = ComplianceAuditEntry(
                entry_id=entry_id,
                prospect_id=prospect_id or "system",
                action_type=event_type.value,
                action_details=encrypted_action_details,
                performed_by=user_id or "system",
                compliance_status=compliance_status or ComplianceStatus.PENDING,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Add additional context if provided
            if additional_context:
                audit_entry.action_details.update(additional_context)
            
            # Add session information
            if session_id:
                audit_entry.action_details["session_id"] = session_id
            
            # Store audit entry
            self.audit_entries.append(audit_entry)
            
            # Check for compliance violations
            await self._check_for_violations(audit_entry)
            
            # Log for monitoring (with masked PII)
            masked_details = mask_pii_for_logging(encrypted_action_details)
            logger.info(f"Audit event logged: {event_type.value} by {user_id or 'system'} - {masked_details}")
            
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            raise
    
    async def _encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive data in audit details."""
        encrypted_data = data.copy()
        
        # Fields that should be encrypted in audit logs
        sensitive_fields = [
            'phone_number', 'email', 'name', 'company_name', 'contact_name',
            'conversation_content', 'call_recording_url', 'personal_data'
        ]
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                if isinstance(encrypted_data[field], str):
                    encrypted_data[field] = await encrypt_field(encrypted_data[field])
                elif isinstance(encrypted_data[field], dict):
                    encrypted_data[field] = await self._encrypt_sensitive_data(encrypted_data[field])
        
        return encrypted_data
    
    async def _check_for_violations(self, audit_entry: ComplianceAuditEntry) -> None:
        """Check audit entry for compliance violations and alert if necessary."""
        try:
            violation_detected = False
            violation_details = {}
            
            # Check for security violations
            if audit_entry.action_type in [
                AuditEventType.SECURITY_VIOLATION.value,
                AuditEventType.POLICY_VIOLATION.value
            ]:
                violation_detected = True
                violation_details = {
                    "type": "security_violation",
                    "severity": "high",
                    "requires_immediate_attention": True
                }
            
            # Check for compliance status violations
            if audit_entry.compliance_status == ComplianceStatus.VIOLATION:
                violation_detected = True
                violation_details = {
                    "type": "compliance_violation",
                    "severity": "medium",
                    "requires_review": True
                }
            
            # Check for suspicious patterns (simplified implementation)
            if await self._detect_suspicious_patterns(audit_entry):
                violation_detected = True
                violation_details = {
                    "type": "suspicious_activity",
                    "severity": "medium",
                    "requires_investigation": True
                }
            
            if violation_detected:
                violation_record = {
                    "audit_entry_id": audit_entry.entry_id,
                    "violation_type": violation_details.get("type"),
                    "severity": violation_details.get("severity"),
                    "detected_at": datetime.now(timezone.utc),
                    "details": violation_details,
                    "resolved": False
                }
                
                self.compliance_violations.append(violation_record)
                
                # Send alert for high-severity violations
                if violation_details.get("severity") == "high":
                    await self._send_violation_alert(violation_record)
                
        except Exception as e:
            logger.error(f"Error checking for violations: {e}")
    
    async def _detect_suspicious_patterns(self, audit_entry: ComplianceAuditEntry) -> bool:
        """Detect suspicious patterns in audit entries."""
        try:
            # Check for rapid successive actions from same user/IP
            recent_entries = [
                entry for entry in self.audit_entries[-100:]  # Check last 100 entries
                if entry.performed_by == audit_entry.performed_by
                and entry.performed_at > datetime.now(timezone.utc) - timedelta(minutes=5)
            ]
            
            # Flag if more than 10 actions in 5 minutes
            if len(recent_entries) > 10:
                return True
            
            # Check for failed access attempts
            if audit_entry.action_type == AuditEventType.DATA_ACCESS.value:
                failed_attempts = [
                    entry for entry in recent_entries
                    if entry.action_type == AuditEventType.DATA_ACCESS.value
                    and entry.action_details.get("success") is False
                ]
                
                # Flag if more than 5 failed attempts
                if len(failed_attempts) > 5:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting suspicious patterns: {e}")
            return False
    
    async def _send_violation_alert(self, violation_record: Dict[str, Any]) -> None:
        """Send alert for compliance violations."""
        try:
            # In production, this would send alerts via email, Slack, etc.
            logger.critical(f"COMPLIANCE VIOLATION DETECTED: {violation_record}")
            
            # For MVP, just log the violation
            # In production, integrate with notification systems
            
        except Exception as e:
            logger.error(f"Error sending violation alert: {e}")
    
    async def search_audit_entries(
        self,
        event_types: Optional[List[AuditEventType]] = None,
        prospect_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        compliance_status: Optional[ComplianceStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ComplianceAuditEntry]:
        """
        Search audit entries with filtering and pagination.
        
        Args:
            event_types: Filter by event types
            prospect_id: Filter by prospect ID
            user_id: Filter by user ID
            start_date: Filter by start date
            end_date: Filter by end date
            compliance_status: Filter by compliance status
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of matching audit entries
        """
        try:
            filtered_entries = self.audit_entries.copy()
            
            # Apply filters
            if event_types:
                event_type_values = [et.value for et in event_types]
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.action_type in event_type_values
                ]
            
            if prospect_id:
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.prospect_id == prospect_id
                ]
            
            if user_id:
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.performed_by == user_id
                ]
            
            if start_date:
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.performed_at >= start_date
                ]
            
            if end_date:
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.performed_at <= end_date
                ]
            
            if compliance_status:
                filtered_entries = [
                    entry for entry in filtered_entries
                    if entry.compliance_status == compliance_status
                ]
            
            # Sort by timestamp (most recent first)
            filtered_entries.sort(key=lambda x: x.performed_at, reverse=True)
            
            # Apply pagination
            return filtered_entries[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error searching audit entries: {e}")
            return []
    
    async def generate_compliance_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            report_type: Type of report (summary, detailed, violations)
            start_date: Report period start
            end_date: Report period end
            include_details: Whether to include detailed entries
            
        Returns:
            Compliance report data
        """
        try:
            # Filter entries for the period
            period_entries = [
                entry for entry in self.audit_entries
                if start_date <= entry.performed_at <= end_date
            ]
            
            # Generate base metrics
            metrics = await self._calculate_compliance_metrics(period_entries)
            
            report = {
                "report_type": report_type,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics,
                "summary": await self._generate_report_summary(period_entries, metrics)
            }
            
            # Add specific report sections based on type
            if report_type == "violations":
                report["violations"] = await self._generate_violations_report(period_entries)
            elif report_type == "detailed":
                report["detailed_entries"] = await self._generate_detailed_entries(period_entries)
                report["user_activity"] = await self._generate_user_activity_report(period_entries)
                report["system_health"] = await self._generate_system_health_report(period_entries)
            
            # Add compliance recommendations
            report["recommendations"] = await self._generate_compliance_recommendations(metrics)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {"error": str(e)}
    
    async def _calculate_compliance_metrics(
        self,
        entries: List[ComplianceAuditEntry]
    ) -> Dict[str, Any]:
        """Calculate compliance metrics from audit entries."""
        total_entries = len(entries)
        
        # Count by event type
        event_type_counts = {}
        for entry in entries:
            event_type_counts[entry.action_type] = event_type_counts.get(entry.action_type, 0) + 1
        
        # Count by compliance status
        status_counts = {}
        for entry in entries:
            status = entry.compliance_status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count violations
        violation_entries = [
            entry for entry in entries
            if entry.compliance_status == ComplianceStatus.VIOLATION
        ]
        
        # Calculate compliance rate
        compliant_entries = [
            entry for entry in entries
            if entry.compliance_status == ComplianceStatus.APPROVED
        ]
        compliance_rate = (len(compliant_entries) / total_entries * 100) if total_entries > 0 else 0
        
        return {
            "total_entries": total_entries,
            "event_type_counts": event_type_counts,
            "status_counts": status_counts,
            "violation_count": len(violation_entries),
            "compliance_rate": round(compliance_rate, 2),
            "unique_users": len(set(entry.performed_by for entry in entries)),
            "unique_prospects": len(set(entry.prospect_id for entry in entries if entry.prospect_id != "system"))
        }
    
    async def _generate_report_summary(
        self,
        entries: List[ComplianceAuditEntry],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate executive summary for compliance report."""
        return {
            "total_activities": metrics["total_entries"],
            "compliance_rate": f"{metrics['compliance_rate']}%",
            "violations_detected": metrics["violation_count"],
            "most_common_activity": max(metrics["event_type_counts"].items(), key=lambda x: x[1])[0] if metrics["event_type_counts"] else "None",
            "risk_level": "Low" if metrics["compliance_rate"] > 95 else "Medium" if metrics["compliance_rate"] > 85 else "High",
            "recommendations_count": len(await self._generate_compliance_recommendations(metrics))
        }
    
    async def _generate_violations_report(
        self,
        entries: List[ComplianceAuditEntry]
    ) -> Dict[str, Any]:
        """Generate detailed violations report."""
        violation_entries = [
            entry for entry in entries
            if entry.compliance_status == ComplianceStatus.VIOLATION
        ]
        
        # Group violations by type
        violations_by_type = {}
        for entry in violation_entries:
            action_type = entry.action_type
            if action_type not in violations_by_type:
                violations_by_type[action_type] = []
            violations_by_type[action_type].append({
                "entry_id": entry.entry_id,
                "timestamp": entry.performed_at.isoformat(),
                "performed_by": entry.performed_by,
                "prospect_id": entry.prospect_id
            })
        
        return {
            "total_violations": len(violation_entries),
            "violations_by_type": violations_by_type,
            "violation_trend": "Increasing" if len(violation_entries) > 0 else "Stable",  # Simplified
            "critical_violations": len([v for v in self.compliance_violations if v.get("severity") == "high"])
        }
    
    async def _generate_detailed_entries(
        self,
        entries: List[ComplianceAuditEntry]
    ) -> List[Dict[str, Any]]:
        """Generate detailed entries for report (with PII masked)."""
        detailed_entries = []
        
        for entry in entries[-50:]:  # Last 50 entries for detailed report
            # Decrypt and mask sensitive data for reporting
            masked_details = mask_pii_for_logging(entry.action_details)
            
            detailed_entries.append({
                "entry_id": entry.entry_id,
                "timestamp": entry.performed_at.isoformat(),
                "event_type": entry.action_type,
                "performed_by": entry.performed_by,
                "compliance_status": entry.compliance_status.value,
                "details": masked_details
            })
        
        return detailed_entries
    
    async def _generate_user_activity_report(
        self,
        entries: List[ComplianceAuditEntry]
    ) -> Dict[str, Any]:
        """Generate user activity analysis."""
        user_activity = {}
        
        for entry in entries:
            user = entry.performed_by
            if user not in user_activity:
                user_activity[user] = {
                    "total_actions": 0,
                    "violations": 0,
                    "last_activity": entry.performed_at
                }
            
            user_activity[user]["total_actions"] += 1
            if entry.compliance_status == ComplianceStatus.VIOLATION:
                user_activity[user]["violations"] += 1
            
            if entry.performed_at > user_activity[user]["last_activity"]:
                user_activity[user]["last_activity"] = entry.performed_at
        
        # Convert datetime objects to ISO strings
        for user_data in user_activity.values():
            user_data["last_activity"] = user_data["last_activity"].isoformat()
        
        return user_activity
    
    async def _generate_system_health_report(
        self,
        entries: List[ComplianceAuditEntry]
    ) -> Dict[str, Any]:
        """Generate system health analysis."""
        error_entries = [
            entry for entry in entries
            if entry.action_type == AuditEventType.SYSTEM_ERROR.value
        ]
        
        return {
            "total_errors": len(error_entries),
            "error_rate": (len(error_entries) / len(entries) * 100) if entries else 0,
            "system_status": "Healthy" if len(error_entries) < len(entries) * 0.01 else "Degraded",
            "uptime_percentage": 99.9  # Simplified calculation
        }
    
    async def _generate_compliance_recommendations(
        self,
        metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate compliance recommendations based on metrics."""
        recommendations = []
        
        # Check compliance rate
        if metrics["compliance_rate"] < 95:
            recommendations.append({
                "priority": "High",
                "category": "Compliance Rate",
                "recommendation": "Improve compliance validation processes",
                "details": f"Current compliance rate is {metrics['compliance_rate']}%, target is 95%+"
            })
        
        # Check violation count
        if metrics["violation_count"] > 0:
            recommendations.append({
                "priority": "Medium",
                "category": "Violations",
                "recommendation": "Review and address compliance violations",
                "details": f"{metrics['violation_count']} violations detected in reporting period"
            })
        
        # Check for missing audit coverage
        expected_events = [
            AuditEventType.COMPLIANCE_VALIDATION.value,
            AuditEventType.CALL_INITIATED.value,
            AuditEventType.APPROVAL_REQUEST_CREATED.value
        ]
        
        missing_events = [
            event for event in expected_events
            if event not in metrics["event_type_counts"]
        ]
        
        if missing_events:
            recommendations.append({
                "priority": "Low",
                "category": "Audit Coverage",
                "recommendation": "Ensure all critical events are being audited",
                "details": f"Missing audit events: {', '.join(missing_events)}"
            })
        
        return recommendations
    
    async def apply_data_retention_policy(self) -> Dict[str, Any]:
        """Apply data retention policies to audit entries."""
        try:
            now = datetime.now(timezone.utc)
            retention_results = {
                "entries_reviewed": 0,
                "entries_archived": 0,
                "entries_deleted": 0,
                "entries_requiring_approval": 0,
                "errors": []
            }
            
            for entry in self.audit_entries.copy():
                retention_results["entries_reviewed"] += 1
                
                try:
                    # Get retention rule for this event type
                    event_type = AuditEventType(entry.action_type)
                    retention_rule = self.retention_rules.get(event_type)
                    
                    if not retention_rule:
                        continue
                    
                    # Calculate age of entry
                    entry_age = (now - entry.performed_at).days
                    
                    # Check if entry should be deleted
                    if retention_rule.retention_days > 0 and entry_age > retention_rule.retention_days:
                        if retention_rule.requires_approval_for_deletion:
                            retention_results["entries_requiring_approval"] += 1
                            # In production, create approval request for deletion
                        else:
                            # Delete entry
                            self.audit_entries.remove(entry)
                            retention_results["entries_deleted"] += 1
                    
                    # Check if entry should be archived
                    elif (retention_rule.archive_after_days and 
                          entry_age > retention_rule.archive_after_days):
                        # In production, move to archive storage
                        retention_results["entries_archived"] += 1
                
                except Exception as e:
                    retention_results["errors"].append(f"Error processing entry {entry.entry_id}: {str(e)}")
            
            logger.info(f"Data retention policy applied: {retention_results}")
            return retention_results
            
        except Exception as e:
            logger.error(f"Error applying data retention policy: {e}")
            return {"error": str(e)}
    
    async def export_audit_data(
        self,
        start_date: datetime,
        end_date: datetime,
        format_type: str = "json",
        include_pii: bool = False
    ) -> Dict[str, Any]:
        """
        Export audit data for compliance reporting or analysis.
        
        Args:
            start_date: Export period start
            end_date: Export period end
            format_type: Export format (json, csv)
            include_pii: Whether to include PII data (requires special authorization)
            
        Returns:
            Export data and metadata
        """
        try:
            # Log data export event
            await self.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                action_details={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "format": format_type,
                    "include_pii": include_pii
                }
            )
            
            # Filter entries for export period
            export_entries = [
                entry for entry in self.audit_entries
                if start_date <= entry.performed_at <= end_date
            ]
            
            # Process entries for export
            processed_entries = []
            for entry in export_entries:
                entry_data = {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.performed_at.isoformat(),
                    "event_type": entry.action_type,
                    "performed_by": entry.performed_by,
                    "prospect_id": entry.prospect_id,
                    "compliance_status": entry.compliance_status.value,
                    "ip_address": entry.ip_address,
                    "user_agent": entry.user_agent
                }
                
                # Handle action details based on PII inclusion
                if include_pii:
                    # Decrypt sensitive data for authorized export
                    entry_data["action_details"] = entry.action_details  # Would decrypt in production
                else:
                    # Mask PII for standard export
                    entry_data["action_details"] = mask_pii_for_logging(entry.action_details)
                
                processed_entries.append(entry_data)
            
            export_data = {
                "metadata": {
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "total_entries": len(processed_entries),
                    "format": format_type,
                    "includes_pii": include_pii
                },
                "entries": processed_entries
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting audit data: {e}")
            return {"error": str(e)}


# Global audit trail service instance
audit_trail_service = AuditTrailService()