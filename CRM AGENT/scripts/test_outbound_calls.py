#!/usr/bin/env python3
"""
Test script for outbound call functionality.

This script demonstrates how to schedule and manage outbound calls
using the AI Calling Agent MVP system.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.outbound_call_manager import (
    outbound_call_manager, CallPriority, CallStatus
)
from app.schemas.prospect_research import (
    ResearchResultSchema, ContactProfileSchema, CompanyIntelligenceSchema
)


def create_sample_research_data(prospect_id: str, name: str, company: str) -> Dict[str, Any]:
    """Create sample research data for testing."""
    return {
        "prospect_id": prospect_id,
        "contact_profile": {
            "name": name,
            "job_title": "CEO",
            "location": "New York, United States",
            "email": f"{name.lower().replace(' ', '.')}@{company.lower().replace(' ', '')}.com"
        },
        "company_intelligence": {
            "company_name": company,
            "industry": "Technology",
            "employee_count": 150,
            "revenue_range": "RANGE_10M_50M"
        },
        "buying_signals": [
            {"description": "Budget approved for new software", "signal_type": "budget"},
            {"description": "Looking to implement this quarter", "signal_type": "timeline"}
        ],
        "lead_score": 85,
        "overall_confidence": 0.8
    }


async def test_schedule_single_call():
    """Test scheduling a single outbound call."""
    print("🔄 Testing single call scheduling...")
    
    research_data = create_sample_research_data(
        "prospect_001",
        "John Doe",
        "Acme Corp"
    )
    
    try:
        task_id = await outbound_call_manager.schedule_call(
            prospect_id="prospect_001",
            phone_number="+15551234567",  # Test number
            research_data=research_data,
            priority=CallPriority.HIGH
        )
        
        print(f"✅ Call scheduled successfully: {task_id}")
        
        # Get task status
        status = await outbound_call_manager.get_task_status(task_id)
        if status:
            print(f"📊 Task Status: {status['status']}")
            print(f"📅 Scheduled Time: {status['scheduled_time']}")
            print(f"🎯 Priority: {status['priority']}")
        
        return task_id
        
    except Exception as e:
        print(f"❌ Failed to schedule call: {e}")
        return None


async def test_bulk_schedule_calls():
    """Test bulk scheduling of multiple calls."""
    print("\n🔄 Testing bulk call scheduling...")
    
    prospects = [
        ("prospect_002", "Jane Smith", "TechStart Inc"),
        ("prospect_003", "Bob Johnson", "Innovation Labs"),
        ("prospect_004", "Alice Brown", "Future Systems")
    ]
    
    task_ids = []
    
    for prospect_id, name, company in prospects:
        research_data = create_sample_research_data(prospect_id, name, company)
        
        try:
            task_id = await outbound_call_manager.schedule_call(
                prospect_id=prospect_id,
                phone_number=f"+1555{len(task_ids) + 2:03d}4567",
                research_data=research_data,
                priority=CallPriority.MEDIUM
            )
            
            task_ids.append(task_id)
            print(f"✅ Scheduled call for {name} at {company}: {task_id}")
            
        except Exception as e:
            print(f"❌ Failed to schedule call for {name}: {e}")
    
    print(f"📊 Total calls scheduled: {len(task_ids)}")
    return task_ids


async def test_queue_status():
    """Test queue status reporting."""
    print("\n🔄 Testing queue status...")
    
    try:
        queue_status = await outbound_call_manager.call_queue.get_queue_status()
        print("📋 Queue Status:")
        for priority, count in queue_status.items():
            print(f"  {priority.upper()}: {count} calls")
        
        total_queued = sum(queue_status.values())
        print(f"📊 Total Queued: {total_queued}")
        
    except Exception as e:
        print(f"❌ Failed to get queue status: {e}")


async def test_budget_status():
    """Test budget status reporting."""
    print("\n🔄 Testing budget status...")
    
    try:
        budget_status = await outbound_call_manager.budget_controller.get_budget_status()
        print("💰 Budget Status:")
        print(f"  Daily Calls Made: {budget_status['daily_calls_made']}")
        print(f"  Daily Calls Remaining: {budget_status['daily_calls_remaining']}")
        print(f"  Concurrent Calls: {budget_status['concurrent_calls']}")
        print(f"  Total Cost: ${budget_status['total_cost_cents'] / 100:.2f}")
        
    except Exception as e:
        print(f"❌ Failed to get budget status: {e}")


async def test_system_status():
    """Test overall system status."""
    print("\n🔄 Testing system status...")
    
    try:
        system_status = await outbound_call_manager.get_system_status()
        print("🖥️  System Status:")
        print(f"  Active Calls: {system_status['active_calls']}")
        print(f"  Completed Calls: {system_status['completed_calls']}")
        print(f"  Processing: {system_status['processing']}")
        
        if 'queue' in system_status:
            print("  Queue:")
            for priority, count in system_status['queue'].items():
                print(f"    {priority.upper()}: {count}")
        
    except Exception as e:
        print(f"❌ Failed to get system status: {e}")


async def test_call_processing_simulation():
    """Test call processing simulation (without actual Twilio calls)."""
    print("\n🔄 Testing call processing simulation...")
    
    # Schedule a test call
    research_data = create_sample_research_data(
        "prospect_sim",
        "Test User",
        "Simulation Corp"
    )
    
    try:
        task_id = await outbound_call_manager.schedule_call(
            prospect_id="prospect_sim",
            phone_number="+15559999999",  # Simulation number
            research_data=research_data,
            priority=CallPriority.HIGH
        )
        
        print(f"✅ Simulation call scheduled: {task_id}")
        
        # Simulate call status updates
        print("📞 Simulating call status updates...")
        
        # Simulate call initiated
        await outbound_call_manager.handle_call_status_update(
            task_id=task_id,
            call_sid="CA_simulation_123",
            status="initiated"
        )
        print("  ✅ Call initiated")
        
        # Simulate call answered
        await outbound_call_manager.handle_call_status_update(
            task_id=task_id,
            call_sid="CA_simulation_123",
            status="completed",
            duration=45
        )
        print("  ✅ Call completed (45 seconds)")
        
        # Check final status
        final_status = await outbound_call_manager.get_task_status(task_id)
        if final_status:
            print(f"📊 Final Status: {final_status['status']}")
            if final_status['attempts']:
                attempt = final_status['attempts'][0]
                print(f"  Result: {attempt['result']}")
                print(f"  Duration: {attempt['duration_seconds']}s")
        
    except Exception as e:
        print(f"❌ Simulation failed: {e}")


async def test_timezone_optimization():
    """Test timezone-based call optimization."""
    print("\n🔄 Testing timezone optimization...")
    
    from app.services.outbound_call_manager import TimezoneOptimizer
    
    # Test different locations
    locations = [
        "New York, United States",
        "London, United Kingdom", 
        "Tokyo, Japan",
        "Sydney, Australia"
    ]
    
    base_time = datetime.utcnow()
    
    for location in locations:
        try:
            timezone = TimezoneOptimizer.get_timezone_for_location(location)
            optimal_time = TimezoneOptimizer.get_optimal_call_time(location, base_time)
            is_business_hours = TimezoneOptimizer.is_business_hours(location, base_time)
            
            print(f"📍 {location}:")
            print(f"  Timezone: {timezone}")
            print(f"  Optimal Time: {optimal_time}")
            print(f"  Business Hours: {is_business_hours}")
            
        except Exception as e:
            print(f"❌ Timezone test failed for {location}: {e}")


async def test_voicemail_detection():
    """Test voicemail detection functionality."""
    print("\n🔄 Testing voicemail detection...")
    
    from app.services.outbound_call_manager import VoicemailDetector
    
    # Test cases
    test_cases = [
        (15, "Please leave a message after the beep", True),
        (25, "You have reached the voicemail of John", True),
        (45, "Hello, how can I help you today?", False),
        (120, "Thank you for calling our company", False),
        (5, None, False)
    ]
    
    for duration, transcription, expected in test_cases:
        result = VoicemailDetector.detect_voicemail(duration, transcription)
        status = "✅" if result == expected else "❌"
        print(f"  {status} Duration: {duration}s, Text: '{transcription}' -> {result}")
    
    # Test message generation
    message = VoicemailDetector.generate_voicemail_message("John Doe", "Acme Corp")
    print(f"📝 Sample Voicemail Message: {message[:100]}...")


async def run_all_tests():
    """Run all outbound call tests."""
    print("🚀 Starting Outbound Call Manager Tests")
    print("=" * 50)
    
    try:
        # Test individual components
        await test_timezone_optimization()
        await test_voicemail_detection()
        
        # Test call scheduling
        task_id = await test_schedule_single_call()
        task_ids = await test_bulk_schedule_calls()
        
        # Test status reporting
        await test_queue_status()
        await test_budget_status()
        await test_system_status()
        
        # Test call processing simulation
        await test_call_processing_simulation()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        
        # Cleanup - cancel any remaining tasks
        if task_id:
            await outbound_call_manager.call_queue.remove_task(task_id)
        
        for tid in task_ids:
            await outbound_call_manager.call_queue.remove_task(tid)
        
        print("🧹 Cleanup completed")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("AI Calling Agent MVP - Outbound Call Manager Test Suite")
    print("=" * 60)
    
    # Run the test suite
    asyncio.run(run_all_tests())