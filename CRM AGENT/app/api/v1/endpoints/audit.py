"""
Audit trail and compliance reporting API endpoints for AI Calling Agent MVP.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from app.services.audit_trail import (
    AuditTrailService, AuditEventType, audit_trail_service
)
from app.schemas.compliance import (
    ComplianceAuditEntry, ComplianceStatus
)

router = APIRouter()


class AuditSearchRequest(BaseModel):
    """Request model for audit entry search."""
    event_types: Optional[List[str]] = None
    prospect_id: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    compliance_status: Optional[str] = None
    limit: int = 100
    offset: int = 0


class ComplianceReportRequest(BaseModel):
    """Request model for compliance report generation."""
    report_type: str
    start_date: datetime
    end_date: datetime
    include_details: bool = False


@router.get("/entries", response_model=List[ComplianceAuditEntry])
async def search_audit_entries(
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    prospect_id: Optional[str] = Query(None, description="Filter by prospect ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    compliance_status: Optional[str] = Query(None, description="Filter by compliance status"),
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Number of results to skip")
) -> List[ComplianceAuditEntry]:
    """Search audit entries with filtering and pagination."""
    try:
        # Parse event types
        parsed_event_types = None
        if event_types:
            try:
                parsed_event_types = [
                    AuditEventType(event_type.strip())
                    for event_type in event_types.split(",")
                ]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
        
        # Parse compliance status
        parsed_compliance_status = None
        if compliance_status:
            try:
                parsed_compliance_status = ComplianceStatus(compliance_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid compliance status: {compliance_status}")
        
        # Search audit entries
        results = await audit_trail_service.search_audit_entries(
            event_types=parsed_event_types,
            prospect_id=prospect_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            compliance_status=parsed_compliance_status,
            limit=limit,
            offset=offset
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search audit entries: {str(e)}")


@router.post("/entries/search", response_model=List[ComplianceAuditEntry])
async def search_audit_entries_post(
    search_request: AuditSearchRequest
) -> List[ComplianceAuditEntry]:
    """Search audit entries using POST request with complex filters."""
    try:
        # Parse event types
        parsed_event_types = None
        if search_request.event_types:
            try:
                parsed_event_types = [
                    AuditEventType(event_type)
                    for event_type in search_request.event_types
                ]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
        
        # Parse compliance status
        parsed_compliance_status = None
        if search_request.compliance_status:
            try:
                parsed_compliance_status = ComplianceStatus(search_request.compliance_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid compliance status: {search_request.compliance_status}")
        
        # Search audit entries
        results = await audit_trail_service.search_audit_entries(
            event_types=parsed_event_types,
            prospect_id=search_request.prospect_id,
            user_id=search_request.user_id,
            start_date=search_request.start_date,
            end_date=search_request.end_date,
            compliance_status=parsed_compliance_status,
            limit=search_request.limit,
            offset=search_request.offset
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search audit entries: {str(e)}")


@router.get("/entries/{entry_id}", response_model=ComplianceAuditEntry)
async def get_audit_entry(entry_id: str) -> ComplianceAuditEntry:
    """Get a specific audit entry by ID."""
    try:
        # Search for the specific entry
        results = await audit_trail_service.search_audit_entries(limit=1000)  # Search all entries
        
        entry = next((e for e in results if e.entry_id == entry_id), None)
        if not entry:
            raise HTTPException(status_code=404, detail="Audit entry not found")
        
        return entry
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit entry: {str(e)}")


@router.post("/reports/compliance")
async def generate_compliance_report(
    report_request: ComplianceReportRequest
) -> Dict[str, Any]:
    """Generate a compliance report."""
    try:
        # Validate report type
        valid_report_types = ["summary", "detailed", "violations"]
        if report_request.report_type not in valid_report_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report type. Must be one of: {', '.join(valid_report_types)}"
            )
        
        # Validate date range
        if report_request.start_date >= report_request.end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        # Generate report
        report = await audit_trail_service.generate_compliance_report(
            report_type=report_request.report_type,
            start_date=report_request.start_date,
            end_date=report_request.end_date,
            include_details=report_request.include_details
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate compliance report: {str(e)}")


@router.get("/reports/compliance/summary")
async def get_compliance_summary(
    days: int = Query(7, description="Number of days to include in summary")
) -> Dict[str, Any]:
    """Get a quick compliance summary for the specified period."""
    try:
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        report = await audit_trail_service.generate_compliance_report(
            report_type="summary",
            start_date=start_date,
            end_date=end_date
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get compliance summary: {str(e)}")


@router.get("/violations")
async def get_compliance_violations(
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Number of results to skip")
) -> Dict[str, Any]:
    """Get compliance violations with filtering."""
    try:
        violations = audit_trail_service.compliance_violations.copy()
        
        # Apply filters
        if resolved is not None:
            violations = [v for v in violations if v.get("resolved") == resolved]
        
        if severity:
            violations = [v for v in violations if v.get("severity") == severity]
        
        # Sort by detection date (most recent first)
        violations.sort(key=lambda x: x.get("detected_at", datetime.min), reverse=True)
        
        # Apply pagination
        total_count = len(violations)
        paginated_violations = violations[offset:offset + limit]
        
        return {
            "violations": paginated_violations,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get compliance violations: {str(e)}")


@router.put("/violations/{violation_id}/resolve")
async def resolve_compliance_violation(
    violation_id: str,
    resolution_notes: Optional[str] = None
) -> Dict[str, Any]:
    """Mark a compliance violation as resolved."""
    try:
        # Find the violation
        violation = None
        for v in audit_trail_service.compliance_violations:
            if v.get("audit_entry_id") == violation_id:
                violation = v
                break
        
        if not violation:
            raise HTTPException(status_code=404, detail="Compliance violation not found")
        
        # Mark as resolved
        violation["resolved"] = True
        violation["resolved_at"] = datetime.now(timezone.utc)
        violation["resolution_notes"] = resolution_notes
        
        # Log the resolution
        await audit_trail_service.log_audit_event(
            event_type=AuditEventType.POLICY_VIOLATION,
            action_details={
                "action": "violation_resolved",
                "violation_id": violation_id,
                "resolution_notes": resolution_notes
            },
            compliance_status=ComplianceStatus.APPROVED
        )
        
        return {
            "status": "success",
            "message": "Compliance violation marked as resolved",
            "violation_id": violation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve violation: {str(e)}")


@router.post("/retention/apply")
async def apply_data_retention_policy() -> Dict[str, Any]:
    """Apply data retention policies to audit entries."""
    try:
        results = await audit_trail_service.apply_data_retention_policy()
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply retention policy: {str(e)}")


@router.get("/retention/rules")
async def get_retention_rules() -> Dict[str, Any]:
    """Get current data retention rules."""
    try:
        rules = {}
        for event_type, rule in audit_trail_service.retention_rules.items():
            rules[event_type.value] = {
                "retention_policy": rule.retention_policy.value,
                "retention_days": rule.retention_days,
                "archive_after_days": rule.archive_after_days,
                "requires_approval_for_deletion": rule.requires_approval_for_deletion
            }
        
        return {
            "retention_rules": rules,
            "total_rules": len(rules)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get retention rules: {str(e)}")


@router.get("/metrics/dashboard")
async def get_audit_dashboard_metrics(
    days: int = Query(30, description="Number of days to include in metrics")
) -> Dict[str, Any]:
    """Get comprehensive audit and compliance metrics for dashboard."""
    try:
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get compliance report
        compliance_report = await audit_trail_service.generate_compliance_report(
            report_type="summary",
            start_date=start_date,
            end_date=end_date
        )
        
        # Get violation statistics
        violations = audit_trail_service.compliance_violations
        recent_violations = [
            v for v in violations
            if v.get("detected_at", datetime.min.replace(tzinfo=timezone.utc)) >= start_date
        ]
        
        # Calculate additional metrics
        total_entries = len(audit_trail_service.audit_entries)
        recent_entries = [
            e for e in audit_trail_service.audit_entries
            if e.performed_at >= start_date
        ]
        
        dashboard_metrics = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "compliance": compliance_report.get("metrics", {}),
            "violations": {
                "total_recent": len(recent_violations),
                "unresolved": len([v for v in recent_violations if not v.get("resolved", False)]),
                "by_severity": {
                    "high": len([v for v in recent_violations if v.get("severity") == "high"]),
                    "medium": len([v for v in recent_violations if v.get("severity") == "medium"]),
                    "low": len([v for v in recent_violations if v.get("severity") == "low"])
                }
            },
            "activity": {
                "total_entries": total_entries,
                "recent_entries": len(recent_entries),
                "daily_average": len(recent_entries) / days if days > 0 else 0,
                "most_active_users": await _get_most_active_users(recent_entries)
            },
            "system_health": {
                "error_rate": await _calculate_error_rate(recent_entries),
                "compliance_rate": compliance_report.get("metrics", {}).get("compliance_rate", 0),
                "status": "Healthy" if compliance_report.get("metrics", {}).get("compliance_rate", 0) > 95 else "Needs Attention"
            }
        }
        
        return dashboard_metrics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard metrics: {str(e)}")


async def _get_most_active_users(entries: List[ComplianceAuditEntry]) -> List[Dict[str, Any]]:
    """Get most active users from audit entries."""
    user_activity = {}
    
    for entry in entries:
        user = entry.performed_by
        if user not in user_activity:
            user_activity[user] = 0
        user_activity[user] += 1
    
    # Sort by activity count and return top 5
    sorted_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return [
        {"user_id": user, "activity_count": count}
        for user, count in sorted_users
    ]


async def _calculate_error_rate(entries: List[ComplianceAuditEntry]) -> float:
    """Calculate error rate from audit entries."""
    if not entries:
        return 0.0
    
    error_entries = [
        entry for entry in entries
        if entry.action_type == AuditEventType.SYSTEM_ERROR.value
    ]
    
    return (len(error_entries) / len(entries)) * 100


@router.get("/export")
async def export_audit_data(
    format: str = Query("json", description="Export format (json, csv)"),
    start_date: Optional[datetime] = Query(None, description="Start date for export"),
    end_date: Optional[datetime] = Query(None, description="End date for export"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to include")
) -> Dict[str, Any]:
    """Export audit data in specified format."""
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
        
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Parse event types
        parsed_event_types = None
        if event_types:
            try:
                parsed_event_types = [
                    AuditEventType(event_type.strip())
                    for event_type in event_types.split(",")
                ]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
        
        # Get audit entries
        entries = await audit_trail_service.search_audit_entries(
            event_types=parsed_event_types,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Large limit for export
        )
        
        # Log the export action
        await audit_trail_service.log_audit_event(
            event_type=AuditEventType.DATA_EXPORT,
            action_details={
                "export_format": format,
                "entries_count": len(entries),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            },
            compliance_status=ComplianceStatus.APPROVED
        )
        
        if format == "json":
            return {
                "format": "json",
                "export_date": datetime.now(timezone.utc).isoformat(),
                "entries_count": len(entries),
                "entries": [entry.dict() for entry in entries]
            }
        else:  # CSV format
            # For CSV, return structured data that can be converted to CSV
            csv_data = []
            for entry in entries:
                csv_data.append({
                    "entry_id": entry.entry_id,
                    "timestamp": entry.performed_at.isoformat(),
                    "event_type": entry.action_type,
                    "prospect_id": entry.prospect_id,
                    "performed_by": entry.performed_by,
                    "compliance_status": entry.compliance_status.value,
                    "ip_address": entry.ip_address or "",
                    "user_agent": entry.user_agent or ""
                })
            
            return {
                "format": "csv",
                "export_date": datetime.now(timezone.utc).isoformat(),
                "entries_count": len(entries),
                "csv_data": csv_data
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export audit data: {str(e)}")