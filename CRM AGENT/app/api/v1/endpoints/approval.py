"""
Approval workflow API endpoints for AI Calling Agent MVP.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.schemas.compliance import (
    ApprovalRequest, ApprovalDecision, ApprovalStatus,
    ComplianceValidation, ComplianceMetrics
)
from app.services.approval_workflow import approval_workflow_service
from app.services.compliance import compliance_service

router = APIRouter()


class ApprovalRequestCreate(BaseModel):
    """Request to create an approval request."""
    prospect_id: str
    prospect_score: int
    prospect_context: Dict[str, Any]
    compliance_validation: ComplianceValidation


class ApprovalDecisionRequest(BaseModel):
    """Request to make an approval decision."""
    decision: ApprovalStatus
    approved_by: str
    reason: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


@router.post("/requests", response_model=ApprovalRequest)
async def create_approval_request(
    request_data: ApprovalRequestCreate
) -> ApprovalRequest:
    """Create a new approval request for human review."""
    try:
        approval_request = await approval_workflow_service.submit_approval_request(
            prospect_id=request_data.prospect_id,
            prospect_score=request_data.prospect_score,
            prospect_context=request_data.prospect_context,
            compliance_validation=request_data.compliance_validation
        )
        return approval_request
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create approval request: {str(e)}")


@router.get("/requests", response_model=List[ApprovalRequest])
async def get_pending_requests() -> List[ApprovalRequest]:
    """Get all pending approval requests."""
    try:
        return approval_workflow_service.get_pending_requests()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending requests: {str(e)}")


@router.get("/requests/{request_id}", response_model=ApprovalRequest)
async def get_approval_request(request_id: str) -> ApprovalRequest:
    """Get a specific approval request by ID."""
    try:
        approval_request = approval_workflow_service.get_request_by_id(request_id)
        if not approval_request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        return approval_request
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get approval request: {str(e)}")


@router.post("/requests/{request_id}/decision")
async def make_approval_decision(
    request_id: str,
    decision_data: ApprovalDecisionRequest
) -> Dict[str, Any]:
    """Make an approval decision for a request."""
    try:
        decision = ApprovalDecision(
            request_id=request_id,
            decision=decision_data.decision,
            approved_by=decision_data.approved_by,
            reason=decision_data.reason,
            conditions=decision_data.conditions
        )
        
        success = await approval_workflow_service.process_approval_decision(request_id, decision)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to process approval decision")
        
        return {
            "status": "success",
            "message": f"Approval decision processed: {decision_data.decision}",
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process decision: {str(e)}")


@router.get("/requests/{request_id}/ui", response_class=HTMLResponse)
async def get_approval_ui(
    request_id: str,
    request: Request,
    action: Optional[str] = Query(None)
) -> str:
    """Get HTML approval interface for a request."""
    try:
        approval_request = approval_workflow_service.get_request_by_id(request_id)
        if not approval_request:
            return "<html><body><h1>Approval Request Not Found</h1></body></html>"
        
        # If action is provided, process it
        if action in ["approve", "reject"]:
            return _create_action_form(approval_request, action)
        
        # Otherwise, show the approval interface
        return _create_approval_interface(approval_request)
        
    except Exception as e:
        return f"<html><body><h1>Error: {str(e)}</h1></body></html>"


def _create_approval_interface(approval_request: ApprovalRequest) -> str:
    """Create HTML approval interface."""
    prospect_context = approval_request.prospect_context
    compliance = approval_request.compliance_validation
    
    company_name = prospect_context.get("company_name", "Unknown Company")
    contact_name = prospect_context.get("contact_name", "Unknown Contact")
    industry = prospect_context.get("industry", "Unknown")
    revenue_range = prospect_context.get("revenue_range", "Unknown")
    
    compliance_status = "✅ Compliant" if compliance.is_compliant else "⚠️ Issues Found"
    compliance_color = "#28a745" if compliance.is_compliant else "#dc3545"
    
    violations_html = ""
    if compliance.violations:
        violations_html = "<ul>" + "".join([f"<li>{v.value}</li>" for v in compliance.violations]) + "</ul>"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Approval Request - {company_name}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                border-bottom: 2px solid #3498db;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .status-badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                color: white;
                font-weight: bold;
                margin-left: 10px;
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin: 20px 0;
            }}
            .info-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #3498db;
            }}
            .compliance-card {{
                background: {('#d4edda' if compliance.is_compliant else '#f8d7da')};
                border-left-color: {compliance_color};
            }}
            .score {{
                font-size: 2em;
                font-weight: bold;
                color: #2c3e50;
            }}
            .actions {{
                text-align: center;
                margin: 40px 0;
            }}
            .btn {{
                display: inline-block;
                padding: 15px 30px;
                margin: 0 10px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;
                border: none;
            }}
            .btn-approve {{
                background-color: #28a745;
                color: white;
            }}
            .btn-reject {{
                background-color: #dc3545;
                color: white;
            }}
            .btn:hover {{
                opacity: 0.9;
                transform: translateY(-1px);
            }}
            .metadata {{
                background: #e9ecef;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                color: #6c757d;
                margin-top: 30px;
            }}
            .expired {{
                color: #dc3545;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 High-Value Prospect Approval</h1>
                <span class="status-badge" style="background-color: {compliance_color};">{compliance_status}</span>
            </div>
            
            <div class="info-grid">
                <div class="info-card">
                    <h3>Prospect Information</h3>
                    <p><strong>Company:</strong> {company_name}</p>
                    <p><strong>Contact:</strong> {contact_name}</p>
                    <p><strong>Industry:</strong> {industry}</p>
                    <p><strong>Revenue:</strong> {revenue_range}</p>
                </div>
                
                <div class="info-card">
                    <h3>Qualification Score</h3>
                    <div class="score">{approval_request.prospect_score}/100</div>
                    <p>High-value prospect requiring approval</p>
                </div>
            </div>
            
            <div class="info-card compliance-card">
                <h3>Compliance Status</h3>
                <p><strong>Overall Status:</strong> {compliance_status}</p>
                {f'<p><strong>Violations Detected:</strong></p>{violations_html}' if violations_html else '<p>All compliance checks passed ✅</p>'}
                <p><strong>Checks Performed:</strong> {len(compliance.checks)}</p>
            </div>
            
            {'<div class="actions"><p class="expired">⚠️ This approval request has expired</p></div>' if approval_request.is_expired else f'''
            <div class="actions">
                <form method="post" action="/api/v1/approval/requests/{approval_request.request_id}/decision" style="display: inline;">
                    <input type="hidden" name="decision" value="approved">
                    <input type="hidden" name="approved_by" value="web_user">
                    <button type="submit" class="btn btn-approve">✅ Approve Call</button>
                </form>
                
                <form method="post" action="/api/v1/approval/requests/{approval_request.request_id}/decision" style="display: inline;">
                    <input type="hidden" name="decision" value="rejected">
                    <input type="hidden" name="approved_by" value="web_user">
                    <button type="submit" class="btn btn-reject">❌ Reject Call</button>
                </form>
            </div>
            '''}
            
            <div class="metadata">
                <p><strong>Request ID:</strong> {approval_request.request_id}</p>
                <p><strong>Requested:</strong> {approval_request.requested_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p><strong>Expires:</strong> {approval_request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p><strong>Status:</strong> {approval_request.status.value.title()}</p>
            </div>
        </div>
    </body>
    </html>
    """


