"""
LLM Performance Monitor

This module provides performance tracking and optimization for LLM usage
in the AI Calling Agent MVP, including budget monitoring, cache optimization,
and usage analytics.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

import structlog

from ..core.config import get_settings
from ..services.audit_trail import audit_service, AuditEventType

logger = structlog.get_logger()


@dataclass
class LLMPerformanceMetrics:
    """Performance metrics for LLM usage."""
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    
    # Budget metrics
    budget_blocks: int = 0
    fallback_uses: int = 0
    template_uses: int = 0
    
    # Token usage
    total_tokens_used: int = 0
    tokens_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Cost tracking
    total_cost: float = 0.0
    cost_by_type: Dict[str, float] = field(default_factory=dict)
    
    # Response time metrics
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    
    # Quality metrics
    avg_confidence_score: float = 0.0
    escalation_rate: float = 0.0
    
    # Time period
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw data."""
        if self.cache_hits + self.cache_misses > 0:
            self.cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses)
        
        if self.total_requests > 0:
            self.escalation_rate = self.budget_blocks / self.total_requests


@dataclass
class LLMRequestLog:
    """Log entry for individual LLM requests."""
    request_id: str
    lead_id: str
    usage_type: str
    prospect_tier: str
    
    # Request details
    request_timestamp: datetime
    response_timestamp: Optional[datetime] = None
    
    # Performance data
    response_time_ms: float = 0.0
    tokens_used: int = 0
    estimated_cost: float = 0.0
    
    # Quality data
    confidence_score: float = 0.0
    from_cache: bool = False
    used_fallback: bool = False
    escalated: bool = False
    
    # Error tracking
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    def mark_completed(self, tokens_used: int, cost: float, confidence: float = 0.0):
        """Mark request as completed with metrics."""
        self.response_timestamp = datetime.utcnow()
        self.response_time_ms = (self.response_timestamp - self.request_timestamp).total_seconds() * 1000
        self.tokens_used = tokens_used
        self.estimated_cost = cost
        self.confidence_score = confidence
    
    def mark_failed(self, error_type: str, error_message: str):
        """Mark request as failed."""
        self.response_timestamp = datetime.utcnow()
        self.response_time_ms = (self.response_timestamp - self.request_timestamp).total_seconds() * 1000
        self.error_type = error_type
        self.error_message = error_message


