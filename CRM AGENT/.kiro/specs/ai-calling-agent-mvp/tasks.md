# AI Calling Agent MVP Implementation Plan

## Overview

This implementation plan converts the AI Calling Agent MVP design into a series of incremental coding tasks following the updated PRD's cost-optimized, bounded autonomy approach. The plan emphasizes deterministic state machines with selective LLM usage, strict budget controls, and production-ready compliance. Each task builds upon existing code, ensuring no orphaned work while maintaining cost efficiency and performance SLAs.

## Implementation Tasks

- [x] 1. Project Foundation and Core Infrastructure
  - Set up FastAPI project structure with proper dependency management
  - Configure environment variables and secrets management
  - Implement basic security middleware and CORS settings
  - Create database models and migration system
  - Set up logging, monitoring, and health check endpoints
  - _Requirements: 6.1, 6.2, 6.5_

- [x] 2. Pydantic Data Models and Validation Layer
  - Create comprehensive Pydantic models for all data structures
  - Implement field validation with regex patterns and constraints
  - Add custom validators for business logic validation
  - Create serialization/deserialization utilities
  - Build data encryption/decryption utilities for PII fields
  - Write unit tests for all data models and validation logic
  - _Requirements: 6.1, 6.2, 6.4_

- [x] 3. Salesforce Integration Foundation
  - ✅ Implement OAuth 2.0 authentication with token refresh logic
  - ✅ Create Salesforce service class with CRUD operations
  - ✅ Add contact lookup and creation functionality
  - ✅ Implement task logging for call activities
  - ✅ Build lead creation and qualification workflows
  - ✅ Add error handling with exponential backoff retry logic
  - ✅ Write integration tests with Salesforce sandbox
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 4. Basic Twilio Voice Integration
  - Set up Twilio webhook endpoints for incoming calls
  - Implement basic call handling with TwiML responses
  - Add speech recognition integration with Twilio
  - Create conversation session management
  - Build call recording and audio processing pipeline
  - Add webhook signature verification for security
  - Write unit tests for webhook handlers
  - _Requirements: 1.1, 1.2, 1.6, 5.1, 5.2_

- [x] 5. ElevenLabs Speech Services Integration
  - Implement speech-to-text transcription service
  - Add text-to-speech synthesis with voice optimization
  - Create audio quality monitoring and fallback logic
  - Build speech processing error handling
  - Add API usage monitoring and rate limiting
  - Optimize audio settings for phone call quality
  - Write integration tests for speech services
  - _Requirements: 1.2, 1.3, 5.1, 5.2, 5.3_

- [x] 6. OpenRouter LLM Service Implementation
  - Create LLM service with Claude-3.5-Sonnet integration
  - Implement conversation context management
  - Build dynamic prompt generation with Salesforce context
  - Add response validation and safety filtering
  - Create conversation history management
  - Implement token usage monitoring and optimization
  - Write unit tests for LLM service functionality
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2_

- [x] 7. Basic Call Handler and Conversation Flow
  - Implement core call processing logic
  - Create conversation turn management
  - Add caller information extraction and storage
  - Build basic lead qualification scoring
  - Implement call outcome determination
  - Add Salesforce integration for call logging
  - Write end-to-end tests for basic call flow
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

