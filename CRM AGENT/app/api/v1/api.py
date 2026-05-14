"""
API v1 router configuration.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import webhooks, speech, llm, agents, research, approval, audit, outbound_calls, call_quality, objections, analytics, monitoring

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"]
)

api_router.include_router(
    speech.router,
    prefix="/speech",
    tags=["speech"]
)

api_router.include_router(
    llm.router,
    prefix="/llm",
    tags=["llm"]
)

api_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["agents"]
)

api_router.include_router(
    research.router,
    prefix="/research",
    tags=["research"]
)

api_router.include_router(
    approval.router,
    prefix="/approval",
    tags=["approval"]
)

api_router.include_router(
    audit.router,
    prefix="/audit",
    tags=["audit"]
)

api_router.include_router(
    outbound_calls.router,
    prefix="/outbound-calls",
    tags=["outbound-calls"]
)

api_router.include_router(
    call_quality.router,
    prefix="/call-quality",
    tags=["call-quality"]
)

api_router.include_router(
    objections.router,
    prefix="/objections",
    tags=["objections"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)

api_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"]
)