def _create_action_form(approval_request: ApprovalRequest, action: str) -> str:
    """Create action confirmation form."""
    action_text = "Approve" if action == "approve" else "Reject"
    action_color = "#28a745" if action == "approve" else "#dc3545"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirm {action_text}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .btn {{
                display: inline-block;
                padding: 15px 30px;
                margin: 10px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;
                border: none;
            }}
            .btn-primary {{
                background-color: {action_color};
                color: white;
            }}
            .btn-secondary {{
                background-color: #6c757d;
                color: white;
            }}
            .form-group {{
                margin: 20px 0;
                text-align: left;
            }}
            .form-control {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Confirm {action_text}</h2>
            <p>Are you sure you want to <strong>{action.lower()}</strong> this approval request?</p>
            
            <form method="post" action="/api/v1/approval/requests/{approval_request.request_id}/decision">
                <input type="hidden" name="decision" value="{action}d">
                
                <div class="form-group">
                    <label for="approved_by">Your Name/ID:</label>
                    <input type="text" id="approved_by" name="approved_by" class="form-control" required>
                </div>
                
                <div class="form-group">
                    <label for="reason">Reason (optional):</label>
                    <textarea id="reason" name="reason" class="form-control" rows="3" placeholder="Optional reason for your decision..."></textarea>
                </div>
                
                <button type="submit" class="btn btn-primary">Confirm {action_text}</button>
                <a href="/api/v1/approval/requests/{approval_request.request_id}/ui" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
    </body>
    </html>
    """


@router.get("/metrics")
async def get_approval_metrics(
    days: int = Query(7, description="Number of days to include in metrics")
) -> Dict[str, Any]:
    """Get approval workflow metrics."""
    try:
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)
        
        metrics = approval_workflow_service.get_approval_metrics(period_start, period_end)
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/compliance/metrics")
async def get_compliance_metrics(
    days: int = Query(7, description="Number of days to include in metrics")
) -> ComplianceMetrics:
    """Get compliance metrics."""
    try:
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)
        
        metrics = await compliance_service.get_compliance_metrics(period_start, period_end)
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get compliance metrics: {str(e)}")


@router.post("/compliance/validate")
async def validate_compliance(
    prospect_id: str,
    phone_number: str,
    prospect_data: Dict[str, Any]
) -> ComplianceValidation:
    """Validate compliance for a prospect."""
    try:
        validation = await compliance_service.validate_compliance(
            prospect_id=prospect_id,
            phone_number=phone_number,
            prospect_data=prospect_data
        )
        return validation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate compliance: {str(e)}")


@router.post("/compliance/dnc")
async def add_to_dnc_list(
    phone_number: str,
    source: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Add phone number to Do Not Call list."""
    try:
        success = await compliance_service.add_to_dnc_list(
            phone_number=phone_number,
            source=source,
            reason=reason
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add to DNC list")
        
        return {
            "status": "success",
            "message": "Phone number added to DNC list",
            "phone_number": phone_number
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to DNC list: {str(e)}")


@router.post("/compliance/consent")
async def record_consent(
    phone_number: str,
    consent_type: str,
    consent_given: bool,
    consent_method: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Record consent for a phone number."""
    try:
        success = await compliance_service.record_consent(
            phone_number=phone_number,
            consent_type=consent_type,
            consent_given=consent_given,
            consent_method=consent_method,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to record consent")
        
        return {
            "status": "success",
            "message": "Consent recorded successfully",
            "phone_number": phone_number,
            "consent_given": consent_given
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record consent: {str(e)}")


# Audit Trail and Reporting Endpoints

@router.get("/audit/search")
async def search_audit_entries(
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    prospect_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="ISO format datetime"),
    end_date: Optional[str] = Query(None, description="ISO format datetime"),
    compliance_status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
) -> List[Dict[str, Any]]:
    """Search audit entries with filtering and pagination."""
    try:
        from app.services.audit_trail import audit_trail_service, AuditEventType
        
        # Parse parameters
        parsed_event_types = None
        if event_types:
            try:
                parsed_event_types = [AuditEventType(et.strip()) for et in event_types.split(",")]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {str(e)}")
        
        parsed_start_date = None
        if start_date:
            try:
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format")
        
        parsed_end_date = None
        if end_date:
            try:
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format")
        
        parsed_compliance_status = None
        if compliance_status:
            try:
                parsed_compliance_status = ComplianceStatus(compliance_status)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid compliance_status")
        
        # Search audit entries
        entries = await audit_trail_service.search_audit_entries(
            event_types=parsed_event_types,
            prospect_id=prospect_id,
            user_id=user_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            compliance_status=parsed_compliance_status,
            limit=limit,
            offset=offset
        )
        
        # Convert to dict format for JSON response
        return [
            {
                "entry_id": entry.entry_id,
                "timestamp": entry.performed_at.isoformat(),
                "event_type": entry.action_type,
                "performed_by": entry.performed_by,
                "prospect_id": entry.prospect_id,
                "compliance_status": entry.compliance_status.value,
                "action_details": entry.action_details,
                "ip_address": entry.ip_address,
                "user_agent": entry.user_agent
            }
            for entry in entries
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search audit entries: {str(e)}")


@router.get("/audit/report/{report_type}")
async def generate_compliance_report(
    report_type: str,
    start_date: str = Query(..., description="ISO format datetime"),
    end_date: str = Query(..., description="ISO format datetime"),
    include_details: bool = Query(False)
) -> Dict[str, Any]:
    """Generate comprehensive compliance report."""
    try:
        from app.services.audit_trail import audit_trail_service
        
        # Validate report type
        valid_report_types = ["summary", "detailed", "violations"]
        if report_type not in valid_report_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid report type. Must be one of: {', '.join(valid_report_types)}"
            )
        
        # Parse dates
        try:
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        # Validate date range
        if parsed_start_date >= parsed_end_date:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
        
        # Generate report
        report = await audit_trail_service.generate_compliance_report(
            report_type=report_type,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            include_details=include_details
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/audit/retention/apply")
async def apply_data_retention_policy() -> Dict[str, Any]:
    """Apply data retention policies to audit entries."""
    try:
        from app.services.audit_trail import audit_trail_service
        
        result = await audit_trail_service.apply_data_retention_policy()
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply retention policy: {str(e)}")


@router.get("/audit/export")
async def export_audit_data(
    start_date: str = Query(..., description="ISO format datetime"),
    end_date: str = Query(..., description="ISO format datetime"),
    format_type: str = Query("json", description="Export format (json, csv)"),
    include_pii: bool = Query(False, description="Include PII data (requires authorization)")
) -> Dict[str, Any]:
    """Export audit data for compliance reporting."""
    try:
        from app.services.audit_trail import audit_trail_service
        
        # Parse dates
        try:
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        # Validate format
        if format_type not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
        
        # Export data
        export_data = await audit_trail_service.export_audit_data(
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            format_type=format_type,
            include_pii=include_pii
        )
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export audit data: {str(e)}")


@router.get("/audit/violations")
async def get_compliance_violations(
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high)"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """Get compliance violations with filtering."""
    try:
        from app.services.audit_trail import audit_trail_service
        
        violations = audit_trail_service.compliance_violations.copy()
        
        # Apply filters
        if severity:
            violations = [v for v in violations if v.get("severity") == severity]
        
        if resolved is not None:
            violations = [v for v in violations if v.get("resolved") == resolved]
        
        # Sort by detection time (most recent first)
        violations.sort(key=lambda x: x.get("detected_at", datetime.min), reverse=True)
        
        # Apply pagination
        paginated_violations = violations[offset:offset + limit]
        
        return {
            "total_violations": len(violations),
            "violations": paginated_violations,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": len(violations) > offset + limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get violations: {str(e)}")


@router.post("/audit/log")
async def log_audit_event(
    event_type: str,
    prospect_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action_details: Optional[Dict[str, Any]] = None,
    compliance_status: Optional[str] = None,
    request: Request = None
) -> Dict[str, Any]:
    """Manually log an audit event."""
    try:
        from app.services.audit_trail import audit_trail_service, AuditEventType
        
        # Validate event type
        try:
            parsed_event_type = AuditEventType(event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
        
        # Parse compliance status
        parsed_compliance_status = None
        if compliance_status:
            try:
                parsed_compliance_status = ComplianceStatus(compliance_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid compliance status: {compliance_status}")
        
        # Extract request information
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        # Log the event
        entry_id = await audit_trail_service.log_audit_event(
            event_type=parsed_event_type,
            prospect_id=prospect_id,
            user_id=user_id,
            action_details=action_details or {},
            compliance_status=parsed_compliance_status,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "status": "success",
            "message": "Audit event logged successfully",
            "entry_id": entry_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log audit event: {str(e)}")