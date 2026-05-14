"""
Webhook Retry Service.

This service provides robust retry logic, error handling, and monitoring
for webhook processing failures with exponential backoff and dead letter queues.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)


class RetryStatus(str, Enum):
    """Status of retry attempts."""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class WebhookType(str, Enum):
    """Types of webhooks."""
    SALESFORCE_LEAD = "salesforce_lead"
    SALESFORCE_CONTACT = "salesforce_contact"
    TWILIO_CALL = "twilio_call"
    EXTERNAL_API = "external_api"


@dataclass
class RetryItem:
    """Retry queue item."""
    id: str
    webhook_type: WebhookType
    event_type: str
    payload: Dict[str, Any]
    original_request_id: str
    created_at: datetime
    last_attempt_at: Optional[datetime] = None
    attempt_count: int = 0
    max_attempts: int = 3
    next_retry_at: Optional[datetime] = None
    status: RetryStatus = RetryStatus.PENDING
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0  # 5 minutes
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    dead_letter_after_hours: int = 24


class WebhookRetryService:
    """
    Service for handling webhook retry logic with exponential backoff,
    dead letter queues, and comprehensive monitoring.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audit_service = AuditTrailService()
        
        # Redis for retry queue management
        self.redis_client: Optional[redis.Redis] = None
        
        # Retry configurations by webhook type
        self.retry_configs = {
            WebhookType.SALESFORCE_LEAD: RetryConfig(
                max_attempts=5,
                base_delay_seconds=2.0,
                max_delay_seconds=600.0
            ),
            WebhookType.SALESFORCE_CONTACT: RetryConfig(
                max_attempts=3,
                base_delay_seconds=1.0,
                max_delay_seconds=300.0
            ),
            WebhookType.TWILIO_CALL: RetryConfig(
                max_attempts=2,
                base_delay_seconds=0.5,
                max_delay_seconds=60.0
            ),
            WebhookType.EXTERNAL_API: RetryConfig(
                max_attempts=3,
                base_delay_seconds=1.0,
                max_delay_seconds=300.0
            )
        }
        
        # Registered retry handlers
        self.retry_handlers: Dict[WebhookType, Callable] = {}
        
        # Statistics
        self.retry_stats = {
            "total_items": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "dead_letter_items": 0,
            "average_retry_count": 0.0,
            "queue_sizes": {}
        }
        
        # Background tasks
        self._retry_processor_task: Optional[asyncio.Task] = None
        self._dead_letter_cleanup_task: Optional[asyncio.Task] = None
        self._stats_update_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize the webhook retry service."""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Start background tasks
            self._retry_processor_task = asyncio.create_task(self._retry_processor_loop())
            self._dead_letter_cleanup_task = asyncio.create_task(self._dead_letter_cleanup_loop())
            self._stats_update_task = asyncio.create_task(self._stats_update_loop())
            
            self.logger.info("Webhook retry service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize webhook retry service: {e}")
            raise
    
    async def add_retry_item(self, 
                           webhook_type: WebhookType,
                           event_type: str,
                           payload: Dict[str, Any],
                           original_request_id: str,
                           error: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add an item to the retry queue.
        
        Args:
            webhook_type: Type of webhook
            event_type: Event type (created, updated, etc.)
            payload: Original webhook payload
            original_request_id: Original request identifier
            error: Error that caused the retry
            metadata: Additional metadata
            
        Returns:
            Retry item ID
        """
        try:
            retry_id = str(uuid.uuid4())
            config = self.retry_configs.get(webhook_type, RetryConfig())
            
            retry_item = RetryItem(
                id=retry_id,
                webhook_type=webhook_type,
                event_type=event_type,
                payload=payload,
                original_request_id=original_request_id,
                created_at=datetime.utcnow(),
                max_attempts=config.max_attempts,
                metadata=metadata or {}
            )
            
            # Add initial error if provided
            if error:
                retry_item.error_history.append({
                    "attempt": 0,
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Calculate initial retry time
            retry_item.next_retry_at = self._calculate_next_retry_time(retry_item, config)
            
            # Store in Redis
            await self._store_retry_item(retry_item)
            
            # Update statistics
            self.retry_stats["total_items"] += 1
            
            # Audit log
            await self.audit_service.log_webhook_retry_added(
                retry_id=retry_id,
                webhook_type=webhook_type.value,
                original_request_id=original_request_id,
                error=error
            )
            
            self.logger.info(
                f"Added retry item for {webhook_type.value}",
                retry_id=retry_id,
                original_request_id=original_request_id
            )
            
            return retry_id
            
        except Exception as e:
            self.logger.error(f"Failed to add retry item: {e}")
            raise
    
    async def get_retry_status(self, retry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a retry item.
        
        Args:
            retry_id: Retry item identifier
            
        Returns:
            Retry item status or None if not found
        """
        try:
            retry_item = await self._get_retry_item(retry_id)
            if not retry_item:
                return None
            
            return {
                "retry_id": retry_item.id,
                "webhook_type": retry_item.webhook_type.value,
                "event_type": retry_item.event_type,
                "status": retry_item.status.value,
                "attempt_count": retry_item.attempt_count,
                "max_attempts": retry_item.max_attempts,
                "created_at": retry_item.created_at.isoformat(),
                "last_attempt_at": retry_item.last_attempt_at.isoformat() if retry_item.last_attempt_at else None,
                "next_retry_at": retry_item.next_retry_at.isoformat() if retry_item.next_retry_at else None,
                "error_count": len(retry_item.error_history),
                "latest_error": retry_item.error_history[-1] if retry_item.error_history else None
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get retry status: {e}")
            return None
    
    async def cancel_retry(self, retry_id: str) -> bool:
        """
        Cancel a pending retry.
        
        Args:
            retry_id: Retry item identifier
            
        Returns:
            True if cancelled successfully
        """
        try:
            retry_item = await self._get_retry_item(retry_id)
            if not retry_item:
                return False
            
            if retry_item.status in [RetryStatus.SUCCESS, RetryStatus.FAILED, RetryStatus.DEAD_LETTER]:
                return False  # Already completed
            
            # Update status to failed
            retry_item.status = RetryStatus.FAILED
            await self._store_retry_item(retry_item)
            
            # Remove from active queue
            await self.redis_client.zrem(f"retry_queue:{retry_item.webhook_type.value}", retry_id)
            
            # Audit log
            await self.audit_service.log_webhook_retry_cancelled(
                retry_id=retry_id,
                original_request_id=retry_item.original_request_id
            )
            
            self.logger.info(f"Cancelled retry item {retry_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel retry: {e}")
            return False
    
    def register_retry_handler(self, webhook_type: WebhookType, handler: Callable):
        """
        Register a retry handler for a webhook type.
        
        Args:
            webhook_type: Type of webhook
            handler: Async function to handle retry
        """
        self.retry_handlers[webhook_type] = handler
        self.logger.info(f"Registered retry handler for {webhook_type.value}")
    
    async def get_retry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive retry statistics."""
        try:
            # Update queue sizes
            for webhook_type in WebhookType:
                queue_size = await self.redis_client.zcard(f"retry_queue:{webhook_type.value}")
                self.retry_stats["queue_sizes"][webhook_type.value] = queue_size
            
            # Calculate success rate
            total_processed = self.retry_stats["successful_retries"] + self.retry_stats["failed_retries"]
            success_rate = (
                self.retry_stats["successful_retries"] / max(1, total_processed)
            )
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "stats": self.retry_stats.copy(),
                "success_rate": success_rate,
                "configurations": {
                    webhook_type.value: {
                        "max_attempts": config.max_attempts,
                        "base_delay_seconds": config.base_delay_seconds,
                        "max_delay_seconds": config.max_delay_seconds
                    }
                    for webhook_type, config in self.retry_configs.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get retry statistics: {e}")
            return {"error": str(e)}
    
    # Private methods
    
    async def _store_retry_item(self, retry_item: RetryItem):
        """Store retry item in Redis."""
        # Store item data
        item_key = f"retry_item:{retry_item.id}"
        item_data = {
            "id": retry_item.id,
            "webhook_type": retry_item.webhook_type.value,
            "event_type": retry_item.event_type,
            "payload": json.dumps(retry_item.payload),
            "original_request_id": retry_item.original_request_id,
            "created_at": retry_item.created_at.isoformat(),
            "last_attempt_at": retry_item.last_attempt_at.isoformat() if retry_item.last_attempt_at else "",
            "attempt_count": retry_item.attempt_count,
            "max_attempts": retry_item.max_attempts,
            "next_retry_at": retry_item.next_retry_at.isoformat() if retry_item.next_retry_at else "",
            "status": retry_item.status.value,
            "error_history": json.dumps(retry_item.error_history),
            "metadata": json.dumps(retry_item.metadata)
        }
        
        await self.redis_client.hset(item_key, mapping=item_data)
        await self.redis_client.expire(item_key, 7 * 24 * 3600)  # 7 days
        
        # Add to sorted set for processing queue (sorted by next_retry_at)
        if retry_item.status == RetryStatus.PENDING and retry_item.next_retry_at:
            queue_key = f"retry_queue:{retry_item.webhook_type.value}"
            score = retry_item.next_retry_at.timestamp()
            await self.redis_client.zadd(queue_key, {retry_item.id: score})
    
    async def _get_retry_item(self, retry_id: str) -> Optional[RetryItem]:
        """Get retry item from Redis."""
        try:
            item_key = f"retry_item:{retry_id}"
            item_data = await self.redis_client.hgetall(item_key)
            
            if not item_data:
                return None
            
            return RetryItem(
                id=item_data["id"],
                webhook_type=WebhookType(item_data["webhook_type"]),
                event_type=item_data["event_type"],
                payload=json.loads(item_data["payload"]),
                original_request_id=item_data["original_request_id"],
                created_at=datetime.fromisoformat(item_data["created_at"]),
                last_attempt_at=datetime.fromisoformat(item_data["last_attempt_at"]) if item_data["last_attempt_at"] else None,
                attempt_count=int(item_data["attempt_count"]),
                max_attempts=int(item_data["max_attempts"]),
                next_retry_at=datetime.fromisoformat(item_data["next_retry_at"]) if item_data["next_retry_at"] else None,
                status=RetryStatus(item_data["status"]),
                error_history=json.loads(item_data["error_history"]),
                metadata=json.loads(item_data["metadata"])
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get retry item {retry_id}: {e}")
            return None
    
    def _calculate_next_retry_time(self, retry_item: RetryItem, config: RetryConfig) -> datetime:
        """Calculate the next retry time with exponential backoff."""
        import random
        
        # Calculate exponential backoff delay
        delay = min(
            config.base_delay_seconds * (config.exponential_base ** retry_item.attempt_count),
            config.max_delay_seconds
        )
        
        # Add jitter to prevent thundering herd
        jitter = delay * config.jitter_factor * random.random()
        total_delay = delay + jitter
        
        return datetime.utcnow() + timedelta(seconds=total_delay)
    
    async def _process_retry_item(self, retry_item: RetryItem) -> bool:
        """Process a single retry item."""
        try:
            # Get retry handler
            handler = self.retry_handlers.get(retry_item.webhook_type)
            if not handler:
                self.logger.error(f"No retry handler for {retry_item.webhook_type.value}")
                return False
            
            # Update attempt count and status
            retry_item.attempt_count += 1
            retry_item.last_attempt_at = datetime.utcnow()
            retry_item.status = RetryStatus.RETRYING
            
            # Execute retry handler
            success = await handler(
                retry_item.payload,
                retry_item.event_type,
                retry_item.original_request_id,
                retry_item.attempt_count
            )
            
            if success:
                # Retry succeeded
                retry_item.status = RetryStatus.SUCCESS
                self.retry_stats["successful_retries"] += 1
                
                # Remove from queue
                await self.redis_client.zrem(
                    f"retry_queue:{retry_item.webhook_type.value}",
                    retry_item.id
                )
                
                # Audit log
                await self.audit_service.log_webhook_retry_success(
                    retry_id=retry_item.id,
                    attempt_count=retry_item.attempt_count,
                    original_request_id=retry_item.original_request_id
                )
                
                self.logger.info(
                    f"Retry succeeded for {retry_item.webhook_type.value}",
                    retry_id=retry_item.id,
                    attempt_count=retry_item.attempt_count
                )
                
            else:
                # Retry failed
                if retry_item.attempt_count >= retry_item.max_attempts:
                    # Max attempts reached - move to dead letter
                    retry_item.status = RetryStatus.DEAD_LETTER
                    self.retry_stats["dead_letter_items"] += 1
                    
                    # Move to dead letter queue
                    await self.redis_client.zadd(
                        "dead_letter_queue",
                        {retry_item.id: datetime.utcnow().timestamp()}
                    )
                    
                    # Remove from retry queue
                    await self.redis_client.zrem(
                        f"retry_queue:{retry_item.webhook_type.value}",
                        retry_item.id
                    )
                    
                    self.logger.warning(
                        f"Retry moved to dead letter queue",
                        retry_id=retry_item.id,
                        attempt_count=retry_item.attempt_count
                    )
                    
                else:
                    # Schedule next retry
                    config = self.retry_configs.get(retry_item.webhook_type, RetryConfig())
                    retry_item.next_retry_at = self._calculate_next_retry_time(retry_item, config)
                    retry_item.status = RetryStatus.PENDING
                    
                    # Update queue with new retry time
                    await self.redis_client.zadd(
                        f"retry_queue:{retry_item.webhook_type.value}",
                        {retry_item.id: retry_item.next_retry_at.timestamp()}
                    )
                
                self.retry_stats["failed_retries"] += 1
            
            # Store updated retry item
            await self._store_retry_item(retry_item)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to process retry item {retry_item.id}: {e}")
            
            # Add error to history
            retry_item.error_history.append({
                "attempt": retry_item.attempt_count,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await self._store_retry_item(retry_item)
            return False
    
    # Background tasks
    
    async def _retry_processor_loop(self):
        """Background loop to process retry queue."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                current_time = datetime.utcnow().timestamp()
                
                # Process each webhook type queue
                for webhook_type in WebhookType:
                    queue_key = f"retry_queue:{webhook_type.value}"
                    
                    # Get items ready for retry
                    ready_items = await self.redis_client.zrangebyscore(
                        queue_key, 0, current_time, withscores=False, start=0, num=10
                    )
                    
                    for retry_id in ready_items:
                        retry_item = await self._get_retry_item(retry_id)
                        if retry_item:
                            await self._process_retry_item(retry_item)
                
            except Exception as e:
                self.logger.error(f"Retry processor loop error: {e}")
    
    async def _dead_letter_cleanup_loop(self):
        """Background loop to clean up old dead letter items."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                # Remove dead letter items older than configured time
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                cutoff_timestamp = cutoff_time.timestamp()
                
                # Get old dead letter items
                old_items = await self.redis_client.zrangebyscore(
                    "dead_letter_queue", 0, cutoff_timestamp, withscores=False
                )
                
                if old_items:
                    # Remove from dead letter queue
                    await self.redis_client.zremrangebyscore(
                        "dead_letter_queue", 0, cutoff_timestamp
                    )
                    
                    # Remove item data
                    for item_id in old_items:
                        await self.redis_client.delete(f"retry_item:{item_id}")
                    
                    self.logger.info(f"Cleaned up {len(old_items)} old dead letter items")
                
            except Exception as e:
                self.logger.error(f"Dead letter cleanup error: {e}")
    
    async def _stats_update_loop(self):
        """Background loop to update statistics."""
        while True:
            try:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                # Update queue sizes
                for webhook_type in WebhookType:
                    queue_size = await self.redis_client.zcard(f"retry_queue:{webhook_type.value}")
                    self.retry_stats["queue_sizes"][webhook_type.value] = queue_size
                
                # Calculate average retry count
                if self.retry_stats["total_items"] > 0:
                    total_attempts = (
                        self.retry_stats["successful_retries"] + 
                        self.retry_stats["failed_retries"]
                    )
                    self.retry_stats["average_retry_count"] = (
                        total_attempts / self.retry_stats["total_items"]
                    )
                
            except Exception as e:
                self.logger.error(f"Stats update error: {e}")


# Global instance
webhook_retry_service = WebhookRetryService()