"""
Outbound Call Manager Service

This module implements budget-controlled outbound call initiation with
call attempt tracking, timezone optimization, and queue management.
Follows the cost-controlled approach with strict budget limits.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
import json
import pytz
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..services.twilio_service import twilio_service
from ..services.salesforce import get_salesforce_service
from ..services.audit_trail import audit_service, AuditEventType
from ..schemas.call_session import CallSessionCreate
from ..schemas.prospect_research import ResearchResultSchema
from ..utils.encryption import encrypt_pii_data

logger = logging.getLogger(__name__)
settings = get_settings()


class CallStatus(str, Enum):
    """Call status enumeration."""
    QUEUED = "queued"
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CallPriority(str, Enum):
    """Call priority levels."""
    HIGH = "high"      # A-tier prospects, score > 80
    MEDIUM = "medium"  # B-tier prospects, score 60-80
    LOW = "low"        # C-tier prospects, score 40-60


class CallAttemptResult(str, Enum):
    """Call attempt result types."""
    SUCCESS = "success"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class CallBudgetLimits:
    """Budget limits for call operations."""
    max_daily_calls: int = 100
    max_concurrent_calls: int = 5
    max_attempts_per_prospect: int = 3
    min_retry_interval_hours: int = 1
    max_retry_interval_hours: int = 24
    cost_per_call_cents: int = 5  # Estimated cost per call


@dataclass
class CallAttempt:
    """Individual call attempt record."""
    attempt_number: int
    scheduled_time: datetime
    initiated_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    call_sid: Optional[str] = None
    status: CallStatus = CallStatus.QUEUED
    result: Optional[CallAttemptResult] = None
    duration_seconds: Optional[int] = None
    cost_cents: Optional[float] = None
    error_message: Optional[str] = None
    voicemail_detected: bool = False


@dataclass
class CallTask:
    """Outbound call task definition."""
    task_id: str
    prospect_id: str
    phone_number: str
    salesforce_lead_id: Optional[str]
    priority: CallPriority
    lead_score: int
    research_data: Dict[str, Any]
    timezone: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_time: Optional[datetime] = None
    attempts: List[CallAttempt] = field(default_factory=list)
    status: CallStatus = CallStatus.QUEUED
    budget_tier: str = "non_vip"  # "non_vip" or "vip"
    
    @property
    def attempt_count(self) -> int:
        """Get current attempt count."""
        return len(self.attempts)
    
    @property
    def last_attempt(self) -> Optional[CallAttempt]:
        """Get the last call attempt."""
        return self.attempts[-1] if self.attempts else None
    
    @property
    def next_retry_time(self) -> Optional[datetime]:
        """Calculate next retry time based on attempt history."""
        if not self.attempts:
            return None
        
        last_attempt = self.last_attempt
        if not last_attempt or last_attempt.status in [CallStatus.ANSWERED, CallStatus.COMPLETED]:
            return None
        
        # Progressive retry intervals: 1h, 4h, 24h
        retry_intervals = [
            timedelta(hours=1),
            timedelta(hours=4),
            timedelta(hours=24)
        ]
        
        attempt_index = min(len(self.attempts) - 1, len(retry_intervals) - 1)
        retry_interval = retry_intervals[attempt_index]
        
        base_time = last_attempt.completed_time or last_attempt.initiated_time or datetime.utcnow()
        return base_time + retry_interval


class TimezoneOptimizer:
    """Timezone-based call timing optimization."""
    
    # Optimal calling hours in local time (9 AM - 6 PM)
    OPTIMAL_START_HOUR = 9
    OPTIMAL_END_HOUR = 18
    
    # Timezone mappings for common locations
    TIMEZONE_MAPPINGS = {
        "united states": "America/New_York",
        "canada": "America/Toronto",
        "united kingdom": "Europe/London",
        "australia": "Australia/Sydney",
        "germany": "Europe/Berlin",
        "france": "Europe/Paris",
        "netherlands": "Europe/Amsterdam",
        "sweden": "Europe/Stockholm",
        "japan": "Asia/Tokyo",
        "singapore": "Asia/Singapore"
    }
    
    @classmethod
    def get_timezone_for_location(cls, location: Optional[str]) -> str:
        """Get timezone for a location."""
        if not location:
            return "UTC"
        
        location_lower = location.lower()
        
        for region, tz in cls.TIMEZONE_MAPPINGS.items():
            if region in location_lower:
                return tz
        
        # Default to UTC for unknown locations
        return "UTC"
    
    @classmethod
    def get_optimal_call_time(cls, location: Optional[str], 
                            preferred_time: Optional[datetime] = None) -> datetime:
        """Get optimal call time for a location."""
        tz_name = cls.get_timezone_for_location(location)
        
        try:
            target_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            target_tz = pytz.UTC
        
        # Use preferred time or current time
        base_time = preferred_time or datetime.utcnow()
        
        # Convert to target timezone
        if base_time.tzinfo is None:
            base_time = pytz.UTC.localize(base_time)
        
        local_time = base_time.astimezone(target_tz)
        
        # Adjust to optimal calling hours
        if local_time.hour < cls.OPTIMAL_START_HOUR:
            # Too early, schedule for start of business hours
            optimal_time = local_time.replace(
                hour=cls.OPTIMAL_START_HOUR, 
                minute=0, 
                second=0, 
                microsecond=0
            )
        elif local_time.hour >= cls.OPTIMAL_END_HOUR:
            # Too late, schedule for next business day
            next_day = local_time + timedelta(days=1)
            optimal_time = next_day.replace(
                hour=cls.OPTIMAL_START_HOUR, 
                minute=0, 
                second=0, 
                microsecond=0
            )
        else:
            # Within business hours, use current time
            optimal_time = local_time
        
        # Convert back to UTC
        return optimal_time.astimezone(pytz.UTC).replace(tzinfo=None)
    
    @classmethod
    def is_business_hours(cls, location: Optional[str], 
                         check_time: Optional[datetime] = None) -> bool:
        """Check if it's business hours in the target location."""
        tz_name = cls.get_timezone_for_location(location)
        
        try:
            target_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return True  # Default to allowing calls
        
        check_time = check_time or datetime.utcnow()
        if check_time.tzinfo is None:
            check_time = pytz.UTC.localize(check_time)
        
        local_time = check_time.astimezone(target_tz)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if local_time.weekday() >= 5:  # Weekend
            return False
        
        # Check if it's within business hours
        return cls.OPTIMAL_START_HOUR <= local_time.hour < cls.OPTIMAL_END_HOUR


