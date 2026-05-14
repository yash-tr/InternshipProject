"""
Call Quality and Performance Optimization Service

This module implements real-time call quality monitoring, STT/TTS optimization,
and adaptive audio settings for the AI Calling Agent MVP. It provides
comprehensive call analytics and performance tracking with automatic
quality adjustments based on connection conditions.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import statistics
from collections import deque
import numpy as np
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..services.audit_trail import audit_service, AuditEventType
from ..utils.encryption import encrypt_pii_data

logger = logging.getLogger(__name__)
settings = get_settings()


class CallQualityLevel(str, Enum):
    """Call quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class AudioIssueType(str, Enum):
    """Types of audio issues."""
    HIGH_LATENCY = "high_latency"
    LOW_VOLUME = "low_volume"
    BACKGROUND_NOISE = "background_noise"
    ECHO = "echo"
    DISTORTION = "distortion"
    DROPOUTS = "dropouts"
    POOR_STT_ACCURACY = "poor_stt_accuracy"
    TTS_DELAYS = "tts_delays"


class OptimizationAction(str, Enum):
    """Optimization actions that can be taken."""
    ADJUST_AUDIO_SETTINGS = "adjust_audio_settings"
    SWITCH_TTS_MODEL = "switch_tts_model"
    REDUCE_RESPONSE_LENGTH = "reduce_response_length"
    INCREASE_TIMEOUT = "increase_timeout"
    ENABLE_NOISE_REDUCTION = "enable_noise_reduction"
    FALLBACK_TO_HUMAN = "fallback_to_human"


@dataclass
class AudioMetrics:
    """Audio quality metrics."""
    timestamp: datetime
    volume_level: float  # 0.0 to 1.0
    noise_level: float  # 0.0 to 1.0
    signal_to_noise_ratio: float  # dB
    frequency_response: Dict[str, float]  # Frequency bands
    distortion_level: float  # 0.0 to 1.0
    echo_detected: bool
    dropout_count: int
    
    @property
    def quality_score(self) -> float:
        """Calculate overall audio quality score (0.0 to 1.0)."""
        # Weighted scoring based on key metrics
        volume_score = min(self.volume_level * 2, 1.0) if self.volume_level < 0.5 else 1.0
        noise_score = 1.0 - self.noise_level
        snr_score = min(self.signal_to_noise_ratio / 20.0, 1.0)  # 20dB = perfect
        distortion_score = 1.0 - self.distortion_level
        echo_penalty = 0.3 if self.echo_detected else 0.0
        dropout_penalty = min(self.dropout_count * 0.1, 0.5)
        
        # Weighted average
        score = (
            volume_score * 0.2 +
            noise_score * 0.3 +
            snr_score * 0.3 +
            distortion_score * 0.2
        ) - echo_penalty - dropout_penalty
        
        return max(0.0, min(1.0, score))


@dataclass
class PerformanceMetrics:
    """Call performance metrics."""
    timestamp: datetime
    stt_latency_ms: float  # Speech-to-text first token latency
    tts_latency_ms: float  # Text-to-speech first audio latency
    response_generation_ms: float  # AI response generation time
    total_turn_latency_ms: float  # End-to-end turn latency
    stt_confidence: float  # STT confidence score
    stt_word_error_rate: float  # Word error rate
    connection_quality: float  # Network connection quality (0.0 to 1.0)
    packet_loss_rate: float  # Network packet loss rate
    jitter_ms: float  # Network jitter
    
    @property
    def performance_score(self) -> float:
        """Calculate overall performance score (0.0 to 1.0)."""
        # Latency scoring (lower is better)
        stt_score = max(0.0, 1.0 - (self.stt_latency_ms - 600) / 1000)  # 600ms target
        tts_score = max(0.0, 1.0 - (self.tts_latency_ms - 800) / 1200)  # 800ms target
        response_score = max(0.0, 1.0 - (self.response_generation_ms - 2000) / 3000)  # 2s target
        total_score = max(0.0, 1.0 - (self.total_turn_latency_ms - 8000) / 7000)  # 8s target
        
        # Accuracy and connection scoring
        stt_accuracy_score = self.stt_confidence
        connection_score = self.connection_quality
        
        # Weighted average
        score = (
            stt_score * 0.2 +
            tts_score * 0.2 +
            response_score * 0.15 +
            total_score * 0.25 +
            stt_accuracy_score * 0.1 +
            connection_score * 0.1
        )
        
        return max(0.0, min(1.0, score))


