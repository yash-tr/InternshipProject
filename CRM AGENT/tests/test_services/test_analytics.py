"""
Tests for analytics service functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.analytics import (
    analytics_service,
    CallOutcome,
    TimeRange,
    CallAnalytics,
    LeadQualityMetrics,
    PerformanceMetrics
)


@pytest.mark.asyncio
class TestAnalyticsService:
    """Test analytics service functionality."""
    
    async def test_record_call_event(self):
        """Test recording call events."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock database session
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            # Test recording call event
            await analytics_service.record_call_event(
                call_sid="CA123456789",
                event_type="incoming",
                outcome=CallOutcome.ANSWERED,
                duration=120.5,
                lead_score=75,
                metadata={"source": "website"}
            )
            
            # Verify database call was made
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
    
    async def test_get_call_analytics_empty_data(self):
        """Test getting call analytics with no data."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock empty database result
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = None
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow()
            
            analytics = await analytics_service.get_call_analytics(start_date, end_date)
            
            # Verify empty analytics returned
            assert analytics.total_calls == 0
            assert analytics.answered_calls == 0
            assert analytics.qualified_leads == 0
            assert analytics.meetings_booked == 0
            assert analytics.answer_rate == 0.0
    
    async def test_get_call_analytics_with_data(self):
        """Test getting call analytics with sample data."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock database result with sample data
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_row = MagicMock()
            mock_row.total_calls = 100
            mock_row.answered_calls = 75
            mock_row.qualified_leads = 30
            mock_row.meetings_booked = 12
            mock_row.avg_duration = 180.5
            mock_result.fetchone.return_value = mock_row
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow()
            
            analytics = await analytics_service.get_call_analytics(start_date, end_date)
            
            # Verify analytics calculations
            assert analytics.total_calls == 100
            assert analytics.answered_calls == 75
            assert analytics.qualified_leads == 30
            assert analytics.meetings_booked == 12
            assert analytics.average_call_duration == 180.5
            assert analytics.answer_rate == 75.0  # 75/100 * 100
            assert analytics.qualification_rate == 40.0  # 30/75 * 100
            assert analytics.meeting_booking_rate == 40.0  # 12/30 * 100
    
    async def test_get_lead_quality_metrics(self):
        """Test getting lead quality metrics."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock database result
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_row = MagicMock()
            mock_row.total_leads = 50
            mock_row.high_quality = 15
            mock_row.medium_quality = 25
            mock_row.low_quality = 10
            mock_row.avg_score = 68.5
            mock_result.fetchone.return_value = mock_row
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow()
            
            metrics = await analytics_service.get_lead_quality_metrics(start_date, end_date)
            
            # Verify metrics
            assert metrics.total_leads == 50
            assert metrics.high_quality_leads == 15
            assert metrics.medium_quality_leads == 25
            assert metrics.low_quality_leads == 10
            assert metrics.average_lead_score == 68.5
    
    async def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        with patch('app.core.performance.performance_monitor') as mock_monitor:
            # Mock performance data
            mock_monitor.get_metrics.return_value = {
                'average_response_time': 1.25,
                'cache_hits': 80,
                'cache_misses': 20,
                'active_calls': 5
            }
            
            metrics = await analytics_service.get_performance_metrics()
            
            # Verify metrics
            assert metrics.average_response_time == 1.25
            assert metrics.cache_hit_rate == 80.0  # 80/(80+20) * 100
            assert metrics.concurrent_calls_peak == 5
    
    async def test_get_cost_analysis(self):
        """Test getting cost analysis."""
        with patch.object(analytics_service, 'get_call_analytics') as mock_analytics:
            # Mock call analytics
            mock_analytics.return_value = CallAnalytics(
                total_calls=100,
                answered_calls=75,
                qualified_leads=30,
                meetings_booked=12,
                average_call_duration=180.0,
                answer_rate=75.0,
                qualification_rate=40.0,
                meeting_booking_rate=40.0,
                cost_per_call=0.15,
                cost_per_qualified_lead=0.5,
                roi_percentage=150.0
            )
            
            start_date = datetime.utcnow() - timedelta(days=7)
            end_date = datetime.utcnow()
            
            cost_analysis = await analytics_service.get_cost_analysis(start_date, end_date)
            
            # Verify cost calculations
            assert cost_analysis["total_cost"] > 0
            assert "cost_breakdown" in cost_analysis
            assert "twilio" in cost_analysis["cost_breakdown"]
            assert "elevenlabs" in cost_analysis["cost_breakdown"]
            assert "llm" in cost_analysis["cost_breakdown"]
            assert cost_analysis["cost_per_call"] > 0
    
    async def test_get_conversion_funnel(self):
        """Test getting conversion funnel analysis."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock database result
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_row = MagicMock()
            mock_row.total_calls = 100
            mock_row.answered = 75
            mock_row.qualified = 30
            mock_row.meetings_booked = 12
            mock_result.fetchone.return_value = mock_row
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow()
            
            funnel = await analytics_service.get_conversion_funnel(start_date, end_date)
            
            # Verify funnel data
            assert funnel["stages"]["calls_made"] == 100
            assert funnel["stages"]["calls_answered"] == 75
            assert funnel["stages"]["leads_qualified"] == 30
            assert funnel["stages"]["meetings_booked"] == 12
            
            # Verify conversion rates
            assert funnel["conversion_rates"]["answer_rate"] == 75.0
            assert funnel["conversion_rates"]["qualification_rate"] == 40.0
            assert funnel["conversion_rates"]["meeting_booking_rate"] == 40.0
            assert funnel["conversion_rates"]["overall_conversion"] == 12.0
    
    async def test_generate_daily_report(self):
        """Test generating comprehensive daily report."""
        with patch.multiple(
            analytics_service,
            get_call_analytics=AsyncMock(return_value=CallAnalytics(
                total_calls=50,
                answered_calls=40,
                qualified_leads=15,
                meetings_booked=6,
                average_call_duration=150.0,
                answer_rate=80.0,
                qualification_rate=37.5,
                meeting_booking_rate=40.0,
                cost_per_call=0.15,
                cost_per_qualified_lead=0.5,
                roi_percentage=200.0
            )),
            get_lead_quality_metrics=AsyncMock(return_value=LeadQualityMetrics(
                total_leads=15,
                high_quality_leads=5,
                medium_quality_leads=8,
                low_quality_leads=2,
                average_lead_score=72.5,
                qualification_accuracy=85.0,
                false_positive_rate=10.0,
                false_negative_rate=5.0
            )),
            get_performance_metrics=AsyncMock(return_value=PerformanceMetrics(
                average_response_time=1.2,
                p95_response_time=2.5,
                p99_response_time=4.0,
                error_rate=2.0,
                uptime_percentage=99.8,
                cache_hit_rate=75.0,
                concurrent_calls_peak=8,
                api_call_efficiency=90.0
            )),
            get_cost_analysis=AsyncMock(return_value={
                "total_cost": 25.50,
                "cost_breakdown": {
                    "twilio": 10.00,
                    "elevenlabs": 12.00,
                    "llm": 1.50,
                    "infrastructure": 2.00
                },
                "cost_per_call": 0.51,
                "cost_per_qualified_lead": 1.70
            }),
            get_conversion_funnel=AsyncMock(return_value={
                "stages": {
                    "calls_made": 50,
                    "calls_answered": 40,
                    "leads_qualified": 15,
                    "meetings_booked": 6
                },
                "conversion_rates": {
                    "answer_rate": 80.0,
                    "qualification_rate": 37.5,
                    "meeting_booking_rate": 40.0,
                    "overall_conversion": 12.0
                }
            })
        ):
            report_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            report = await analytics_service.generate_daily_report(report_date)
            
            # Verify report structure
            assert "date" in report
            assert "summary" in report
            assert "call_analytics" in report
            assert "lead_quality" in report
            assert "performance" in report
            assert "cost_analysis" in report
            assert "conversion_funnel" in report
            assert "generated_at" in report
            
            # Verify summary data
            summary = report["summary"]
            assert summary["total_calls"] == 50
            assert summary["qualified_leads"] == 15
            assert summary["meetings_booked"] == 6
            assert summary["total_cost"] == 25.50
            assert summary["roi_percentage"] == 200.0
    
    async def test_cache_integration(self):
        """Test analytics caching integration."""
        with patch('app.core.cache.cache_manager') as mock_cache:
            # Mock cache miss then hit
            mock_cache.get.side_effect = [None, {"total_calls": 100}]
            mock_cache.set.return_value = True
            
            with patch('app.services.analytics.get_async_session') as mock_session:
                # Mock database
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_row = MagicMock()
                mock_row.total_calls = 100
                mock_row.answered_calls = 75
                mock_row.qualified_leads = 30
                mock_row.meetings_booked = 12
                mock_row.avg_duration = 180.0
                mock_result.fetchone.return_value = mock_row
                mock_db.execute.return_value = mock_result
                mock_session.return_value.__aenter__.return_value = mock_db
                mock_session.return_value.__aexit__.return_value = None
                
                start_date = datetime.utcnow() - timedelta(days=1)
                end_date = datetime.utcnow()
                
                # First call should hit database and cache result
                analytics1 = await analytics_service.get_call_analytics(start_date, end_date)
                
                # Verify cache was called
                mock_cache.get.assert_called()
                mock_cache.set.assert_called()
                
                # Second call should hit cache
                analytics2 = await analytics_service.get_call_analytics(start_date, end_date)
                
                # Verify both calls returned data
                assert analytics1.total_calls == 100
                assert analytics2 is not None  # Would be from cache mock


