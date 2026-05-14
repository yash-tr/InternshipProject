"""
Analytics and reporting API endpoints.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from app.services.analytics import (
    analytics_service,
    CallAnalytics,
    LeadQualityMetrics,
    PerformanceMetrics,
    TimeRange
)
from app.core.cache import cache_manager

logger = structlog.get_logger()

router = APIRouter()


class AnalyticsRequest(BaseModel):
    """Request model for analytics queries."""
    start_date: datetime
    end_date: datetime
    time_range: TimeRange = TimeRange.DAY
    filters: Optional[Dict[str, Any]] = None


class DashboardData(BaseModel):
    """Dashboard data model."""
    call_analytics: CallAnalytics
    lead_quality: LeadQualityMetrics
    performance: PerformanceMetrics
    cost_analysis: Dict[str, Any]
    conversion_funnel: Dict[str, Any]
    last_updated: datetime


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data(
    days: int = Query(7, description="Number of days to include in analytics", ge=1, le=90)
) -> DashboardData:
    """Get comprehensive dashboard data for the specified time period."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logger.info("Fetching dashboard data", start_date=start_date, end_date=end_date)
        
        # Check cache first
        cache_key = f"dashboard:{days}:{end_date.strftime('%Y%m%d%H')}"
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            logger.info("Serving cached dashboard data")
            return DashboardData(**cached_data)
        
        # Fetch all analytics data
        call_analytics = await analytics_service.get_call_analytics(start_date, end_date)
        lead_quality = await analytics_service.get_lead_quality_metrics(start_date, end_date)
        performance = await analytics_service.get_performance_metrics()
        cost_analysis = await analytics_service.get_cost_analysis(start_date, end_date)
        conversion_funnel = await analytics_service.get_conversion_funnel(start_date, end_date)
        
        dashboard_data = DashboardData(
            call_analytics=call_analytics,
            lead_quality=lead_quality,
            performance=performance,
            cost_analysis=cost_analysis,
            conversion_funnel=conversion_funnel,
            last_updated=datetime.utcnow()
        )
        
        # Cache the result for 15 minutes
        await cache_manager.set(cache_key, dashboard_data.dict(), ttl=900)
        
        logger.info("Dashboard data fetched successfully")
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to fetch dashboard data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")


@router.get("/calls", response_model=CallAnalytics)
async def get_call_analytics(
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(..., description="End date for analytics"),
    time_range: TimeRange = Query(TimeRange.DAY, description="Time range granularity")
) -> CallAnalytics:
    """Get call analytics for the specified time period."""
    try:
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        if (end_date - start_date).days > 365:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")
        
        analytics = await analytics_service.get_call_analytics(start_date, end_date, time_range)
        
        logger.info("Call analytics fetched", 
                   start_date=start_date, 
                   end_date=end_date,
                   total_calls=analytics.total_calls)
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch call analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch call analytics")


@router.get("/leads", response_model=LeadQualityMetrics)
async def get_lead_quality_metrics(
    start_date: datetime = Query(..., description="Start date for metrics"),
    end_date: datetime = Query(..., description="End date for metrics")
) -> LeadQualityMetrics:
    """Get lead quality metrics for the specified time period."""
    try:
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        metrics = await analytics_service.get_lead_quality_metrics(start_date, end_date)
        
        logger.info("Lead quality metrics fetched", 
                   start_date=start_date, 
                   end_date=end_date,
                   total_leads=metrics.total_leads)
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch lead quality metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch lead quality metrics")


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics() -> PerformanceMetrics:
    """Get current system performance metrics."""
    try:
        metrics = await analytics_service.get_performance_metrics()
        
        logger.info("Performance metrics fetched", 
                   avg_response_time=metrics.average_response_time,
                   cache_hit_rate=metrics.cache_hit_rate)
        
        return metrics
        
    except Exception as e:
        logger.error("Failed to fetch performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch performance metrics")


@router.get("/costs")
async def get_cost_analysis(
    start_date: datetime = Query(..., description="Start date for cost analysis"),
    end_date: datetime = Query(..., description="End date for cost analysis")
) -> Dict[str, Any]:
    """Get cost analysis for the specified time period."""
    try:
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        cost_analysis = await analytics_service.get_cost_analysis(start_date, end_date)
        
        logger.info("Cost analysis fetched", 
                   start_date=start_date, 
                   end_date=end_date,
                   total_cost=cost_analysis["total_cost"])
        
        return cost_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch cost analysis", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch cost analysis")


