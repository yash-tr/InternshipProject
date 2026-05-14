# Call Quality Monitoring System

## Overview

The Call Quality Monitoring system provides real-time analysis and optimization of call quality for the AI Calling Agent MVP. It monitors audio quality, performance metrics, and automatically applies optimizations to improve call experience while maintaining strict cost controls.

## Features

### Real-Time Audio Analysis
- **Volume Level Detection**: Monitors audio volume and detects low volume issues
- **Noise Level Analysis**: Identifies background noise and interference
- **Signal-to-Noise Ratio**: Calculates SNR for audio clarity assessment
- **Frequency Response Analysis**: Analyzes key frequency bands for speech clarity
- **Distortion Detection**: Identifies audio clipping and distortion
- **Echo Detection**: Detects echo and feedback issues using autocorrelation
- **Dropout Detection**: Counts audio dropouts and silence periods

### Performance Monitoring
- **Latency Tracking**: Monitors STT, TTS, and response generation latencies
- **STT Accuracy**: Tracks speech-to-text confidence and word error rates
- **Connection Quality**: Monitors network connection quality and stability
- **Turn-Around Time**: Measures end-to-end conversation turn latency
- **Packet Loss & Jitter**: Estimates network performance metrics

### Automatic Optimization
- **Adaptive Audio Settings**: Adjusts volume, noise reduction, and echo cancellation
- **TTS Model Switching**: Switches to faster TTS models when latency is high
- **Response Length Optimization**: Reduces response length to improve latency
- **Timeout Adjustments**: Increases timeouts for poor connections
- **Noise Reduction**: Enables noise reduction for noisy environments

### Quality Levels
- **Excellent** (0.9+): Optimal call quality with minimal issues
- **Good** (0.7-0.9): Good quality with minor issues
- **Fair** (0.5-0.7): Acceptable quality with some issues
- **Poor** (0.3-0.5): Poor quality requiring optimization
- **Critical** (<0.3): Severe quality issues requiring intervention

## Architecture

### Core Components

#### CallQualityMonitor
Main service class that orchestrates quality monitoring:
```python
from app.services.call_quality_monitor import call_quality_monitor

# Start monitoring
session = await call_quality_monitor.start_monitoring(call_sid)

# Record metrics
audio_metrics = await call_quality_monitor.record_audio_metrics(
    call_sid=call_sid,
    audio_data=audio_bytes,
    sample_rate=8000
)

performance_metrics = await call_quality_monitor.record_performance_metrics(
    call_sid=call_sid,
    stt_latency_ms=500.0,
    tts_latency_ms=700.0,
    response_generation_ms=1500.0
)

# Analyze and optimize
snapshot = await call_quality_monitor.analyze_call_quality(call_sid)
```

#### AudioMetrics
Comprehensive audio quality metrics:
```python
@dataclass
class AudioMetrics:
    volume_level: float          # 0.0 to 1.0
    noise_level: float           # 0.0 to 1.0
    signal_to_noise_ratio: float # dB
    frequency_response: Dict[str, float]
    distortion_level: float      # 0.0 to 1.0
    echo_detected: bool
    dropout_count: int
    
    @property
    def quality_score(self) -> float:
        # Weighted scoring algorithm
```

#### PerformanceMetrics
Call performance and latency metrics:
```python
@dataclass
class PerformanceMetrics:
    stt_latency_ms: float
    tts_latency_ms: float
    response_generation_ms: float
    total_turn_latency_ms: float
    stt_confidence: float
    connection_quality: float
    
    @property
    def performance_score(self) -> float:
        # Performance scoring based on SLA targets
```

#### OptimizationSettings
Adaptive settings for call optimization:
```python
@dataclass
class OptimizationSettings:
    # Audio settings
    noise_reduction_enabled: bool = False
    volume_boost: float = 1.0
    echo_cancellation: bool = True
    
    # TTS settings
    tts_model: str = "eleven_turbo_v2"
    speech_rate: float = 1.0
    
    # Response settings
    max_response_length: int = 150
    response_timeout_ms: int = 5000
```

## API Endpoints

### Start Monitoring
```http
POST /api/v1/call-quality/start
Content-Type: application/json

{
    "call_sid": "CA1234567890abcdef",
    "optimization_settings": {
        "noise_reduction_enabled": false,
        "tts_model": "eleven_turbo_v2",
        "max_response_length": 150
    }
}
```

### Record Audio Metrics
```http
POST /api/v1/call-quality/audio-metrics
Content-Type: multipart/form-data

call_sid: CA1234567890abcdef
sample_rate: 8000
audio_file: [binary audio data]
```