@dataclass
class CallQualitySnapshot:
    """Complete call quality snapshot."""
    call_sid: str
    timestamp: datetime
    audio_metrics: AudioMetrics
    performance_metrics: PerformanceMetrics
    detected_issues: List[AudioIssueType]
    quality_level: CallQualityLevel
    optimization_actions: List[OptimizationAction]
    
    @property
    def overall_score(self) -> float:
        """Calculate overall call quality score."""
        audio_weight = 0.6
        performance_weight = 0.4
        return (
            self.audio_metrics.quality_score * audio_weight +
            self.performance_metrics.performance_score * performance_weight
        )


@dataclass
class OptimizationSettings:
    """Adaptive optimization settings."""
    # Audio settings
    noise_reduction_enabled: bool = False
    noise_reduction_strength: float = 0.5  # 0.0 to 1.0
    volume_boost: float = 1.0  # Multiplier
    echo_cancellation: bool = True
    
    # TTS settings
    tts_model: str = "eleven_turbo_v2"  # ElevenLabs model
    speech_rate: float = 1.0  # 0.5 to 2.0
    stability: float = 0.5  # 0.0 to 1.0
    similarity_boost: float = 0.75  # 0.0 to 1.0
    
    # Response settings
    max_response_length: int = 150  # tokens
    response_timeout_ms: int = 5000
    
    # Connection settings
    connection_timeout_ms: int = 10000
    retry_attempts: int = 3
    adaptive_bitrate: bool = True