- [x] 8. Prospect Scoring and Qualification System
  - [x] 8.1 Rules-Based Prospect Scoring Engine
    - Implement deterministic scoring for clear cases (revenue, employee count, role)
    - Create company size and industry scoring matrices
    - Add job title and seniority level scoring algorithms
    - Build geographic and timezone scoring factors
    - Implement budget and timeline indicators scoring
    - Create scoring validation and testing framework
    - Write unit tests for all scoring rules and edge cases
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [x] 8.2 LLM-Assisted Gray Zone Classification
    - Add small LLM classifier for ambiguous cases (45-55 score range)
    - Create structured JSON output with max 64 tokens
    - Implement 24-hour caching for LLM scoring results
    - Build confidence thresholds and fallback logic
    - Add cost tracking and budget controls for LLM usage
    - Create scoring rationale generation and explanation
    - Write integration tests for LLM scoring pipeline
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [x] 8.3 Value Tier Assignment and Routing
    - Implement A/B/C tier assignment based on composite scores
    - Create routing logic for different value tiers
    - Add priority queue management by tier and staleness
    - Build tier-based workflow customization
    - Implement tier analytics and performance tracking
    - Create tier adjustment and optimization mechanisms
    - Write unit tests for tier assignment and routing logic
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 9. Human Approval and Compliance System
  - [x] 9.1 Compliance-First Approval Workflows
    - Create approval workflows for high-value prospects (score > 80)
    - Implement DNC (Do Not Call) list checking and validation
    - Add consent verification and opt-in/opt-out management
    - Build regional calling window enforcement (timezone-aware)
    - Create compliance gate validation before call execution
    - Add TCPA and GDPR compliance checking
    - Write integration tests for compliance validation workflows
    - _Requirements: 4.4, 4.5, 6.6, 7.1, 7.2_
  - [x] 9.2 Human Approval Interface and Notifications
    - Build approval request generation with prospect context
    - Create Slack integration for approval notifications
    - Add email notification system for approvers
    - Implement approval timeout handling (24-hour default)
    - Build approval decision tracking with audit trail
    - Create approval dashboard and management interface
    - Write integration tests for notification and approval systems
    - _Requirements: 4.4, 4.5, 6.6, 7.1, 7.2_
  - [x] 9.3 Audit Trail and Compliance Reporting
    - Implement comprehensive audit logging for all decisions
    - Create compliance reporting and dashboard
    - Add data retention and purging policies
    - Build audit trail search and filtering capabilities
    - Create compliance metrics and KPI tracking
    - Add automated compliance violation detection
    - Write compliance validation and reporting tests
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 10. Autonomous Call Execution System
  - [x] 10.1 Budget-Controlled Call Initiation
    - Implement outbound call initiation with Twilio streaming
    - Create call attempt tracking with 3-attempt limit
    - Add call timing optimization based on prospect timezone
    - Build call queue management with priority handling
    - Implement voicemail detection and template message delivery
    - Create call failure handling and escalation logic
    - Write integration tests for call initiation and management
    - _Requirements: 1.1, 1.2, 1.6, 4.1, 4.2, 5.1, 5.2, 5.3_
  - [x] 10.2 FSM-Based Dialog Management
    - Create finite state machine for conversation flow
    - Implement template-first response system
    - Add selective LLM usage (max 1-2 calls per conversation)
    - Build conversation state persistence and recovery
    - Create dialog branching based on prospect responses
    - Add conversation timeout and abandonment handling
    - Write unit tests for FSM states and transitions
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2_
  - [x] 10.3 Call Quality and Performance Optimization
    - Implement real-time call quality monitoring
    - Add STT/TTS optimization for phone call clarity
    - Create adaptive audio settings based on connection quality
    - Build call analytics and performance tracking
    - Add call recording and quality assurance features
    - Create call outcome determination and classification
    - Write integration tests for call quality and optimization
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 11. Deal Closing and Conversation Management
  - [x] 11.1 Template-Based Objection Handling
    - Leverage existing call handler with enhanced FSM dialog states
    - Create comprehensive objection handling template library
    - Implement objection classification and routing
    - Add template customization based on prospect profile
    - Build objection tracking and success rate analytics
    - Create objection escalation to human agents
    - Write unit tests for objection handling templates and logic
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3_
  - [x] 11.2 Selective LLM for Complex Scenarios
    - Create pre-call LLM planner (1 call per lead, 24h cache)
    - Add selective LLM for complex objections (max 80 tokens)
    - Implement LLM usage budget controls and monitoring
    - Build LLM response validation and safety filtering
    - Create LLM fallback to template responses
    - Add LLM performance tracking and optimization
    - Write integration tests for LLM usage and budget controls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3_
  - [x] 11.3 Deal Progression and Outcome Tracking
    - Build deal progression tracking with stage management
    - Create closing outcome determination and classification
    - Implement Salesforce writeback for deal updates
    - Add deal analytics and conversion tracking
    - Build deal pipeline reporting and forecasting
    - Create deal handoff to human sales representatives
    - Write integration tests for deal tracking and Salesforce sync
    - _Requirements: 2.1, 2.2, 2.3, 4.4, 4.5_

- [x] 12. Security and Data Protection
  - [x] 12.1 Data Encryption and PII Protection
    - Implement comprehensive data encryption for PII fields
    - Add field-level encryption for sensitive customer data
    - Create secure key management and rotation
    - Build data anonymization and pseudonymization
    - Add encryption at rest and in transit
    - Create data classification and handling policies
    - Write security tests for encryption and data protection
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [x] 12.2 Access Control and Authentication
    - Add role-based access control (RBAC) system
    - Implement API authentication and authorization
    - Create session management and token validation
    - Build multi-factor authentication for admin access
    - Add IP whitelisting and rate limiting
    - Create security monitoring and intrusion detection
    - Write security tests for access control and authentication
    - _Requirements: 6.1, 6.2, 6.5, 6.6_
  - [x] 12.3 Security Monitoring and Incident Response
    - Implement comprehensive security logging and monitoring
    - Create automated threat detection and alerting
    - Build incident response workflows and procedures
    - Add security metrics and compliance reporting
    - Create vulnerability scanning and assessment
    - Build security audit and penetration testing framework
    - Write security validation and compliance tests
    - _Requirements: 6.1, 6.2, 6.5, 6.6_

