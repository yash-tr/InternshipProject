"""
Tests for Call Quality Monitor service.
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.services.call_quality_monitor import (
    CallQualityMonitor,
    AudioMetrics,
    PerformanceMetrics,
    CallQualitySnapshot,
    OptimizationSettings,
    CallQualityLevel,
    AudioIssueType,
    OptimizationAction,
    CallMonitorSession
)


@pytest.fixture
def call_quality_monitor():
    """Create a CallQualityMonitor instance for testing."""
    return CallQualityMonitor()


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing."""
    # Generate 1 second of sample audio at 8kHz
    sample_rate = 8000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Generate a sine wave with some noise
    frequency = 440  # A4 note
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    audio += 0.1 * np.random.normal(0, 1, len(audio))  # Add noise
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


@pytest.fixture
def optimization_settings():
    """Create sample optimization settings."""
    return OptimizationSettings(
        noise_reduction_enabled=False,
        tts_model="eleven_turbo_v2",
        max_response_length=100,
        response_timeout_ms=5000
    )


class TestCallQualityMonitor:
    """Test cases for CallQualityMonitor."""
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, call_quality_monitor, optimization_settings):
        """Test starting call monitoring."""
        call_sid = "test_call_123"
        
        session = await call_quality_monitor.start_monitoring(
            call_sid=call_sid,
            initial_settings=optimization_settings
        )
        
        assert session.call_sid == call_sid
        assert session.settings == optimization_settings
        assert call_sid in call_quality_monitor.active_monitors
        assert call_sid in call_quality_monitor.quality_history
    
    @pytest.mark.asyncio
    async def test_record_audio_metrics(self, call_quality_monitor, sample_audio_data):
        """Test recording audio metrics."""
        call_sid = "test_call_123"
        
        # Start monitoring first
        await call_quality_monitor.start_monitoring(call_sid)
        
        # Record audio metrics
        metrics = await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=sample_audio_data,
            sample_rate=8000
        )
        
        assert isinstance(metrics, AudioMetrics)
        assert 0.0 <= metrics.volume_level <= 1.0
        assert 0.0 <= metrics.noise_level <= 1.0
        assert metrics.signal_to_noise_ratio > -60  # Reasonable SNR
        assert isinstance(metrics.frequency_response, dict)
        assert 0.0 <= metrics.distortion_level <= 1.0
        assert isinstance(metrics.echo_detected, bool)
        assert metrics.dropout_count >= 0
        assert 0.0 <= metrics.quality_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_record_performance_metrics(self, call_quality_monitor):
        """Test recording performance metrics."""
        call_sid = "test_call_123"
        
        # Start monitoring first
        await call_quality_monitor.start_monitoring(call_sid)
        
        # Record performance metrics
        metrics = await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=500.0,
            tts_latency_ms=700.0,
            response_generation_ms=1500.0,
            stt_confidence=0.9,
            connection_quality=0.8
        )
        
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.stt_latency_ms == 500.0
        assert metrics.tts_latency_ms == 700.0
        assert metrics.response_generation_ms == 1500.0
        assert metrics.total_turn_latency_ms == 2700.0  # Sum of all latencies
        assert metrics.stt_confidence == 0.9
        assert metrics.connection_quality == 0.8
        assert 0.0 <= metrics.performance_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_analyze_call_quality(self, call_quality_monitor, sample_audio_data):
        """Test call quality analysis."""
        call_sid = "test_call_123"
        
        # Start monitoring
        await call_quality_monitor.start_monitoring(call_sid)
        
        # Record some metrics
        await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=sample_audio_data,
            sample_rate=8000
        )
        
        await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=600.0,
            tts_latency_ms=800.0,
            response_generation_ms=2000.0,
            stt_confidence=0.8,
            connection_quality=0.9
        )
        
        # Analyze quality
        snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
        
        assert isinstance(snapshot, CallQualitySnapshot)
        assert snapshot.call_sid == call_sid
        assert isinstance(snapshot.audio_metrics, AudioMetrics)
        assert isinstance(snapshot.performance_metrics, PerformanceMetrics)
        assert isinstance(snapshot.detected_issues, list)
        assert isinstance(snapshot.quality_level, CallQualityLevel)
        assert isinstance(snapshot.optimization_actions, list)
        assert 0.0 <= snapshot.overall_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_issue_detection(self, call_quality_monitor):
        """Test audio issue detection."""
        # Create metrics with known issues
        audio_metrics = AudioMetrics(
            timestamp=datetime.utcnow(),
            volume_level=0.1,  # Low volume
            noise_level=0.4,   # High noise
            signal_to_noise_ratio=5.0,
            frequency_response={"low": 0.5, "mid": 0.5, "high": 0.3},
            distortion_level=0.3,  # High distortion
            echo_detected=True,    # Echo present
            dropout_count=5        # Many dropouts
        )
        
        performance_metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            stt_latency_ms=800.0,
            tts_latency_ms=1600.0,  # High TTS latency
            response_generation_ms=3000.0,
            total_turn_latency_ms=12000.0,  # High total latency
            stt_confidence=0.6,  # Low STT confidence
            stt_word_error_rate=0.4,
            connection_quality=0.7,
            packet_loss_rate=0.05,
            jitter_ms=30.0
        )
        
        # Test issue detection
        issues = call_quality_monitor._detect_issues(audio_metrics, performance_metrics)
        
        expected_issues = {
            AudioIssueType.LOW_VOLUME,
            AudioIssueType.BACKGROUND_NOISE,
            AudioIssueType.ECHO,
            AudioIssueType.DISTORTION,
            AudioIssueType.DROPOUTS,
            AudioIssueType.HIGH_LATENCY,
            AudioIssueType.POOR_STT_ACCURACY,
            AudioIssueType.TTS_DELAYS
        }
        
        assert set(issues) == expected_issues
    
    @pytest.mark.asyncio
    async def test_optimization_actions(self, call_quality_monitor):
        """Test optimization action generation."""
        issues = [
            AudioIssueType.BACKGROUND_NOISE,
            AudioIssueType.HIGH_LATENCY,
            AudioIssueType.TTS_DELAYS
        ]
        
        settings = OptimizationSettings(
            noise_reduction_enabled=False,
            tts_model="eleven_turbo_v2",
            max_response_length=150
        )
        
        actions = call_quality_monitor._generate_optimization_actions(issues, settings)
        
        expected_actions = {
            OptimizationAction.ENABLE_NOISE_REDUCTION,
            OptimizationAction.ADJUST_AUDIO_SETTINGS,
            OptimizationAction.SWITCH_TTS_MODEL,
            OptimizationAction.REDUCE_RESPONSE_LENGTH,
            OptimizationAction.INCREASE_TIMEOUT
        }
        
        assert set(actions).issubset(expected_actions)
        assert OptimizationAction.ENABLE_NOISE_REDUCTION in actions
    
    @pytest.mark.asyncio
    async def test_apply_optimizations(self, call_quality_monitor):
        """Test applying optimization actions."""
        call_sid = "test_call_123"
        
        # Start monitoring
        session = await call_quality_monitor.start_monitoring(call_sid)
        original_settings = session.settings
        
        actions = [
            OptimizationAction.ENABLE_NOISE_REDUCTION,
            OptimizationAction.SWITCH_TTS_MODEL,
            OptimizationAction.REDUCE_RESPONSE_LENGTH
        ]
        
        # Apply optimizations
        await call_quality_monitor._apply_optimizations(call_sid, actions, session)
        
        # Check that settings were updated
        assert session.settings.noise_reduction_enabled == True
        assert session.settings.tts_model == "eleven_turbo_v2_5"
        assert session.settings.max_response_length < original_settings.max_response_length
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, call_quality_monitor, sample_audio_data):
        """Test stopping call monitoring."""
        call_sid = "test_call_123"
        
        # Start monitoring and record some data
        await call_quality_monitor.start_monitoring(call_sid)
        
        await call_quality_monitor.record_audio_metrics(
            call_sid=call_sid,
            audio_data=sample_audio_data,
            sample_rate=8000
        )
        
        await call_quality_monitor.record_performance_metrics(
            call_sid=call_sid,
            stt_latency_ms=600.0,
            tts_latency_ms=800.0,
            response_generation_ms=2000.0
        )
        
        # Analyze quality to create history
        await call_quality_monitor.analyze_call_quality(call_sid)
        
        # Stop monitoring
        report = await call_quality_monitor.stop_monitoring(call_sid)
        
        assert report is not None
        assert report["call_sid"] == call_sid
        assert "monitoring_duration_minutes" in report
        assert "total_snapshots" in report
        assert "average_overall_score" in report
        assert call_sid not in call_quality_monitor.active_monitors
        assert call_sid not in call_quality_monitor.quality_history
    
    @pytest.mark.asyncio
    async def test_system_metrics(self, call_quality_monitor):
        """Test getting system-wide metrics."""
        # Start monitoring multiple calls
        call_sids = ["call_1", "call_2", "call_3"]
        
        for call_sid in call_sids:
            await call_quality_monitor.start_monitoring(call_sid)
        
        # Get system metrics
        metrics = await call_quality_monitor.get_system_metrics()
        
        assert metrics["active_monitored_calls"] == 3
        assert "average_quality_score" in metrics
        assert "current_issue_counts" in metrics
        assert "system_status" in metrics
    
    def test_quality_level_determination(self, call_quality_monitor):
        """Test quality level determination."""
        assert call_quality_monitor._determine_quality_level(0.95) == CallQualityLevel.EXCELLENT
        assert call_quality_monitor._determine_quality_level(0.8) == CallQualityLevel.GOOD
        assert call_quality_monitor._determine_quality_level(0.6) == CallQualityLevel.FAIR
        assert call_quality_monitor._determine_quality_level(0.4) == CallQualityLevel.POOR
        assert call_quality_monitor._determine_quality_level(0.2) == CallQualityLevel.CRITICAL