@pytest.mark.asyncio
class TestAnalyticsErrorHandling:
    """Test analytics error handling."""
    
    async def test_database_error_handling(self):
        """Test handling of database errors."""
        with patch('app.services.analytics.get_async_session') as mock_session:
            # Mock database error
            mock_session.side_effect = Exception("Database connection failed")
            
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow()
            
            # Should return empty analytics instead of raising exception
            analytics = await analytics_service.get_call_analytics(start_date, end_date)
            
            assert analytics.total_calls == 0
            assert analytics.answer_rate == 0.0
    
    async def test_cache_error_handling(self):
        """Test handling of cache errors."""
        with patch('app.core.cache.cache_manager') as mock_cache:
            # Mock cache error
            mock_cache.get.side_effect = Exception("Redis connection failed")
            mock_cache.set.side_effect = Exception("Redis connection failed")
            
            with patch('app.services.analytics.get_async_session') as mock_session:
                # Mock successful database call
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_row = MagicMock()
                mock_row.total_calls = 50
                mock_row.answered_calls = 40
                mock_row.qualified_leads = 15
                mock_row.meetings_booked = 6
                mock_row.avg_duration = 120.0
                mock_result.fetchone.return_value = mock_row
                mock_db.execute.return_value = mock_result
                mock_session.return_value.__aenter__.return_value = mock_db
                mock_session.return_value.__aexit__.return_value = None
                
                start_date = datetime.utcnow() - timedelta(days=1)
                end_date = datetime.utcnow()
                
                # Should still work despite cache errors
                analytics = await analytics_service.get_call_analytics(start_date, end_date)
                
                assert analytics.total_calls == 50
                assert analytics.answered_calls == 40