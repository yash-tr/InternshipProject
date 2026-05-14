"""
Approval workflow service for AI Calling Agent MVP.
Handles human approval requests, notifications, and decision tracking.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import logging
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.schemas.compliance import (
    ApprovalRequest, ApprovalDecision, ApprovalStatus,
    ComplianceValidation, ComplianceAuditEntry
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationService:
    """Service for sending approval notifications via Slack and email."""
    
    def __init__(self):
        self.slack_webhook_url = settings.SLACK_WEBHOOK_URL
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
    
    async def send_slack_notification(
        self,
        approval_request: ApprovalRequest,
        channel: str = "#approvals"
    ) -> bool:
        """Send approval request notification to Slack."""
        try:
            if not self.slack_webhook_url:
                logger.warning("Slack webhook URL not configured")
                return False
            
            # Create Slack message
            message = self._create_slack_message(approval_request)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook_url,
                    json=message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for approval request {approval_request.request_id}")
                        return True
                    else:
                        logger.error(f"Failed to send Slack notification: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _create_slack_message(self, approval_request: ApprovalRequest) -> Dict[str, Any]:
        """Create Slack message for approval request."""
        prospect_context = approval_request.prospect_context
        compliance = approval_request.compliance_validation
        
        # Extract key prospect information
        company_name = prospect_context.get("company_name", "Unknown Company")
        contact_name = prospect_context.get("contact_name", "Unknown Contact")
        industry = prospect_context.get("industry", "Unknown")
        revenue_range = prospect_context.get("revenue_range", "Unknown")
        
        # Create compliance status summary
        compliance_summary = "✅ Compliant" if compliance.is_compliant else "⚠️ Issues Found"
        if compliance.violations:
            compliance_summary += f" ({len(compliance.violations)} violations)"
        
        # Create approval URL (would link to approval dashboard)
        approval_url = f"{settings.BASE_URL}/approval/{approval_request.request_id}"
        
        return {
            "text": f"🔔 High-Value Prospect Approval Required",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎯 High-Value Prospect Approval Required"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Company:* {company_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Contact:* {contact_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Industry:* {industry}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Revenue:* {revenue_range}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Score:* {approval_request.prospect_score}/100"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Compliance:* {compliance_summary}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Request ID:* `{approval_request.request_id}`\n*Expires:* {approval_request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Approve"
                            },
                            "style": "primary",
                            "url": f"{approval_url}?action=approve"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "❌ Reject"
                            },
                            "style": "danger",
                            "url": f"{approval_url}?action=reject"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📋 View Details"
                            },
                            "url": approval_url
                        }
                    ]
                }
            ]
        }
    
    async def send_email_notification(
        self,
        approval_request: ApprovalRequest,
        recipient_emails: List[str]
    ) -> bool:
        """Send approval request notification via email."""
        try:
            if not all([self.smtp_server, self.smtp_username, self.smtp_password]):
                logger.warning("Email configuration not complete")
                return False
            
            # Create email message
            subject = f"Approval Required: High-Value Prospect (Score: {approval_request.prospect_score})"
            html_body = self._create_email_html(approval_request)
            text_body = self._create_email_text(approval_request)
            
            # Send to each recipient
            success_count = 0
            for email in recipient_emails:
                if await self._send_single_email(email, subject, html_body, text_body):
                    success_count += 1
            
            logger.info(f"Email notifications sent to {success_count}/{len(recipient_emails)} recipients")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending email notifications: {e}")
            return False
    
    async def _send_single_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """Send a single email notification."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = recipient
            
            # Add text and HTML parts
            text_part = MIMEText(text_body, 'plain')
            html_part = MIMEText(html_body, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return False
    
    def _create_email_html(self, approval_request: ApprovalRequest) -> str:
        """Create HTML email body for approval request."""
        prospect_context = approval_request.prospect_context
        compliance = approval_request.compliance_validation
        
        company_name = prospect_context.get("company_name", "Unknown Company")
        contact_name = prospect_context.get("contact_name", "Unknown Contact")
        industry = prospect_context.get("industry", "Unknown")
        revenue_range = prospect_context.get("revenue_range", "Unknown")
        
        approval_url = f"{settings.BASE_URL}/approval/{approval_request.request_id}"
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    🎯 High-Value Prospect Approval Required
                </h2>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #2c3e50;">Prospect Information</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Company:</td>
                            <td style="padding: 8px 0;">{company_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Contact:</td>
                            <td style="padding: 8px 0;">{contact_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Industry:</td>
                            <td style="padding: 8px 0;">{industry}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Revenue:</td>
                            <td style="padding: 8px 0;">{revenue_range}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Qualification Score:</td>
                            <td style="padding: 8px 0;"><strong>{approval_request.prospect_score}/100</strong></td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: {'#d4edda' if compliance.is_compliant else '#f8d7da'}; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="margin-top: 0;">Compliance Status</h4>
                    <p>{'✅ All compliance checks passed' if compliance.is_compliant else '⚠️ Compliance issues detected'}</p>
                    {f'<p><strong>Violations:</strong> {", ".join([v.value for v in compliance.violations])}</p>' if compliance.violations else ''}
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{approval_url}?action=approve" 
                       style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 0 10px; display: inline-block;">
                        ✅ Approve
                    </a>
                    <a href="{approval_url}?action=reject" 
                       style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 0 10px; display: inline-block;">
                        ❌ Reject
                    </a>
                </div>
                
                <div style="border-top: 1px solid #dee2e6; padding-top: 20px; margin-top: 30px; font-size: 14px; color: #6c757d;">
                    <p><strong>Request ID:</strong> {approval_request.request_id}</p>
                    <p><strong>Expires:</strong> {approval_request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                    <p><a href="{approval_url}">View full details and make decision</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_email_text(self, approval_request: ApprovalRequest) -> str:
        """Create plain text email body for approval request."""
        prospect_context = approval_request.prospect_context
        compliance = approval_request.compliance_validation
        
        company_name = prospect_context.get("company_name", "Unknown Company")
        contact_name = prospect_context.get("contact_name", "Unknown Contact")
        industry = prospect_context.get("industry", "Unknown")
        revenue_range = prospect_context.get("revenue_range", "Unknown")
        
        approval_url = f"{settings.BASE_URL}/approval/{approval_request.request_id}"
        
        return f"""
HIGH-VALUE PROSPECT APPROVAL REQUIRED

Prospect Information:
- Company: {company_name}
- Contact: {contact_name}
- Industry: {industry}
- Revenue: {revenue_range}
- Qualification Score: {approval_request.prospect_score}/100

Compliance Status: {'Compliant' if compliance.is_compliant else 'Issues Detected'}
{f'Violations: {", ".join([v.value for v in compliance.violations])}' if compliance.violations else ''}

Request Details:
- Request ID: {approval_request.request_id}
- Expires: {approval_request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}

To make your decision, visit: {approval_url}

Actions:
- Approve: {approval_url}?action=approve
- Reject: {approval_url}?action=reject
        """


class ApprovalWorkflowService:
    """Service for managing human approval workflows."""
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        self.completed_requests: Dict[str, ApprovalRequest] = {}
        self.approver_emails = settings.APPROVER_EMAILS or []
        self.approval_timeout_hours = 24
    
    async def submit_approval_request(
        self,
        prospect_id: str,
        prospect_score: int,
        prospect_context: Dict[str, Any],
        compliance_validation: ComplianceValidation
    ) -> ApprovalRequest:
        """Submit a new approval request for human review."""
        try:
            # Create approval request
            request_id = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(hours=self.approval_timeout_hours)
            
            approval_request = ApprovalRequest(
                request_id=request_id,
                prospect_id=prospect_id,
                prospect_score=prospect_score,
                prospect_context=prospect_context,
                compliance_validation=compliance_validation,
                requested_by="ai_calling_agent",
                expires_at=expires_at
            )
            
            # Store request
            self.pending_requests[request_id] = approval_request
            
            # Send notifications
            await self._send_approval_notifications(approval_request)
            
            # Schedule timeout check
            asyncio.create_task(self._schedule_timeout_check(request_id, expires_at))
            
            logger.info(f"Submitted approval request {request_id} for prospect {prospect_id}")
            return approval_request
            
        except Exception as e:
            logger.error(f"Error submitting approval request: {e}")
            raise
    
    async def _send_approval_notifications(self, approval_request: ApprovalRequest) -> None:
        """Send approval notifications via configured channels."""
        try:
            # Send Slack notification
            slack_success = await self.notification_service.send_slack_notification(approval_request)
            
            # Send email notifications
            email_success = False
            if self.approver_emails:
                email_success = await self.notification_service.send_email_notification(
                    approval_request, self.approver_emails
                )
            
            if not slack_success and not email_success:
                logger.warning(f"Failed to send any notifications for approval request {approval_request.request_id}")
            
        except Exception as e:
            logger.error(f"Error sending approval notifications: {e}")
    
    async def process_approval_decision(
        self,
        request_id: str,
        decision: ApprovalDecision
    ) -> bool:
        """Process an approval decision from a human approver."""
        try:
            # Find the pending request
            if request_id not in self.pending_requests:
                logger.error(f"Approval request {request_id} not found or already processed")
                return False
            
            approval_request = self.pending_requests[request_id]
            
            # Check if request has expired
            if approval_request.is_expired:
                logger.warning(f"Approval request {request_id} has expired")
                approval_request.status = ApprovalStatus.TIMEOUT
                self._move_to_completed(request_id, approval_request)
                return False
            
            # Update request with decision
            approval_request.status = decision.decision
            approval_request.approved_by = decision.approved_by
            approval_request.approved_at = datetime.now(timezone.utc)
            approval_request.rejection_reason = decision.reason
            
            # Move to completed requests
            self._move_to_completed(request_id, approval_request)
            
            # Send confirmation notification
            await self._send_decision_confirmation(approval_request, decision)
            
            logger.info(f"Processed approval decision for request {request_id}: {decision.decision}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing approval decision: {e}")
            return False
    
    def _move_to_completed(self, request_id: str, approval_request: ApprovalRequest) -> None:
        """Move request from pending to completed."""
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
        self.completed_requests[request_id] = approval_request
    
    async def _send_decision_confirmation(
        self,
        approval_request: ApprovalRequest,
        decision: ApprovalDecision
    ) -> None:
        """Send confirmation of approval decision."""
        try:
            # For MVP, just log the confirmation
            # In production, this could send notifications to relevant stakeholders
            logger.info(f"Approval decision confirmed: {decision.decision} by {decision.approved_by}")
            
        except Exception as e:
            logger.error(f"Error sending decision confirmation: {e}")
    
    async def _schedule_timeout_check(self, request_id: str, expires_at: datetime) -> None:
        """Schedule a timeout check for an approval request."""
        try:
            # Calculate delay until expiration
            now = datetime.now(timezone.utc)
            delay_seconds = (expires_at - now).total_seconds()
            
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
                
                # Check if request is still pending
                if request_id in self.pending_requests:
                    approval_request = self.pending_requests[request_id]
                    approval_request.status = ApprovalStatus.TIMEOUT
                    self._move_to_completed(request_id, approval_request)
                    
                    logger.warning(f"Approval request {request_id} timed out")
                    
                    # Send timeout notification
                    await self._send_timeout_notification(approval_request)
            
        except Exception as e:
            logger.error(f"Error in timeout check for request {request_id}: {e}")
    
    async def _send_timeout_notification(self, approval_request: ApprovalRequest) -> None:
        """Send notification when approval request times out."""
        try:
            # For MVP, just log the timeout
            # In production, this could send alerts to administrators
            logger.warning(f"Approval request {approval_request.request_id} timed out without decision")
            
        except Exception as e:
            logger.error(f"Error sending timeout notification: {e}")
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self.pending_requests.values())
    
    def get_request_by_id(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self.pending_requests.get(request_id) or self.completed_requests.get(request_id)
    
    def get_approval_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Get approval workflow metrics for a period."""
        try:
            all_requests = list(self.pending_requests.values()) + list(self.completed_requests.values())
            period_requests = [
                req for req in all_requests
                if period_start <= req.requested_at <= period_end
            ]
            
            total_requests = len(period_requests)
            approved = len([req for req in period_requests if req.status == ApprovalStatus.APPROVED])
            rejected = len([req for req in period_requests if req.status == ApprovalStatus.REJECTED])
            timeouts = len([req for req in period_requests if req.status == ApprovalStatus.TIMEOUT])
            pending = len([req for req in period_requests if req.status == ApprovalStatus.PENDING])
            
            # Calculate average approval time
            completed_requests = [req for req in period_requests if req.approved_at]
            avg_approval_time = 0.0
            if completed_requests:
                total_time = sum([
                    (req.approved_at - req.requested_at).total_seconds() / 3600
                    for req in completed_requests
                ])
                avg_approval_time = total_time / len(completed_requests)
            
            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_requests": total_requests,
                "approved": approved,
                "rejected": rejected,
                "timeouts": timeouts,
                "pending": pending,
                "approval_rate": (approved / total_requests * 100) if total_requests > 0 else 0,
                "average_approval_time_hours": avg_approval_time
            }
            
        except Exception as e:
            logger.error(f"Error calculating approval metrics: {e}")
            return {}


# Global approval workflow service instance
approval_workflow_service = ApprovalWorkflowService()