class CallQueue:
    """Priority-based call queue management."""
    
    def __init__(self):
        self._queues: Dict[CallPriority, List[CallTask]] = {
            CallPriority.HIGH: [],
            CallPriority.MEDIUM: [],
            CallPriority.LOW: []
        }
        self._lock = asyncio.Lock()
    
    async def add_task(self, task: CallTask):
        """Add a call task to the appropriate priority queue."""
        async with self._lock:
            self._queues[task.priority].append(task)
            
            # Sort by scheduled time within priority
            self._queues[task.priority].sort(
                key=lambda t: t.scheduled_time or datetime.utcnow()
            )
            
            logger.info(
                f"Added call task {task.task_id} to {task.priority.value} priority queue"
            )
    
    async def get_next_task(self) -> Optional[CallTask]:
        """Get the next task to execute based on priority and timing."""
        async with self._lock:
            current_time = datetime.utcnow()
            
            # Check high priority first, then medium, then low
            for priority in [CallPriority.HIGH, CallPriority.MEDIUM, CallPriority.LOW]:
                queue = self._queues[priority]
                
                for i, task in enumerate(queue):
                    # Check if task is ready to execute
                    if task.scheduled_time and task.scheduled_time > current_time:
                        continue
                    
                    # Check if it's business hours for the prospect
                    if not TimezoneOptimizer.is_business_hours(
                        task.research_data.get("location")
                    ):
                        continue
                    
                    # Remove and return the task
                    return queue.pop(i)
            
            return None
    
    async def remove_task(self, task_id: str) -> bool:
        """Remove a task from all queues."""
        async with self._lock:
            for queue in self._queues.values():
                for i, task in enumerate(queue):
                    if task.task_id == task_id:
                        queue.pop(i)
                        logger.info(f"Removed call task {task_id} from queue")
                        return True
            return False
    
    async def get_queue_status(self) -> Dict[str, int]:
        """Get current queue status."""
        async with self._lock:
            return {
                priority.value: len(queue) 
                for priority, queue in self._queues.items()
            }