class TestAudioMetrics:
    """Test cases for AudioMetrics."""
    
    def test_quality_score_calculation(self):
        """Test audio quality score calculation."""
        # Perfect audio
        perfect_metrics = AudioMetrics(
            timestamp=datetime.utcnow(),
            volume_level=0.7,
            noise_level=0.0,
            signal_to_noise_ratio=30.0,
            frequency_response={"low": 0.5, "mid": 0.5, "high": 0.3},
            distortion_level=0.0,
            echo_detected=False,
            dropout_count=0
        )
        
        assert perfect_metrics.quality_score > 0.9
        
        # Poor audio
        poor_metrics = AudioMetrics(
            timestamp=datetime.utcnow(),
            volume_level=0.1,
            noise_level=0.8,
            signal_to_noise_ratio=5.0,
            frequency_response={"low": 0.2, "mid": 0.2, "high": 0.1},
            distortion_level=0.5,
            echo_detected=True,
            dropout_count=10
        )
        
        assert poor_metrics.quality_score < 0.3


class TestPerformanceMetrics:
    """Test cases for PerformanceMetrics."""
    
    def test_performance_score_calculation(self):
        """Test performance score calculation."""
        # Excellent performance
        excellent_metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            stt_latency_ms=400.0,
            tts_latency_ms=600.0,
            response_generation_ms=1000.0,
            total_turn_latency_ms=2000.0,
            stt_confidence=0.95,
            stt_word_error_rate=0.05,
            connection_quality=0.95,
            packet_loss_rate=0.01,
            jitter_ms=10.0
        )
        
        assert excellent_metrics.performance_score > 0.8
        
        # Poor performance
        poor_metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            stt_latency_ms=2000.0,
            tts_latency_ms=3000.0,
            response_generation_ms=8000.0,
            total_turn_latency_ms=13000.0,
            stt_confidence=0.5,
            stt_word_error_rate=0.5,
            connection_quality=0.3,
            packet_loss_rate=0.2,
            jitter_ms=100.0
        )
        
        assert poor_metrics.performance_score < 0.3