- [x] 13. System Integration and Workflow Orchestration
  - [x] 13.1 Complete Agent Workflow Integration
    - Connect all agents with budget enforcement at each node
    - Implement comprehensive caching (enrichment, plans, TTS)
    - Add workflow monitoring with cost/token tracking
    - Build performance optimization with SLA monitoring
    - Create hard budget guards and workflow termination
    - Add workflow error recovery and retry mechanisms
    - Write end-to-end tests for complete workflow integration
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [x] 13.2 Salesforce Webhook Integration
    - Create Salesforce webhook endpoint for lead triggers
    - Implement webhook signature verification and security
    - Add lead data validation and processing
    - Build automatic workflow triggering for new leads
    - Create webhook retry logic and error handling
    - Add webhook monitoring and alerting
    - Write integration tests for webhook processing
    - _Requirements: 2.1, 2.2, 2.6, 4.1, 6.1, 6.2_
  - [x] 13.3 External API Integration and Management
    - Implement circuit breaker patterns for external APIs
    - Add API rate limiting and quota management
    - Create API health monitoring and failover logic
    - Build API response caching and optimization
    - Add API cost tracking and budget controls
    - Create API integration testing and validation
    - Write integration tests for all external API connections
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 14. Performance, Monitoring, and Analytics
  - [x] 14.1 System Performance and Scalability
    - Implement connection pooling for database and APIs
    - Add caching layers for frequently accessed data
    - Create async processing for background tasks
    - Build load balancing and auto-scaling configuration
    - Add performance monitoring and profiling
    - Optimize database queries and API calls
    - Write load tests for concurrent call handling
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [x] 14.2 Business Analytics and Reporting
    - Implement comprehensive application monitoring
    - Create business metrics tracking and dashboards
    - Add call analytics and conversion reporting
    - Build lead qualification accuracy monitoring
    - Create ROI and cost-effectiveness analytics
    - Add real-time alerting for critical business metrics
    - Write analytics validation and reporting tests
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [x] 14.3 Operational Monitoring and Alerting
    - Build comprehensive system health monitoring
    - Create service availability and uptime tracking
    - Add error rate and performance degradation alerting
    - Build capacity planning and resource utilization monitoring
    - Create operational dashboards and status pages
    - Add automated incident detection and escalation
    - Write monitoring and alerting validation tests
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 7.1, 7.2_

- [ ] 15. Production Deployment and Operations
  - [ ] 15.1 Production Deployment Infrastructure
    - Create containerized deployment with Docker and Kubernetes
    - Set up CI/CD pipeline with automated testing and deployment
    - Configure production environment with secrets management
    - Add database migration and backup strategies
    - Create monitoring and logging infrastructure
    - Build deployment rollback and recovery procedures
    - Write deployment validation and smoke tests
    - _Requirements: 5.1, 5.2, 5.6, 6.1, 6.2, 6.5_
  - [ ] 15.2 Quality Assurance and Testing
    - Create comprehensive integration test suite
    - Add end-to-end testing with real phone calls
    - Build automated testing for all API integrations
    - Create performance benchmarking and validation
    - Add security testing and vulnerability scanning
    - Build compliance validation and audit testing
    - Write user acceptance tests for all workflows
    - _Requirements: All requirements validation_
  - [ ] 15.3 Documentation and Operational Procedures
    - Create comprehensive API documentation
    - Write deployment and configuration guides
    - Add troubleshooting and maintenance documentation
    - Create user guides for human approval workflows
    - Build developer onboarding and contribution guides
    - Add security and compliance documentation
    - Create operational runbooks and procedures
    - _Requirements: All requirements documentation_

## Implementation Priority and Approach

### Phase 1: Core Cost-Controlled Foundation (Tasks 8-9)
**Priority**: Critical - Must complete before autonomous calling
**Focus**: Rules-first approach with minimal LLM usage
- **Task 8**: Prospect Scoring and Qualification System
  - Start with deterministic rules-based scoring (8.1)
  - Add LLM only for gray zone cases with strict token limits (8.2)
  - Implement value tier routing for cost optimization (8.3)
- **Task 9**: Human Approval and Compliance System
  - Build compliance-first workflows (9.1)
  - Add human approval for high-value prospects (9.2)
  - Implement comprehensive audit trails (9.3)

### Phase 2: Autonomous Call Execution (Tasks 10-11)
**Priority**: High - Core autonomous functionality
**Focus**: Template-first with selective LLM usage
- **Task 10**: Autonomous Call Execution System
  - Implement budget-controlled call initiation (10.1)
  - Build FSM-based dialog management (10.2)
  - Add call quality optimization (10.3)
