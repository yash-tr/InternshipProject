# Outbound Call Manager Documentation

## Overview

The Outbound Call Manager is a budget-controlled system for managing autonomous outbound calls in the AI Calling Agent MVP. It implements strict cost controls, call attempt tracking, timezone optimization, and queue management with priority handling.

## Key Features

### 1. Budget Control
- **Daily Call Limits**: Configurable maximum calls per day (default: 100)
- **Concurrent Call Limits**: Maximum simultaneous calls (default: 5)
- **Cost Tracking**: Real-time cost monitoring and budget enforcement
- **Hard Budget Guards**: Automatic workflow termination when limits are reached

### 2. Call Attempt Management
- **3-Attempt Limit**: Maximum 3 attempts per prospect
- **Progressive Retry Intervals**: 1h, 4h, 24h between attempts
- **Failure Handling**: Automatic retry scheduling and escalation logic
- **Attempt History**: Complete tracking of all call attempts

### 3. Timezone Optimization
- **Business Hours Detection**: Automatic timezone detection from location
- **Optimal Call Timing**: Schedules calls during business hours (9 AM - 6 PM local time)
- **Weekend Avoidance**: Skips weekend calling automatically
- **Global Support**: Supports major timezones worldwide

### 4. Priority Queue Management
- **Three Priority Levels**: High (A-tier), Medium (B-tier), Low (C-tier)
- **Score-Based Prioritization**: Automatic priority assignment based on lead scores
- **FIFO Within Priority**: First-in-first-out within each priority level
- **Dynamic Scheduling**: Real-time queue management and task scheduling

### 5. Voicemail Detection
- **Duration-Based Detection**: Identifies voicemails by call duration (10-60 seconds)
- **Transcription Analysis**: Uses speech patterns to detect voicemail greetings
- **Professional Messages**: Generates appropriate voicemail messages
- **Follow-up Creation**: Automatic Salesforce task creation for voicemails

## Architecture

### Core Components

```
OutboundCallManager
├── BudgetController      # Cost control and limits
├── CallQueue            # Priority-based task queue
├── TimezoneOptimizer    # Business hours optimization
├── VoicemailDetector    # Voicemail detection logic
└── CallTask             # Individual call task management
```

### Data Models

#### CallTask
- **task_id**: Unique identifier for the call task
- **prospect_id**: Prospect identifier from research
- **phone_number**: Target phone number
- **priority**: Call priority (HIGH/MEDIUM/LOW)
- **lead_score**: Prospect qualification score
- **research_data**: Complete prospect research information
- **attempts**: List of call attempts with results
- **scheduled_time**: Next scheduled call time
- **status**: Current task status

#### CallAttempt
- **attempt_number**: Sequential attempt number (1-3)
- **call_sid**: Twilio Call SID
- **status**: Call status (QUEUED/INITIATED/COMPLETED/FAILED)
- **result**: Call result (SUCCESS/NO_ANSWER/VOICEMAIL/FAILED)
- **duration_seconds**: Call duration
- **cost_cents**: Call cost in cents
- **voicemail_detected**: Boolean voicemail flag

## Usage

### Scheduling Calls

```python
from app.services.outbound_call_manager import outbound_call_manager, CallPriority

# Schedule a single call
task_id = await outbound_call_manager.schedule_call(
    prospect_id="prospect_123",
    phone_number="+15551234567",
    research_data=research_result,
    priority=CallPriority.HIGH
)
```

### Starting Call Processing

```python
# Start the call processing loop
await outbound_call_manager.start_call_processing()

# Stop the call processing loop
await outbound_call_manager.stop_call_processing()
```

### Monitoring Status

```python
# Get task status
status = await outbound_call_manager.get_task_status(task_id)

# Get system status
system_status = await outbound_call_manager.get_system_status()

# Get budget status
budget_status = await outbound_call_manager.budget_controller.get_budget_status()
```

## API Endpoints

### Schedule Call
```http
POST /api/v1/outbound-calls/schedule
Content-Type: application/json

{
  "prospect_id": "prospect_123",
  "phone_number": "+15551234567",
  "research_data": {...},
  "priority": "high",
  "preferred_time": "2024-01-15T14:00:00Z"
}
```

### Get Task Status
```http
GET /api/v1/outbound-calls/task/{task_id}
```

### Get System Status
```http
GET /api/v1/outbound-calls/status
```

### Start/Stop Processing
```http
POST /api/v1/outbound-calls/start-processing
POST /api/v1/outbound-calls/stop-processing
```

## Configuration

### Budget Limits
```python
class CallBudgetLimits:
    max_daily_calls: int = 100
    max_concurrent_calls: int = 5
    max_attempts_per_prospect: int = 3
    min_retry_interval_hours: int = 1
    max_retry_interval_hours: int = 24
    cost_per_call_cents: int = 5
```

