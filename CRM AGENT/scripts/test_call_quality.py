#!/usr/bin/env python3
"""
Test script for Call Quality Monitoring system.

This script tests the call quality monitoring functionality including:
- Audio metrics analysis
- Performance metrics recording
- Quality analysis and optimization
- System metrics reporting
"""

import asyncio
import sys
import os
import numpy as np
from datetime import datetime
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.call_quality_monitor import (
    call_quality_monitor,
    OptimizationSettings,
    CallQualityLevel,
    AudioIssueType,
    OptimizationAction
)


def generate_test_audio(duration_seconds: float = 1.0, 
                       sample_rate: int = 8000,
                       add_noise: bool = False,
                       add_distortion: bool = False) -> bytes:
    """Generate test audio data."""
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    
    # Generate a sine wave (440 Hz - A4 note)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    
    if add_noise:
        # Add background noise
        noise = 0.3 * np.random.normal(0, 1, len(audio))
        audio += noise
    
    if add_distortion:
        # Add clipping distortion
        audio = np.clip(audio * 2, -0.95, 0.95)
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


async def test_basic_monitoring():
    """Test basic call monitoring functionality."""
    print("🔍 Testing basic call monitoring...")
    
    call_sid = "test_call_basic_001"
    
    try:
        # Start monitoring
        session = await call_quality_monitor.start_monitoring(call_sid)
        print(f"✅ Started monitoring for call {call_sid}")
        
        # Generate and analyze audio
        clean_audio = generate_test_audio(duration_seconds=2.0)
        audio_metrics = await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=clean_audio,
            sample_rate=8000
        )
        
        print(f"📊 Audio Quality Score: {audio_metrics.quality_score:.3f}")
        print(f"📊 Volume Level: {audio_metrics.volume_level:.3f}")
        print(f"📊 Noise Level: {audio_metrics.noise_level:.3f}")
        print(f"📊 SNR: {audio_metrics.signal_to_noise_ratio:.1f} dB")
        
        # Record performance metrics
        performance_metrics = await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=500.0,
            tts_latency_ms=700.0,
            response_generation_ms=1500.0,
            stt_confidence=0.9,
            connection_quality=0.8
        )
        
        print(f"⚡ Performance Score: {performance_metrics.performance_score:.3f}")
        print(f"⚡ Total Latency: {performance_metrics.total_turn_latency_ms:.0f} ms")
        
        # Analyze call quality
        snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        if snapshot:
            print(f"🎯 Overall Quality: {snapshot.quality_level.value} ({snapshot.overall_score:.3f})")
            print(f"🎯 Issues Detected: {len(snapshot.detected_issues)}")
            print(f"🎯 Optimizations: {len(snapshot.optimization_actions)}")
        
        # Stop monitoring
        report = await call_quality_monitor.stop_monitoring(call_sid)
        if report:
            print(f"📋 Final Report: {report['average_overall_score']:.3f} avg quality")
        
        print("✅ Basic monitoring test completed\n")
        
    except Exception as e:
        print(f"❌ Basic monitoring test failed: {e}\n")


async def test_poor_quality_detection():
    """Test detection of poor audio quality and optimization actions."""
    print("🔍 Testing poor quality detection...")
    
    call_sid = "test_call_poor_002"
    
    try:
        # Start monitoring with custom settings
        settings = OptimizationSettings(
            noise_reduction_enabled=False,
            tts_model="eleven_turbo_v2",
            max_response_length=150
        )
        
        session = await call_quality_monitor.start_monitoring(call_sid, settings)
        print(f"✅ Started monitoring with custom settings")
        
        # Generate poor quality audio
        poor_audio = generate_test_audio(
            duration_seconds=2.0,
            add_noise=True,
            add_distortion=True
        )
        
        audio_metrics = await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=poor_audio,
            sample_rate=8000
        )
        
        print(f"📊 Poor Audio Quality Score: {audio_metrics.quality_score:.3f}")
        print(f"📊 High Noise Level: {audio_metrics.noise_level:.3f}")
        print(f"📊 Distortion: {audio_metrics.distortion_level:.3f}")
        
        # Record poor performance metrics
        performance_metrics = await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=1200.0,  # High latency
            tts_latency_ms=1800.0,  # High TTS latency
            response_generation_ms=4000.0,  # Slow response
            stt_confidence=0.6,  # Low confidence
            connection_quality=0.4  # Poor connection
        )
        
        print(f"⚡ Poor Performance Score: {performance_metrics.performance_score:.3f}")
        print(f"⚡ High Total Latency: {performance_metrics.total_turn_latency_ms:.0f} ms")
        
        # Analyze quality - should detect issues and suggest optimizations
        snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        if snapshot:
            print(f"🎯 Quality Level: {snapshot.quality_level.value} ({snapshot.overall_score:.3f})")
            print(f"🚨 Issues Detected: {[issue.value for issue in snapshot.detected_issues]}")
            print(f"🔧 Optimizations Applied: {[action.value for action in snapshot.optimization_actions]}")
            
            # Check if optimizations were applied
            updated_settings = session.settings
            print(f"🔧 Noise Reduction Enabled: {updated_settings.noise_reduction_enabled}")
            print(f"🔧 TTS Model: {updated_settings.tts_model}")
            print(f"🔧 Max Response Length: {updated_settings.max_response_length}")
        
        # Stop monitoring
        report = await call_quality_monitor.stop_monitoring(call_sid)
        if report:
            print(f"📋 Final Report: {report['total_issues_detected']} issues, {report['total_optimizations_applied']} optimizations")
        
        print("✅ Poor quality detection test completed\n")
        
    except Exception as e:
        print(f"❌ Poor quality detection test failed: {e}\n")


