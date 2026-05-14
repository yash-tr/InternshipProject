"""
Salesforce CRM integration service with OAuth 2.0 authentication.
Handles contact management, task logging, and lead qualification workflows.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import aiohttp
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.utils.encryption import encrypt_pii_data, decrypt_pii_data

logger = logging.getLogger(__name__)
settings = get_settings()


class SalesforceAuthToken(BaseModel):
    """Salesforce OAuth token model."""
    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired with 5-minute buffer."""
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))


class SalesforceContact(BaseModel):
    """Salesforce Contact record model."""
    Id: Optional[str] = None
    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    Phone: Optional[str] = None
    Email: Optional[str] = None
    Company: Optional[str] = None
    LeadSource: str = "AI_Calling_Agent"
    Description: Optional[str] = None


class SalesforceTask(BaseModel):
    """Salesforce Task record model."""
    WhoId: str  # Contact/Lead ID
    Subject: str
    Description: str
    Type: str = "Call"
    TaskSubtype: str = "Call"
    CallType: str = "Inbound"
    Priority: str = "Normal"
    Status: str = "Completed"
    ActivityDate: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"))  # YYYY-MM-DD format


class SalesforceLead(BaseModel):
    """Salesforce Lead record model."""
    FirstName: Optional[str] = None
    LastName: str
    Phone: str
    Email: Optional[str] = None
    Company: str
    LeadSource: str = "AI_Agent_Qualification"
    Status: str = "Open - Not Contacted"
    Rating: Optional[str] = None  # Hot, Warm, Cold
    Description: Optional[str] = None