class CallQualityMonitor:
    """
    Real-time call quality monitoring and optimization service.
    
    Provides comprehensive monitoring of audio quality, performance metrics,
    and automatic optimization based on detected issues and connection conditions.
    """
    
    def __init__(self):
        self.active_monitors: Dict[str, 'CallMonitorSession'] = {}
        self.quality_history: Dict[str, deque] = {}  # Rolling history per call
        self.global_metrics: Dict[str, Any] = {}
        self.optimization_rules: Dict[AudioIssueType, List[OptimizationAction]] = self._init_optimization_rules()
        
        logger.info("Call Quality Monitor initialized")
    
    def _init_optimization_rules(self) -> Dict[AudioIssueType, List[OptimizationAction]]:
        """Initialize optimization rules for different audio issues."""
        return {
            AudioIssueType.HIGH_LATENCY: [
                OptimizationAction.SWITCH_TTS_MODEL,
                OptimizationAction.REDUCE_RESPONSE_LENGTH,
                OptimizationAction.INCREASE_TIMEOUT
            ],
            AudioIssueType.LOW_VOLUME: [
                OptimizationAction.ADJUST_AUDIO_SETTINGS
            ],
            AudioIssueType.BACKGROUND_NOISE: [
                OptimizationAction.ENABLE_NOISE_REDUCTION,
                OptimizationAction.ADJUST_AUDIO_SETTINGS
            ],
            AudioIssueType.ECHO: [
                OptimizationAction.ADJUST_AUDIO_SETTINGS
            ],
            AudioIssueType.DISTORTION: [
                OptimizationAction.ADJUST_AUDIO_SETTINGS,
                OptimizationAction.SWITCH_TTS_MODEL
            ],
            AudioIssueType.DROPOUTS: [
                OptimizationAction.INCREASE_TIMEOUT,
                OptimizationAction.FALLBACK_TO_HUMAN
            ],
            AudioIssueType.POOR_STT_ACCURACY: [
                OptimizationAction.ENABLE_NOISE_REDUCTION,
                OptimizationAction.INCREASE_TIMEOUT
            ],
            AudioIssueType.TTS_DELAYS: [
                OptimizationAction.SWITCH_TTS_MODEL,
                OptimizationAction.REDUCE_RESPONSE_LENGTH
            ]
        }
    
    async def start_monitoring(self, 
                             call_sid: str,
                             initial_settings: Optional[OptimizationSettings] = None) -> 'CallMonitorSession':
        """
        Start monitoring a call session.
        
        Args:
            call_sid: Twilio Call SID
            initial_settings: Initial optimization settings
            
        Returns:
            CallMonitorSession instance
        """
        try:
            if call_sid in self.active_monitors:
                logger.warning(f"Monitor already exists for call {call_sid}")
                return self.active_monitors[call_sid]
            
            # Create monitor session
            session = CallMonitorSession(
                call_sid=call_sid,
                monitor=self,
                settings=initial_settings or OptimizationSettings()
            )
            
            self.active_monitors[call_sid] = session
            self.quality_history[call_sid] = deque(maxlen=100)  # Keep last 100 snapshots
            
            # Log monitoring start
            await audit_service.log_event(
                event_type=AuditEventType.CALL_INITIATED,
                entity_type="call_quality_monitor",
                entity_id=call_sid,
                details={
                    "monitoring_started": True,
                    "initial_settings": initial_settings.__dict__ if initial_settings else None
                }
            )
            
            logger.info(f"Started quality monitoring for call {call_sid}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to start monitoring for call {call_sid}: {e}")
            raise
    
    async def record_audio_metrics(self, 
                                 call_sid: str,
                                 audio_data: bytes,
                                 sample_rate: int = 8000) -> AudioMetrics:
        """
        Analyze audio data and record metrics.
        
        Args:
            call_sid: Twilio Call SID
            audio_data: Raw audio data
            sample_rate: Audio sample rate
            
        Returns:
            AudioMetrics instance
        """
        try:
            # Convert audio data to numpy array for analysis
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Calculate audio metrics
            volume_level = float(np.sqrt(np.mean(audio_array ** 2)))  # RMS volume
            
            # Simple noise estimation (high-frequency content)
            if len(audio_array) > sample_rate // 10:  # At least 100ms of audio
                # High-pass filter approximation for noise estimation
                diff = np.diff(audio_array)
                noise_level = float(np.sqrt(np.mean(diff ** 2)))
            else:
                noise_level = 0.0
            
            # Signal-to-noise ratio estimation
            if noise_level > 0:
                snr = 20 * np.log10(volume_level / noise_level) if volume_level > 0 else -60
            else:
                snr = 60.0  # Assume good SNR if no noise detected
            
            # Frequency response analysis (simplified)
            if len(audio_array) >= 1024:
                fft = np.fft.fft(audio_array[:1024])
                freqs = np.fft.fftfreq(1024, 1/sample_rate)
                magnitude = np.abs(fft)
                
                # Analyze key frequency bands
                low_band = np.mean(magnitude[(freqs >= 300) & (freqs <= 1000)])
                mid_band = np.mean(magnitude[(freqs >= 1000) & (freqs <= 3000)])
                high_band = np.mean(magnitude[(freqs >= 3000) & (freqs <= 4000)])
                
                frequency_response = {
                    "low": float(low_band),
                    "mid": float(mid_band),
                    "high": float(high_band)
                }
            else:
                frequency_response = {"low": 0.0, "mid": 0.0, "high": 0.0}
            
            # Distortion detection (simplified THD estimation)
            if len(audio_array) >= 512:
                # Look for clipping
                clipping_ratio = np.sum(np.abs(audio_array) > 0.95) / len(audio_array)
                distortion_level = float(min(clipping_ratio * 10, 1.0))
            else:
                distortion_level = 0.0
            
            # Echo detection (simplified autocorrelation)
            echo_detected = False
            if len(audio_array) >= sample_rate // 4:  # At least 250ms
                # Look for strong autocorrelation at typical echo delays (50-200ms)
                delay_samples = range(sample_rate // 20, sample_rate // 5)  # 50-200ms
                for delay in delay_samples:
                    if delay < len(audio_array):
                        correlation = np.corrcoef(
                            audio_array[:-delay], 
                            audio_array[delay:]
                        )[0, 1]
                        if not np.isnan(correlation) and correlation > 0.7:
                            echo_detected = True
                            break
            
            # Dropout detection (silence periods)
            silence_threshold = 0.01
            silence_mask = np.abs(audio_array) < silence_threshold
            if len(silence_mask) > 0:
                # Count transitions from sound to silence
                transitions = np.diff(silence_mask.astype(int))
                dropout_count = int(np.sum(transitions == 1))
            else:
                dropout_count = 0
            
            metrics = AudioMetrics(
                timestamp=datetime.utcnow(),
                volume_level=volume_level,
                noise_level=noise_level,
                signal_to_noise_ratio=snr,
                frequency_response=frequency_response,
                distortion_level=distortion_level,
                echo_detected=echo_detected,
                dropout_count=dropout_count
            )
            
            # Store metrics in session if exists
            if call_sid in self.active_monitors:
                self.active_monitors[call_sid].add_audio_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing audio metrics for call {call_sid}: {e}")
            # Return default metrics on error
            return AudioMetrics(
                timestamp=datetime.utcnow(),
                volume_level=0.5,
                noise_level=0.1,
                signal_to_noise_ratio=20.0,
                frequency_response={"low": 0.5, "mid": 0.5, "high": 0.3},
                distortion_level=0.0,
                echo_detected=False,
                dropout_count=0
            )
    
    async def record_performance_metrics(self,
                                       call_sid: str,
                                       stt_latency_ms: float,
                                       tts_latency_ms: float,
                                       response_generation_ms: float,
                                       stt_confidence: float = 1.0,
                                       connection_quality: float = 1.0) -> PerformanceMetrics:
        """
        Record performance metrics for a call turn.
        
        Args:
            call_sid: Twilio Call SID
            stt_latency_ms: Speech-to-text latency
            tts_latency_ms: Text-to-speech latency
            response_generation_ms: AI response generation time
            stt_confidence: STT confidence score
            connection_quality: Network connection quality
            
        Returns:
            PerformanceMetrics instance
        """
        try:
            total_latency = stt_latency_ms + response_generation_ms + tts_latency_ms
            
            # Estimate word error rate based on confidence
            word_error_rate = max(0.0, 1.0 - stt_confidence)
            
            # Simulate network metrics (in production, these would come from Twilio)
            packet_loss_rate = max(0.0, 1.0 - connection_quality) * 0.1
            jitter_ms = max(0.0, 1.0 - connection_quality) * 50
            
            metrics = PerformanceMetrics(
                timestamp=datetime.utcnow(),
                stt_latency_ms=stt_latency_ms,
                tts_latency_ms=tts_latency_ms,
                response_generation_ms=response_generation_ms,
                total_turn_latency_ms=total_latency,
                stt_confidence=stt_confidence,
                stt_word_error_rate=word_error_rate,
                connection_quality=connection_quality,
                packet_loss_rate=packet_loss_rate,
                jitter_ms=jitter_ms
            )
            
            # Store metrics in session if exists
            if call_sid in self.active_monitors:
                self.active_monitors[call_sid].add_performance_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error recording performance metrics for call {call_sid}: {e}")
            raise
    
    async def analyze_call_quality(self, call_sid: str) -> Optional[CallQualitySnapshot]:
        """
        Analyze current call quality and generate recommendations.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            CallQualitySnapshot with analysis and recommendations
        """
        try:
            session = self.active_monitors.get(call_sid)
            if not session:
                logger.warning(f"No monitor session found for call {call_sid}")
                return None
            
            # Get latest metrics
            latest_audio = session.get_latest_audio_metrics()
            latest_performance = session.get_latest_performance_metrics()
            
            if not latest_audio or not latest_performance:
                logger.warning(f"Insufficient metrics for call {call_sid}")
                return None
            
            # Detect issues
            detected_issues = self._detect_issues(latest_audio, latest_performance)
            
            # Determine quality level
            overall_score = (latest_audio.quality_score + latest_performance.performance_score) / 2
            quality_level = self._determine_quality_level(overall_score)
            
            # Generate optimization actions
            optimization_actions = self._generate_optimization_actions(detected_issues, session.settings)
            
            snapshot = CallQualitySnapshot(
                call_sid=call_sid,
                timestamp=datetime.utcnow(),
                audio_metrics=latest_audio,
                performance_metrics=latest_performance,
                detected_issues=detected_issues,
                quality_level=quality_level,
                optimization_actions=optimization_actions
            )
            
            # Store in history
            self.quality_history[call_sid].append(snapshot)
            
            # Apply optimizations if needed
            if optimization_actions:
                await self._apply_optimizations(call_sid, optimization_actions, session)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error analyzing call quality for {call_sid}: {e}")
            return None
    
    def _detect_issues(self, 
                      audio_metrics: AudioMetrics, 
                      performance_metrics: PerformanceMetrics) -> List[AudioIssueType]:
        """Detect audio and performance issues."""
        issues = []
        
        # Audio issues
        if audio_metrics.volume_level < 0.2:
            issues.append(AudioIssueType.LOW_VOLUME)
        
        if audio_metrics.noise_level > 0.3:
            issues.append(AudioIssueType.BACKGROUND_NOISE)
        
        if audio_metrics.echo_detected:
            issues.append(AudioIssueType.ECHO)
        
        if audio_metrics.distortion_level > 0.2:
            issues.append(AudioIssueType.DISTORTION)
        
        if audio_metrics.dropout_count > 3:
            issues.append(AudioIssueType.DROPOUTS)
        
        # Performance issues
        if performance_metrics.total_turn_latency_ms > 10000:  # 10 seconds
            issues.append(AudioIssueType.HIGH_LATENCY)
        
        if performance_metrics.stt_confidence < 0.7:
            issues.append(AudioIssueType.POOR_STT_ACCURACY)
        
        if performance_metrics.tts_latency_ms > 1500:  # 1.5 seconds
            issues.append(AudioIssueType.TTS_DELAYS)
        
        return issues
    
    def _determine_quality_level(self, overall_score: float) -> CallQualityLevel:
        """Determine quality level based on overall score."""
        if overall_score >= 0.9:
            return CallQualityLevel.EXCELLENT
        elif overall_score >= 0.7:
            return CallQualityLevel.GOOD
        elif overall_score >= 0.5:
            return CallQualityLevel.FAIR
        elif overall_score >= 0.3:
            return CallQualityLevel.POOR
        else:
            return CallQualityLevel.CRITICAL
    
    def _generate_optimization_actions(self, 
                                     issues: List[AudioIssueType],
                                     current_settings: OptimizationSettings) -> List[OptimizationAction]:
        """Generate optimization actions based on detected issues."""
        actions = set()
        
        for issue in issues:
            if issue in self.optimization_rules:
                actions.update(self.optimization_rules[issue])
        
        # Filter out actions already applied
        filtered_actions = []
        for action in actions:
            if self._should_apply_action(action, current_settings):
                filtered_actions.append(action)
        
        return filtered_actions
    
    def _should_apply_action(self, 
                           action: OptimizationAction, 
                           settings: OptimizationSettings) -> bool:
        """Check if optimization action should be applied."""
        if action == OptimizationAction.ENABLE_NOISE_REDUCTION:
            return not settings.noise_reduction_enabled
        elif action == OptimizationAction.SWITCH_TTS_MODEL:
            return settings.tts_model != "eleven_turbo_v2_5"  # Faster model
        elif action == OptimizationAction.REDUCE_RESPONSE_LENGTH:
            return settings.max_response_length > 80
        elif action == OptimizationAction.INCREASE_TIMEOUT:
            return settings.response_timeout_ms < 8000
        else:
            return True
    
    async def _apply_optimizations(self,
                                 call_sid: str,
                                 actions: List[OptimizationAction],
                                 session: 'CallMonitorSession'):
        """Apply optimization actions to improve call quality."""
        try:
            settings = session.settings
            applied_actions = []
            
            for action in actions:
                if action == OptimizationAction.ENABLE_NOISE_REDUCTION:
                    settings.noise_reduction_enabled = True
                    settings.noise_reduction_strength = 0.7
                    applied_actions.append(action)
                
                elif action == OptimizationAction.ADJUST_AUDIO_SETTINGS:
                    settings.volume_boost = min(settings.volume_boost * 1.2, 2.0)
                    settings.echo_cancellation = True
                    applied_actions.append(action)
                
                elif action == OptimizationAction.SWITCH_TTS_MODEL:
                    settings.tts_model = "eleven_turbo_v2_5"  # Faster model
                    applied_actions.append(action)
                
                elif action == OptimizationAction.REDUCE_RESPONSE_LENGTH:
                    settings.max_response_length = max(settings.max_response_length - 20, 50)
                    applied_actions.append(action)
                
                elif action == OptimizationAction.INCREASE_TIMEOUT:
                    settings.response_timeout_ms = min(settings.response_timeout_ms + 1000, 10000)
                    applied_actions.append(action)
            
            if applied_actions:
                # Log optimization actions
                await audit_service.log_event(
                    event_type=AuditEventType.SYSTEM_OPTIMIZATION,
                    entity_type="call_quality_monitor",
                    entity_id=call_sid,
                    details={
                        "applied_actions": [action.value for action in applied_actions],
                        "new_settings": settings.__dict__
                    }
                )
                
                logger.info(f"Applied optimizations for call {call_sid}: {applied_actions}")
            
        except Exception as e:
            logger.error(f"Error applying optimizations for call {call_sid}: {e}")
    
    async def stop_monitoring(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """
        Stop monitoring a call and return final metrics.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            Final call quality report
        """
        try:
            session = self.active_monitors.pop(call_sid, None)
            if not session:
                logger.warning(f"No monitor session found for call {call_sid}")
                return None
            
            # Generate final report
            history = list(self.quality_history.get(call_sid, []))
            
            if history:
                # Calculate aggregate metrics
                audio_scores = [snapshot.audio_metrics.quality_score for snapshot in history]
                performance_scores = [snapshot.performance_metrics.performance_score for snapshot in history]
                overall_scores = [snapshot.overall_score for snapshot in history]
                
                final_report = {
                    "call_sid": call_sid,
                    "monitoring_duration_minutes": (datetime.utcnow() - session.start_time).total_seconds() / 60,
                    "total_snapshots": len(history),
                    "final_quality_level": history[-1].quality_level.value if history else "unknown",
                    "average_audio_score": statistics.mean(audio_scores) if audio_scores else 0.0,
                    "average_performance_score": statistics.mean(performance_scores) if performance_scores else 0.0,
                    "average_overall_score": statistics.mean(overall_scores) if overall_scores else 0.0,
                    "min_overall_score": min(overall_scores) if overall_scores else 0.0,
                    "max_overall_score": max(overall_scores) if overall_scores else 0.0,
                    "total_issues_detected": sum(len(snapshot.detected_issues) for snapshot in history),
                    "total_optimizations_applied": sum(len(snapshot.optimization_actions) for snapshot in history),
                    "final_settings": session.settings.__dict__
                }
            else:
                final_report = {
                    "call_sid": call_sid,
                    "monitoring_duration_minutes": 0,
                    "total_snapshots": 0,
                    "error": "No quality data collected"
                }
            
            # Clean up history
            self.quality_history.pop(call_sid, None)
            
            # Log monitoring end
            await audit_service.log_event(
                event_type=AuditEventType.CALL_COMPLETED,
                entity_type="call_quality_monitor",
                entity_id=call_sid,
                details=final_report
            )
            
            logger.info(f"Stopped quality monitoring for call {call_sid}")
            return final_report
            
        except Exception as e:
            logger.error(f"Error stopping monitoring for call {call_sid}: {e}")
            return None
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide call quality metrics."""
        try:
            active_calls = len(self.active_monitors)
            
            # Aggregate metrics from active sessions
            if active_calls > 0:
                current_scores = []
                current_issues = []
                
                for session in self.active_monitors.values():
                    latest_audio = session.get_latest_audio_metrics()
                    latest_performance = session.get_latest_performance_metrics()
                    
                    if latest_audio and latest_performance:
                        score = (latest_audio.quality_score + latest_performance.performance_score) / 2
                        current_scores.append(score)
                        
                        issues = self._detect_issues(latest_audio, latest_performance)
                        current_issues.extend(issues)
                
                avg_quality = statistics.mean(current_scores) if current_scores else 0.0
                issue_counts = {issue.value: current_issues.count(issue) for issue in AudioIssueType}
            else:
                avg_quality = 0.0
                issue_counts = {}
            
            return {
                "active_monitored_calls": active_calls,
                "average_quality_score": avg_quality,
                "current_issue_counts": issue_counts,
                "total_calls_monitored": len(self.quality_history),
                "system_status": "healthy" if avg_quality > 0.7 else "degraded" if avg_quality > 0.4 else "critical"
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}


class CallMonitorSession:
    """Individual call monitoring session."""
    
    def __init__(self, call_sid: str, monitor: CallQualityMonitor, settings: OptimizationSettings):
        self.call_sid = call_sid
        self.monitor = monitor
        self.settings = settings
        self.start_time = datetime.utcnow()
        self.audio_metrics_history: deque = deque(maxlen=50)
        self.performance_metrics_history: deque = deque(maxlen=50)
    
    def add_audio_metrics(self, metrics: AudioMetrics):
        """Add audio metrics to session history."""
        self.audio_metrics_history.append(metrics)
    
    def add_performance_metrics(self, metrics: PerformanceMetrics):
        """Add performance metrics to session history."""
        self.performance_metrics_history.append(metrics)
    
    def get_latest_audio_metrics(self) -> Optional[AudioMetrics]:
        """Get latest audio metrics."""
        return self.audio_metrics_history[-1] if self.audio_metrics_history else None
    
    def get_latest_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """Get latest performance metrics."""
        return self.performance_metrics_history[-1] if self.performance_metrics_history else None


# Global instance
call_quality_monitor = CallQualityMonitor()