class BudgetController:
    """Budget control for outbound calling operations."""
    
    def __init__(self):
        self.limits = CallBudgetLimits()
        self.daily_stats = {
            "calls_made": 0,
            "total_cost_cents": 0,
            "last_reset": datetime.utcnow().date()
        }
        self.concurrent_calls = 0
        self._lock = asyncio.Lock()
    
    async def check_daily_budget(self) -> bool:
        """Check if daily call budget is available."""
        async with self._lock:
            # Reset daily stats if it's a new day
            today = datetime.utcnow().date()
            if self.daily_stats["last_reset"] != today:
                self.daily_stats = {
                    "calls_made": 0,
                    "total_cost_cents": 0,
                    "last_reset": today
                }
            
            return self.daily_stats["calls_made"] < self.limits.max_daily_calls
    
    async def check_concurrent_limit(self) -> bool:
        """Check if concurrent call limit allows new calls."""
        async with self._lock:
            return self.concurrent_calls < self.limits.max_concurrent_calls
    
    async def reserve_call_slot(self) -> bool:
        """Reserve a call slot if budget allows."""
        async with self._lock:
            if not await self.check_daily_budget():
                logger.warning("Daily call budget exceeded")
                return False
            
            if not await self.check_concurrent_limit():
                logger.warning("Concurrent call limit reached")
                return False
            
            self.concurrent_calls += 1
            return True
    
    async def release_call_slot(self, cost_cents: float = None):
        """Release a call slot and update costs."""
        async with self._lock:
            self.concurrent_calls = max(0, self.concurrent_calls - 1)
            self.daily_stats["calls_made"] += 1
            
            if cost_cents:
                self.daily_stats["total_cost_cents"] += cost_cents
    
    async def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        async with self._lock:
            return {
                "daily_calls_made": self.daily_stats["calls_made"],
                "daily_calls_remaining": self.limits.max_daily_calls - self.daily_stats["calls_made"],
                "concurrent_calls": self.concurrent_calls,
                "concurrent_slots_available": self.limits.max_concurrent_calls - self.concurrent_calls,
                "total_cost_cents": self.daily_stats["total_cost_cents"],
                "last_reset": self.daily_stats["last_reset"].isoformat()
            }


class VoicemailDetector:
    """Voicemail detection and handling."""
    
    # Common voicemail indicators
    VOICEMAIL_INDICATORS = [
        "voicemail", "voice mail", "leave a message", "after the beep",
        "not available", "please leave", "mailbox", "recording"
    ]
    
    # Duration thresholds for voicemail detection
    MIN_VOICEMAIL_DURATION = 10  # seconds
    MAX_VOICEMAIL_DURATION = 60  # seconds
    
    @classmethod
    def detect_voicemail(cls, call_duration: int, 
                        transcription: Optional[str] = None) -> bool:
        """Detect if call went to voicemail."""
        # Duration-based detection
        if cls.MIN_VOICEMAIL_DURATION <= call_duration <= cls.MAX_VOICEMAIL_DURATION:
            duration_indicates_voicemail = True
        else:
            duration_indicates_voicemail = False
        
        # Transcription-based detection
        transcription_indicates_voicemail = False
        if transcription:
            transcription_lower = transcription.lower()
            transcription_indicates_voicemail = any(
                indicator in transcription_lower 
                for indicator in cls.VOICEMAIL_INDICATORS
            )
        
        return duration_indicates_voicemail or transcription_indicates_voicemail
    
    @classmethod
    def generate_voicemail_message(cls, prospect_name: Optional[str] = None,
                                 company_name: Optional[str] = None) -> str:
        """Generate a professional voicemail message."""
        greeting = f"Hi {prospect_name}" if prospect_name else "Hello"
        
        message = (
            f"{greeting}, this is an AI assistant calling on behalf of our sales team. "
            f"I was reaching out to discuss how we might be able to help "
        )
        
        if company_name:
            message += f"{company_name} "
        
        message += (
            "with your business needs. I'll follow up with an email with more information, "
            "or feel free to call us back at your convenience. Thank you!"
        )
        
        return message