class SalesforceAPIError(Exception):
    """Custom exception for Salesforce API errors."""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class SalesforceService:
    """
    Salesforce CRM integration service with OAuth 2.0 authentication.
    Provides CRUD operations, contact management, and lead qualification.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._auth_token: Optional[SalesforceAuthToken] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.max_retries = 3
        self.base_backoff_delay = 1.0
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def authenticate(self) -> SalesforceAuthToken:
        """
        Authenticate with Salesforce using OAuth 2.0 password flow.
        Returns access token with automatic refresh logic.
        """
        if self._auth_token and not self._auth_token.is_expired:
            return self._auth_token
        
        session = await self._get_session()
        auth_url = f"{self.settings.salesforce_base_url}/services/oauth2/token"
        
        # Combine password and security token
        password_with_token = f"{self.settings.SALESFORCE_PASSWORD}{self.settings.SALESFORCE_SECURITY_TOKEN}"
        
        auth_data = {
            "grant_type": "password",
            "client_id": self.settings.SALESFORCE_CLIENT_ID,
            "client_secret": self.settings.SALESFORCE_CLIENT_SECRET,
            "username": self.settings.SALESFORCE_USERNAME,
            "password": password_with_token
        }
        
        try:
            async with session.post(auth_url, data=auth_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Salesforce authentication failed: {error_text}")
                    raise SalesforceAPIError(
                        f"Authentication failed: {error_text}",
                        status_code=response.status
                    )
                
                auth_response = await response.json()
                
                # Token expires in 2 hours by default
                expires_at = datetime.utcnow() + timedelta(hours=2)
                
                self._auth_token = SalesforceAuthToken(
                    access_token=auth_response["access_token"],
                    instance_url=auth_response["instance_url"],
                    expires_at=expires_at
                )
                
                logger.info("Successfully authenticated with Salesforce")
                return self._auth_token
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error during Salesforce authentication: {e}")
            raise SalesforceAPIError(f"Network error: {e}")
    
    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated API request to Salesforce with retry logic.
        Implements exponential backoff for transient failures.
        """
        token = await self.authenticate()
        session = await self._get_session()
        
        url = f"{token.instance_url}/services/data/v58.0{endpoint}"
        headers = {
            "Authorization": f"{token.token_type} {token.access_token}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params
                ) as response:
                    
                    response_text = await response.text()
                    
                    if response.status == 401:
                        # Token expired, clear and retry
                        self._auth_token = None
                        if attempt < self.max_retries - 1:
                            logger.warning("Token expired, refreshing and retrying")
                            continue
                    
                    if response.status >= 400:
                        logger.error(f"Salesforce API error: {response.status} - {response_text}")
                        raise SalesforceAPIError(
                            f"API request failed: {response_text}",
                            status_code=response.status
                        )
                    
                    if response_text:
                        return await response.json()
                    else:
                        return {}
                        
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Network error after {self.max_retries} attempts: {e}")
                    raise SalesforceAPIError(f"Network error: {e}")
                
                # Exponential backoff with jitter
                delay = self.base_backoff_delay * (2 ** attempt)
                jitter = delay * 0.1  # 10% jitter
                await asyncio.sleep(delay + jitter)
                logger.warning(f"Retrying request after {delay:.2f}s (attempt {attempt + 1})")
        
        raise SalesforceAPIError("Max retries exceeded") 
   
    async def find_contact_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Find existing contact by phone number.
        Returns contact record or None if not found.
        """
        # Sanitize phone number for SOQL query
        sanitized_phone = phone.replace("'", "\\'")
        
        query = f"""
        SELECT Id, FirstName, LastName, Phone, Email, Account.Name, LeadSource, Description
        FROM Contact 
        WHERE Phone = '{sanitized_phone}'
        LIMIT 1
        """
        
        try:
            response = await self._make_api_request(
                method="GET",
                endpoint="/query",
                params={"q": query}
            )
            
            records = response.get("records", [])
            if records:
                contact = records[0]
                logger.info(f"Found existing contact: {contact['Id']}")
                return contact
            
            logger.info(f"No existing contact found for phone: {phone}")
            return None
            
        except SalesforceAPIError as e:
            logger.error(f"Error searching for contact: {e}")
            return None
    
    async def create_contact(self, contact_data: SalesforceContact) -> Dict[str, Any]:
        """
        Create new contact in Salesforce.
        Returns created contact record with ID.
        """
        # Encrypt PII data before storing
        encrypted_data = await encrypt_pii_data(contact_data.dict(exclude_none=True))
        
        try:
            response = await self._make_api_request(
                method="POST",
                endpoint="/sobjects/Contact",
                data=encrypted_data
            )
            
            contact_id = response.get("id")
            logger.info(f"Created new contact: {contact_id}")
            
            # Return full contact record
            return await self.get_contact_by_id(contact_id)
            
        except SalesforceAPIError as e:
            logger.error(f"Error creating contact: {e}")
            raise
    
    async def update_contact(self, contact_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing contact with new information.
        Returns updated contact record.
        """
        # Encrypt PII data before updating
        encrypted_data = await encrypt_pii_data(update_data)
        
        try:
            await self._make_api_request(
                method="PATCH",
                endpoint=f"/sobjects/Contact/{contact_id}",
                data=encrypted_data
            )
            
            logger.info(f"Updated contact: {contact_id}")
            return await self.get_contact_by_id(contact_id)
            
        except SalesforceAPIError as e:
            logger.error(f"Error updating contact {contact_id}: {e}")
            raise
    
    async def get_contact_by_id(self, contact_id: str) -> Dict[str, Any]:
        """Get contact record by ID."""
        try:
            response = await self._make_api_request(
                method="GET",
                endpoint=f"/sobjects/Contact/{contact_id}"
            )
            
            # Decrypt PII data before returning
            return await decrypt_pii_data(response)
            
        except SalesforceAPIError as e:
            logger.error(f"Error fetching contact {contact_id}: {e}")
            raise
    
    async def find_or_create_contact(
        self, 
        phone: str, 
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find existing contact by phone or create new one.
        This is the main entry point for contact management.
        """
        # First, try to find existing contact
        existing_contact = await self.find_contact_by_phone(phone)
        if existing_contact:
            # Update with any new information
            if additional_data:
                update_fields = {}
                for key, value in additional_data.items():
                    if value and key in ["FirstName", "LastName", "Email", "Company"]:
                        # Map Company to Account lookup if needed
                        if key == "Company":
                            update_fields["Description"] = f"Company: {value}"
                        else:
                            update_fields[key] = value
                
                if update_fields:
                    return await self.update_contact(existing_contact["Id"], update_fields)
            
            return existing_contact
        
        # Create new contact
        contact_data = SalesforceContact(
            Phone=phone,
            LeadSource="AI_Calling_Agent",
            Description=f"Created by AI Calling Agent on {datetime.utcnow().isoformat()}"
        )
        
        # Add additional data if provided
        if additional_data:
            for key, value in additional_data.items():
                if value and hasattr(contact_data, key):
                    setattr(contact_data, key, value)
        
        return await self.create_contact(contact_data)
    
    async def log_call_activity(
        self,
        contact_id: str,
        call_summary: str,
        call_outcome: str,
        call_duration: Optional[int] = None,
        lead_score: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Log call interaction as Task record in Salesforce.
        Creates comprehensive activity record for sales team follow-up.
        """
        # Determine priority based on lead score
        priority = "High" if lead_score and lead_score > 80 else "Normal"
        
        # Build comprehensive task description
        description_parts = [f"Call Summary: {call_summary}"]
        if call_duration:
            description_parts.append(f"Duration: {call_duration} seconds")
        if lead_score:
            description_parts.append(f"Lead Score: {lead_score}/100")
        description_parts.append(f"Outcome: {call_outcome}")
        
        task_data = SalesforceTask(
            WhoId=contact_id,
            Subject=f"AI Agent Call - {call_outcome}",
            Description="\n".join(description_parts),
            Priority=priority,
            ActivityDate=datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        try:
            response = await self._make_api_request(
                method="POST",
                endpoint="/sobjects/Task",
                data=task_data.dict()
            )
            
            task_id = response.get("id")
            logger.info(f"Created call activity task: {task_id}")
            return response
            
        except SalesforceAPIError as e:
            logger.error(f"Error logging call activity: {e}")
            raise
    
    async def create_qualified_lead(
        self,
        contact_data: Dict[str, Any],
        qualification_score: int,
        qualification_details: str
    ) -> Dict[str, Any]:
        """
        Create Lead record for qualified prospects.
        Converts high-scoring contacts into actionable leads for sales team.
        """
        # Determine lead rating based on score
        if qualification_score > 80:
            rating = "Hot"
        elif qualification_score >= 60:
            rating = "Warm"
        else:
            rating = "Cold"
        
        # Extract required fields for Lead
        lead_data = SalesforceLead(
            FirstName=contact_data.get("FirstName"),
            LastName=contact_data.get("LastName") or "Unknown",
            Phone=contact_data.get("Phone"),
            Email=contact_data.get("Email"),
            Company=contact_data.get("Company") or "Unknown Company",
            Rating=rating,
            Description=f"AI Qualification Score: {qualification_score}/100\n\n{qualification_details}"
        )
        
        try:
            response = await self._make_api_request(
                method="POST",
                endpoint="/sobjects/Lead",
                data=lead_data.dict(exclude_none=True)
            )
            
            lead_id = response.get("id")
            logger.info(f"Created qualified lead: {lead_id} (Score: {qualification_score})")
            
            # Create immediate follow-up task for high-priority leads
            if qualification_score > 80:
                await self.create_follow_up_task(
                    lead_id=lead_id,
                    priority="High",
                    subject="High-Priority AI Qualified Lead - Contact Today",
                    due_date=datetime.utcnow().date()
                )
            
            return response
            
        except SalesforceAPIError as e:
            logger.error(f"Error creating qualified lead: {e}")
            raise
    
    async def create_follow_up_task(
        self,
        contact_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        priority: str = "Normal",
        subject: str = "Follow up on AI call",
        due_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create follow-up task for sales team.
        Links to either Contact or Lead record for proper assignment.
        """
        if not contact_id and not lead_id:
            raise ValueError("Either contact_id or lead_id must be provided")
        
        # Default due date to next business day
        if not due_date:
            due_date = datetime.utcnow().date() + timedelta(days=1)
        
        task_data = {
            "Subject": subject,
            "Priority": priority,
            "Status": "Not Started",
            "Type": "Call",
            "ActivityDate": due_date.strftime("%Y-%m-%d"),
            "Description": "Follow up on AI agent conversation. Review call notes and contact prospect."
        }
        
        # Link to appropriate record
        if contact_id:
            task_data["WhoId"] = contact_id
        else:
            task_data["WhoId"] = lead_id
        
        try:
            response = await self._make_api_request(
                method="POST",
                endpoint="/sobjects/Task",
                data=task_data
            )
            
            task_id = response.get("id")
            logger.info(f"Created follow-up task: {task_id}")
            return response
            
        except SalesforceAPIError as e:
            logger.error(f"Error creating follow-up task: {e}")
            raise
    
    async def search_contacts(
        self,
        search_term: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search contacts by name, email, or company.
        Returns list of matching contact records.
        """
        # Sanitize search term for SOSL
        sanitized_term = search_term.replace("'", "\\'").replace('"', '\\"')
        
        # SOSL search across multiple fields
        search_query = f"""
        FIND {{"{sanitized_term}"}} 
        IN ALL FIELDS 
        RETURNING Contact(Id, FirstName, LastName, Phone, Email, Account.Name, LeadSource)
        LIMIT {limit}
        """
        
        try:
            response = await self._make_api_request(
                method="GET",
                endpoint="/search",
                params={"q": search_query}
            )
            
            # Extract Contact records from search results
            search_records = response.get("searchRecords", [])
            contacts = [record for record in search_records if record.get("attributes", {}).get("type") == "Contact"]
            
            logger.info(f"Found {len(contacts)} contacts matching '{search_term}'")
            return contacts
            
        except SalesforceAPIError as e:
            logger.error(f"Error searching contacts: {e}")
            return []
    
    async def get_contact_activities(self, contact_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent activities (Tasks, Events) for a contact.
        Useful for understanding contact history before calls.
        """
        query = f"""
        SELECT Id, Subject, Description, Type, Priority, Status, ActivityDate, CreatedDate
        FROM Task 
        WHERE WhoId = '{contact_id}'
        ORDER BY CreatedDate DESC
        LIMIT {limit}
        """
        
        try:
            response = await self._make_api_request(
                method="GET",
                endpoint="/query",
                params={"q": query}
            )
            
            activities = response.get("records", [])
            logger.info(f"Retrieved {len(activities)} activities for contact {contact_id}")
            return activities
            
        except SalesforceAPIError as e:
            logger.error(f"Error fetching contact activities: {e}")
            return []
    
    async def health_check(self) -> bool:
        """
        Check Salesforce API connectivity and authentication.
        Returns True if service is healthy, False otherwise.
        """
        try:
            # Simple query to test connectivity
            await self._make_api_request(
                method="GET",
                endpoint="/query",
                params={"q": "SELECT Id FROM Contact LIMIT 1"}
            )
            return True
        except Exception as e:
            logger.error(f"Salesforce health check failed: {e}")
            return False


# Global service instance
_salesforce_service: Optional[SalesforceService] = None


async def get_salesforce_service() -> SalesforceService:
    """
    Get or create Salesforce service instance.
    Dependency injection for FastAPI endpoints.
    """
    global _salesforce_service
    if not _salesforce_service:
        _salesforce_service = SalesforceService()
    return _salesforce_service