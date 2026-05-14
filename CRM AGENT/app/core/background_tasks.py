"""
Background task processing for async operations.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

import structlog
from pydantic import BaseModel

from app.core.cache import cache_manager
from app.core.performance import performance_monitor

logger = structlog.get_logger()


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class BackgroundTask(BaseModel):
    """Background task model."""
    id: str
    name: str
    function_name: str
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    result: Optional[Any] = None


class TaskQueue:
    """Priority-based task queue for background processing."""
    
    def __init__(self):
        self.queues = {
            TaskPriority.CRITICAL: asyncio.Queue(),
            TaskPriority.HIGH: asyncio.Queue(),
            TaskPriority.NORMAL: asyncio.Queue(),
            TaskPriority.LOW: asyncio.Queue()
        }
        self.tasks: Dict[str, BackgroundTask] = {}
        self.workers: List[asyncio.Task] = []
        self.running = False
        self.worker_count = 5
    
    async def add_task(
        self,
        task_id: str,
        name: str,
        function_name: str,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> BackgroundTask:
        """Add task to queue."""
        task = BackgroundTask(
            id=task_id,
            name=name,
            function_name=function_name,
            args=args or [],
            kwargs=kwargs or {},
            priority=priority,
            created_at=datetime.utcnow(),
            max_retries=max_retries
        )
        
        self.tasks[task_id] = task
        await self.queues[priority].put(task)
        
        logger.info("Task added to queue", task_id=task_id, name=name, priority=priority)
        return task
    
    async def get_next_task(self) -> Optional[BackgroundTask]:
        """Get next task from highest priority queue."""
        # Check queues in priority order
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            queue = self.queues[priority]
            if not queue.empty():
                try:
                    task = await asyncio.wait_for(queue.get(), timeout=0.1)
                    return task
                except asyncio.TimeoutError:
                    continue
        return None
    
    async def start_workers(self):
        """Start background worker tasks."""
        if self.running:
            return
        
        self.running = True
        self.workers = []
        
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started {self.worker_count} background workers")
    
    async def stop_workers(self):
        """Stop background worker tasks."""
        self.running = False
        
        for worker in self.workers:
            worker.cancel()
        
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers = []
        logger.info("Stopped background workers")
    
    async def _worker(self, worker_name: str):
        """Background worker to process tasks."""
        logger.info(f"Background worker {worker_name} started")
        
        while self.running:
            try:
                task = await self.get_next_task()
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                await self._execute_task(task, worker_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error", error=str(e))
                await asyncio.sleep(1)
        
        logger.info(f"Background worker {worker_name} stopped")
    
    async def _execute_task(self, task: BackgroundTask, worker_name: str):
        """Execute a background task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        logger.info("Executing background task", 
                   task_id=task.id, 
                   name=task.name, 
                   worker=worker_name)
        
        try:
            # Get the function to execute
            function = TASK_FUNCTIONS.get(task.function_name)
            if not function:
                raise ValueError(f"Unknown function: {task.function_name}")
            
            # Execute the function
            if asyncio.iscoroutinefunction(function):
                result = await function(*task.args, **task.kwargs)
            else:
                result = function(*task.args, **task.kwargs)
            
            # Mark task as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result
            
            logger.info("Background task completed", 
                       task_id=task.id, 
                       name=task.name,
                       duration=(task.completed_at - task.started_at).total_seconds())
        
        except Exception as e:
            task.error_message = str(e)
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                
                # Add back to queue with delay
                await asyncio.sleep(min(2 ** task.retry_count, 60))  # Exponential backoff
                await self.queues[task.priority].put(task)
                
                logger.warning("Background task failed, retrying", 
                             task_id=task.id, 
                             name=task.name,
                             retry_count=task.retry_count,
                             error=str(e))
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                
                logger.error("Background task failed permanently", 
                           task_id=task.id, 
                           name=task.name,
                           error=str(e))
    
    def get_task_status(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task status."""
        return self.tasks.get(task_id)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {
            "total_tasks": len(self.tasks),
            "queue_sizes": {
                priority.value: queue.qsize() 
                for priority, queue in self.queues.items()
            },
            "task_status_counts": {},
            "worker_count": len(self.workers),
            "running": self.running
        }
        
        # Count tasks by status
        for task in self.tasks.values():
            status = task.status.value
            stats["task_status_counts"][status] = stats["task_status_counts"].get(status, 0) + 1
        
        return stats


# Global task queue instance
task_queue = TaskQueue()


# Background task functions
async def process_salesforce_sync(contact_data: Dict[str, Any]):
    """Background task to sync contact data with Salesforce."""
    from app.services.salesforce import SalesforceService
    
    try:
        sf_service = SalesforceService()
        
        # Update or create contact
        if contact_data.get('Id'):
            result = await sf_service.update_contact(contact_data['Id'], contact_data)
        else:
            result = await sf_service.create_contact(contact_data)
        
        logger.info("Salesforce sync completed", contact_id=result.get('Id'))
        return result
        
    except Exception as e:
        logger.error("Salesforce sync failed", error=str(e))
        raise


async def process_call_recording(call_sid: str, recording_url: str):
    """Background task to process call recordings."""
    from app.services.elevenlabs_service import ElevenLabsService
    
    try:
        speech_service = ElevenLabsService()
        
        # Transcribe the recording
        transcript = await speech_service.transcribe_audio(recording_url)
        
        # Store transcript in cache
        await cache_manager.set(f"transcript:{call_sid}", transcript, ttl=7*24*3600)
        
        logger.info("Call recording processed", call_sid=call_sid)
        return {"call_sid": call_sid, "transcript": transcript}
        
    except Exception as e:
        logger.error("Call recording processing failed", call_sid=call_sid, error=str(e))
        raise


async def process_lead_enrichment(lead_id: str, company_domain: str):
    """Background task to enrich lead data."""
    from app.services.web_scraping import WebScrapingService
    
    try:
        scraping_service = WebScrapingService()
        
        # Enrich company data
        enrichment_data = await scraping_service.enrich_company_data(company_domain)
        
        # Cache the enrichment data
        await cache_manager.set_enrichment_data(company_domain, "", enrichment_data)
        
        logger.info("Lead enrichment completed", lead_id=lead_id)
        return enrichment_data
        
    except Exception as e:
        logger.error("Lead enrichment failed", lead_id=lead_id, error=str(e))
        raise


async def process_cache_warming(cache_keys: List[str]):
    """Background task to warm cache with frequently accessed data."""
    try:
        warmed_count = 0
        
        for key in cache_keys:
            # Check if key needs warming (not in cache or expiring soon)
            cached_value = await cache_manager.get(key)
            if not cached_value:
                # Implement cache warming logic based on key type
                if key.startswith("contact:"):
                    phone = key.split(":")[1]
                    # Warm contact cache
                    from app.services.salesforce import SalesforceService
                    sf_service = SalesforceService()
                    contact_data = await sf_service.find_contact_by_phone(phone)
                    if contact_data:
                        await cache_manager.set_contact_data(phone, contact_data)
                        warmed_count += 1
        
        logger.info("Cache warming completed", warmed_keys=warmed_count)
        return {"warmed_keys": warmed_count}
        
    except Exception as e:
        logger.error("Cache warming failed", error=str(e))
        raise


def cleanup_old_tasks():
    """Synchronous task to cleanup old completed tasks."""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Remove old completed/failed tasks
        old_task_ids = [
            task_id for task_id, task in task_queue.tasks.items()
            if task.completed_at and task.completed_at < cutoff_time
        ]
        
        for task_id in old_task_ids:
            del task_queue.tasks[task_id]
        
        logger.info("Task cleanup completed", removed_tasks=len(old_task_ids))
        return {"removed_tasks": len(old_task_ids)}
        
    except Exception as e:
        logger.error("Task cleanup failed", error=str(e))
        raise


# Registry of available background task functions
TASK_FUNCTIONS = {
    "process_salesforce_sync": process_salesforce_sync,
    "process_call_recording": process_call_recording,
    "process_lead_enrichment": process_lead_enrichment,
    "process_cache_warming": process_cache_warming,
    "cleanup_old_tasks": cleanup_old_tasks
}


# Convenience functions for common background tasks

async def schedule_salesforce_sync(contact_data: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL):
    """Schedule Salesforce sync as background task."""
    task_id = f"sf_sync_{contact_data.get('Phone', 'unknown')}_{int(datetime.utcnow().timestamp())}"
    
    return await task_queue.add_task(
        task_id=task_id,
        name="Salesforce Contact Sync",
        function_name="process_salesforce_sync",
        args=[contact_data],
        priority=priority
    )


async def schedule_call_recording_processing(call_sid: str, recording_url: str):
    """Schedule call recording processing as background task."""
    task_id = f"recording_{call_sid}"
    
    return await task_queue.add_task(
        task_id=task_id,
        name="Call Recording Processing",
        function_name="process_call_recording",
        args=[call_sid, recording_url],
        priority=TaskPriority.HIGH
    )


async def schedule_lead_enrichment(lead_id: str, company_domain: str):
    """Schedule lead enrichment as background task."""
    task_id = f"enrichment_{lead_id}"
    
    return await task_queue.add_task(
        task_id=task_id,
        name="Lead Data Enrichment",
        function_name="process_lead_enrichment",
        args=[lead_id, company_domain],
        priority=TaskPriority.NORMAL
    )


async def schedule_cache_warming(cache_keys: List[str]):
    """Schedule cache warming as background task."""
    task_id = f"cache_warm_{int(datetime.utcnow().timestamp())}"
    
    return await task_queue.add_task(
        task_id=task_id,
        name="Cache Warming",
        function_name="process_cache_warming",
        args=[cache_keys],
        priority=TaskPriority.LOW
    )