class TestCallMonitorSession:
    """Test cases for CallMonitorSession."""
    
    def test_session_creation(self, call_quality_monitor, optimization_settings):
        """Test monitor session creation."""
        call_sid = "test_call_123"
        
        session = CallMonitorSession(
            call_sid=call_sid,
            monitor=call_quality_monitor,
            settings=optimization_settings
        )
        
        assert session.call_sid == call_sid
        assert session.monitor == call_quality_monitor
        assert session.settings == optimization_settings
        assert len(session.audio_metrics_history) == 0
        assert len(session.performance_metrics_history) == 0
    
    def test_metrics_history(self, call_quality_monitor, optimization_settings):
        """Test metrics history management."""
        call_sid = "test_call_123"
        
        session = CallMonitorSession(
            call_sid=call_sid,
            monitor=call_quality_monitor,
            settings=optimization_settings
        )
        
        # Add audio metrics
        audio_metrics = AudioMetrics(
            timestamp=datetime.utcnow(),
            volume_level=0.5,
            noise_level=0.1,
            signal_to_noise_ratio=20.0,
            frequency_response={"low": 0.5, "mid": 0.5, "high": 0.3},
            distortion_level=0.0,
            echo_detected=False,
            dropout_count=0
        )
        
        session.add_audio_metrics(audio_metrics)
        assert len(session.audio_metrics_history) == 1
        assert session.get_latest_audio_metrics() == audio_metrics
        
        # Add performance metrics
        performance_metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            stt_latency_ms=600.0,
            tts_latency_ms=800.0,
            response_generation_ms=2000.0,
            total_turn_latency_ms=3400.0,
            stt_confidence=0.9,
            stt_word_error_rate=0.1,
            connection_quality=0.8,
            packet_loss_rate=0.02,
            jitter_ms=20.0
        )
        
        session.add_performance_metrics(performance_metrics)
        assert len(session.performance_metrics_history) == 1
        assert session.get_latest_performance_metrics() == performance_metrics


