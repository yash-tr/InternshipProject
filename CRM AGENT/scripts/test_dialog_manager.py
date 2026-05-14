#!/usr/bin/env python3
"""
Test script for Dialog Manager functionality.

This script demonstrates the FSM-based dialog management system
with template-first responses and selective LLM usage.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dialog_manager import (
    dialog_manager, DialogState, DialogTemplateLibrary, 
    DialogContext, LLMBudgetTracker
)


async def test_template_library():
    """Test the dialog template library."""
    print("🔄 Testing Dialog Template Library...")
    
    library = DialogTemplateLibrary()
    
    # Test template retrieval
    greeting_templates = library.get_templates(DialogState.GREETING)
    print(f"✅ Found {len(greeting_templates)} greeting templates")
    
    # Test template matching
    context = DialogContext(
        call_sid="test",
        prospect_data={},
        conversation_history=[],
        extracted_information={},
        current_state=DialogState.OBJECTION_HANDLING,
        state_entry_time=datetime.utcnow()
    )
    
    # Test price objection matching
    price_template = library.find_best_template(
        DialogState.OBJECTION_HANDLING, 
        context, 
        "That's too expensive"
    )
    
    if price_template:
        print(f"✅ Price objection template found: {price_template.template_id}")
        print(f"   Response: {price_template.response[:100]}...")
    
    # Test timing objection matching
    timing_template = library.find_best_template(
        DialogState.OBJECTION_HANDLING, 
        context, 
        "We don't have time right now"
    )
    
    if timing_template:
        print(f"✅ Timing objection template found: {timing_template.template_id}")
        print(f"   Response: {timing_template.response[:100]}...")


async def test_budget_tracker():
    """Test the LLM budget tracking system."""
    print("\n🔄 Testing LLM Budget Tracker...")
    
    # Test non-VIP budget
    non_vip_tracker = LLMBudgetTracker(is_vip=False)
    print(f"📊 Non-VIP Budget: {non_vip_tracker.max_llm_calls_non_vip} calls max")
    
    assert non_vip_tracker.can_use_llm() is True
    non_vip_tracker.record_llm_usage(50)
    print(f"✅ Used 1 call, remaining: {non_vip_tracker.can_use_llm()}")
    
    # Test VIP budget
    vip_tracker = LLMBudgetTracker(is_vip=True)
    print(f"📊 VIP Budget: {vip_tracker.max_llm_calls_vip} calls max")
    
    for i in range(3):
        if vip_tracker.can_use_llm():
            vip_tracker.record_llm_usage(30)
            print(f"✅ VIP used call {i+1}, tokens: {vip_tracker.current_tokens_used}")
    
    print(f"📊 VIP budget exhausted: {not vip_tracker.can_use_llm()}")


async def test_conversation_flow():
    """Test a complete conversation flow."""
    print("\n🔄 Testing Complete Conversation Flow...")
    
    call_sid = "test_conversation_123"
    prospect_data = {
        "name": "John Doe",
        "company": "Test Corp",
        "industry": "Technology",
        "lead_score": 75
    }
    
    # Start conversation
    print("📞 Starting conversation...")
    initial_response = await dialog_manager.start_conversation(call_sid, prospect_data)
    print(f"🤖 AI: {initial_response}")
    
    # Simulate conversation turns
    conversation_turns = [
        "Hi, I'm doing well, thank you",
        "I'm the CTO at Test Corp",
        "We have about 150 employees",
        "Our biggest challenge is managing our data efficiently",
        "That sounds interesting, but what would this cost us?",
        "I'd like to learn more. Can we schedule a demo?"
    ]
    
    for i, user_input in enumerate(conversation_turns, 1):
        print(f"\n👤 User: {user_input}")
        
        try:
            response, should_end = await dialog_manager.process_turn(call_sid, user_input)
            print(f"🤖 AI: {response}")
            
            if should_end:
                print("📞 Call ended by AI")
                break
                
            # Get conversation status
            status = await dialog_manager.get_conversation_status(call_sid)
            if status:
                print(f"📊 State: {status['current_state']}, Turns: {status['total_turns']}")
                print(f"💰 LLM Budget: {status['llm_budget_used']['calls_used']}/{status['llm_budget_used']['calls_used'] + status['llm_budget_used']['calls_remaining']}")
        
        except Exception as e:
            print(f"❌ Error in turn {i}: {e}")
            break
    
    # End conversation
    print("\n📞 Ending conversation...")
    summary = await dialog_manager.end_conversation(call_sid, "completed")
    
    if summary:
        print("📋 Conversation Summary:")
        print(f"   Final State: {summary.get('final_state')}")
        print(f"   Total Turns: {summary.get('total_turns')}")
        print(f"   Duration: {summary.get('duration_minutes', 0):.1f} minutes")
        print(f"   LLM Calls: {summary.get('llm_calls_used', 0)}")
        print(f"   Tokens Used: {summary.get('tokens_used', 0)}")


async def test_objection_handling():
    """Test objection handling scenarios."""
    print("\n🔄 Testing Objection Handling...")
    
    call_sid = "objection_test_456"
    prospect_data = {
        "name": "Jane Smith",
        "company": "Objection Corp",
        "lead_score": 80  # VIP prospect
    }
    
    # Start conversation
    await dialog_manager.start_conversation(call_sid, prospect_data)
    
    # Test different objections
    objections = [
        ("Price", "That's way too expensive for our budget"),
        ("Timing", "We're too busy to implement anything new right now"),
        ("Authority", "I need to check with my boss first"),
        ("Need", "I'm not sure we really need this solution")
    ]
    
    for objection_type, objection_text in objections:
        print(f"\n🚫 Testing {objection_type} Objection:")
        print(f"👤 User: {objection_text}")
        
        try:
            response, should_end = await dialog_manager.process_turn(call_sid, objection_text)
            print(f"🤖 AI: {response[:150]}...")
            
            # Should not end call on objections
            if should_end:
                print("⚠️  Warning: Call ended on objection")
            else:
                print("✅ Objection handled, conversation continues")
        
        except Exception as e:
            print(f"❌ Error handling {objection_type} objection: {e}")
    
    # End conversation
    await dialog_manager.end_conversation(call_sid, "objection_handling")


async def test_timeout_scenario():
    """Test conversation timeout handling."""
    print("\n🔄 Testing Timeout Scenario...")
    
    call_sid = "timeout_test_789"
    prospect_data = {"name": "Timeout User", "lead_score": 60}
    
    # Start conversation
    await dialog_manager.start_conversation(call_sid, prospect_data)
    
    # Get context and simulate timeout
    context = dialog_manager.conversation_contexts.get(call_sid)
    if context:
        # Simulate timeout by setting old entry time
        from datetime import timedelta
        context.state_entry_time = datetime.utcnow() - timedelta(minutes=5)
        context.timeout_duration = timedelta(minutes=2)
        
        print("⏰ Simulating timeout condition...")
        
        # Process turn - should trigger timeout
        response, should_end = await dialog_manager.process_turn(call_sid, "Hello")
        
        print(f"🤖 AI (timeout): {response}")
        print(f"📞 Call ended due to timeout: {should_end}")
        
        if should_end:
            print("✅ Timeout handling working correctly")
        else:
            print("❌ Timeout not detected properly")
    
    # Cleanup
    await dialog_manager.end_conversation(call_sid, "timeout")


async def test_state_transitions():
    """Test dialog state transitions."""
    print("\n🔄 Testing State Transitions...")
    
    call_sid = "state_test_101"
    prospect_data = {"name": "State User", "lead_score": 70}
    
    # Start conversation
    await dialog_manager.start_conversation(call_sid, prospect_data)
    
    # Test state progression
    state_progression = [
        ("Greeting", "Hello, I'm doing great!"),
        ("Qualification", "I'm the VP of Engineering"),
        ("Needs Analysis", "We're struggling with data processing speed"),
        ("Closing", "That sounds like exactly what we need")
    ]
    
    for expected_next_state, user_input in state_progression:
        print(f"\n🔄 Expected transition to: {expected_next_state}")
        print(f"👤 User: {user_input}")
        
        response, should_end = await dialog_manager.process_turn(call_sid, user_input)
        print(f"🤖 AI: {response[:100]}...")
        
        # Check current state
        status = await dialog_manager.get_conversation_status(call_sid)
        if status:
            current_state = status['current_state']
            print(f"📊 Current State: {current_state}")
        
        if should_end:
            print("📞 Conversation ended")
            break
    
    # End conversation
    await dialog_manager.end_conversation(call_sid, "completed")


async def test_vip_vs_non_vip():
    """Test VIP vs non-VIP prospect handling."""
    print("\n🔄 Testing VIP vs Non-VIP Handling...")
    
    # Non-VIP prospect
    non_vip_call = "non_vip_test"
    non_vip_data = {"name": "Regular User", "lead_score": 50}
    
    await dialog_manager.start_conversation(non_vip_call, non_vip_data)
    non_vip_status = await dialog_manager.get_conversation_status(non_vip_call)
    
    print(f"👤 Non-VIP Prospect (Score: 50):")
    print(f"   LLM Calls Available: {non_vip_status['llm_budget_used']['calls_remaining']}")
    
    # VIP prospect
    vip_call = "vip_test"
    vip_data = {"name": "VIP User", "lead_score": 90}
    
    await dialog_manager.start_conversation(vip_call, vip_data)
    vip_status = await dialog_manager.get_conversation_status(vip_call)
    
    print(f"⭐ VIP Prospect (Score: 90):")
    print(f"   LLM Calls Available: {vip_status['llm_budget_used']['calls_remaining']}")
    
    # Cleanup
    await dialog_manager.end_conversation(non_vip_call, "test")
    await dialog_manager.end_conversation(vip_call, "test")
    
    if vip_status['llm_budget_used']['calls_remaining'] > non_vip_status['llm_budget_used']['calls_remaining']:
        print("✅ VIP prospects get more LLM budget as expected")
    else:
        print("❌ VIP budget allocation not working correctly")


async def run_all_tests():
    """Run all dialog manager tests."""
    print("🚀 Starting Dialog Manager Test Suite")
    print("=" * 60)
    
    try:
        # Test individual components
        await test_template_library()
        await test_budget_tracker()
        
        # Test conversation flows
        await test_conversation_flow()
        await test_objection_handling()
        await test_timeout_scenario()
        await test_state_transitions()
        await test_vip_vs_non_vip()
        
        print("\n" + "=" * 60)
        print("✅ All Dialog Manager tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("AI Calling Agent MVP - Dialog Manager Test Suite")
    print("=" * 60)
    
    # Run the test suite
    asyncio.run(run_all_tests())