"""
Business analytics and reporting service for AI Calling Agent.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.cache import cache_manager
from app.core.config import get_settings

logger = structlog.get_logger()


class MetricType(str, Enum):
    """Types of business metrics."""
    CALL_VOLUME = "call_volume"
    CONVERSION_RATE = "conversion_rate"
    LEAD_QUALITY = "lead_quality"
    RESPONSE_TIME = "response_time"
    COST_EFFICIENCY = "cost_efficiency"
    CUSTOMER_SATISFACTION = "customer_satisfaction"


class TimeRange(str, Enum):
    """Time range options for analytics."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class CallOutcome(str, Enum):
    """Call outcome classifications."""
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    FAILED = "failed"
    QUALIFIED = "qualified"
    MEETING_BOOKED = "meeting_booked"
    NOT_INTERESTED = "not_interested"


class BusinessMetric(BaseModel):
    """Business metric data model."""
    metric_type: MetricType
    value: float
    timestamp: datetime
    metadata: Dict[str, Any] = {}
    time_range: TimeRange
    period_start: datetime
    period_end: datetime


class CallAnalytics(BaseModel):
    """Call analytics data model."""
    total_calls: int
    answered_calls: int
    qualified_leads: int
    meetings_booked: int
    average_call_duration: float
    answer_rate: float
    qualification_rate: float
    meeting_booking_rate: float
    cost_per_call: float
    cost_per_qualified_lead: float
    roi_percentage: float


class LeadQualityMetrics(BaseModel):
    """Lead quality metrics data model."""
    total_leads: int
    high_quality_leads: int  # Score > 80
    medium_quality_leads: int  # Score 60-80
    low_quality_leads: int  # Score < 60
    average_lead_score: float
    qualification_accuracy: float
    false_positive_rate: float
    false_negative_rate: float


class PerformanceMetrics(BaseModel):
    """System performance metrics data model."""
    average_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    uptime_percentage: float
    cache_hit_rate: float
    concurrent_calls_peak: int
    api_call_efficiency: float


