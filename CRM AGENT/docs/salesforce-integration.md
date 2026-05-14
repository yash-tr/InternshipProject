# Salesforce Integration Guide

## Overview

The AI Calling Agent integrates with Salesforce CRM to manage contacts, log call activities, and create qualified leads. This integration follows OAuth 2.0 authentication standards and implements comprehensive error handling with retry logic.

## Features

### Authentication
- OAuth 2.0 password flow authentication
- Automatic token refresh with expiration handling
- Secure credential management via environment variables
- Support for both production and sandbox environments

### Contact Management
- Find existing contacts by phone number
- Create new contacts with AI_Calling_Agent lead source
- Update contact information from conversation data
- Encrypted PII data storage for security compliance

### Activity Logging
- Create Task records for every call interaction
- Include conversation summaries and lead scores
- Set appropriate priority based on qualification scores
- Link activities to contact records for sales team visibility

### Lead Qualification
- Convert qualified contacts (score > 60) to Lead records
- Automatic lead rating assignment (Hot/Warm/Cold)
- Create immediate follow-up tasks for high-priority leads
- Comprehensive qualification details in lead descriptions

### Error Handling
- Exponential backoff retry logic for transient failures
- Graceful degradation when Salesforce is unavailable
- Comprehensive logging for troubleshooting
- Token refresh on authentication failures

## Configuration

### Environment Variables

```bash
# Salesforce OAuth Configuration
SALESFORCE_CLIENT_ID=your-connected-app-client-id
SALESFORCE_CLIENT_SECRET=your-connected-app-client-secret
SALESFORCE_USERNAME=your-salesforce-username
SALESFORCE_PASSWORD=your-salesforce-password
SALESFORCE_SECURITY_TOKEN=your-security-token
SALESFORCE_DOMAIN=login  # or "test" for sandbox

# Encryption for PII Protection
ENCRYPTION_KEY=your-32-byte-encryption-key
```

### Salesforce Setup

1. **Create Connected App**:
   - Go to Setup → App Manager → New Connected App
   - Enable OAuth Settings
   - Add OAuth Scopes: `api`, `refresh_token`, `offline_access`
   - Set callback URL (not used for password flow)

2. **Generate Security Token**:
   - Go to Personal Settings → Reset My Security Token
   - Check email for security token

3. **Configure User Permissions**:
   - Ensure user has API access
   - Grant permissions for Contact, Task, and Lead objects
   - Consider creating dedicated integration user

## Usage Examples

### Basic Contact Operations

```python
from app.services.salesforce import get_salesforce_service

async def handle_incoming_call(phone_number: str, conversation_data: dict):
    async with await get_salesforce_service() as sf:
        # Find or create contact
        contact = await sf.find_or_create_contact(
            phone=phone_number,
            additional_data={
                "FirstName": conversation_data.get("first_name"),
                "LastName": conversation_data.get("last_name"),
                "Email": conversation_data.get("email")
            }
        )
        
        # Log call activity
        await sf.log_call_activity(
            contact_id=contact["Id"],
            call_summary=conversation_data["summary"],
            call_outcome=conversation_data["outcome"],
            call_duration=conversation_data["duration"],
            lead_score=conversation_data["qualification_score"]
        )
        
        # Create qualified lead if score is high enough
        if conversation_data["qualification_score"] >= 60:
            await sf.create_qualified_lead(
                contact_data=contact,
                qualification_score=conversation_data["qualification_score"],
                qualification_details=conversation_data["qualification_notes"]
            )
```

### Health Check

```python
async def check_salesforce_health():
    async with await get_salesforce_service() as sf:
        is_healthy = await sf.health_check()
        if not is_healthy:
            logger.error("Salesforce integration is unhealthy")
            # Implement fallback behavior
```

## Data Models

### Contact Record
- **Id**: Salesforce record ID
- **FirstName**: Contact first name
- **LastName**: Contact last name  
- **Phone**: Primary phone number
- **Email**: Email address
- **Company**: Company name (stored in Description)
- **LeadSource**: Always set to "AI_Calling_Agent"

### Task Record
- **WhoId**: Linked Contact/Lead ID
- **Subject**: Call summary title
- **Description**: Detailed call notes and outcomes
- **Type**: Always "Call"
- **TaskSubtype**: Always "Call"
- **CallType**: Always "Inbound"
- **Priority**: Based on lead score (High for >80, Normal otherwise)
- **Status**: Always "Completed"

### Lead Record
- **FirstName/LastName**: From contact data
- **Phone**: Primary phone number
- **Email**: Email address
- **Company**: Company name
- **LeadSource**: Always "AI_Agent_Qualification"
- **Status**: Always "Open - Not Contacted"
- **Rating**: Hot (>80), Warm (60-80), Cold (<60)
- **Description**: Qualification score and details

## Security Considerations

### PII Encryption
- All sensitive data is encrypted before storage
- Uses AES-256 encryption with PBKDF2 key derivation
- Configurable encryption key via environment variables
- Automatic decryption on data retrieval

### API Security
- OAuth 2.0 token-based authentication
- Tokens cached with automatic refresh
- SOQL injection prevention through parameterization
- Input validation and sanitization

### Access Control
- Dedicated integration user recommended
- Minimal required permissions (Contact, Task, Lead objects)
- API usage monitoring and rate limiting
- Audit trail through Salesforce logs

## Monitoring and Troubleshooting

### Logging
- Comprehensive structured logging with correlation IDs
- PII masking in log outputs
- Error details with context for debugging
- Performance metrics for API calls

### Common Issues

1. **Authentication Failures**:
   - Verify client ID and secret
   - Check security token validity
   - Ensure user has API access

2. **API Rate Limits**:
   - Monitor API usage in Salesforce
   - Implement request throttling
   - Use bulk operations for high volume

3. **Network Timeouts**:
   - Check network connectivity
   - Verify Salesforce instance availability
   - Review retry configuration

### Health Monitoring

```python
# Add to application health check endpoint
async def salesforce_health():
    try:
        async with await get_salesforce_service() as sf:
            return await sf.health_check()
    except Exception as e:
        logger.error(f"Salesforce health check failed: {e}")
        return False
```

## Testing

### Unit Tests
- Model validation tests
- Authentication logic tests
- Error handling scenarios
- Retry mechanism verification

### Integration Tests
- Real Salesforce sandbox testing
- End-to-end workflow validation
- Performance and load testing
- Error recovery testing

### Test Configuration

```bash
# Use sandbox for testing
SALESFORCE_DOMAIN=test
SALESFORCE_USERNAME=test@example.com.sandbox
```

## Performance Optimization

### Connection Management
- Connection pooling for high-volume scenarios
- Session reuse across requests
- Async/await for non-blocking operations

### Caching Strategy
- Authentication token caching
- Contact lookup result caching (short-term)
- Metadata caching for field validation

### Bulk Operations
- Batch multiple operations when possible
- Use Salesforce Bulk API for large datasets
- Implement queue-based processing for high volume

## Compliance and Governance

### Data Retention
- Follow Salesforce data retention policies
- Implement data archival strategies
- Regular cleanup of old activity records

### Audit Requirements
- Enable Salesforce audit trail
- Log all integration activities
- Maintain compliance documentation

### Privacy Compliance
- GDPR/CCPA compliance through encryption
- Data minimization principles
- Right to be forgotten implementation