- **Task 11**: Deal Closing and Conversation Management
  - Create template-based objection handling (11.1)
  - Add selective LLM for complex scenarios (11.2)
  - Build deal progression tracking (11.3)

### Phase 3: Security and Integration (Tasks 12-13)
**Priority**: High - Production readiness
**Focus**: Security, compliance, and system integration
- **Task 12**: Security and Data Protection
  - Implement comprehensive data encryption (12.1)
  - Add access control and authentication (12.2)
  - Build security monitoring (12.3)
- **Task 13**: System Integration and Workflow Orchestration
  - Complete agent workflow integration (13.1)
  - Add Salesforce webhook integration (13.2)
  - Implement external API management (13.3)

### Phase 4: Production Operations (Tasks 14-15)
**Priority**: Medium - Operational excellence
**Focus**: Monitoring, analytics, and deployment
- **Task 14**: Performance, Monitoring, and Analytics
  - Build system performance and scalability (14.1)
  - Add business analytics and reporting (14.2)
  - Implement operational monitoring (14.3)
- **Task 15**: Production Deployment and Operations
  - Create production deployment infrastructure (15.1)
  - Build quality assurance and testing (15.2)
  - Add documentation and procedures (15.3)

## Cost Control Implementation Strategy

### Budget Enforcement Patterns
```python
# Example budget control implementation
class BudgetController:
    def __init__(self):
        self.external_calls_budget = {"non_vip": 1, "vip": 2}
        self.llm_calls_budget = {"planner": 1, "runtime_non_vip": 1, "runtime_vip": 3}
        self.token_limits = {"classifier": 64, "planner": 600, "runtime": 80}
    
    async def check_budget(self, prospect_tier: str, operation: str) -> bool:
        # Implement budget checking logic
        pass
```

### Caching Strategy Implementation
```python
# Cache key patterns from PRD
CACHE_KEYS = {
    "enrichment": "enrichment:{domain}|{company}",  # TTL=7d
    "classifier": "classifier:{leadId}",            # TTL=24h
    "plan": "plan:{leadId}:{ctx_hash}",            # TTL=24h
    "tts": "tts:{prompt_hash}"                     # TTL=30d
}
```

### Development Approach
- **Rules-First Philosophy**: Implement deterministic logic before adding LLM components
- **Budget-Driven Development**: Every external API call and LLM usage must be justified and tracked
- **Template-First Conversations**: Build comprehensive template libraries before selective LLM usage
- **Compliance-First Design**: Security and compliance considerations drive architectural decisions
- **Cost-Aware Testing**: Include budget and cost validation in all test suites

### Testing Strategy
- **Budget Compliance Tests**: Validate that all operations stay within defined cost limits
- **Cache Effectiveness Tests**: Ensure caching reduces external API calls by target percentages
- **Template Coverage Tests**: Verify template responses handle majority of conversation scenarios
- **Performance SLA Tests**: Validate p95 latency ≤ 8s and median external calls ≤ 1 (non-VIP)
- **Security and Compliance Tests**: Comprehensive validation of data protection and audit trails

### Deployment Strategy
- **Phase 1 Rollout**: Rules-based scoring and human approval workflows only
- **Phase 2 Rollout**: Enable template-based autonomous calling with LLM disabled
- **Phase 3 Rollout**: Selective LLM for A-tier prospects only with strict monitoring
- **Phase 4 Rollout**: Full autonomous workflow with comprehensive cost tracking

### Quality Gates and Success Metrics
- **Cost Control**: External calls ≤ budget, LLM calls ≤ budget, tokens within limits
- **Performance**: p95 pre-dial latency ≤ 8s, STT first-token ≤ 600ms, TTS first-audio ≤ 800ms
- **Cache Efficiency**: Cache hit rate ≥ 30% by week 2 of deployment
- **Compliance**: 100% audit trail coverage, zero PII leaks, DNC compliance
- **Business Metrics**: Answered call rate, meeting-booked rate, qualification accuracy

### Risk Mitigation
- **Budget Overruns**: Hard limits with workflow termination, real-time cost monitoring
- **API Failures**: Circuit breakers, graceful degradation, comprehensive fallbacks
- **Compliance Violations**: Automated compliance checking, human approval gates
- **Performance Degradation**: Auto-scaling, load balancing, performance monitoring
- **Security Incidents**: Comprehensive logging, incident response procedures, data encryption

### Leveraging Existing Code
- **Prospect Research Agent**: Already implemented, add cost controls and caching
- **Call Handler**: Enhance with FSM states and template system
- **Salesforce Service**: Extend with webhook handling and bulk operations
- **Speech Services**: Add caching and quality optimization
- **LLM Service**: Add budget controls and selective usage patterns
- **Orchestrator**: Enhance with cost tracking and budget enforcement