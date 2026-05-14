"""
Structured logging configuration for the AI Calling Agent.
"""
import logging
import sys
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add log level and timestamp
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Add JSON formatting for production
            structlog.processors.JSONRenderer() if log_level.upper() != "DEBUG" 
            else structlog.dev.ConsoleRenderer(colors=True)
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class SecurityAuditLogger:
    """Specialized logger for security events and compliance auditing."""
    
    def __init__(self):
        self.logger = structlog.get_logger("security_audit")
    
    async def log_data_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        client_ip: str,
        success: bool = True,
        additional_data: Dict[str, Any] = None
    ) -> None:
        """Log data access events for compliance auditing."""
        log_data = {
            "event_type": "data_access",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "client_ip": client_ip,
            "success": success,
        }
        
        if additional_data:
            log_data.update(additional_data)
        
        if success:
            self.logger.info("Data access event", **log_data)
        else:
            self.logger.warning("Failed data access attempt", **log_data)
    
    async def log_authentication_event(
        self,
        user_id: str,
        event_type: str,
        client_ip: str,
        success: bool = True,
        failure_reason: str = None
    ) -> None:
        """Log authentication events."""
        log_data = {
            "event_type": "authentication",
            "user_id": user_id,
            "auth_event": event_type,
            "client_ip": client_ip,
            "success": success,
        }
        
        if failure_reason:
            log_data["failure_reason"] = failure_reason
        
        if success:
            self.logger.info("Authentication event", **log_data)
        else:
            self.logger.warning("Authentication failure", **log_data)
    
    async def log_api_call(
        self,
        service: str,
        endpoint: str,
        response_code: int,
        response_time_ms: float,
        user_id: str = None
    ) -> None:
        """Log external API calls for monitoring."""
        self.logger.info(
            "External API call",
            event_type="api_call",
            service=service,
            endpoint=endpoint,
            response_code=response_code,
            response_time_ms=response_time_ms,
            user_id=user_id
        )