class AnalyticsService:
    """Business analytics and reporting service."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def record_call_event(
        self,
        call_sid: str,
        event_type: str,
        outcome: CallOutcome,
        duration: Optional[float] = None,
        lead_score: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a call event for analytics."""
        try:
            async for session in get_async_session():
                # Insert call event record
                query = text("""
                    INSERT INTO call_events (
                        call_sid, event_type, outcome, duration, 
                        lead_score, metadata, created_at
                    ) VALUES (
                        :call_sid, :event_type, :outcome, :duration,
                        :lead_score, :metadata, :created_at
                    )
                """)
                
                await session.execute(query, {
                    "call_sid": call_sid,
                    "event_type": event_type,
                    "outcome": outcome.value,
                    "duration": duration,
                    "lead_score": lead_score,
                    "metadata": json.dumps(metadata or {}),
                    "created_at": datetime.utcnow()
                })
                
                await session.commit()
                
                logger.info("Call event recorded", 
                           call_sid=call_sid, 
                           event_type=event_type, 
                           outcome=outcome)
                
        except Exception as e:
            logger.error("Failed to record call event", 
                        call_sid=call_sid, 
                        error=str(e))
    
    async def get_call_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        time_range: TimeRange = TimeRange.DAY
    ) -> CallAnalytics:
        """Get call analytics for specified time period."""
        try:
            # Check cache first
            cache_key = f"call_analytics:{start_date.isoformat()}:{end_date.isoformat()}:{time_range}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return CallAnalytics(**cached_result)
            
            async for session in get_async_session():
                # Get call statistics
                query = text("""
                    SELECT 
                        COUNT(*) as total_calls,
                        COUNT(CASE WHEN outcome = 'answered' THEN 1 END) as answered_calls,
                        COUNT(CASE WHEN outcome = 'qualified' THEN 1 END) as qualified_leads,
                        COUNT(CASE WHEN outcome = 'meeting_booked' THEN 1 END) as meetings_booked,
                        AVG(CASE WHEN duration IS NOT NULL THEN duration END) as avg_duration,
                        AVG(CASE WHEN lead_score IS NOT NULL THEN lead_score END) as avg_lead_score
                    FROM call_events 
                    WHERE created_at BETWEEN :start_date AND :end_date
                """)
                
                result = await session.execute(query, {
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                row = result.fetchone()
                
                if not row or row.total_calls == 0:
                    # Return empty analytics
                    analytics = CallAnalytics(
                        total_calls=0,
                        answered_calls=0,
                        qualified_leads=0,
                        meetings_booked=0,
                        average_call_duration=0.0,
                        answer_rate=0.0,
                        qualification_rate=0.0,
                        meeting_booking_rate=0.0,
                        cost_per_call=0.0,
                        cost_per_qualified_lead=0.0,
                        roi_percentage=0.0
                    )
                else:
                    # Calculate rates and costs
                    answer_rate = (row.answered_calls / row.total_calls) * 100 if row.total_calls > 0 else 0
                    qualification_rate = (row.qualified_leads / row.answered_calls) * 100 if row.answered_calls > 0 else 0
                    meeting_booking_rate = (row.meetings_booked / row.qualified_leads) * 100 if row.qualified_leads > 0 else 0
                    
                    # Estimate costs (these would come from actual cost tracking)
                    estimated_cost_per_call = 0.15  # $0.15 per call (Twilio + AI costs)
                    total_cost = row.total_calls * estimated_cost_per_call
                    cost_per_qualified_lead = total_cost / row.qualified_leads if row.qualified_leads > 0 else 0
                    
                    # Estimate ROI (assuming $500 value per meeting booked)
                    revenue = row.meetings_booked * 500
                    roi_percentage = ((revenue - total_cost) / total_cost) * 100 if total_cost > 0 else 0
                    
                    analytics = CallAnalytics(
                        total_calls=row.total_calls,
                        answered_calls=row.answered_calls,
                        qualified_leads=row.qualified_leads,
                        meetings_booked=row.meetings_booked,
                        average_call_duration=row.avg_duration or 0.0,
                        answer_rate=answer_rate,
                        qualification_rate=qualification_rate,
                        meeting_booking_rate=meeting_booking_rate,
                        cost_per_call=estimated_cost_per_call,
                        cost_per_qualified_lead=cost_per_qualified_lead,
                        roi_percentage=roi_percentage
                    )
                
                # Cache the result
                await cache_manager.set(cache_key, analytics.dict(), ttl=1800)  # 30 minutes
                
                return analytics
                
        except Exception as e:
            logger.error("Failed to get call analytics", error=str(e))
            # Return empty analytics on error
            return CallAnalytics(
                total_calls=0,
                answered_calls=0,
                qualified_leads=0,
                meetings_booked=0,
                average_call_duration=0.0,
                answer_rate=0.0,
                qualification_rate=0.0,
                meeting_booking_rate=0.0,
                cost_per_call=0.0,
                cost_per_qualified_lead=0.0,
                roi_percentage=0.0
            )
    
    async def get_lead_quality_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> LeadQualityMetrics:
        """Get lead quality metrics for specified time period."""
        try:
            cache_key = f"lead_quality:{start_date.isoformat()}:{end_date.isoformat()}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return LeadQualityMetrics(**cached_result)
            
            async for session in get_async_session():
                query = text("""
                    SELECT 
                        COUNT(*) as total_leads,
                        COUNT(CASE WHEN lead_score > 80 THEN 1 END) as high_quality,
                        COUNT(CASE WHEN lead_score BETWEEN 60 AND 80 THEN 1 END) as medium_quality,
                        COUNT(CASE WHEN lead_score < 60 THEN 1 END) as low_quality,
                        AVG(lead_score) as avg_score
                    FROM call_events 
                    WHERE created_at BETWEEN :start_date AND :end_date
                    AND lead_score IS NOT NULL
                """)
                
                result = await session.execute(query, {
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                row = result.fetchone()
                
                if not row or row.total_leads == 0:
                    metrics = LeadQualityMetrics(
                        total_leads=0,
                        high_quality_leads=0,
                        medium_quality_leads=0,
                        low_quality_leads=0,
                        average_lead_score=0.0,
                        qualification_accuracy=0.0,
                        false_positive_rate=0.0,
                        false_negative_rate=0.0
                    )
                else:
                    # Calculate qualification accuracy (would need actual outcome data)
                    # For now, estimate based on score distribution
                    qualification_accuracy = 85.0  # Placeholder
                    false_positive_rate = 10.0    # Placeholder
                    false_negative_rate = 5.0     # Placeholder
                    
                    metrics = LeadQualityMetrics(
                        total_leads=row.total_leads,
                        high_quality_leads=row.high_quality,
                        medium_quality_leads=row.medium_quality,
                        low_quality_leads=row.low_quality,
                        average_lead_score=row.avg_score or 0.0,
                        qualification_accuracy=qualification_accuracy,
                        false_positive_rate=false_positive_rate,
                        false_negative_rate=false_negative_rate
                    )
                
                # Cache the result
                await cache_manager.set(cache_key, metrics.dict(), ttl=1800)
                
                return metrics
                
        except Exception as e:
            logger.error("Failed to get lead quality metrics", error=str(e))
            return LeadQualityMetrics(
                total_leads=0,
                high_quality_leads=0,
                medium_quality_leads=0,
                low_quality_leads=0,
                average_lead_score=0.0,
                qualification_accuracy=0.0,
                false_positive_rate=0.0,
                false_negative_rate=0.0
            )
    
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get system performance metrics."""
        try:
            from app.core.performance import performance_monitor
            
            # Get performance data from monitoring system
            perf_data = performance_monitor.get_metrics()
            
            # Calculate performance metrics
            metrics = PerformanceMetrics(
                average_response_time=perf_data.get('average_response_time', 0.0),
                p95_response_time=perf_data.get('p95_response_time', 0.0),  # Would need histogram data
                p99_response_time=perf_data.get('p99_response_time', 0.0),  # Would need histogram data
                error_rate=0.0,  # Would calculate from error tracking
                uptime_percentage=99.5,  # Would calculate from uptime monitoring
                cache_hit_rate=self._calculate_cache_hit_rate(perf_data),
                concurrent_calls_peak=perf_data.get('active_calls', 0),
                api_call_efficiency=85.0  # Placeholder - would calculate from API usage
            )
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to get performance metrics", error=str(e))
            return PerformanceMetrics(
                average_response_time=0.0,
                p95_response_time=0.0,
                p99_response_time=0.0,
                error_rate=0.0,
                uptime_percentage=0.0,
                cache_hit_rate=0.0,
                concurrent_calls_peak=0,
                api_call_efficiency=0.0
            )
    
    def _calculate_cache_hit_rate(self, perf_data: Dict[str, Any]) -> float:
        """Calculate cache hit rate from performance data."""
        hits = perf_data.get('cache_hits', 0)
        misses = perf_data.get('cache_misses', 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return (hits / total) * 100
    
    async def get_cost_analysis(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get cost analysis for specified time period."""
        try:
            cache_key = f"cost_analysis:{start_date.isoformat()}:{end_date.isoformat()}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get call volume for cost calculation
            call_analytics = await self.get_call_analytics(start_date, end_date)
            
            # Cost breakdown (estimated)
            twilio_cost = call_analytics.total_calls * 0.05  # $0.05 per call
            elevenlabs_cost = call_analytics.total_calls * 0.08  # $0.08 per call for TTS/STT
            llm_cost = call_analytics.qualified_leads * 0.02  # $0.02 per qualified lead for LLM
            infrastructure_cost = (end_date - start_date).days * 5.0  # $5 per day
            
            total_cost = twilio_cost + elevenlabs_cost + llm_cost + infrastructure_cost
            
            cost_analysis = {
                "total_cost": total_cost,
                "cost_breakdown": {
                    "twilio": twilio_cost,
                    "elevenlabs": elevenlabs_cost,
                    "llm": llm_cost,
                    "infrastructure": infrastructure_cost
                },
                "cost_per_call": total_cost / call_analytics.total_calls if call_analytics.total_calls > 0 else 0,
                "cost_per_qualified_lead": total_cost / call_analytics.qualified_leads if call_analytics.qualified_leads > 0 else 0,
                "cost_per_meeting": total_cost / call_analytics.meetings_booked if call_analytics.meetings_booked > 0 else 0,
                "period_days": (end_date - start_date).days,
                "daily_average_cost": total_cost / max((end_date - start_date).days, 1)
            }
            
            # Cache the result
            await cache_manager.set(cache_key, cost_analysis, ttl=3600)  # 1 hour
            
            return cost_analysis
            
        except Exception as e:
            logger.error("Failed to get cost analysis", error=str(e))
            return {
                "total_cost": 0.0,
                "cost_breakdown": {},
                "cost_per_call": 0.0,
                "cost_per_qualified_lead": 0.0,
                "cost_per_meeting": 0.0,
                "period_days": 0,
                "daily_average_cost": 0.0
            }
    
    async def get_conversion_funnel(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get conversion funnel analysis."""
        try:
            async for session in get_async_session():
                query = text("""
                    SELECT 
                        COUNT(*) as total_calls,
                        COUNT(CASE WHEN outcome IN ('answered', 'qualified', 'meeting_booked') THEN 1 END) as answered,
                        COUNT(CASE WHEN outcome IN ('qualified', 'meeting_booked') THEN 1 END) as qualified,
                        COUNT(CASE WHEN outcome = 'meeting_booked' THEN 1 END) as meetings_booked
                    FROM call_events 
                    WHERE created_at BETWEEN :start_date AND :end_date
                """)
                
                result = await session.execute(query, {
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                row = result.fetchone()
                
                if not row or row.total_calls == 0:
                    return {
                        "stages": {
                            "calls_made": 0,
                            "calls_answered": 0,
                            "leads_qualified": 0,
                            "meetings_booked": 0
                        },
                        "conversion_rates": {
                            "answer_rate": 0.0,
                            "qualification_rate": 0.0,
                            "meeting_booking_rate": 0.0,
                            "overall_conversion": 0.0
                        }
                    }
                
                # Calculate conversion rates
                answer_rate = (row.answered / row.total_calls) * 100 if row.total_calls > 0 else 0
                qualification_rate = (row.qualified / row.answered) * 100 if row.answered > 0 else 0
                meeting_rate = (row.meetings_booked / row.qualified) * 100 if row.qualified > 0 else 0
                overall_conversion = (row.meetings_booked / row.total_calls) * 100 if row.total_calls > 0 else 0
                
                return {
                    "stages": {
                        "calls_made": row.total_calls,
                        "calls_answered": row.answered,
                        "leads_qualified": row.qualified,
                        "meetings_booked": row.meetings_booked
                    },
                    "conversion_rates": {
                        "answer_rate": answer_rate,
                        "qualification_rate": qualification_rate,
                        "meeting_booking_rate": meeting_rate,
                        "overall_conversion": overall_conversion
                    }
                }
                
        except Exception as e:
            logger.error("Failed to get conversion funnel", error=str(e))
            return {
                "stages": {
                    "calls_made": 0,
                    "calls_answered": 0,
                    "leads_qualified": 0,
                    "meetings_booked": 0
                },
                "conversion_rates": {
                    "answer_rate": 0.0,
                    "qualification_rate": 0.0,
                    "meeting_booking_rate": 0.0,
                    "overall_conversion": 0.0
                }
            }
    
    async def generate_daily_report(self, date: datetime) -> Dict[str, Any]:
        """Generate comprehensive daily analytics report."""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        try:
            # Get all analytics data
            call_analytics = await self.get_call_analytics(start_date, end_date)
            lead_quality = await self.get_lead_quality_metrics(start_date, end_date)
            performance = await self.get_performance_metrics()
            cost_analysis = await self.get_cost_analysis(start_date, end_date)
            conversion_funnel = await self.get_conversion_funnel(start_date, end_date)
            
            report = {
                "date": date.isoformat(),
                "summary": {
                    "total_calls": call_analytics.total_calls,
                    "qualified_leads": call_analytics.qualified_leads,
                    "meetings_booked": call_analytics.meetings_booked,
                    "total_cost": cost_analysis["total_cost"],
                    "roi_percentage": call_analytics.roi_percentage
                },
                "call_analytics": call_analytics.dict(),
                "lead_quality": lead_quality.dict(),
                "performance": performance.dict(),
                "cost_analysis": cost_analysis,
                "conversion_funnel": conversion_funnel,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate daily report", date=date, error=str(e))
            return {
                "date": date.isoformat(),
                "error": "Failed to generate report",
                "generated_at": datetime.utcnow().isoformat()
            }


# Global analytics service instance
analytics_service = AnalyticsService()