async def test_concurrent_monitoring():
    """Test monitoring multiple calls concurrently."""
    print("🔍 Testing concurrent call monitoring...")
    
    call_sids = [f"test_call_concurrent_{i:03d}" for i in range(5)]
    
    try:
        # Start monitoring multiple calls
        sessions = []
        for call_sid in call_sids:
            session = await call_quality_monitor.start_monitoring(call_sid)
            sessions.append(session)
        
        print(f"✅ Started monitoring {len(sessions)} concurrent calls")
        
        # Record metrics for all calls
        for i, call_sid in enumerate(call_sids):
            # Vary audio quality
            audio = generate_test_audio(
                duration_seconds=1.0,
                add_noise=(i % 2 == 0),  # Every other call has noise
                add_distortion=(i % 3 == 0)  # Every third call has distortion
            )
            
            await call_quality_monitor.record_audio_metrics(
                call_sid=call_sid,
                audio_data=audio,
                sample_rate=8000
            )
            
            # Vary performance metrics
            await call_quality_monitor.record_performance_metrics(
                call_sid=call_sid,
                stt_latency_ms=400.0 + (i * 200),  # Increasing latency
                tts_latency_ms=600.0 + (i * 100),
                response_generation_ms=1000.0 + (i * 500),
                stt_confidence=0.9 - (i * 0.1),  # Decreasing confidence
                connection_quality=0.9 - (i * 0.1)
            )
        
        # Analyze all calls
        snapshots = []
        for call_sid in call_sids:
            snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
            if snapshot:
                snapshots.append(snapshot)
        
        print(f"📊 Analyzed {len(snapshots)} calls")
        
        # Get system metrics
        system_metrics = await call_quality_monitor.get_system_metrics()
        print(f"🖥️  System Status: {system_metrics['system_status']}")
        print(f"🖥️  Active Calls: {system_metrics['active_monitored_calls']}")
        print(f"🖥️  Average Quality: {system_metrics['average_quality_score']:.3f}")
        
        # Stop all monitoring
        reports = []
        for call_sid in call_sids:
            report = await call_quality_monitor.stop_monitoring(call_sid)
            if report:
                reports.append(report)
        
        print(f"📋 Generated {len(reports)} final reports")
        print("✅ Concurrent monitoring test completed\n")
        
    except Exception as e:
        print(f"❌ Concurrent monitoring test failed: {e}\n")