class TestOptimizationSettings:
    """Test cases for OptimizationSettings."""
    
    def test_default_settings(self):
        """Test default optimization settings."""
        settings = OptimizationSettings()
        
        assert settings.noise_reduction_enabled == False
        assert settings.noise_reduction_strength == 0.5
        assert settings.volume_boost == 1.0
        assert settings.echo_cancellation == True
        assert settings.tts_model == "eleven_turbo_v2"
        assert settings.speech_rate == 1.0
        assert settings.max_response_length == 150
        assert settings.response_timeout_ms == 5000
    
    def test_custom_settings(self):
        """Test custom optimization settings."""
        settings = OptimizationSettings(
            noise_reduction_enabled=True,
            tts_model="eleven_turbo_v2_5",
            max_response_length=80,
            response_timeout_ms=8000
        )
        
        assert settings.noise_reduction_enabled == True
        assert settings.tts_model == "eleven_turbo_v2_5"
        assert settings.max_response_length == 80
        assert settings.response_timeout_ms == 8000


@pytest.mark.asyncio
async def test_error_handling(call_quality_monitor):
    """Test error handling in call quality monitoring."""
    # Test with non-existent call
    snapshot = await call_quality_monitor.analyze_call_quality("non_existent_call")
    assert snapshot is None
    
    # Test stopping non-existent monitoring
    report = await call_quality_monitor.stop_monitoring("non_existent_call")
    assert report is None
    
    # Test with invalid audio data
    metrics = await call_quality_monitor.record_audio_metrics(
        call_sid="test_call",
        audio_data=b"invalid_audio_data",
        sample_rate=8000
    )
    
    # Should return default metrics on error
    assert isinstance(metrics, AudioMetrics)
    assert metrics.volume_level >= 0.0


@pytest.mark.asyncio
async def test_concurrent_monitoring(call_quality_monitor):
    """Test concurrent call monitoring."""
    call_sids = [f"call_{i}" for i in range(5)]
    
    # Start monitoring multiple calls concurrently
    tasks = [
        call_quality_monitor.start_monitoring(call_sid)
        for call_sid in call_sids
    ]
    
    sessions = await asyncio.gather(*tasks)
    
    assert len(sessions) == 5
    assert len(call_quality_monitor.active_monitors) == 5
    
    # Stop all monitoring
    stop_tasks = [
        call_quality_monitor.stop_monitoring(call_sid)
        for call_sid in call_sids
    ]
    
    reports = await asyncio.gather(*stop_tasks)
    
    assert len([r for r in reports if r is not None]) == 5
    assert len(call_quality_monitor.active_monitors) == 0