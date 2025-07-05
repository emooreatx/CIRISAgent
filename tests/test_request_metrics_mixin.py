"""
Tests for RequestMetricsMixin - Demonstrates usage and validates functionality.
"""
import asyncio
import time
import pytest
from typing import Optional

from ciris_engine.logic.services.mixins import RequestMetricsMixin, RequestMetrics


class MockService(RequestMetricsMixin):
    """Mock service that uses RequestMetricsMixin."""
    
    def __init__(self):
        super().__init__()
        self.should_fail = False
    
    async def handle_request(self, message: str) -> str:
        """Simulate handling a request with metrics tracking."""
        request_id = self.track_request_start()
        
        try:
            # Simulate processing time
            await asyncio.sleep(0.01)  # 10ms
            
            if self.should_fail:
                raise ValueError("Simulated error")
            
            result = f"Processed: {message}"
            self.track_request_end(request_id, success=True)
            return result
            
        except Exception as e:
            self.track_request_end(request_id, success=False)
            raise


@pytest.mark.asyncio
async def test_request_metrics_basic():
    """Test basic request metrics functionality."""
    service = MockService()
    
    # Initial metrics should be empty
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 0
    assert metrics.error_count == 0
    assert metrics.average_response_time_ms == 0.0
    assert metrics.success_rate == 100.0
    assert metrics.last_request_time is None
    
    # Handle a successful request
    result = await service.handle_request("test message")
    assert result == "Processed: test message"
    
    # Check metrics after one request
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 1
    assert metrics.error_count == 0
    assert metrics.average_response_time_ms > 0  # Should have some response time
    assert metrics.average_response_time_ms < 100  # Should be fast
    assert metrics.success_rate == 100.0
    assert metrics.last_request_time is not None


@pytest.mark.asyncio
async def test_request_metrics_with_errors():
    """Test request metrics with errors."""
    service = MockService()
    
    # Handle some successful requests
    for i in range(3):
        await service.handle_request(f"message {i}")
    
    # Now cause some errors
    service.should_fail = True
    for i in range(2):
        with pytest.raises(ValueError):
            await service.handle_request(f"error {i}")
    
    # Check metrics
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 5  # 3 success + 2 errors
    assert metrics.error_count == 2
    assert metrics.success_rate == 60.0  # 3/5 = 60%
    assert metrics.average_response_time_ms > 0


@pytest.mark.asyncio
async def test_request_metrics_response_times():
    """Test response time tracking."""
    service = MockService()
    
    # Handle multiple requests with different delays
    async def delayed_request(delay_ms: int) -> None:
        request_id = service.track_request_start()
        await asyncio.sleep(delay_ms / 1000)  # Convert to seconds
        service.track_request_end(request_id, success=True)
    
    # Create requests with known delays
    await delayed_request(10)
    await delayed_request(20)
    await delayed_request(30)
    
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 3
    
    # Average should be around 20ms (10+20+30)/3
    assert 15 < metrics.average_response_time_ms < 25
    
    # Test percentiles
    p50 = service.get_response_time_percentile(50)
    assert 15 < p50 < 25  # Median should be around 20ms


@pytest.mark.asyncio
async def test_request_metrics_concurrent():
    """Test metrics with concurrent requests."""
    service = MockService()
    
    # Handle multiple concurrent requests
    tasks = []
    for i in range(10):
        tasks.append(service.handle_request(f"concurrent {i}"))
    
    results = await asyncio.gather(*tasks)
    
    # Check all completed successfully
    assert len(results) == 10
    assert all(r.startswith("Processed:") for r in results)
    
    # Check metrics
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 10
    assert metrics.error_count == 0
    assert metrics.success_rate == 100.0
    
    # Should have 10 active requests at peak (or close to it)
    # Note: By the time we check, all should be completed
    assert service.get_active_request_count() == 0


def test_request_metrics_reset():
    """Test resetting metrics."""
    service = MockService()
    
    # Track some requests synchronously for testing
    for i in range(5):
        request_id = service.track_request_start()
        time.sleep(0.001)  # 1ms
        service.track_request_end(request_id, success=i % 2 == 0)
    
    # Verify metrics exist
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 5
    assert metrics.error_count == 2  # Failed on odd numbers
    
    # Reset metrics
    service.reset_request_metrics()
    
    # Verify reset
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 0
    assert metrics.error_count == 0
    assert metrics.average_response_time_ms == 0.0
    assert metrics.success_rate == 100.0
    assert metrics.last_request_time is None


def test_request_metrics_edge_cases():
    """Test edge cases for request metrics."""
    service = MockService()
    
    # Test tracking end for non-existent request
    service.track_request_end("non_existent_id", success=True)
    metrics = service.get_request_metrics()
    assert metrics.requests_handled == 0  # Should not crash or count
    
    # Test percentile with no data
    assert service.get_response_time_percentile(50) == 0.0
    
    # Test invalid percentile - need to add some data first so it doesn't return early
    service._response_times.append(100.0)  # Add dummy data
    with pytest.raises(ValueError):
        service.get_response_time_percentile(150)
    
    # Test recent error rate with no requests
    assert service.get_recent_error_rate() == 0.0


def test_request_metrics_schema_validation():
    """Test that RequestMetrics schema follows CIRIS patterns."""
    # Create metrics with all fields
    metrics = RequestMetrics(
        requests_handled=100,
        error_count=5,
        average_response_time_ms=25.5,
        success_rate=95.0,
        last_request_time=None
    )
    
    # Verify all fields are present
    assert metrics.requests_handled == 100
    assert metrics.error_count == 5
    assert metrics.average_response_time_ms == 25.5
    assert metrics.success_rate == 95.0
    assert metrics.last_request_time is None
    
    # Test validation - negative values should fail
    with pytest.raises(ValueError):
        RequestMetrics(requests_handled=-1)
    
    with pytest.raises(ValueError):
        RequestMetrics(success_rate=150.0)  # Over 100%
    
    # Test extra fields are forbidden (CIRIS pattern)
    with pytest.raises(ValueError):
        RequestMetrics(
            requests_handled=10,
            error_count=0,
            average_response_time_ms=10.0,
            success_rate=100.0,
            extra_field="not_allowed"  # This should fail
        )