@router.get("/conversion-funnel")
async def get_conversion_funnel(
    start_date: datetime = Query(..., description="Start date for funnel analysis"),
    end_date: datetime = Query(..., description="End date for funnel analysis")
) -> Dict[str, Any]:
    """Get conversion funnel analysis for the specified time period."""
    try:
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        funnel = await analytics_service.get_conversion_funnel(start_date, end_date)
        
        logger.info("Conversion funnel fetched", 
                   start_date=start_date, 
                   end_date=end_date,
                   total_calls=funnel["stages"]["calls_made"])
        
        return funnel
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch conversion funnel", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch conversion funnel")


@router.get("/reports/daily")
async def get_daily_report(
    date: datetime = Query(..., description="Date for the daily report")
) -> Dict[str, Any]:
    """Get comprehensive daily analytics report."""
    try:
        # Ensure date is not in the future
        if date.date() > datetime.utcnow().date():
            raise HTTPException(status_code=400, detail="Cannot generate report for future dates")
        
        report = await analytics_service.generate_daily_report(date)
        
        logger.info("Daily report generated", 
                   date=date.date(),
                   total_calls=report.get("summary", {}).get("total_calls", 0))
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate daily report", date=date, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate daily report")


@router.get("/reports/weekly")
async def get_weekly_report(
    week_start: datetime = Query(..., description="Start date of the week")
) -> Dict[str, Any]:
    """Get comprehensive weekly analytics report."""
    try:
        week_end = week_start + timedelta(days=7)
        
        # Ensure week is not in the future
        if week_start.date() > datetime.utcnow().date():
            raise HTTPException(status_code=400, detail="Cannot generate report for future dates")
        
        # Get analytics for the week
        call_analytics = await analytics_service.get_call_analytics(week_start, week_end, TimeRange.WEEK)
        lead_quality = await analytics_service.get_lead_quality_metrics(week_start, week_end)
        cost_analysis = await analytics_service.get_cost_analysis(week_start, week_end)
        conversion_funnel = await analytics_service.get_conversion_funnel(week_start, week_end)
        
        # Calculate week-over-week changes (would need previous week data)
        # For now, just return current week data
        
        report = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "summary": {
                "total_calls": call_analytics.total_calls,
                "qualified_leads": call_analytics.qualified_leads,
                "meetings_booked": call_analytics.meetings_booked,
                "total_cost": cost_analysis["total_cost"],
                "roi_percentage": call_analytics.roi_percentage
            },
            "call_analytics": call_analytics.dict(),
            "lead_quality": lead_quality.dict(),
            "cost_analysis": cost_analysis,
            "conversion_funnel": conversion_funnel,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Weekly report generated", 
                   week_start=week_start.date(),
                   total_calls=call_analytics.total_calls)
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate weekly report", week_start=week_start, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate weekly report")


@router.post("/events/call")
async def record_call_event(
    call_sid: str,
    event_type: str,
    outcome: str,
    duration: Optional[float] = None,
    lead_score: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Record a call event for analytics tracking."""
    try:
        from app.services.analytics import CallOutcome
        
        # Validate outcome
        try:
            outcome_enum = CallOutcome(outcome)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid outcome: {outcome}")
        
        await analytics_service.record_call_event(
            call_sid=call_sid,
            event_type=event_type,
            outcome=outcome_enum,
            duration=duration,
            lead_score=lead_score,
            metadata=metadata
        )
        
        logger.info("Call event recorded", 
                   call_sid=call_sid, 
                   event_type=event_type, 
                   outcome=outcome)
        
        return {"status": "success", "message": "Call event recorded"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to record call event", 
                    call_sid=call_sid, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to record call event")


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics."""
    try:
        stats = cache_manager.get_stats()
        
        return {
            "cache_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get cache stats")


@router.delete("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Pattern to match for cache clearing")
):
    """Clear cache entries matching the specified pattern."""
    try:
        if pattern:
            cleared_count = await cache_manager.clear_pattern(pattern)
            message = f"Cleared {cleared_count} cache entries matching pattern: {pattern}"
        else:
            # Clear all cache (be careful with this in production)
            cleared_count = await cache_manager.clear_pattern("*")
            message = f"Cleared all {cleared_count} cache entries"
        
        logger.info("Cache cleared", pattern=pattern, cleared_count=cleared_count)
        
        return {
            "status": "success",
            "message": message,
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        logger.error("Failed to clear cache", pattern=pattern, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to clear cache")