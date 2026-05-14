# AI Calling Agent MVP

A production-ready AI voice assistant that handles inbound and outbound calls with seamless Salesforce CRM integration.

## Features

- **Intelligent Call Handling**: 24/7 AI-powered voice assistant
- **Salesforce Integration**: Automatic contact management and lead qualification
- **Real-time Performance**: Sub-2-second response times
- **Security & Compliance**: SOC 2, GDPR, CCPA ready architecture
- **Monitoring & Analytics**: Comprehensive health checks and metrics

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Redis (optional, for caching)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-calling-agent-mvp
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. Initialize database:
```bash
alembic upgrade head
```

6. Run the application:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Configuration

Copy `.env.example` to `.env` and configure the following:

#### Required API Keys
- **Salesforce**: Client ID, Secret, Username, Password, Security Token
- **Twilio**: Account SID, Auth Token, Phone Number
- **ElevenLabs**: API Key for speech services
- **OpenRouter**: API Key for LLM services

#### Database
- **PostgreSQL**: `DATABASE_URL=postgresql://user:password@localhost:5432/ai_calling_agent`
- **SQLite** (dev): `DATABASE_URL=sqlite:///./ai_calling_agent.db`

### API Endpoints

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics`
- **Twilio Webhook**: `POST /api/v1/webhooks/twilio/incoming-call`
- **Salesforce Webhook**: `POST /api/v1/webhooks/salesforce/lead-created`

### Development

Run with auto-reload:
```bash
uvicorn app.main:app --reload
```

Run tests:
```bash
pytest
```

Format code:
```bash
black app/
isort app/
```

### Deployment

The application is designed for deployment on:
- Railway
- Render
- AWS ECS
- Docker containers

See deployment documentation for platform-specific instructions.

## Architecture

- **Backend**: FastAPI with Python 3.11+
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Telephony**: Twilio Voice API
- **Speech**: ElevenLabs STT/TTS
- **LLM**: OpenRouter with Claude-3.5-Sonnet
- **CRM**: Salesforce REST API
- **Monitoring**: Structured logging with Sentry integration

## Security

- Data encryption at rest and in transit
- OAuth 2.0 for Salesforce authentication
- Webhook signature verification
- Comprehensive audit logging
- Security headers and CORS protection

## License

MIT License - see LICENSE file for details.