### Record Performance Metrics
```http
POST /api/v1/call-quality/performance-metrics
Content-Type: application/json

{
    "call_sid": "CA1234567890abcdef",
    "stt_latency_ms": 500.0,
    "tts_latency_ms": 700.0,
    "response_generation_ms": 1500.0,
    "stt_confidence": 0.9,
    "connection_quality": 0.8
}
```

### Analyze Call Quality
```http
GET /api/v1/call-quality/analyze/CA1234567890abcdef

Response:
{
    "call_sid": "CA1234567890abcdef",
    "overall_score": 0.85,
    "quality_level": "good",
    "detected_issues": ["background_noise"],
    "optimization_actions": ["enable_noise_reduction"]
}
```

### System Metrics
```http
GET /api/v1/call-quality/metrics

Response:
{
    "active_monitored_calls": 5,
    "average_quality_score": 0.78,
    "system_status": "healthy",
    "current_issue_counts": {
        "background_noise": 2,
        "high_latency": 1
    }
}
```

## Integration with Call Handler

The call quality monitor is automatically integrated with the call handler:

```python
# In CallHandler.initialize_call_session()
await call_quality_monitor.start_monitoring(call_sid)

# In CallHandler.process_conversation_turn()
if audio_data:
    await call_quality_monitor.record_audio_metrics(
        call_sid=call_sid,
        audio_data=audio_data,
        sample_rate=8000
    )

await call_quality_monitor.record_performance_metrics(
    call_sid=call_sid,
    stt_latency_ms=stt_latency,
    tts_latency_ms=tts_latency,
    response_generation_ms=response_generation_time
)

# Automatic analysis and optimization
await call_quality_monitor.analyze_call_quality(call_sid)

# In CallHandler.end_call_session()
quality_report = await call_quality_monitor.stop_monitoring(call_sid)
```

## Optimization Rules

### Issue Detection Rules
- **Low Volume**: volume_level < 0.2
- **Background Noise**: noise_level > 0.3
- **Echo**: Strong autocorrelation at typical echo delays
- **Distortion**: distortion_level > 0.2
- **High Latency**: total_turn_latency_ms > 10000
- **Poor STT**: stt_confidence < 0.7
- **TTS Delays**: tts_latency_ms > 1500

### Optimization Actions
- **Background Noise** → Enable noise reduction, adjust audio settings
- **High Latency** → Switch TTS model, reduce response length, increase timeout
- **Low Volume** → Adjust audio settings, increase volume boost
- **Echo** → Enable echo cancellation, adjust audio settings
- **TTS Delays** → Switch to faster TTS model, reduce response length

### Optimization Thresholds
```python
OPTIMIZATION_RULES = {
    AudioIssueType.BACKGROUND_NOISE: [
        OptimizationAction.ENABLE_NOISE_REDUCTION,
        OptimizationAction.ADJUST_AUDIO_SETTINGS
    ],
    AudioIssueType.HIGH_LATENCY: [
        OptimizationAction.SWITCH_TTS_MODEL,
        OptimizationAction.REDUCE_RESPONSE_LENGTH,
        OptimizationAction.INCREASE_TIMEOUT
    ]
}
```

## Performance Targets

### SLA Targets
- **STT First Token**: ≤ 600ms (target)
- **TTS First Audio**: ≤ 800ms (target)
- **Response Generation**: ≤ 2000ms (target)
- **Total Turn Latency**: ≤ 8000ms (target)
- **Audio Quality Score**: ≥ 0.7 (good)
- **Performance Score**: ≥ 0.7 (good)

### Quality Scoring
Audio quality score calculation:
```python
def calculate_audio_quality_score(metrics):
    volume_score = min(metrics.volume_level * 2, 1.0) if metrics.volume_level < 0.5 else 1.0
    noise_score = 1.0 - metrics.noise_level
    snr_score = min(metrics.signal_to_noise_ratio / 20.0, 1.0)
    distortion_score = 1.0 - metrics.distortion_level
    echo_penalty = 0.3 if metrics.echo_detected else 0.0
    dropout_penalty = min(metrics.dropout_count * 0.1, 0.5)
    
    score = (
        volume_score * 0.2 +
        noise_score * 0.3 +
        snr_score * 0.3 +
        distortion_score * 0.2
    ) - echo_penalty - dropout_penalty
    
    return max(0.0, min(1.0, score))
```

## Monitoring and Alerting

### System Health Monitoring
- **Active Calls**: Number of calls being monitored
- **Average Quality**: System-wide average quality score
- **Issue Distribution**: Count of different issue types
- **System Status**: healthy/degraded/critical based on average quality

