"""
Tests for the Outbound Call Manager service.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.outbound_call_manager import (
    OutboundCallManager, CallTask, CallPriority, CallStatus, CallAttemptResult,
    BudgetController, CallQueue, TimezoneOptimizer, VoicemailDetector,
    CallBudgetLimits, CallAttempt
)
from app.schemas.prospect_research import ResearchResultSchema, ContactProfileSchema, CompanyIntelligenceSchema


class TestBudgetController:
    """Test budget control functionality."""
    
    @pytest.fixture
    def budget_controller(self):
        """Create a budget controller for testing."""
        return BudgetController()
    
    @pytest.mark.asyncio
    async def test_daily_budget_check(self, budget_controller):
        """Test daily budget checking."""
        # Should allow calls initially
        assert await budget_controller.check_daily_budget() is True
        
        # Simulate reaching daily limit
        budget_controller.daily_stats["calls_made"] = budget_controller.limits.max_daily_calls
        assert await budget_controller.check_daily_budget() is False
    
    @pytest.mark.asyncio
    async def test_concurrent_limit_check(self, budget_controller):
        """Test concurrent call limit checking."""
        # Should allow calls initially
        assert await budget_controller.check_concurrent_limit() is True
        
        # Simulate reaching concurrent limit
        budget_controller.concurrent_calls = budget_controller.limits.max_concurrent_calls
        assert await budget_controller.check_concurrent_limit() is False
    
    @pytest.mark.asyncio
    async def test_reserve_and_release_call_slot(self, budget_controller):
        """Test call slot reservation and release."""
        # Reserve a slot
        assert await budget_controller.reserve_call_slot() is True
        assert budget_controller.concurrent_calls == 1
        
        # Release the slot
        await budget_controller.release_call_slot(cost_cents=5.0)
        assert budget_controller.concurrent_calls == 0
        assert budget_controller.daily_stats["calls_made"] == 1
        assert budget_controller.daily_stats["total_cost_cents"] == 5.0
    
    @pytest.mark.asyncio
    async def test_budget_status(self, budget_controller):
        """Test budget status reporting."""
        status = await budget_controller.get_budget_status()
        
        assert "daily_calls_made" in status
        assert "daily_calls_remaining" in status
        assert "concurrent_calls" in status
        assert "total_cost_cents" in status


class TestTimezoneOptimizer:
    """Test timezone optimization functionality."""
    
    def test_get_timezone_for_location(self):
        """Test timezone detection from location."""
        assert TimezoneOptimizer.get_timezone_for_location("New York, United States") == "America/New_York"
        assert TimezoneOptimizer.get_timezone_for_location("London, United Kingdom") == "Europe/London"
        assert TimezoneOptimizer.get_timezone_for_location("Unknown Location") == "UTC"
        assert TimezoneOptimizer.get_timezone_for_location(None) == "UTC"
    
    def test_get_optimal_call_time(self):
        """Test optimal call time calculation."""
        # Test with US Eastern timezone
        base_time = datetime(2024, 1, 15, 5, 0, 0)  # 5 AM UTC (too early for EST)
        optimal_time = TimezoneOptimizer.get_optimal_call_time("New York, United States", base_time)
        
        # Should be adjusted to business hours
        assert optimal_time is not None
        assert isinstance(optimal_time, datetime)
    
    def test_is_business_hours(self):
        """Test business hours checking."""
        # Test weekday during business hours
        weekday_business = datetime(2024, 1, 15, 15, 0, 0)  # Monday 3 PM UTC
        assert TimezoneOptimizer.is_business_hours("United States", weekday_business) is True
        
        # Test weekend
        weekend = datetime(2024, 1, 13, 15, 0, 0)  # Saturday
        assert TimezoneOptimizer.is_business_hours("United States", weekend) is False


class TestVoicemailDetector:
    """Test voicemail detection functionality."""
    
    def test_detect_voicemail_by_duration(self):
        """Test voicemail detection based on call duration."""
        # Short duration should indicate voicemail
        assert VoicemailDetector.detect_voicemail(15) is True
        
        # Very short or very long duration should not
        assert VoicemailDetector.detect_voicemail(5) is False
        assert VoicemailDetector.detect_voicemail(120) is False
    
    def test_detect_voicemail_by_transcription(self):
        """Test voicemail detection based on transcription."""
        # Voicemail indicators in transcription
        assert VoicemailDetector.detect_voicemail(30, "Please leave a message after the beep") is True
        assert VoicemailDetector.detect_voicemail(30, "You have reached the voicemail") is True
        
        # Normal conversation
        assert VoicemailDetector.detect_voicemail(30, "Hello, how can I help you?") is False
    
    def test_generate_voicemail_message(self):
        """Test voicemail message generation."""
        message = VoicemailDetector.generate_voicemail_message("John Doe", "Acme Corp")
        
        assert "John Doe" in message
        assert "Acme Corp" in message
        assert "AI assistant" in message
        assert len(message) > 50  # Should be a substantial message


class TestCallQueue:
    """Test call queue management."""
    
    @pytest.fixture
    def call_queue(self):
        """Create a call queue for testing."""
        return CallQueue()
    
    @pytest.fixture
    def sample_task(self):
        """Create a sample call task."""
        return CallTask(
            task_id="test_task_1",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"},
            scheduled_time=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_add_task(self, call_queue, sample_task):
        """Test adding tasks to queue."""
        await call_queue.add_task(sample_task)
        
        status = await call_queue.get_queue_status()
        assert status[CallPriority.MEDIUM.value] == 1
    
    @pytest.mark.asyncio
    async def test_get_next_task(self, call_queue, sample_task):
        """Test getting next task from queue."""
        await call_queue.add_task(sample_task)
        
        next_task = await call_queue.get_next_task()
        assert next_task is not None
        assert next_task.task_id == sample_task.task_id
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, call_queue):
        """Test that high priority tasks are processed first."""
        # Add tasks with different priorities
        high_task = CallTask(
            task_id="high_task",
            prospect_id="prospect_high",
            phone_number="+15551111111",
            salesforce_lead_id="lead_high",
            priority=CallPriority.HIGH,
            lead_score=90,
            research_data={"company": "High Corp"},
            scheduled_time=datetime.utcnow()
        )
        
        low_task = CallTask(
            task_id="low_task",
            prospect_id="prospect_low",
            phone_number="+15552222222",
            salesforce_lead_id="lead_low",
            priority=CallPriority.LOW,
            lead_score=50,
            research_data={"company": "Low Corp"},
            scheduled_time=datetime.utcnow()
        )
        
        # Add low priority first, then high priority
        await call_queue.add_task(low_task)
        await call_queue.add_task(high_task)
        
        # High priority should be returned first
        next_task = await call_queue.get_next_task()
        assert next_task.priority == CallPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_remove_task(self, call_queue, sample_task):
        """Test removing tasks from queue."""
        await call_queue.add_task(sample_task)
        
        removed = await call_queue.remove_task(sample_task.task_id)
        assert removed is True
        
        status = await call_queue.get_queue_status()
        assert status[CallPriority.MEDIUM.value] == 0


class TestOutboundCallManager:
    """Test the main outbound call manager."""
    
    @pytest.fixture
    def call_manager(self):
        """Create an outbound call manager for testing."""
        return OutboundCallManager()
    
    @pytest.fixture
    def sample_research_data(self):
        """Create sample research data."""
        contact = ContactProfileSchema(
            name="John Doe",
            job_title="CEO",
            location="New York, United States"
        )
        company = CompanyIntelligenceSchema(
            company_name="Test Corp",
            industry="Technology",
            employee_count=100
        )
        
        return ResearchResultSchema(
            prospect_id="prospect_1",
            contact_profile=contact,
            company_intelligence=company,
            lead_score=75
        )
    
    @pytest.mark.asyncio
    async def test_schedule_call(self, call_manager, sample_research_data):
        """Test scheduling an outbound call."""
        task_id = await call_manager.schedule_call(
            prospect_id="prospect_1",
            phone_number="+15551234567",
            research_data=sample_research_data,
            priority=CallPriority.HIGH
        )
        
        assert task_id is not None
        assert task_id.startswith("call_prospect_1_")
        
        # Check that task was added to queue
        queue_status = await call_manager.call_queue.get_queue_status()
        assert queue_status[CallPriority.HIGH.value] == 1
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, call_manager, sample_research_data):
        """Test getting task status."""
        task_id = await call_manager.schedule_call(
            prospect_id="prospect_1",
            phone_number="+15551234567",
            research_data=sample_research_data
        )
        
        # Get next task to move it to active calls
        task = await call_manager.call_queue.get_next_task()
        if task:
            call_manager.active_calls[task_id] = task
        
        status = await call_manager.get_task_status(task_id)
        assert status is not None
        assert status["task_id"] == task_id
        assert status["prospect_id"] == "prospect_1"
    
    @pytest.mark.asyncio
    async def test_get_system_status(self, call_manager):
        """Test getting system status."""
        status = await call_manager.get_system_status()
        
        assert "budget" in status
        assert "queue" in status
        assert "active_calls" in status
        assert "completed_calls" in status
        assert "processing" in status
    
    @pytest.mark.asyncio
    @patch('app.services.outbound_call_manager.twilio_service')
    async def test_execute_call(self, mock_twilio, call_manager, sample_research_data):
        """Test call execution."""
        # Mock Twilio service
        mock_twilio.initiate_outbound_call = AsyncMock(return_value={
            "call_sid": "CA1234567890abcdef",
            "status": "initiated"
        })
        
        # Create a task
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data=sample_research_data.dict() if hasattr(sample_research_data, 'dict') else sample_research_data,
            scheduled_time=datetime.utcnow()
        )
        
        # Execute the call
        await call_manager._execute_call(task)
        
        # Verify call was initiated
        mock_twilio.initiate_outbound_call.assert_called_once()
        assert len(task.attempts) == 1
        assert task.attempts[0].status == CallStatus.RINGING
    
    @pytest.mark.asyncio
    async def test_handle_call_status_update(self, call_manager):
        """Test handling call status updates."""
        # Create a task with an attempt
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"}
        )
        
        attempt = CallAttempt(
            attempt_number=1,
            scheduled_time=datetime.utcnow(),
            initiated_time=datetime.utcnow(),
            call_sid="CA1234567890abcdef",
            status=CallStatus.RINGING
        )
        
        task.attempts.append(attempt)
        call_manager.active_calls["test_task"] = task
        
        # Handle status update
        await call_manager.handle_call_status_update(
            task_id="test_task",
            call_sid="CA1234567890abcdef",
            status="completed",
            duration=45,
            transcription="Hello, this is a test call"
        )
        
        # Verify attempt was updated
        assert attempt.status == CallStatus.COMPLETED
        assert attempt.result == CallAttemptResult.SUCCESS
        assert attempt.duration_seconds == 45
    
    @pytest.mark.asyncio
    async def test_voicemail_handling(self, call_manager):
        """Test voicemail detection and handling."""
        # Create a task
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={
                "contact_profile": {"name": "John Doe"},
                "company_intelligence": {"company_name": "Test Corp"}
            }
        )
        
        attempt = CallAttempt(
            attempt_number=1,
            scheduled_time=datetime.utcnow(),
            initiated_time=datetime.utcnow(),
            call_sid="CA1234567890abcdef",
            status=CallStatus.COMPLETED,
            result=CallAttemptResult.VOICEMAIL,
            duration_seconds=20,
            voicemail_detected=True
        )
        
        # Handle voicemail
        await call_manager._handle_voicemail(task, attempt)
        
        # Verify task was completed
        assert task.task_id in call_manager.call_history
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, call_manager):
        """Test call retry logic."""
        # Create a task with a failed attempt
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"}
        )
        
        # Add a failed attempt
        failed_attempt = CallAttempt(
            attempt_number=1,
            scheduled_time=datetime.utcnow(),
            initiated_time=datetime.utcnow(),
            completed_time=datetime.utcnow(),
            call_sid="CA1234567890abcdef",
            status=CallStatus.NO_ANSWER,
            result=CallAttemptResult.NO_ANSWER
        )
        
        task.attempts.append(failed_attempt)
        
        # Schedule retry
        await call_manager._schedule_retry(task)
        
        # Verify retry was scheduled
        assert task.next_retry_time is not None
        assert task.scheduled_time is not None
        assert task.status == CallStatus.QUEUED
    
    @pytest.mark.asyncio
    async def test_budget_enforcement(self, call_manager):
        """Test that budget limits are enforced."""
        # Set very low daily limit
        call_manager.budget_controller.limits.max_daily_calls = 0
        
        # Try to process a call
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"}
        )
        
        await call_manager.call_queue.add_task(task)
        
        # Process should skip due to budget
        await call_manager._process_next_call()
        
        # Task should still be in queue
        queue_status = await call_manager.call_queue.get_queue_status()
        assert queue_status[CallPriority.MEDIUM.value] == 1


class TestCallTaskModel:
    """Test the CallTask data model."""
    
    def test_call_task_creation(self):
        """Test creating a call task."""
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.HIGH,
            lead_score=85,
            research_data={"company": "Test Corp"}
        )
        
        assert task.task_id == "test_task"
        assert task.priority == CallPriority.HIGH
        assert task.attempt_count == 0
        assert task.last_attempt is None
    
    def test_attempt_tracking(self):
        """Test call attempt tracking."""
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"}
        )
        
        # Add an attempt
        attempt = CallAttempt(
            attempt_number=1,
            scheduled_time=datetime.utcnow(),
            initiated_time=datetime.utcnow(),
            call_sid="CA1234567890abcdef"
        )
        
        task.attempts.append(attempt)
        
        assert task.attempt_count == 1
        assert task.last_attempt == attempt
    
    def test_next_retry_time_calculation(self):
        """Test next retry time calculation."""
        task = CallTask(
            task_id="test_task",
            prospect_id="prospect_1",
            phone_number="+15551234567",
            salesforce_lead_id="lead_1",
            priority=CallPriority.MEDIUM,
            lead_score=70,
            research_data={"company": "Test Corp"}
        )
        
        # Add a failed attempt
        base_time = datetime.utcnow()
        attempt = CallAttempt(
            attempt_number=1,
            scheduled_time=base_time,
            initiated_time=base_time,
            completed_time=base_time,
            call_sid="CA1234567890abcdef",
            status=CallStatus.NO_ANSWER,
            result=CallAttemptResult.NO_ANSWER
        )
        
        task.attempts.append(attempt)
        
        # Calculate next retry time
        next_retry = task.next_retry_time
        assert next_retry is not None
        assert next_retry > base_time
        
        # Should be approximately 1 hour later for first retry
        expected_retry = base_time + timedelta(hours=1)
        time_diff = abs((next_retry - expected_retry).total_seconds())
        assert time_diff < 60  # Within 1 minute


@pytest.mark.integration
class TestOutboundCallIntegration:
    """Integration tests for outbound calling system."""
    
    @pytest.mark.asyncio
    @patch('app.services.outbound_call_manager.twilio_service')
    @patch('app.services.outbound_call_manager.get_salesforce_service')
    async def test_full_call_workflow(self, mock_sf_service, mock_twilio_service):
        """Test complete call workflow from scheduling to completion."""
        # Mock services
        mock_twilio_service.initiate_outbound_call = AsyncMock(return_value={
            "call_sid": "CA1234567890abcdef",
            "status": "initiated"
        })
        
        mock_sf = AsyncMock()
        mock_sf_service.return_value = mock_sf
        
        # Create call manager
        call_manager = OutboundCallManager()
        
        # Create research data
        research_data = {
            "prospect_id": "prospect_1",
            "contact_profile": {
                "name": "John Doe",
                "job_title": "CEO",
                "location": "New York, United States"
            },
            "company_intelligence": {
                "company_name": "Test Corp",
                "industry": "Technology"
            },
            "lead_score": 85
        }
        
        # Schedule call
        task_id = await call_manager.schedule_call(
            prospect_id="prospect_1",
            phone_number="+15551234567",
            research_data=research_data,
            priority=CallPriority.HIGH
        )
        
        # Process the call
        await call_manager._process_next_call()
        
        # Verify call was initiated
        mock_twilio_service.initiate_outbound_call.assert_called_once()
        
        # Simulate call completion
        await call_manager.handle_call_status_update(
            task_id=task_id,
            call_sid="CA1234567890abcdef",
            status="completed",
            duration=60
        )
        
        # Verify task was completed
        task_status = await call_manager.get_task_status(task_id)
        assert task_status is not None
        assert len(task_status["attempts"]) == 1
        assert task_status["attempts"][0]["result"] == CallAttemptResult.SUCCESS.value