class OutboundCallManager:
    """
    Main service for managing outbound call operations with budget controls.
    
    Handles call initiation, attempt tracking, timezone optimization,
    queue management, and voicemail detection.
    """
    
    def __init__(self):
        self.budget_controller = BudgetController()
        self.call_queue = CallQueue()
        self.active_calls: Dict[str, CallTask] = {}
        self.call_history: Dict[str, CallTask] = {}
        self._processing = False
        self._lock = asyncio.Lock()
        
        logger.info("Outbound Call Manager initialized")
    
    async def schedule_call(self, 
                          prospect_id: str,
                          phone_number: str,
                          research_data: ResearchResultSchema,
                          priority: CallPriority = CallPriority.MEDIUM,
                          preferred_time: Optional[datetime] = None) -> str:
        """
        Schedule an outbound call for a prospect.
        
        Args:
            prospect_id: Unique prospect identifier
            phone_number: Phone number to call
            research_data: Research data for the prospect
            priority: Call priority level
            preferred_time: Preferred call time (optional)
            
        Returns:
            Task ID for the scheduled call
        """
        try:
            # Generate task ID
            task_id = f"call_{prospect_id}_{int(datetime.utcnow().timestamp())}"
            
            # Determine budget tier based on lead score
            lead_score = getattr(research_data, 'lead_score', 0)
            budget_tier = "vip" if lead_score >= 80 else "non_vip"
            
            # Optimize call timing based on prospect location
            location = None
            if hasattr(research_data, 'contact_profile') and research_data.contact_profile:
                location = getattr(research_data.contact_profile, 'location', None)
            
            optimal_time = TimezoneOptimizer.get_optimal_call_time(
                location, preferred_time
            )
            
            # Create call task
            task = CallTask(
                task_id=task_id,
                prospect_id=prospect_id,
                phone_number=phone_number,
                salesforce_lead_id=getattr(research_data, 'salesforce_lead_id', None),
                priority=priority,
                lead_score=lead_score,
                research_data=research_data.dict() if hasattr(research_data, 'dict') else research_data,
                timezone=TimezoneOptimizer.get_timezone_for_location(location),
                scheduled_time=optimal_time,
                budget_tier=budget_tier
            )
            
            # Add to queue
            await self.call_queue.add_task(task)
            
            # Log audit event
            await audit_service.log_event(
                event_type=AuditEventType.CALL_SCHEDULED,
                entity_type="prospect",
                entity_id=prospect_id,
                details={
                    "task_id": task_id,
                    "phone_number": phone_number,
                    "priority": priority.value,
                    "scheduled_time": optimal_time.isoformat(),
                    "budget_tier": budget_tier
                }
            )
            
            logger.info(
                f"Scheduled call {task_id} for prospect {prospect_id} "
                f"at {optimal_time} (priority: {priority.value})"
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to schedule call for prospect {prospect_id}: {e}")
            raise
    
    async def start_call_processing(self):
        """Start the call processing loop."""
        if self._processing:
            logger.warning("Call processing already running")
            return
        
        self._processing = True
        logger.info("Starting call processing loop")
        
        try:
            while self._processing:
                await self._process_next_call()
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            logger.error(f"Call processing loop error: {e}")
        finally:
            self._processing = False
            logger.info("Call processing loop stopped")
    
    async def stop_call_processing(self):
        """Stop the call processing loop."""
        self._processing = False
        logger.info("Stopping call processing loop")
    
    async def _process_next_call(self):
        """Process the next call in the queue."""
        try:
            # Check budget availability
            if not await self.budget_controller.check_daily_budget():
                logger.warning("Daily call budget exhausted, skipping call processing")
                return
            
            if not await self.budget_controller.check_concurrent_limit():
                # Wait a bit for concurrent calls to complete
                return
            
            # Get next task from queue
            task = await self.call_queue.get_next_task()
            if not task:
                return  # No tasks ready
            
            # Check attempt limits
            if task.attempt_count >= self.budget_controller.limits.max_attempts_per_prospect:
                logger.info(f"Max attempts reached for task {task.task_id}")
                await self._complete_task(task, CallAttemptResult.FAILED, "Max attempts reached")
                return
            
            # Execute the call
            await self._execute_call(task)
            
        except Exception as e:
            logger.error(f"Error processing call: {e}")
    
    async def _execute_call(self, task: CallTask):
        """Execute an outbound call."""
        attempt_number = task.attempt_count + 1
        
        try:
            # Reserve budget slot
            if not await self.budget_controller.reserve_call_slot():
                logger.warning(f"Cannot reserve budget slot for task {task.task_id}")
                # Reschedule for later
                task.scheduled_time = datetime.utcnow() + timedelta(minutes=30)
                await self.call_queue.add_task(task)
                return
            
            # Create call attempt record
            attempt = CallAttempt(
                attempt_number=attempt_number,
                scheduled_time=task.scheduled_time or datetime.utcnow(),
                initiated_time=datetime.utcnow(),
                status=CallStatus.INITIATED
            )
            
            task.attempts.append(attempt)
            task.status = CallStatus.INITIATED
            
            # Add to active calls
            async with self._lock:
                self.active_calls[task.task_id] = task
            
            logger.info(
                f"Executing call attempt {attempt_number} for task {task.task_id} "
                f"to {task.phone_number}"
            )
            
            # Initiate Twilio call
            webhook_url = f"{settings.BASE_URL}/api/v1/webhooks/twilio/outbound/{task.task_id}"
            
            call_result = await twilio_service.initiate_outbound_call(
                to_number=task.phone_number,
                webhook_url=webhook_url,
                caller_id=settings.TWILIO_PHONE_NUMBER
            )
            
            # Update attempt with call details
            attempt.call_sid = call_result.get('call_sid')
            attempt.status = CallStatus.RINGING
            
            # Log audit event
            await audit_service.log_event(
                event_type=AuditEventType.CALL_INITIATED,
                entity_type="prospect",
                entity_id=task.prospect_id,
                details={
                    "task_id": task.task_id,
                    "call_sid": attempt.call_sid,
                    "attempt_number": attempt_number,
                    "phone_number": task.phone_number
                }
            )
            
            logger.info(
                f"Initiated call {attempt.call_sid} for task {task.task_id} "
                f"(attempt {attempt_number})"
            )
            
        except Exception as e:
            logger.error(f"Failed to execute call for task {task.task_id}: {e}")
            
            # Update attempt with error
            if task.attempts:
                task.attempts[-1].status = CallStatus.FAILED
                task.attempts[-1].error_message = str(e)
                task.attempts[-1].completed_time = datetime.utcnow()
            
            # Release budget slot
            await self.budget_controller.release_call_slot()
            
            # Remove from active calls
            async with self._lock:
                self.active_calls.pop(task.task_id, None)
            
            # Schedule retry if attempts remaining
            await self._handle_call_failure(task, str(e))
    
    async def handle_call_status_update(self, 
                                      task_id: str,
                                      call_sid: str,
                                      status: str,
                                      duration: Optional[int] = None,
                                      transcription: Optional[str] = None):
        """Handle call status updates from Twilio webhooks."""
        try:
            async with self._lock:
                task = self.active_calls.get(task_id)
            
            if not task:
                logger.warning(f"Received status update for unknown task {task_id}")
                return
            
            # Find the matching attempt
            attempt = None
            for att in task.attempts:
                if att.call_sid == call_sid:
                    attempt = att
                    break
            
            if not attempt:
                logger.warning(f"No matching attempt found for call {call_sid}")
                return
            
            # Update attempt status
            attempt.completed_time = datetime.utcnow()
            attempt.duration_seconds = duration
            
            # Determine call result
            if status == "completed":
                if duration and duration > 30:  # Meaningful conversation
                    attempt.result = CallAttemptResult.SUCCESS
                    attempt.status = CallStatus.COMPLETED
                elif VoicemailDetector.detect_voicemail(duration or 0, transcription):
                    attempt.result = CallAttemptResult.VOICEMAIL
                    attempt.status = CallStatus.VOICEMAIL
                    attempt.voicemail_detected = True
                else:
                    attempt.result = CallAttemptResult.NO_ANSWER
                    attempt.status = CallStatus.NO_ANSWER
            elif status == "busy":
                attempt.result = CallAttemptResult.BUSY
                attempt.status = CallStatus.BUSY
            elif status == "no-answer":
                attempt.result = CallAttemptResult.NO_ANSWER
                attempt.status = CallStatus.NO_ANSWER
            else:
                attempt.result = CallAttemptResult.FAILED
                attempt.status = CallStatus.FAILED
            
            # Calculate cost
            attempt.cost_cents = self.budget_controller.limits.cost_per_call_cents
            
            # Release budget slot
            await self.budget_controller.release_call_slot(attempt.cost_cents)
            
            # Remove from active calls
            async with self._lock:
                self.active_calls.pop(task_id, None)
            
            # Handle the result
            await self._handle_call_result(task, attempt)
            
            logger.info(
                f"Call {call_sid} completed with result {attempt.result.value} "
                f"(duration: {duration}s)"
            )
            
        except Exception as e:
            logger.error(f"Error handling call status update: {e}")
    
    async def _handle_call_result(self, task: CallTask, attempt: CallAttempt):
        """Handle the result of a call attempt."""
        try:
            if attempt.result == CallAttemptResult.SUCCESS:
                # Call was successful, mark task as completed
                await self._complete_task(task, attempt.result, "Call answered and conversation completed")
                
            elif attempt.result == CallAttemptResult.VOICEMAIL:
                # Left voicemail, schedule follow-up
                await self._handle_voicemail(task, attempt)
                
            elif attempt.result in [CallAttemptResult.NO_ANSWER, CallAttemptResult.BUSY]:
                # Schedule retry if attempts remaining
                if task.attempt_count < self.budget_controller.limits.max_attempts_per_prospect:
                    await self._schedule_retry(task)
                else:
                    await self._complete_task(task, attempt.result, "Max attempts reached")
                    
            else:  # FAILED or BLOCKED
                await self._handle_call_failure(task, attempt.error_message or "Call failed")
            
        except Exception as e:
            logger.error(f"Error handling call result for task {task.task_id}: {e}")
    
    async def _handle_voicemail(self, task: CallTask, attempt: CallAttempt):
        """Handle voicemail detection and follow-up."""
        try:
            # Generate voicemail message
            research_data = task.research_data
            prospect_name = research_data.get("contact_profile", {}).get("name")
            company_name = research_data.get("company_intelligence", {}).get("company_name")
            
            voicemail_message = VoicemailDetector.generate_voicemail_message(
                prospect_name, company_name
            )
            
            # Log voicemail event
            await audit_service.log_event(
                event_type=AuditEventType.CALL_COMPLETED,
                entity_type="prospect",
                entity_id=task.prospect_id,
                details={
                    "task_id": task.task_id,
                    "call_sid": attempt.call_sid,
                    "result": "voicemail",
                    "voicemail_message": voicemail_message,
                    "duration_seconds": attempt.duration_seconds
                }
            )
            
            # Create follow-up task in Salesforce
            if task.salesforce_lead_id:
                try:
                    salesforce_service = await get_salesforce_service()
                    await salesforce_service.create_task({
                        "WhoId": task.salesforce_lead_id,
                        "Subject": "AI Agent - Voicemail Left",
                        "Description": f"Voicemail message: {voicemail_message}",
                        "Type": "Call",
                        "Status": "Completed",
                        "Priority": "Normal"
                    })
                except Exception as sf_error:
                    logger.warning(f"Failed to create Salesforce follow-up task: {sf_error}")
            
            # Complete the task
            await self._complete_task(task, CallAttemptResult.VOICEMAIL, "Voicemail left")
            
        except Exception as e:
            logger.error(f"Error handling voicemail for task {task.task_id}: {e}")
    
    async def _schedule_retry(self, task: CallTask):
        """Schedule a retry for a failed call attempt."""
        try:
            retry_time = task.next_retry_time
            if not retry_time:
                logger.warning(f"Cannot calculate retry time for task {task.task_id}")
                return
            
            # Optimize retry time for business hours
            location = task.research_data.get("contact_profile", {}).get("location")
            optimal_retry_time = TimezoneOptimizer.get_optimal_call_time(location, retry_time)
            
            task.scheduled_time = optimal_retry_time
            task.status = CallStatus.QUEUED
            
            # Add back to queue
            await self.call_queue.add_task(task)
            
            logger.info(
                f"Scheduled retry for task {task.task_id} at {optimal_retry_time} "
                f"(attempt {task.attempt_count + 1})"
            )
            
        except Exception as e:
            logger.error(f"Error scheduling retry for task {task.task_id}: {e}")
    
    async def _handle_call_failure(self, task: CallTask, error_message: str):
        """Handle call failure and determine next steps."""
        try:
            if task.attempt_count < self.budget_controller.limits.max_attempts_per_prospect:
                # Schedule retry
                await self._schedule_retry(task)
            else:
                # Max attempts reached, complete with failure
                await self._complete_task(task, CallAttemptResult.FAILED, error_message)
            
        except Exception as e:
            logger.error(f"Error handling call failure for task {task.task_id}: {e}")
    
    async def _complete_task(self, task: CallTask, result: CallAttemptResult, reason: str):
        """Complete a call task and perform cleanup."""
        try:
            task.status = CallStatus.COMPLETED
            
            # Move to history
            async with self._lock:
                self.call_history[task.task_id] = task
                self.active_calls.pop(task.task_id, None)
            
            # Log completion event
            await audit_service.log_event(
                event_type=AuditEventType.CALL_COMPLETED,
                entity_type="prospect",
                entity_id=task.prospect_id,
                details={
                    "task_id": task.task_id,
                    "result": result.value,
                    "reason": reason,
                    "total_attempts": task.attempt_count,
                    "total_cost_cents": sum(att.cost_cents or 0 for att in task.attempts)
                }
            )
            
            # Update Salesforce with final result
            if task.salesforce_lead_id:
                try:
                    await self._update_salesforce_call_result(task, result, reason)
                except Exception as sf_error:
                    logger.warning(f"Failed to update Salesforce: {sf_error}")
            
            logger.info(
                f"Completed call task {task.task_id} with result {result.value}: {reason}"
            )
            
        except Exception as e:
            logger.error(f"Error completing task {task.task_id}: {e}")
    
    async def _update_salesforce_call_result(self, 
                                           task: CallTask, 
                                           result: CallAttemptResult, 
                                           reason: str):
        """Update Salesforce with call results."""
        try:
            salesforce_service = await get_salesforce_service()
            
            # Create task record
            task_data = {
                "WhoId": task.salesforce_lead_id,
                "Subject": f"AI Agent Call - {result.value.title()}",
                "Description": f"Call Result: {reason}\nAttempts: {task.attempt_count}\nTotal Cost: ${sum(att.cost_cents or 0 for att in task.attempts) / 100:.2f}",
                "Type": "Call",
                "TaskSubtype": "Call",
                "CallType": "Outbound",
                "Status": "Completed",
                "Priority": "High" if task.priority == CallPriority.HIGH else "Normal"
            }
            
            await salesforce_service.create_task(task_data)
            
            # Update lead status based on result
            if result == CallAttemptResult.SUCCESS:
                # Update lead to contacted status
                await salesforce_service.update_lead(task.salesforce_lead_id, {
                    "Status": "Contacted",
                    "AI_Last_Call_Date__c": datetime.utcnow().isoformat(),
                    "AI_Call_Outcome__c": "Success"
                })
            
        except Exception as e:
            logger.error(f"Error updating Salesforce for task {task.task_id}: {e}")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a specific call task."""
        try:
            # Check active calls first
            async with self._lock:
                task = self.active_calls.get(task_id) or self.call_history.get(task_id)
            
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "prospect_id": task.prospect_id,
                "phone_number": task.phone_number,
                "status": task.status.value,
                "priority": task.priority.value,
                "attempt_count": task.attempt_count,
                "max_attempts": self.budget_controller.limits.max_attempts_per_prospect,
                "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
                "next_retry_time": task.next_retry_time.isoformat() if task.next_retry_time else None,
                "attempts": [
                    {
                        "attempt_number": att.attempt_number,
                        "call_sid": att.call_sid,
                        "status": att.status.value,
                        "result": att.result.value if att.result else None,
                        "duration_seconds": att.duration_seconds,
                        "cost_cents": att.cost_cents,
                        "voicemail_detected": att.voicemail_detected,
                        "initiated_time": att.initiated_time.isoformat() if att.initiated_time else None,
                        "completed_time": att.completed_time.isoformat() if att.completed_time else None
                    }
                    for att in task.attempts
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return None
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status and metrics."""
        try:
            budget_status = await self.budget_controller.get_budget_status()
            queue_status = await self.call_queue.get_queue_status()
            
            async with self._lock:
                active_count = len(self.active_calls)
                history_count = len(self.call_history)
            
            return {
                "budget": budget_status,
                "queue": queue_status,
                "active_calls": active_count,
                "completed_calls": history_count,
                "processing": self._processing
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {}


# Global instance
outbound_call_manager = OutboundCallManager()