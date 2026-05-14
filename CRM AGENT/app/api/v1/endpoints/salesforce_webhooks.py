"""
Salesforce Webhook Integration Endpoints.

This module provides secure webhook endpoints for Salesforce integration
with signature verification, lead data validation, and automatic workflow triggering.
"""

import hashlib
import hmac
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
import structlog

from app.core.config import get_settings
from app.services.workflow_integration import workflow_integration_service
from app.services.salesforce import SalesforceService
from app.services.audit_trail import AuditTrailService
from app.schemas.salesforce import SalesforceLeadWebhook, SalesforceContactWebhook
from app.schemas.base import BaseModel
from app.middleware.security import verify_request_signature

logger = structlog.get_logger()
router = APIRouter()


class SalesforceWebhookProcessor:
    """
    Processor for Salesforce webhook events with security validation,
    data processing, and workflow automation.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.salesforce_service = SalesforceService()
        self.audit_service = AuditTrailService()
        
        # Webhook configuration
        self.webhook_config = {
            "lead_created": {
                "enabled": True,
                "auto_trigger_workflow": True,
                "priority_mapping": {
                    "Hot": "vip",
                    "Warm": "high", 
                    "Cold": "normal"
                }
            },
            "lead_updated": {
                "enabled": True,
                "auto_trigger_workflow": False,
                "trigger_conditions": ["Status", "Rating", "Score__c"]
            },
            "contact_created": {
                "enabled": True,
                "auto_trigger_workflow": False,
                "require_phone": True
            }
        }
        
        # Retry configuration
        self.retry_config = {
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 60.0,
            "exponential_base": 2
        }
        
        # Monitoring
        self.webhook_stats = {
            "total_received": 0,
            "successful_processed": 0,
            "failed_processed": 0,
            "workflows_triggered": 0,
            "signature_failures": 0,
            "validation_failures": 0
        }
    
    async def process_lead_webhook(self, 
                                 webhook_data: Dict[str, Any], 
                                 event_type: str,
                                 request_id: str) -> Dict[str, Any]:
        """
        Process Salesforce lead webhook with validation and workflow triggering.
        
        Args:
            webhook_data: Webhook payload data
            event_type: Type of webhook event (created, updated, etc.)
            request_id: Unique request identifier
            
        Returns:
            Processing result
        """
        try:
            # Validate lead data
            validation_result = await self._validate_lead_data(webhook_data)
            if not validation_result["valid"]:
                self.webhook_stats["validation_failures"] += 1
                return {
                    "success": False,
                    "error": "Lead data validation failed",
                    "details": validation_result["errors"]
                }
            
            # Extract lead information
            lead_data = self._extract_lead_data(webhook_data)
            
            # Determine if workflow should be triggered
            should_trigger = await self._should_trigger_workflow(lead_data, event_type)
            
            result = {
                "success": True,
                "lead_id": lead_data.get("Id"),
                "event_type": event_type,
                "workflow_triggered": False,
                "processing_time": datetime.utcnow().isoformat()
            }
            
            if should_trigger:
                # Trigger automated workflow
                workflow_result = await self._trigger_lead_workflow(lead_data, request_id)
                result.update({
                    "workflow_triggered": True,
                    "workflow_id": workflow_result.get("workflow_id"),
                    "workflow_success": workflow_result.get("success", False)
                })
                
                if workflow_result.get("success"):
                    self.webhook_stats["workflows_triggered"] += 1
            
            # Audit log the webhook processing
            await self.audit_service.log_webhook_processing(
                webhook_type="salesforce_lead",
                event_type=event_type,
                lead_id=lead_data.get("Id"),
                request_id=request_id,
                result=result
            )
            
            self.webhook_stats["successful_processed"] += 1
            return result
            
        except Exception as e:
            self.logger.error(f"Lead webhook processing failed: {e}", request_id=request_id)
            self.webhook_stats["failed_processed"] += 1
            
            # Audit log the failure
            await self.audit_service.log_webhook_error(
                webhook_type="salesforce_lead",
                event_type=event_type,
                request_id=request_id,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }
    
    async def process_contact_webhook(self, 
                                    webhook_data: Dict[str, Any], 
                                    event_type: str,
                                    request_id: str) -> Dict[str, Any]:
        """
        Process Salesforce contact webhook.
        
        Args:
            webhook_data: Webhook payload data
            event_type: Type of webhook event
            request_id: Unique request identifier
            
        Returns:
            Processing result
        """
        try:
            # Validate contact data
            validation_result = await self._validate_contact_data(webhook_data)
            if not validation_result["valid"]:
                self.webhook_stats["validation_failures"] += 1
                return {
                    "success": False,
                    "error": "Contact data validation failed",
                    "details": validation_result["errors"]
                }
            
            # Extract contact information
            contact_data = self._extract_contact_data(webhook_data)
            
            # Process contact-specific logic
            result = {
                "success": True,
                "contact_id": contact_data.get("Id"),
                "event_type": event_type,
                "processing_time": datetime.utcnow().isoformat()
            }
            
            # Check if contact has phone and should trigger workflow
            if (contact_data.get("Phone") and 
                self.webhook_config["contact_created"]["auto_trigger_workflow"]):
                
                # Convert contact to lead-like data for workflow
                lead_like_data = self._convert_contact_to_lead_data(contact_data)
                workflow_result = await self._trigger_lead_workflow(lead_like_data, request_id)
                
                result.update({
                    "workflow_triggered": True,
                    "workflow_id": workflow_result.get("workflow_id"),
                    "workflow_success": workflow_result.get("success", False)
                })
            
            # Audit log
            await self.audit_service.log_webhook_processing(
                webhook_type="salesforce_contact",
                event_type=event_type,
                contact_id=contact_data.get("Id"),
                request_id=request_id,
                result=result
            )
            
            self.webhook_stats["successful_processed"] += 1
            return result
            
        except Exception as e:
            self.logger.error(f"Contact webhook processing failed: {e}", request_id=request_id)
            self.webhook_stats["failed_processed"] += 1
            
            await self.audit_service.log_webhook_error(
                webhook_type="salesforce_contact",
                event_type=event_type,
                request_id=request_id,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }
    
    async def _validate_lead_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Salesforce lead webhook data."""
        errors = []
        
        # Required fields
        required_fields = ["Id", "Name", "Status"]
        for field in required_fields:
            if not webhook_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate phone format if present
        phone = webhook_data.get("Phone")
        if phone and not self._is_valid_phone(phone):
            errors.append(f"Invalid phone format: {phone}")
        
        # Validate email format if present
        email = webhook_data.get("Email")
        if email and not self._is_valid_email(email):
            errors.append(f"Invalid email format: {email}")
        
        # Validate lead status
        valid_statuses = ["Open - Not Contacted", "Working - Contacted", "Closed - Converted", "Closed - Not Converted"]
        if webhook_data.get("Status") not in valid_statuses:
            errors.append(f"Invalid lead status: {webhook_data.get('Status')}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _validate_contact_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Salesforce contact webhook data."""
        errors = []
        
        # Required fields
        required_fields = ["Id", "LastName"]
        for field in required_fields:
            if not webhook_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate phone if required
        if self.webhook_config["contact_created"]["require_phone"]:
            phone = webhook_data.get("Phone")
            if not phone:
                errors.append("Phone number is required for contact webhooks")
            elif not self._is_valid_phone(phone):
                errors.append(f"Invalid phone format: {phone}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _extract_lead_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize lead data from webhook."""
        return {
            "Id": webhook_data.get("Id"),
            "Name": webhook_data.get("Name"),
            "FirstName": webhook_data.get("FirstName"),
            "LastName": webhook_data.get("LastName"),
            "Company": webhook_data.get("Company"),
            "Phone": webhook_data.get("Phone"),
            "Email": webhook_data.get("Email"),
            "Status": webhook_data.get("Status"),
            "Rating": webhook_data.get("Rating"),
            "LeadSource": webhook_data.get("LeadSource"),
            "Industry": webhook_data.get("Industry"),
            "NumberOfEmployees": webhook_data.get("NumberOfEmployees"),
            "AnnualRevenue": webhook_data.get("AnnualRevenue"),
            "Website": webhook_data.get("Website"),
            "Description": webhook_data.get("Description"),
            "CreatedDate": webhook_data.get("CreatedDate"),
            "LastModifiedDate": webhook_data.get("LastModifiedDate")
        }
    
    def _extract_contact_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize contact data from webhook."""
        return {
            "Id": webhook_data.get("Id"),
            "FirstName": webhook_data.get("FirstName"),
            "LastName": webhook_data.get("LastName"),
            "Phone": webhook_data.get("Phone"),
            "Email": webhook_data.get("Email"),
            "AccountId": webhook_data.get("AccountId"),
            "Title": webhook_data.get("Title"),
            "Department": webhook_data.get("Department"),
            "LeadSource": webhook_data.get("LeadSource"),
            "Description": webhook_data.get("Description"),
            "CreatedDate": webhook_data.get("CreatedDate"),
            "LastModifiedDate": webhook_data.get("LastModifiedDate")
        }
    
    async def _should_trigger_workflow(self, lead_data: Dict[str, Any], event_type: str) -> bool:
        """Determine if a workflow should be triggered for the lead."""
        config = self.webhook_config.get(f"lead_{event_type}", {})
        
        if not config.get("enabled", False):
            return False
        
        if event_type == "created":
            return config.get("auto_trigger_workflow", False)
        
        elif event_type == "updated":
            # Check if any trigger conditions were met
            trigger_conditions = config.get("trigger_conditions", [])
            # In a real implementation, we'd compare old vs new values
            # For now, assume any update to a lead with phone triggers workflow
            return bool(lead_data.get("Phone"))
        
        return False
    
    async def _trigger_lead_workflow(self, lead_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """Trigger automated workflow for a lead."""
        try:
            # Determine priority based on lead rating
            priority = self._determine_lead_priority(lead_data)
            
            # Prepare prospect data for workflow
            prospect_data = {
                "prospect_id": lead_data.get("Id"),
                "salesforce_lead_id": lead_data.get("Id"),
                "phone_number": lead_data.get("Phone"),
                "email": lead_data.get("Email"),
                "first_name": lead_data.get("FirstName"),
                "last_name": lead_data.get("LastName"),
                "company": lead_data.get("Company"),
                "industry": lead_data.get("Industry"),
                "website": lead_data.get("Website"),
                "lead_source": lead_data.get("LeadSource"),
                "webhook_request_id": request_id
            }
            
            # Start integrated workflow
            workflow_result = await workflow_integration_service.start_integrated_workflow(
                prospect_data,
                priority=priority
            )
            
            self.logger.info(
                f"Triggered workflow for lead {lead_data.get('Id')}",
                workflow_id=workflow_result.get("workflow_id"),
                priority=priority,
                request_id=request_id
            )
            
            return workflow_result
            
        except Exception as e:
            self.logger.error(f"Failed to trigger workflow for lead: {e}", request_id=request_id)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _determine_lead_priority(self, lead_data: Dict[str, Any]) -> str:
        """Determine workflow priority based on lead data."""
        rating = lead_data.get("Rating", "")
        
        # Use rating mapping from config
        priority_mapping = self.webhook_config["lead_created"]["priority_mapping"]
        priority = priority_mapping.get(rating, "normal")
        
        # Additional logic based on other factors
        annual_revenue = lead_data.get("AnnualRevenue")
        if annual_revenue and annual_revenue > 10000000:  # $10M+
            priority = "vip"
        
        num_employees = lead_data.get("NumberOfEmployees")
        if num_employees and num_employees > 1000:
            priority = "high" if priority == "normal" else priority
        
        return priority
    
    def _convert_contact_to_lead_data(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert contact data to lead-like format for workflow processing."""
        return {
            "Id": contact_data.get("Id"),
            "Name": f"{contact_data.get('FirstName', '')} {contact_data.get('LastName', '')}".strip(),
            "FirstName": contact_data.get("FirstName"),
            "LastName": contact_data.get("LastName"),
            "Phone": contact_data.get("Phone"),
            "Email": contact_data.get("Email"),
            "Company": None,  # Would need to fetch from Account
            "Status": "Open - Not Contacted",
            "LeadSource": contact_data.get("LeadSource", "Contact Webhook"),
            "CreatedDate": contact_data.get("CreatedDate"),
            "LastModifiedDate": contact_data.get("LastModifiedDate")
        }
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format."""
        if not phone:
            return False
        
        # Remove common formatting characters
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Basic validation - should have 10-15 digits
        if len(cleaned) < 10 or len(cleaned) > 15:
            return False
        
        # Should start with + for international or be 10+ digits
        if not (cleaned.startswith('+') or len(cleaned) >= 10):
            return False
        
        return True
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        if not email:
            return False
        
        # Basic email validation
        return '@' in email and '.' in email.split('@')[-1]
    
    async def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook processing statistics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": self.webhook_stats.copy(),
            "config": self.webhook_config,
            "success_rate": (
                self.webhook_stats["successful_processed"] / 
                max(1, self.webhook_stats["total_received"])
            )
        }


# Global processor instance
webhook_processor = SalesforceWebhookProcessor()


async def verify_salesforce_webhook_signature(request: Request) -> bool:
    """
    Verify Salesforce webhook signature for security.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if signature is valid
    """
    try:
        settings = get_settings()
        
        # Get signature from headers
        signature = request.headers.get("X-Salesforce-Signature")
        if not signature:
            logger.warning("Missing Salesforce webhook signature")
            return False
        
        # Get request body
        body = await request.body()
        
        # Calculate expected signature
        expected_signature = hmac.new(
            settings.SALESFORCE_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if not is_valid:
            logger.warning("Invalid Salesforce webhook signature")
            webhook_processor.webhook_stats["signature_failures"] += 1
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


@router.post("/salesforce/lead-created")
async def handle_lead_created_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response
):
    """
    Handle Salesforce lead created webhook.
    
    This endpoint receives notifications when new leads are created in Salesforce
    and automatically triggers the AI calling workflow.
    """
    request_id = f"lead-created-{datetime.utcnow().timestamp()}"
    
    try:
        # Verify webhook signature
        if not await verify_salesforce_webhook_signature(request):
            raise HTTPException(
                status_code=401, 
                detail="Invalid webhook signature"
            )
        
        # Parse webhook data
        webhook_data = await request.json()
        
        # Update stats
        webhook_processor.webhook_stats["total_received"] += 1
        
        # Process webhook in background to avoid timeout
        background_tasks.add_task(
            process_lead_webhook_background,
            webhook_data,
            "created",
            request_id
        )
        
        # Return immediate response to Salesforce
        response.status_code = 200
        return {
            "status": "accepted",
            "message": "Lead webhook received and queued for processing",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lead created webhook error: {e}", request_id=request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.post("/salesforce/lead-updated")
async def handle_lead_updated_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response
):
    """
    Handle Salesforce lead updated webhook.
    
    This endpoint receives notifications when leads are updated in Salesforce
    and conditionally triggers workflows based on the changes.
    """
    request_id = f"lead-updated-{datetime.utcnow().timestamp()}"
    
    try:
        # Verify webhook signature
        if not await verify_salesforce_webhook_signature(request):
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        
        # Parse webhook data
        webhook_data = await request.json()
        
        # Update stats
        webhook_processor.webhook_stats["total_received"] += 1
        
        # Process webhook in background
        background_tasks.add_task(
            process_lead_webhook_background,
            webhook_data,
            "updated",
            request_id
        )
        
        response.status_code = 200
        return {
            "status": "accepted",
            "message": "Lead update webhook received and queued for processing",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lead updated webhook error: {e}", request_id=request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.post("/salesforce/contact-created")
async def handle_contact_created_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response
):
    """
    Handle Salesforce contact created webhook.
    
    This endpoint receives notifications when new contacts are created in Salesforce.
    """
    request_id = f"contact-created-{datetime.utcnow().timestamp()}"
    
    try:
        # Verify webhook signature
        if not await verify_salesforce_webhook_signature(request):
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        
        # Parse webhook data
        webhook_data = await request.json()
        
        # Update stats
        webhook_processor.webhook_stats["total_received"] += 1
        
        # Process webhook in background
        background_tasks.add_task(
            process_contact_webhook_background,
            webhook_data,
            "created",
            request_id
        )
        
        response.status_code = 200
        return {
            "status": "accepted",
            "message": "Contact webhook received and queued for processing",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact created webhook error: {e}", request_id=request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.get("/salesforce/webhook-stats")
async def get_webhook_statistics():
    """
    Get Salesforce webhook processing statistics.
    
    Returns comprehensive statistics about webhook processing performance,
    success rates, and configuration.
    """
    try:
        stats = await webhook_processor.get_webhook_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get webhook stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve webhook statistics: {str(e)}"
        )


@router.post("/salesforce/webhook-config")
async def update_webhook_configuration(config_update: Dict[str, Any]):
    """
    Update webhook configuration.
    
    Allows dynamic configuration of webhook processing behavior,
    priority mappings, and trigger conditions.
    """
    try:
        # Validate configuration update
        valid_keys = ["lead_created", "lead_updated", "contact_created"]
        for key in config_update:
            if key not in valid_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid configuration key: {key}"
                )
        
        # Update configuration
        webhook_processor.webhook_config.update(config_update)
        
        logger.info("Webhook configuration updated", config=config_update)
        
        return {
            "status": "success",
            "message": "Webhook configuration updated",
            "updated_config": webhook_processor.webhook_config,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update webhook config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration update failed: {str(e)}"
        )


# Background task functions

async def process_lead_webhook_background(
    webhook_data: Dict[str, Any],
    event_type: str,
    request_id: str
):
    """Background task to process lead webhook."""
    try:
        result = await webhook_processor.process_lead_webhook(
            webhook_data,
            event_type,
            request_id
        )
        
        logger.info(
            f"Lead webhook processed",
            request_id=request_id,
            success=result.get("success"),
            workflow_triggered=result.get("workflow_triggered", False)
        )
        
    except Exception as e:
        logger.error(f"Background lead webhook processing failed: {e}", request_id=request_id)


async def process_contact_webhook_background(
    webhook_data: Dict[str, Any],
    event_type: str,
    request_id: str
):
    """Background task to process contact webhook."""
    try:
        result = await webhook_processor.process_contact_webhook(
            webhook_data,
            event_type,
            request_id
        )
        
        logger.info(
            f"Contact webhook processed",
            request_id=request_id,
            success=result.get("success"),
            workflow_triggered=result.get("workflow_triggered", False)
        )
        
    except Exception as e:
        logger.error(f"Background contact webhook processing failed: {e}", request_id=request_id)