### Timezone Settings
```python
# Optimal calling hours (local time)
OPTIMAL_START_HOUR = 9   # 9 AM
OPTIMAL_END_HOUR = 18    # 6 PM

# Supported timezones
TIMEZONE_MAPPINGS = {
    "united states": "America/New_York",
    "canada": "America/Toronto",
    "united kingdom": "Europe/London",
    # ... more timezones
}
```

## Integration with Twilio

### Webhook Configuration
The system requires Twilio webhooks to be configured for:

1. **Call Status Updates**: `/api/v1/webhooks/twilio/outbound/{task_id}`
2. **Conversation Handling**: `/api/v1/webhooks/twilio/outbound-conversation/{task_id}`

### TwiML Generation
The system automatically generates appropriate TwiML responses for:
- Call initiation and greeting
- Conversation management
- Call completion and cleanup

## Integration with Salesforce

### Automatic CRM Updates
- **Task Creation**: Creates Salesforce tasks for all call attempts
- **Lead Status Updates**: Updates lead status based on call results
- **Activity Logging**: Logs complete call history and outcomes
- **Follow-up Tasks**: Creates follow-up tasks for voicemails and qualified leads

### Data Synchronization
```python
# Example Salesforce task creation
task_data = {
    "WhoId": salesforce_lead_id,
    "Subject": "AI Agent Call - Success",
    "Description": "Call completed successfully...",
    "Type": "Call",
    "Status": "Completed",
    "Priority": "High"
}
```

## Error Handling

### Call Failures
- **Automatic Retry**: Failed calls are automatically retried with progressive delays
- **Max Attempts**: Hard limit of 3 attempts per prospect
- **Error Logging**: Complete error tracking and audit trails
- **Graceful Degradation**: System continues operating despite individual call failures

### Budget Overruns
- **Hard Limits**: Immediate workflow termination when budgets are exceeded
- **Real-time Monitoring**: Continuous budget tracking and alerting
- **Daily Reset**: Automatic budget reset at midnight
- **Cost Tracking**: Detailed cost analysis and reporting

## Testing

### Test Script
Run the comprehensive test suite:
```bash
python scripts/test_outbound_calls.py
```

### Test Coverage
- Budget control functionality
- Timezone optimization
- Voicemail detection
- Queue management
- Call processing simulation
- Error handling scenarios

## Monitoring and Analytics

### Key Metrics
- **Call Volume**: Daily/hourly call statistics
- **Success Rates**: Answer rates, conversion rates, voicemail rates
- **Cost Analysis**: Cost per call, daily spending, budget utilization
- **Queue Performance**: Queue depth, processing times, priority distribution

### Dashboards
The system provides real-time dashboards for:
- Budget status and utilization
- Queue status by priority
- Active call monitoring
- Historical performance metrics

## Security and Compliance

### Data Protection
- **PII Encryption**: All personally identifiable information is encrypted
- **Secure Storage**: Call data stored with field-level encryption
- **Access Control**: Role-based access to call management functions
- **Audit Trails**: Complete audit logging for compliance

### Compliance Features
- **DNC Checking**: Do Not Call list validation (integration ready)
- **Consent Management**: Opt-in/opt-out tracking
- **Regional Compliance**: Timezone-aware calling windows
- **Data Retention**: Configurable data retention policies

## Performance Optimization

### Caching Strategy
- **Research Data**: 7-day TTL for prospect research
- **Call Plans**: 24-hour TTL for call strategies
- **TTS Audio**: 30-day TTL for generated audio

### Scalability
- **Async Processing**: Non-blocking call processing
- **Connection Pooling**: Efficient database and API connections
- **Load Balancing**: Horizontal scaling support
- **Resource Optimization**: Memory and CPU efficient operations

## Troubleshooting

### Common Issues

#### Calls Not Processing
1. Check if call processing is started: `GET /api/v1/outbound-calls/status`
2. Verify budget availability: `GET /api/v1/outbound-calls/budget/status`
3. Check queue status: `GET /api/v1/outbound-calls/queue/status`

#### Budget Exceeded
1. Check daily limits in configuration
2. Review cost tracking and usage
3. Adjust budget limits if needed
4. Monitor for cost optimization opportunities

#### Timezone Issues
1. Verify location data in prospect research
2. Check timezone mapping configuration
3. Validate business hours logic
4. Test with different geographic locations

### Logging
The system provides comprehensive logging at multiple levels:
- **INFO**: Normal operations and status updates
- **WARNING**: Non-critical issues and fallbacks
- **ERROR**: Critical failures and exceptions
- **DEBUG**: Detailed execution traces (development only)

## Future Enhancements

### Planned Features
- **Advanced Voicemail Detection**: ML-based voicemail classification
- **Dynamic Pricing**: Real-time cost optimization
- **A/B Testing**: Call strategy experimentation
- **Advanced Analytics**: Predictive success modeling
- **Integration Expansion**: Additional CRM and telephony providers

### Scalability Improvements
- **Distributed Processing**: Multi-node call processing
- **Advanced Queuing**: Redis-based queue management
- **Real-time Monitoring**: Enhanced observability and alerting
- **Auto-scaling**: Dynamic resource allocation based on demand