class LLMPerformanceMonitor:
    """
    Monitor and optimize LLM performance.
    
    Tracks usage patterns, identifies optimization opportunities,
    and provides real-time performance insights.
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self.settings = get_settings()
        
        # Performance tracking
        self.current_metrics = LLMPerformanceMetrics()
        self.hourly_metrics: Dict[str, LLMPerformanceMetrics] = {}
        self.daily_metrics: Dict[str, LLMPerformanceMetrics] = {}
        
        # Request logging
        self.active_requests: Dict[str, LLMRequestLog] = {}
        self.recent_requests: deque = deque(maxlen=1000)  # Keep last 1000 requests
        
        # Response time tracking
        self.response_times: deque = deque(maxlen=100)  # Last 100 response times
        
        # Cache optimization
        self.cache_patterns: Dict[str, int] = defaultdict(int)
        self.cache_misses_by_type: Dict[str, int] = defaultdict(int)
        
        # Budget alerts
        self.budget_thresholds = {
            'daily_token_warning': 80000,  # 80% of daily limit
            'daily_cost_warning': 40.0,    # 80% of daily limit
            'hourly_token_warning': 5000,  # High hourly usage
            'cache_hit_rate_warning': 0.3  # Low cache hit rate
        }
        
        # Alert tracking
        self.alerts_sent: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(hours=1)  # Don't spam alerts
        
        logger.info("LLM Performance Monitor initialized")
    
    def start_request(
        self,
        request_id: str,
        lead_id: str,
        usage_type: str,
        prospect_tier: str
    ) -> LLMRequestLog:
        """Start tracking a new LLM request."""
        request_log = LLMRequestLog(
            request_id=request_id,
            lead_id=lead_id,
            usage_type=usage_type,
            prospect_tier=prospect_tier,
            request_timestamp=datetime.utcnow()
        )
        
        self.active_requests[request_id] = request_log
        self.current_metrics.total_requests += 1
        
        return request_log
    
    def complete_request(
        self,
        request_id: str,
        tokens_used: int,
        cost: float,
        confidence: float = 0.0,
        from_cache: bool = False,
        used_fallback: bool = False,
        escalated: bool = False
    ) -> None:
        """Complete tracking for an LLM request."""
        if request_id not in self.active_requests:
            logger.warning("Completing unknown request", request_id=request_id)
            return
        
        request_log = self.active_requests.pop(request_id)
        request_log.mark_completed(tokens_used, cost, confidence)
        request_log.from_cache = from_cache
        request_log.used_fallback = used_fallback
        request_log.escalated = escalated
        
        # Update metrics
        self.current_metrics.successful_requests += 1
        self.current_metrics.total_tokens_used += tokens_used
        self.current_metrics.total_cost += cost
        
        # Update type-specific metrics
        usage_type = request_log.usage_type
        self.current_metrics.tokens_by_type[usage_type] = (
            self.current_metrics.tokens_by_type.get(usage_type, 0) + tokens_used
        )
        self.current_metrics.cost_by_type[usage_type] = (
            self.current_metrics.cost_by_type.get(usage_type, 0.0) + cost
        )
        
        # Update cache metrics
        if from_cache:
            self.current_metrics.cache_hits += 1
        else:
            self.current_metrics.cache_misses += 1
        
        # Update fallback metrics
        if used_fallback:
            self.current_metrics.fallback_uses += 1
        
        # Update escalation metrics
        if escalated:
            self.current_metrics.budget_blocks += 1
        
        # Track response time
        self.response_times.append(request_log.response_time_ms)
        
        # Store request log
        self.recent_requests.append(request_log)
        
        # Update derived metrics
        self.current_metrics.calculate_derived_metrics()
        
        # Check for alerts
        asyncio.create_task(self._check_performance_alerts())
        
        logger.debug(
            "Completed LLM request tracking",
            request_id=request_id,
            usage_type=usage_type,
            tokens_used=tokens_used,
            response_time_ms=request_log.response_time_ms,
            from_cache=from_cache
        )
    
    def fail_request(
        self,
        request_id: str,
        error_type: str,
        error_message: str
    ) -> None:
        """Mark an LLM request as failed."""
        if request_id not in self.active_requests:
            logger.warning("Failing unknown request", request_id=request_id)
            return
        
        request_log = self.active_requests.pop(request_id)
        request_log.mark_failed(error_type, error_message)
        
        # Update metrics
        self.current_metrics.failed_requests += 1
        
        # Track response time even for failures
        self.response_times.append(request_log.response_time_ms)
        
        # Store request log
        self.recent_requests.append(request_log)
        
        logger.warning(
            "Failed LLM request",
            request_id=request_id,
            error_type=error_type,
            error_message=error_message,
            response_time_ms=request_log.response_time_ms
        )
    
    def record_cache_pattern(self, cache_key: str, hit: bool) -> None:
        """Record cache usage patterns for optimization."""
        self.cache_patterns[cache_key] += 1
        
        if not hit:
            # Extract usage type from cache key for miss tracking
            if 'planner' in cache_key:
                self.cache_misses_by_type['planner'] += 1
            elif 'classifier' in cache_key:
                self.cache_misses_by_type['classifier'] += 1
            elif 'runtime' in cache_key:
                self.cache_misses_by_type['runtime'] += 1
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        # Calculate response time percentiles
        if self.response_times:
            sorted_times = sorted(self.response_times)
            n = len(sorted_times)
            
            self.current_metrics.avg_response_time_ms = sum(sorted_times) / n
            self.current_metrics.p95_response_time_ms = sorted_times[int(n * 0.95)] if n > 0 else 0
            self.current_metrics.p99_response_time_ms = sorted_times[int(n * 0.99)] if n > 0 else 0
        
        # Calculate average confidence
        if self.recent_requests:
            confidence_scores = [req.confidence_score for req in self.recent_requests if req.confidence_score > 0]
            if confidence_scores:
                self.current_metrics.avg_confidence_score = sum(confidence_scores) / len(confidence_scores)
        
        return {
            'current_metrics': {
                'total_requests': self.current_metrics.total_requests,
                'successful_requests': self.current_metrics.successful_requests,
                'failed_requests': self.current_metrics.failed_requests,
                'success_rate': (
                    self.current_metrics.successful_requests / max(1, self.current_metrics.total_requests)
                ),
                'cache_hits': self.current_metrics.cache_hits,
                'cache_misses': self.current_metrics.cache_misses,
                'cache_hit_rate': self.current_metrics.cache_hit_rate,
                'budget_blocks': self.current_metrics.budget_blocks,
                'fallback_uses': self.current_metrics.fallback_uses,
                'total_tokens_used': self.current_metrics.total_tokens_used,
                'total_cost': self.current_metrics.total_cost,
                'tokens_by_type': dict(self.current_metrics.tokens_by_type),
                'cost_by_type': dict(self.current_metrics.cost_by_type),
                'avg_response_time_ms': self.current_metrics.avg_response_time_ms,
                'p95_response_time_ms': self.current_metrics.p95_response_time_ms,
                'p99_response_time_ms': self.current_metrics.p99_response_time_ms,
                'avg_confidence_score': self.current_metrics.avg_confidence_score,
                'escalation_rate': self.current_metrics.escalation_rate
            },
            'active_requests': len(self.active_requests),
            'recent_requests_count': len(self.recent_requests),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations based on performance data."""
        recommendations = []
        
        # Cache optimization recommendations
        if self.current_metrics.cache_hit_rate < 0.5 and self.current_metrics.total_requests > 50:
            recommendations.append({
                'type': 'cache_optimization',
                'priority': 'high',
                'title': 'Low Cache Hit Rate',
                'description': f'Cache hit rate is {self.current_metrics.cache_hit_rate:.1%}. Consider increasing cache TTL or improving cache key generation.',
                'metric': 'cache_hit_rate',
                'current_value': self.current_metrics.cache_hit_rate,
                'target_value': 0.7
            })
        
        # Response time optimization
        if self.current_metrics.p95_response_time_ms > 5000:  # 5 seconds
            recommendations.append({
                'type': 'response_time_optimization',
                'priority': 'medium',
                'title': 'High Response Times',
                'description': f'95th percentile response time is {self.current_metrics.p95_response_time_ms:.0f}ms. Consider optimizing prompts or using smaller models.',
                'metric': 'p95_response_time_ms',
                'current_value': self.current_metrics.p95_response_time_ms,
                'target_value': 3000
            })
        
        # Budget optimization
        if self.current_metrics.fallback_uses > self.current_metrics.successful_requests * 0.2:
            recommendations.append({
                'type': 'budget_optimization',
                'priority': 'medium',
                'title': 'High Fallback Usage',
                'description': f'{self.current_metrics.fallback_uses} fallback responses used. Consider increasing budget limits for better quality.',
                'metric': 'fallback_rate',
                'current_value': self.current_metrics.fallback_uses / max(1, self.current_metrics.total_requests),
                'target_value': 0.1
            })
        
        # Token efficiency
        avg_tokens_per_request = self.current_metrics.total_tokens_used / max(1, self.current_metrics.successful_requests)
        if avg_tokens_per_request > 200:  # High token usage
            recommendations.append({
                'type': 'token_optimization',
                'priority': 'low',
                'title': 'High Token Usage',
                'description': f'Average {avg_tokens_per_request:.0f} tokens per request. Consider optimizing prompts for efficiency.',
                'metric': 'avg_tokens_per_request',
                'current_value': avg_tokens_per_request,
                'target_value': 150
            })
        
        # Cost efficiency
        if self.current_metrics.total_cost > 0:
            cost_per_request = self.current_metrics.total_cost / max(1, self.current_metrics.successful_requests)
            if cost_per_request > 0.05:  # $0.05 per request
                recommendations.append({
                    'type': 'cost_optimization',
                    'priority': 'high',
                    'title': 'High Cost Per Request',
                    'description': f'Average ${cost_per_request:.3f} per request. Consider using smaller models or improving caching.',
                    'metric': 'cost_per_request',
                    'current_value': cost_per_request,
                    'target_value': 0.02
                })
        
        return recommendations
    
    def get_usage_patterns(self) -> Dict[str, Any]:
        """Analyze usage patterns for optimization insights."""
        if not self.recent_requests:
            return {'error': 'No recent requests to analyze'}
        
        # Analyze by usage type
        usage_by_type = defaultdict(list)
        for req in self.recent_requests:
            usage_by_type[req.usage_type].append(req)
        
        type_analysis = {}
        for usage_type, requests in usage_by_type.items():
            if not requests:
                continue
            
            response_times = [req.response_time_ms for req in requests if req.response_time_ms > 0]
            tokens_used = [req.tokens_used for req in requests if req.tokens_used > 0]
            cache_hits = sum(1 for req in requests if req.from_cache)
            fallbacks = sum(1 for req in requests if req.used_fallback)
            
            type_analysis[usage_type] = {
                'total_requests': len(requests),
                'avg_response_time_ms': sum(response_times) / len(response_times) if response_times else 0,
                'avg_tokens_used': sum(tokens_used) / len(tokens_used) if tokens_used else 0,
                'cache_hit_rate': cache_hits / len(requests) if requests else 0,
                'fallback_rate': fallbacks / len(requests) if requests else 0
            }
        
        # Analyze by prospect tier
        tier_analysis = defaultdict(list)
        for req in self.recent_requests:
            tier_analysis[req.prospect_tier].append(req)
        
        tier_stats = {}
        for tier, requests in tier_analysis.items():
            if not requests:
                continue
            
            tokens_used = [req.tokens_used for req in requests if req.tokens_used > 0]
            costs = [req.estimated_cost for req in requests if req.estimated_cost > 0]
            
            tier_stats[tier] = {
                'total_requests': len(requests),
                'avg_tokens_used': sum(tokens_used) / len(tokens_used) if tokens_used else 0,
                'avg_cost': sum(costs) / len(costs) if costs else 0,
                'total_cost': sum(costs)
            }
        
        # Analyze peak usage times
        hourly_usage = defaultdict(int)
        for req in self.recent_requests:
            hour = req.request_timestamp.hour
            hourly_usage[hour] += 1
        
        peak_hours = sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'usage_by_type': type_analysis,
            'usage_by_tier': tier_stats,
            'peak_hours': [{'hour': hour, 'requests': count} for hour, count in peak_hours],
            'cache_patterns': dict(sorted(self.cache_patterns.items(), key=lambda x: x[1], reverse=True)[:10]),
            'cache_misses_by_type': dict(self.cache_misses_by_type),
            'analysis_period': {
                'start': min(req.request_timestamp for req in self.recent_requests).isoformat(),
                'end': max(req.request_timestamp for req in self.recent_requests).isoformat(),
                'total_requests': len(self.recent_requests)
            }
        }
    
    async def _check_performance_alerts(self) -> None:
        """Check for performance issues and send alerts."""
        try:
            current_time = datetime.utcnow()
            
            # Check daily token usage
            if (self.current_metrics.total_tokens_used > self.budget_thresholds['daily_token_warning'] and
                self._should_send_alert('daily_token_warning', current_time)):
                
                await self._send_alert(
                    alert_type='daily_token_warning',
                    title='High Daily Token Usage',
                    message=f'Daily token usage ({self.current_metrics.total_tokens_used}) exceeds warning threshold ({self.budget_thresholds["daily_token_warning"]})',
                    severity='warning'
                )
            
            # Check daily cost
            if (self.current_metrics.total_cost > self.budget_thresholds['daily_cost_warning'] and
                self._should_send_alert('daily_cost_warning', current_time)):
                
                await self._send_alert(
                    alert_type='daily_cost_warning',
                    title='High Daily Cost',
                    message=f'Daily cost (${self.current_metrics.total_cost:.2f}) exceeds warning threshold (${self.budget_thresholds["daily_cost_warning"]:.2f})',
                    severity='warning'
                )
            
            # Check cache hit rate
            if (self.current_metrics.cache_hit_rate < self.budget_thresholds['cache_hit_rate_warning'] and
                self.current_metrics.total_requests > 20 and
                self._should_send_alert('cache_hit_rate_warning', current_time)):
                
                await self._send_alert(
                    alert_type='cache_hit_rate_warning',
                    title='Low Cache Hit Rate',
                    message=f'Cache hit rate ({self.current_metrics.cache_hit_rate:.1%}) is below warning threshold ({self.budget_thresholds["cache_hit_rate_warning"]:.1%})',
                    severity='info'
                )
            
        except Exception as e:
            logger.error("Failed to check performance alerts", error=str(e))
    
    def _should_send_alert(self, alert_type: str, current_time: datetime) -> bool:
        """Check if alert should be sent based on cooldown."""
        last_sent = self.alerts_sent.get(alert_type)
        if last_sent is None:
            return True
        
        return current_time - last_sent > self.alert_cooldown
    
    async def _send_alert(self, alert_type: str, title: str, message: str, severity: str) -> None:
        """Send performance alert."""
        try:
            current_time = datetime.utcnow()
            
            # Log alert
            logger.warning(
                "LLM Performance Alert",
                alert_type=alert_type,
                title=title,
                message=message,
                severity=severity
            )
            
            # Record in audit trail
            await audit_service.log_event(
                event_type=AuditEventType.SYSTEM_ALERT,
                user_id="system",
                resource_type="llm_performance",
                resource_id=alert_type,
                details={
                    'alert_type': alert_type,
                    'title': title,
                    'message': message,
                    'severity': severity,
                    'current_metrics': self.get_current_metrics()
                }
            )
            
            # Update alert tracking
            self.alerts_sent[alert_type] = current_time
            
        except Exception as e:
            logger.error("Failed to send performance alert", error=str(e))
    
    def reset_metrics(self) -> None:
        """Reset current metrics (typically called daily)."""
        self.current_metrics = LLMPerformanceMetrics()
        self.response_times.clear()
        self.cache_patterns.clear()
        self.cache_misses_by_type.clear()
        
        logger.info("Reset LLM performance metrics")


# Global performance monitor instance
llm_performance_monitor = LLMPerformanceMonitor()