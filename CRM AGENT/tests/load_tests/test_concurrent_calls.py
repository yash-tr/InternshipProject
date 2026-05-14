"""
Load tests for concurrent call handling performance.
"""
import asyncio
import time
from typing import List
import pytest
import aiohttp
from unittest.mock import AsyncMock, patch

from app.core.performance import performance_monitor
from app.services.call_handler import CallHandler
from app.services.salesforce import SalesforceService


class LoadTestConfig:
    """Configuration for load testing."""
    
    MAX_CONCURRENT_CALLS = 10
    TEST_DURATION_SECONDS = 60
    RAMP_UP_SECONDS = 10
    TARGET_RESPONSE_TIME = 2.0  # seconds
    ERROR_RATE_THRESHOLD = 0.05  # 5%


class CallSimulator:
    """Simulate concurrent phone calls for load testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.call_results = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def simulate_incoming_call(self, call_id: str, phone_number: str) -> dict:
        """Simulate a single incoming call."""
        start_time = time.time()
        
        try:
            # Simulate Twilio webhook for incoming call
            webhook_data = {
                "From": phone_number,
                "CallSid": call_id,
                "To": "+1234567890",
                "CallStatus": "in-progress"
            }
            
            async with self.session.post(
                f"{self.base_url}/webhook/incoming-call",
                data=webhook_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_time = time.time() - start_time
                
                result = {
                    "call_id": call_id,
                    "phone_number": phone_number,
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": response.status == 200,
                    "error": None
                }
                
                if response.status == 200:
                    result["response_body"] = await response.text()
                
                self.call_results.append(result)
                return result
                
        except Exception as e:
            response_time = time.time() - start_time
            result = {
                "call_id": call_id,
                "phone_number": phone_number,
                "status_code": 0,
                "response_time": response_time,
                "success": False,
                "error": str(e)
            }
            self.call_results.append(result)
            return result
    
    async def simulate_conversation_turn(self, call_id: str, message: str) -> dict:
        """Simulate a conversation turn."""
        start_time = time.time()
        
        try:
            webhook_data = {
                "CallSid": call_id,
                "SpeechResult": message,
                "Confidence": "0.95"
            }
            
            async with self.session.post(
                f"{self.base_url}/webhook/conversation",
                data=webhook_data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response_time = time.time() - start_time
                
                return {
                    "call_id": call_id,
                    "message": message,
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": response.status == 200,
                    "error": None
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "call_id": call_id,
                "message": message,
                "status_code": 0,
                "response_time": response_time,
                "success": False,
                "error": str(e)
            }


@pytest.mark.asyncio
@pytest.mark.load_test
class TestConcurrentCallHandling:
    """Load tests for concurrent call handling."""
    
    @pytest.fixture
    async def call_simulator(self):
        """Create call simulator."""
        async with CallSimulator() as simulator:
            yield simulator
    
    @patch('app.services.salesforce.SalesforceService.find_or_create_contact')
    @patch('app.services.elevenlabs_service.ElevenLabsService.synthesize_speech')
    @patch('app.services.openrouter_llm.OpenRouterService.generate_response')
    async def test_concurrent_call_capacity(
        self,
        mock_llm,
        mock_tts,
        mock_salesforce,
        call_simulator
    ):
        """Test system capacity under concurrent call load."""
        
        # Mock external services for consistent testing
        mock_salesforce.return_value = {
            "Id": "003XXXXXXXXXXXXXXX",
            "Phone": "+1234567890",
            "FirstName": "Test",
            "LastName": "User"
        }
        mock_tts.return_value = "http://example.com/audio.mp3"
        mock_llm.return_value = "Thank you for calling. How can I help you today?"
        
        # Generate test phone numbers
        phone_numbers = [f"+155512345{i:02d}" for i in range(LoadTestConfig.MAX_CONCURRENT_CALLS)]
        call_ids = [f"CA{i:010d}" for i in range(LoadTestConfig.MAX_CONCURRENT_CALLS)]
        
        # Start performance monitoring
        await performance_monitor.initialize()
        
        # Execute concurrent calls
        tasks = []
        for call_id, phone in zip(call_ids, phone_numbers):
            task = call_simulator.simulate_incoming_call(call_id, phone)
            tasks.append(task)
        
        # Run all calls concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze results
        successful_calls = [r for r in results if isinstance(r, dict) and r.get('success', False)]
        failed_calls = [r for r in results if not (isinstance(r, dict) and r.get('success', False))]
        
        success_rate = len(successful_calls) / len(results)
        error_rate = len(failed_calls) / len(results)
        
        if successful_calls:
            avg_response_time = sum(r['response_time'] for r in successful_calls) / len(successful_calls)
            max_response_time = max(r['response_time'] for r in successful_calls)
            min_response_time = min(r['response_time'] for r in successful_calls)
        else:
            avg_response_time = max_response_time = min_response_time = 0
        
        # Performance assertions
        assert success_rate >= (1 - LoadTestConfig.ERROR_RATE_THRESHOLD), \
            f"Success rate {success_rate:.2%} below threshold"
        
        assert avg_response_time <= LoadTestConfig.TARGET_RESPONSE_TIME, \
            f"Average response time {avg_response_time:.2f}s exceeds target"
        
        # Log performance metrics
        print(f"\n=== Load Test Results ===")
        print(f"Total calls: {len(results)}")
        print(f"Successful calls: {len(successful_calls)}")
        print(f"Failed calls: {len(failed_calls)}")
        print(f"Success rate: {success_rate:.2%}")
        print(f"Error rate: {error_rate:.2%}")
        print(f"Average response time: {avg_response_time:.2f}s")
        print(f"Min response time: {min_response_time:.2f}s")
        print(f"Max response time: {max_response_time:.2f}s")
        print(f"Total test duration: {total_time:.2f}s")
        
        # Get system metrics
        metrics = performance_monitor.get_metrics()
        print(f"Cache hit rate: {metrics.get('cache_hits', 0) / (metrics.get('cache_hits', 0) + metrics.get('cache_misses', 1)) * 100:.1f}%")
        print(f"Active calls peak: {metrics.get('active_calls', 0)}")
    
    @patch('app.services.salesforce.SalesforceService.find_or_create_contact')
    @patch('app.services.elevenlabs_service.ElevenLabsService.synthesize_speech')
    @patch('app.services.openrouter_llm.OpenRouterService.generate_response')
    async def test_sustained_load(
        self,
        mock_llm,
        mock_tts,
        mock_salesforce,
        call_simulator
    ):
        """Test system performance under sustained load."""
        
        # Mock external services
        mock_salesforce.return_value = {"Id": "003XXXXXXXXXXXXXXX", "Phone": "+1234567890"}
        mock_tts.return_value = "http://example.com/audio.mp3"
        mock_llm.return_value = "I understand. Let me help you with that."
        
        # Start performance monitoring
        await performance_monitor.initialize()
        
        # Run sustained load test
        start_time = time.time()
        call_counter = 0
        results = []
        
        while time.time() - start_time < LoadTestConfig.TEST_DURATION_SECONDS:
            # Create batch of concurrent calls
            batch_size = min(5, LoadTestConfig.MAX_CONCURRENT_CALLS)
            batch_tasks = []
            
            for i in range(batch_size):
                call_id = f"CA{call_counter:010d}"
                phone = f"+155512345{call_counter % 100:02d}"
                call_counter += 1
                
                task = call_simulator.simulate_incoming_call(call_id, phone)
                batch_tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
            
            # Brief pause between batches
            await asyncio.sleep(0.5)
        
        total_duration = time.time() - start_time
        
        # Analyze sustained load results
        successful_calls = [r for r in results if isinstance(r, dict) and r.get('success', False)]
        calls_per_second = len(results) / total_duration
        
        if successful_calls:
            avg_response_time = sum(r['response_time'] for r in successful_calls) / len(successful_calls)
        else:
            avg_response_time = 0
        
        print(f"\n=== Sustained Load Test Results ===")
        print(f"Test duration: {total_duration:.1f}s")
        print(f"Total calls: {len(results)}")
        print(f"Calls per second: {calls_per_second:.2f}")
        print(f"Average response time: {avg_response_time:.2f}s")
        
        # Performance assertions for sustained load
        assert calls_per_second >= 2.0, f"Throughput {calls_per_second:.2f} calls/sec too low"
        assert avg_response_time <= LoadTestConfig.TARGET_RESPONSE_TIME * 1.5, \
            f"Response time degraded under sustained load"
    
    async def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Simulate memory-intensive operations
        call_handler = CallHandler()
        
        # Create many call sessions
        sessions = []
        for i in range(100):
            session_data = {
                "call_sid": f"CA{i:010d}",
                "caller_phone": f"+155512345{i:02d}",
                "conversation_history": [
                    {"role": "user", "content": f"Hello, this is test call {i}"},
                    {"role": "assistant", "content": "Thank you for calling. How can I help you?"}
                ] * 10  # Simulate long conversation
            }
            sessions.append(session_data)
        
        # Process sessions
        for session in sessions:
            # Simulate call processing without external API calls
            pass
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        print(f"\n=== Memory Usage Test ===")
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Memory growth: {memory_growth:.1f} MB")
        
        # Assert memory growth is reasonable (less than 100MB for this test)
        assert memory_growth < 100, f"Excessive memory growth: {memory_growth:.1f} MB"


@pytest.mark.asyncio
async def test_database_connection_pool():
    """Test database connection pool performance."""
    from app.core.database import init_db, get_async_session
    
    await init_db()
    
    # Test concurrent database operations
    async def db_operation():
        async for session in get_async_session():
            # Simulate database query
            await asyncio.sleep(0.1)
            return "success"
    
    # Run concurrent database operations
    tasks = [db_operation() for _ in range(20)]
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    duration = time.time() - start_time
    
    # All operations should succeed
    assert all(r == "success" for r in results)
    
    # Should complete reasonably quickly with connection pooling
    assert duration < 5.0, f"Database operations took too long: {duration:.2f}s"
    
    print(f"Database pool test: {len(results)} operations in {duration:.2f}s")


if __name__ == "__main__":
    # Run load tests directly
    asyncio.run(test_database_connection_pool())