# AI Calling Agent Development Standards

## Architecture Principles

### Technology Stack Standards
- **Backend Framework**: FastAPI with Python 3.11+
- **CRM Integration**: Salesforce API with OAuth 2.0 authentication
- **LLM Service**: OpenRouter API (mistralai/mistral-nemo:free for cost efficiency)
- **Speech Services**: ElevenLabs for both STT and TTS (unified provider)
- **Telephony**: Twilio Voice API with webhook integration
- **Database**: Salesforce objects for CRM data + SQLite for local logs
- **Deployment**: Railway or Render free tier for MVP

### Code Quality Standards
- Use Pydantic models for all data validation
- Implement proper error handling with graceful fallbacks
- Follow async/await patterns for all I/O operations
- Keep API responses under 2 seconds for real-time conversation
- Log all interactions for debugging and analytics

### Security Requirements
- Store all API keys in environment variables
- Use OAuth 2.0 for Salesforce authentication
- Validate all webhook requests from Twilio
- Sanitize all user inputs before processing
- Never log sensitive customer information

### Performance Guidelines
- Keep LLM responses under 150 tokens for phone conversations
- Use ElevenLabs Turbo model for fastest TTS generation
- Implement conversation session management for context
- Cache Salesforce authentication tokens
- Process recordings in background tasks

### Business Logic Standards
- Always create or update Salesforce contact records
- Log every call as a Task in Salesforce
- Implement lead scoring based on conversation content
- Create follow-up tasks for qualified leads (score > 60)
- Use EARS format for all requirements documentation

### Error Handling Patterns
- Graceful degradation when APIs are unavailable
- Fallback responses for transcription failures
- Automatic retry logic for Salesforce API calls
- User-friendly error messages during calls
- Comprehensive logging for troubleshooting

### Testing Requirements
- Unit tests for all service classes
- Integration tests for Salesforce API calls
- Mock Twilio webhooks for call flow testing
- Load testing for concurrent call handling
- End-to-end testing with real phone calls