### Quality Alerts
- **Critical Quality** (< 0.3): Immediate alert for severe quality issues
- **Poor Quality** (< 0.5): Warning alert for quality degradation
- **High Issue Rate**: Alert when issue detection rate exceeds threshold
- **Optimization Failures**: Alert when optimizations fail to improve quality

## Testing

### Unit Tests
```bash
# Run call quality monitor tests
pytest tests/test_services/test_call_quality_monitor.py -v
```

### Integration Tests
```bash
# Run call quality integration test script
python scripts/test_call_quality.py
```

### Test Scenarios
- **Basic Monitoring**: Start/stop monitoring, record metrics
- **Poor Quality Detection**: Test issue detection and optimization
- **Concurrent Monitoring**: Multiple simultaneous calls
- **Optimization Settings**: Test adaptive settings changes
- **System Metrics**: System-wide monitoring and reporting

## Configuration

### Environment Variables
```bash
# Call quality monitoring settings
CALL_QUALITY_ENABLED=true
CALL_QUALITY_HISTORY_SIZE=100
CALL_QUALITY_CACHE_SIZE=1000

# Audio analysis settings
AUDIO_SAMPLE_RATE=8000
AUDIO_ANALYSIS_WINDOW_SIZE=1024
NOISE_REDUCTION_STRENGTH=0.5

# Performance thresholds
STT_LATENCY_TARGET_MS=600
TTS_LATENCY_TARGET_MS=800
RESPONSE_GENERATION_TARGET_MS=2000
TOTAL_TURN_LATENCY_TARGET_MS=8000
```

### Optimization Settings
```python
# Default optimization settings
DEFAULT_OPTIMIZATION_SETTINGS = OptimizationSettings(
    noise_reduction_enabled=False,
    noise_reduction_strength=0.5,
    volume_boost=1.0,
    echo_cancellation=True,
    tts_model="eleven_turbo_v2",
    speech_rate=1.0,
    stability=0.5,
    similarity_boost=0.75,
    max_response_length=150,
    response_timeout_ms=5000,
    connection_timeout_ms=10000,
    retry_attempts=3,
    adaptive_bitrate=True
)
```

## Cost Control

### Budget Considerations
- **Audio Analysis**: Minimal CPU cost for real-time analysis
- **Metric Storage**: In-memory storage with configurable history size
- **Optimization Actions**: No external API calls, only setting adjustments
- **Monitoring Overhead**: < 1% of total call processing time

### Resource Usage
- **Memory**: ~1MB per active call session
- **CPU**: ~2-5% additional CPU usage for audio analysis
- **Storage**: Metrics stored in memory, optionally persisted to database
- **Network**: No additional network overhead

## Troubleshooting

### Common Issues

#### High False Positive Rate
- Adjust issue detection thresholds
- Calibrate audio analysis parameters
- Review optimization rules

#### Poor Optimization Effectiveness
- Verify optimization actions are being applied
- Check TTS model availability
- Review timeout and response length settings

#### Performance Impact
- Monitor CPU usage during audio analysis
- Adjust analysis window size
- Reduce history retention size

### Debug Logging
```python
import logging
logging.getLogger("app.services.call_quality_monitor").setLevel(logging.DEBUG)
```

### Metrics Collection
```python
# Get detailed system metrics
metrics = await call_quality_monitor.get_system_metrics()

# Get call-specific history
history = call_quality_monitor.quality_history.get(call_sid, [])

# Get current optimization settings
session = call_quality_monitor.active_monitors.get(call_sid)
settings = session.settings if session else None
```

## Future Enhancements

### Planned Features
- **Machine Learning Models**: Train ML models for better issue detection
- **Predictive Quality**: Predict quality issues before they occur
- **Advanced Audio Processing**: More sophisticated audio analysis algorithms
- **Real-time Dashboards**: Web-based quality monitoring dashboards
- **Historical Analytics**: Long-term quality trend analysis
- **A/B Testing**: Test different optimization strategies

### Integration Opportunities
- **Twilio Insights**: Integration with Twilio's call quality metrics
- **External Monitoring**: Integration with external monitoring services
- **CRM Integration**: Quality metrics in Salesforce call records
- **Analytics Platforms**: Export metrics to analytics platforms

## Conclusion

The Call Quality Monitoring system provides comprehensive real-time monitoring and optimization of call quality while maintaining strict cost controls. It automatically detects issues, applies optimizations, and provides detailed metrics for system monitoring and improvement.

The system is designed to be:
- **Cost-Effective**: Minimal resource usage and no external API calls
- **Real-Time**: Immediate issue detection and optimization
- **Scalable**: Handles multiple concurrent calls efficiently
- **Configurable**: Flexible settings and thresholds
- **Observable**: Comprehensive metrics and logging