async def test_optimization_settings():
    """Test optimization settings and their effects."""
    print("🔍 Testing optimization settings...")
    
    call_sid = "test_call_optimization_003"
    
    try:
        # Start with specific settings
        initial_settings = OptimizationSettings(
            noise_reduction_enabled=False,
            noise_reduction_strength=0.3,
            tts_model="eleven_turbo_v2",
            max_response_length=120,
            response_timeout_ms=4000
        )
        
        session = await call_quality_monitor.start_monitoring(call_sid, initial_settings)
        print(f"✅ Started with initial settings:")
        print(f"   - Noise Reduction: {initial_settings.noise_reduction_enabled}")
        print(f"   - TTS Model: {initial_settings.tts_model}")
        print(f"   - Max Response Length: {initial_settings.max_response_length}")
        
        # Simulate conditions that trigger optimizations
        noisy_audio = generate_test_audio(duration_seconds=1.5, add_noise=True)
        await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=noisy_audio,
            sample_rate=8000
        )
        
        # High latency performance
        await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=800.0,
            tts_latency_ms=1600.0,  # Triggers TTS optimization
            response_generation_ms=3000.0,
            stt_confidence=0.7,
            connection_quality=0.6
        )
        
        # Analyze - should trigger optimizations
        snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        if snapshot:
            print(f"🔧 Optimizations triggered: {[action.value for action in snapshot.optimization_actions]}")
            
            # Check updated settings
            updated_settings = session.settings
            print(f"✅ Updated settings:")
            print(f"   - Noise Reduction: {updated_settings.noise_reduction_enabled}")
            print(f"   - TTS Model: {updated_settings.tts_model}")
            print(f"   - Max Response Length: {updated_settings.max_response_length}")
            print(f"   - Response Timeout: {updated_settings.response_timeout_ms}")
        
        # Test another round with improved conditions
        clean_audio = generate_test_audio(duration_seconds=1.0)
        await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=clean_audio,
            sample_rate=8000
        )
        
        await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=500.0,
            tts_latency_ms=600.0,  # Better with optimized settings
            response_generation_ms=1200.0,
            stt_confidence=0.9,
            connection_quality=0.8
        )
        
        # Final analysis
        final_snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        if final_snapshot:
            print(f"📈 Final Quality: {final_snapshot.quality_level.value} ({final_snapshot.overall_score:.3f})")
        
        await call_quality_monitor.stop_monitoring(call_sid)
        print("✅ Optimization settings test completed\n")
        
    except Exception as e:
        print(f"❌ Optimization settings test failed: {e}\n")


async def test_system_metrics():
    """Test system-wide metrics and reporting."""
    print("🔍 Testing system metrics...")
    
    try:
        # Start multiple calls with different quality levels
        test_calls = [
            ("excellent_call", False, False, 0.95),
            ("good_call", False, False, 0.8),
            ("fair_call", True, False, 0.6),
            ("poor_call", True, True, 0.4)
        ]
        
        for call_name, add_noise, add_distortion, connection_quality in test_calls:
            call_sid = f"test_{call_name}"
            await call_quality_monitor.start_monitoring(call_sid)
            
            # Generate appropriate audio
            audio = generate_test_audio(
                duration_seconds=1.0,
                add_noise=add_noise,
                add_distortion=add_distortion
            )
            
            await call_quality_monitor.record_audio_metrics(
                call_sid=call_sid,
                audio_data=audio,
                sample_rate=8000
            )
            
            # Performance metrics based on quality level
            base_latency = 500.0 if connection_quality > 0.8 else 1000.0
            await call_quality_monitor.record_performance_metrics(
                call_sid=call_sid,
                stt_latency_ms=base_latency,
                tts_latency_ms=base_latency * 1.2,
                response_generation_ms=base_latency * 2,
                stt_confidence=connection_quality,
                connection_quality=connection_quality
            )
            
            await call_quality_monitor.analyze_call_quality(call_sid)
        
        # Get comprehensive system metrics
        metrics = await call_quality_monitor.get_system_metrics()
        
        print(f"🖥️  System Metrics:")
        print(f"   - Active Calls: {metrics['active_monitored_calls']}")
        print(f"   - Average Quality: {metrics['average_quality_score']:.3f}")
        print(f"   - System Status: {metrics['system_status']}")
        print(f"   - Total Calls Monitored: {metrics['total_calls_monitored']}")
        
        if metrics['current_issue_counts']:
            print(f"   - Current Issues:")
            for issue, count in metrics['current_issue_counts'].items():
                if count > 0:
                    print(f"     * {issue}: {count}")
        
        # Clean up
        for call_name, _, _, _ in test_calls:
            call_sid = f"test_{call_name}"
            await call_quality_monitor.stop_monitoring(call_sid)
        
        print("✅ System metrics test completed\n")
        
    except Exception as e:
        print(f"❌ System metrics test failed: {e}\n")


async def main():
    """Run all call quality monitoring tests."""
    print("🚀 Starting Call Quality Monitoring Tests\n")
    print("=" * 60)
    
    # Run all tests
    await test_basic_monitoring()
    await test_poor_quality_detection()
    await test_concurrent_monitoring()
    await test_optimization_settings()
    await test_system_metrics()
    
    print("=" * 60)
    print("🎉 All Call Quality Monitoring tests completed!")
    
    # Final system check
    final_metrics = await call_quality_monitor.get_system_metrics()
    print(f"📊 Final System State:")
    print(f"   - Active Calls: {final_metrics['active_monitored_calls']}")
    print(f"   - System Status: {final_metrics['system_status']}")


if __name__ == "__main__":
    asyncio.run(main())