#!/usr/bin/env python3
"""
Test script for Enhanced Objection Handling system.

This script tests the objection handling functionality including:
- Objection classification and severity detection
- Response generation with prospect customization
- Objection tracking and analytics
- Integration with dialog management
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.objection_handler import (
    enhanced_objection_handler,
    ObjectionType,
    ObjectionSeverity,
    ResponseStrategy
)


async def test_objection_classification():
    """Test objection classification with various inputs."""
    print("🔍 Testing Objection Classification...")
    
    test_cases = [
        # Price objections
        ("This is way too expensive for our budget", ObjectionType.PRICE, ObjectionSeverity.HIGH),
        ("The cost seems a bit high", ObjectionType.PRICE, ObjectionSeverity.MEDIUM),
        ("We can't afford this right now", ObjectionType.PRICE, ObjectionSeverity.HIGH),
        
        # Timing objections
        ("We're too busy to deal with this", ObjectionType.TIMING, ObjectionSeverity.MEDIUM),
        ("This isn't the right time", ObjectionType.TIMING, ObjectionSeverity.MEDIUM),
        ("Absolutely no time for this", ObjectionType.TIMING, ObjectionSeverity.CRITICAL),
        
        # Authority objections
        ("I need to check with my boss", ObjectionType.AUTHORITY, ObjectionSeverity.MEDIUM),
        ("This isn't my decision to make", ObjectionType.AUTHORITY, ObjectionSeverity.HIGH),
        ("I have no authority over this", ObjectionType.AUTHORITY, ObjectionSeverity.CRITICAL),
        
        # Need objections
        ("We don't really need this", ObjectionType.NEED, ObjectionSeverity.MEDIUM),
        ("Our current solution works fine", ObjectionType.NEED, ObjectionSeverity.MEDIUM),
        ("Everything is perfect as is", ObjectionType.NEED, ObjectionSeverity.CRITICAL),
        
        # Trust objections
        ("I'm not sure about this", ObjectionType.TRUST, ObjectionSeverity.MEDIUM),
        ("This seems too good to be true", ObjectionType.TRUST, ObjectionSeverity.MEDIUM),
        ("I don't trust new technology", ObjectionType.TRUST, ObjectionSeverity.HIGH),
        
        # Competition objections
        ("We already have a solution", ObjectionType.COMPETITION, ObjectionSeverity.MEDIUM),
        ("Our current vendor is great", ObjectionType.COMPETITION, ObjectionSeverity.MEDIUM),
        ("We're locked into a contract", ObjectionType.COMPETITION, ObjectionSeverity.CRITICAL),
        
        # Priority objections
        ("We have other priorities", ObjectionType.PRIORITY, ObjectionSeverity.MEDIUM),
        ("This isn't important right now", ObjectionType.PRIORITY, ObjectionSeverity.MEDIUM),
        ("Absolutely not a priority", ObjectionType.PRIORITY, ObjectionSeverity.CRITICAL)
    ]
    
    correct_classifications = 0
    total_tests = len(test_cases)
    
    for user_input, expected_type, expected_severity in test_cases:
        objection_type, severity, confidence = enhanced_objection_handler.classifier.classify_objection(user_input)
        
        type_correct = objection_type == expected_type
        severity_correct = severity == expected_severity
        
        if type_correct:
            correct_classifications += 1
        
        status = "✅" if type_correct else "❌"
        severity_status = "✅" if severity_correct else "❌"
        
        print(f"{status} '{user_input[:40]}...' -> {objection_type.value} ({confidence:.2f}) {severity_status} {severity.value}")
    
    accuracy = correct_classifications / total_tests
    print(f"\n📊 Classification Accuracy: {accuracy:.1%} ({correct_classifications}/{total_tests})")
    print("✅ Objection classification test completed\n")


async def test_response_generation():
    """Test response generation with different prospect profiles."""
    print("🔍 Testing Response Generation...")
    
    prospect_profiles = [
        {
            "name": "Technology Company",
            "data": {
                "company_name": "TechCorp Inc",
                "industry": "technology",
                "job_title": "CTO",
                "company_size": "500-1000"
            }
        },
        {
            "name": "Healthcare Organization", 
            "data": {
                "company_name": "HealthSystem LLC",
                "industry": "healthcare",
                "job_title": "Director of IT",
                "company_size": "1000+"
            }
        },
        {
            "name": "Financial Services",
            "data": {
                "company_name": "FinanceFirst Bank",
                "industry": "finance",
                "job_title": "CFO",
                "company_size": "100-500"
            }
        },
        {
            "name": "Manufacturing Company",
            "data": {
                "company_name": "ManufacturePro",
                "industry": "manufacturing",
                "job_title": "Operations Manager",
                "company_size": "200-500"
            }
        }
    ]
    
    test_objections = [
        ("This is too expensive for our budget", ObjectionType.PRICE, ObjectionSeverity.HIGH),
        ("We don't have time for this right now", ObjectionType.TIMING, ObjectionSeverity.MEDIUM),
        ("I need to get approval from my team", ObjectionType.AUTHORITY, ObjectionSeverity.MEDIUM)
    ]
    
    for profile in prospect_profiles:
        print(f"\n🏢 Testing {profile['name']}:")
        
        for objection_text, objection_type, severity in test_objections:
            response = enhanced_objection_handler.response_generator.generate_response(
                objection_type, severity, profile['data']
            )
            
            if response:
                # Check if company name is properly substituted
                has_company = profile['data']['company_name'] in response.template
                customization_status = "✅" if has_company else "📝"
                
                print(f"  {customization_status} {objection_type.value.title()}: {response.template[:80]}...")
                print(f"     Strategy: {response.strategy.value}")
                print(f"     Follow-up: {len(response.follow_up_questions)} questions")
            else:
                print(f"  ❌ {objection_type.value.title()}: No response template found")
    
    print("✅ Response generation test completed\n")


async def test_complete_objection_handling():
    """Test complete objection handling workflow."""
    print("🔍 Testing Complete Objection Handling Workflow...")
    
    test_scenarios = [
        {
            "call_sid": "test_price_objection",
            "prospect": {
                "company_name": "StartupCorp",
                "industry": "technology",
                "job_title": "Founder",
                "company_size": "10-50"
            },
            "objection": "This is way too expensive for a startup like us",
            "follow_up": "That makes sense, let's see the numbers"
        },
        {
            "call_sid": "test_timing_objection",
            "prospect": {
                "company_name": "BusyCorp",
                "industry": "finance",
                "job_title": "VP Operations",
                "company_size": "500-1000"
            },
            "objection": "We're in the middle of a major project and don't have time",
            "follow_up": "I understand, but we're still not ready"
        },
        {
            "call_sid": "test_authority_objection",
            "prospect": {
                "company_name": "HierarchyCorp",
                "industry": "healthcare",
                "job_title": "Manager",
                "company_size": "1000+"
            },
            "objection": "I need to get approval from my director before we can proceed",
            "follow_up": "Yes, I'll need to present this to the leadership team"
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n📞 Testing Call: {scenario['call_sid']}")
        print(f"   Company: {scenario['prospect']['company_name']} ({scenario['prospect']['industry']})")
        print(f"   Contact: {scenario['prospect']['job_title']}")
        
        # Handle initial objection
        response_text, should_escalate, objection_info = await enhanced_objection_handler.handle_objection(
            call_sid=scenario['call_sid'],
            user_input=scenario['objection'],
            prospect_data=scenario['prospect']
        )
        
        print(f"   Objection: '{scenario['objection']}'")
        print(f"   Classified: {objection_info['objection_type']} ({objection_info['severity']}) - {objection_info['confidence']:.2f}")
        print(f"   Strategy: {objection_info['strategy']}")
        print(f"   Response: {response_text[:100]}...")
        print(f"   Escalate: {'Yes' if should_escalate else 'No'}")
        
        # Handle follow-up response
        objection_id = objection_info['objection_id']
        resolved = await enhanced_objection_handler.update_objection_outcome(
            objection_id=objection_id,
            user_response=scenario['follow_up']
        )
        
        print(f"   Follow-up: '{scenario['follow_up']}'")
        print(f"   Resolved: {'Yes' if resolved else 'No'}")
        
        # Get call analytics
        analytics = await enhanced_objection_handler.get_call_objection_analytics(scenario['call_sid'])
        if analytics:
            print(f"   Analytics: {analytics.total_objections} objections, {analytics.resolution_rate:.1%} resolved")
    
    print("✅ Complete objection handling test completed\n")


async def test_escalation_logic():
    """Test objection escalation logic."""
    print("🔍 Testing Escalation Logic...")
    
    escalation_scenarios = [
        {
            "name": "Multiple Objections",
            "call_sid": "escalation_multiple",
            "objections": [
                "This is too expensive",
                "We don't have time for this", 
                "I don't think we need it",
                "This won't work for us",
                "I'm not interested"
            ]
        },
        {
            "name": "Critical Objection",
            "call_sid": "escalation_critical",
            "objections": [
                "This is absolutely impossible for us to implement"
            ]
        },
        {
            "name": "Escalation Request",
            "call_sid": "escalation_request",
            "objections": [
                "I want to speak to a human representative"
            ]
        }
    ]
    
    prospect_data = {
        "company_name": "TestCorp",
        "industry": "technology",
        "job_title": "Manager"
    }
    
    for scenario in escalation_scenarios:
        print(f"\n🚨 Testing {scenario['name']}:")
        
        should_escalate_final = False
        for i, objection in enumerate(scenario['objections']):
            response_text, should_escalate, objection_info = await enhanced_objection_handler.handle_objection(
                call_sid=scenario['call_sid'],
                user_input=objection,
                prospect_data=prospect_data
            )
            
            print(f"   Objection {i+1}: '{objection}'")
            print(f"   Should Escalate: {'Yes' if should_escalate else 'No'}")
            
            should_escalate_final = should_escalate
            
            if should_escalate:
                break
        
        # Get final analytics
        analytics = await enhanced_objection_handler.get_call_objection_analytics(scenario['call_sid'])
        if analytics:
            print(f"   Final: {analytics.total_objections} objections, escalation needed: {'Yes' if should_escalate_final else 'No'}")
    
    print("✅ Escalation logic test completed\n")


async def test_system_analytics():
    """Test system-wide objection analytics."""
    print("🔍 Testing System Analytics...")
    
    # Generate some test data across multiple calls
    test_calls = [
        ("analytics_call_1", "This costs too much", "TechCorp", "technology"),
        ("analytics_call_2", "We're too busy right now", "HealthCorp", "healthcare"),
        ("analytics_call_3", "I need to ask my boss", "FinanceCorp", "finance"),
        ("analytics_call_4", "We already have a solution", "ManufactureCorp", "manufacturing"),
        ("analytics_call_5", "I'm not sure about this", "StartupCorp", "technology")
    ]
    
    for call_sid, objection, company, industry in test_calls:
        prospect_data = {
            "company_name": company,
            "industry": industry,
            "job_title": "Manager"
        }
        
        await enhanced_objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=objection,
            prospect_data=prospect_data
        )
    
    # Get system metrics
    metrics = await enhanced_objection_handler.get_system_objection_metrics()
    
    print(f"📊 System Objection Metrics:")
    print(f"   Total Objections: {metrics['total_objections']}")
    print(f"   Active Calls: {metrics['active_calls_with_objections']}")
    print(f"   Resolution Rate: {metrics['overall_resolution_rate']:.1%}")
    print(f"   Escalation Rate: {metrics['overall_escalation_rate']:.1%}")
    
    if metrics['most_common_objection']:
        print(f"   Most Common: {metrics['most_common_objection']}")
    
    print(f"   Objections by Type:")
    for obj_type, count in metrics['objections_by_type'].items():
        print(f"     - {obj_type.title()}: {count}")
    
    print(f"   Objections by Severity:")
    for severity, count in metrics['objections_by_severity'].items():
        print(f"     - {severity.title()}: {count}")
    
    if metrics['strategy_effectiveness']:
        print(f"   Strategy Effectiveness:")
        for strategy, stats in metrics['strategy_effectiveness'].items():
            print(f"     - {strategy}: {stats['success_rate']:.1%} ({stats['total_uses']} uses)")
    
    print("✅ System analytics test completed\n")


async def test_prospect_customization():
    """Test prospect-specific response customization."""
    print("🔍 Testing Prospect Customization...")
    
    # Same objection, different prospect profiles
    objection = "This seems expensive for what we get"
    
    prospect_profiles = [
        {
            "name": "Startup CEO",
            "data": {
                "company_name": "InnovateCorp",
                "industry": "technology",
                "job_title": "CEO",
                "company_size": "10-50"
            }
        },
        {
            "name": "Enterprise CFO",
            "data": {
                "company_name": "MegaCorp International",
                "industry": "finance",
                "job_title": "CFO", 
                "company_size": "5000+"
            }
        },
        {
            "name": "Healthcare Director",
            "data": {
                "company_name": "Regional Medical Center",
                "industry": "healthcare",
                "job_title": "Director of IT",
                "company_size": "1000-5000"
            }
        }
    ]
    
    responses = []
    for profile in prospect_profiles:
        call_sid = f"customization_{profile['name'].lower().replace(' ', '_')}"
        
        response_text, should_escalate, objection_info = await enhanced_objection_handler.handle_objection(
            call_sid=call_sid,
            user_input=objection,
            prospect_data=profile['data']
        )
        
        responses.append((profile['name'], response_text))
        
        print(f"👤 {profile['name']} ({profile['data']['company_name']}):")
        print(f"   Industry: {profile['data']['industry']}")
        print(f"   Response: {response_text[:120]}...")
        print(f"   Company mentioned: {'Yes' if profile['data']['company_name'] in response_text else 'No'}")
        print()
    
    # Check that responses are different (customized)
    unique_responses = len(set(response[1] for response in responses))
    print(f"📊 Response Customization: {unique_responses}/{len(responses)} unique responses")
    
    if unique_responses > 1:
        print("✅ Responses are properly customized for different prospects")
    else:
        print("⚠️  Responses may need more customization")
    
    print("✅ Prospect customization test completed\n")


async def test_integration_with_dialog_manager():
    """Test integration with dialog manager."""
    print("🔍 Testing Dialog Manager Integration...")
    
    # Test the objection detection heuristics
    from app.services.dialog_manager import DialogManager
    
    dialog_manager = DialogManager()
    
    test_inputs = [
        ("This is too expensive", True),
        ("We're too busy right now", True),
        ("I need to think about it", True),
        ("That sounds interesting", False),
        ("Tell me more about the features", False),
        ("How does this work?", False),
        ("But I'm concerned about the cost", True),
        ("However, we don't have the budget", True)
    ]
    
    correct_detections = 0
    for user_input, expected_objection in test_inputs:
        is_objection = dialog_manager._looks_like_objection(user_input)
        
        if is_objection == expected_objection:
            correct_detections += 1
        
        status = "✅" if is_objection == expected_objection else "❌"
        print(f"{status} '{user_input}' -> {'Objection' if is_objection else 'Not Objection'}")
    
    detection_accuracy = correct_detections / len(test_inputs)
    print(f"\n📊 Objection Detection Accuracy: {detection_accuracy:.1%} ({correct_detections}/{len(test_inputs)})")
    
    print("✅ Dialog manager integration test completed\n")


async def main():
    """Run all objection handling tests."""
    print("🚀 Starting Enhanced Objection Handling Tests\n")
    print("=" * 70)
    
    # Run all tests
    await test_objection_classification()
    await test_response_generation()
    await test_complete_objection_handling()
    await test_escalation_logic()
    await test_system_analytics()
    await test_prospect_customization()
    await test_integration_with_dialog_manager()
    
    print("=" * 70)
    print("🎉 All Enhanced Objection Handling tests completed!")
    
    # Final system check
    final_metrics = await enhanced_objection_handler.get_system_objection_metrics()
    print(f"📊 Final System State:")
    print(f"   Total Objections Handled: {final_metrics['total_objections']}")
    print(f"   Active Calls: {final_metrics['active_calls_with_objections']}")
    print(f"   System Status: {'Healthy' if final_metrics['total_objections'] > 0 else 'Ready'}")


if __name__ == "__main__":
    asyncio.run(main())