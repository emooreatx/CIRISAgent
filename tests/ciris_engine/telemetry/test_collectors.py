"""Tests for telemetry collectors."""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from ciris_engine.telemetry.collectors import (
    BaseCollector,
    InstantCollector,
    FastCollector,
    NormalCollector,
    SlowCollector,
    AggregateCollector,
    CollectorManager,
    MetricData
)
from ciris_engine.telemetry.security import SecurityFilter


class MockTestCollector(BaseCollector):
    """Test collector for base functionality."""
    
    def __init__(self, interval_ms=100):
        super().__init__(interval_ms)
        self.collected_metrics = []
        
    async def collect_raw_metrics(self):
        return [MetricData(
            name="test_metric",
            value=1.0,
            timestamp=datetime.utcnow(),
            tags={"test": "true"}
        )]
        
    async def process_metrics(self, metrics):
        self.collected_metrics.extend(metrics)


@pytest.mark.asyncio
async def test_base_collector_lifecycle():
    """Test basic collector start/stop lifecycle."""
    collector = MockTestCollector()
    assert not collector._running
    
    await collector.start()
    assert collector._running
    assert collector._task is not None
    
    # Let it collect a few metrics
    await asyncio.sleep(0.25)
    
    await collector.stop()
    assert not collector._running
    assert len(collector.collected_metrics) > 0


@pytest.mark.asyncio
async def test_collector_rate_limiting():
    """Test that collectors respect rate limiting."""
    # Create collector with very low limit
    class HighVolumeCollector(BaseCollector):
        async def collect_raw_metrics(self):
            # Return more metrics than allowed
            return [MetricData(f"metric_{i}", float(i), datetime.utcnow(), {}) 
                   for i in range(20)]
        
        async def process_metrics(self, metrics):
            self.processed_count = len(metrics)
    
    collector = HighVolumeCollector(interval_ms=100, max_metrics_per_interval=5)
    await collector.start()
    await asyncio.sleep(0.15)
    await collector.stop()
    
    # Should have been rate limited to 5
    assert collector.processed_count <= 5


@pytest.mark.asyncio
async def test_instant_collector():
    """Test instant collector for critical metrics."""
    telemetry_service = AsyncMock()
    circuit_breaker_registry = Mock()
    circuit_breaker_registry._breakers = {
        "test_breaker": Mock(state="open")
    }
    
    collector = InstantCollector(
        telemetry_service=telemetry_service,
        circuit_breaker_registry=circuit_breaker_registry
    )
    
    # Test metric collection
    metrics = await collector.collect_raw_metrics()
    assert len(metrics) > 0
    assert any("circuit_breaker" in m.name for m in metrics)
    
    # Test processing
    await collector.process_metrics(metrics)
    assert telemetry_service.record_metric.call_count > 0


@pytest.mark.asyncio 
async def test_fast_collector():
    """Test fast collector for active system metrics."""
    telemetry_service = AsyncMock()
    thought_manager = Mock(active_thoughts_count=5)
    
    collector = FastCollector(
        telemetry_service=telemetry_service,
        thought_manager=thought_manager
    )
    
    metrics = await collector.collect_raw_metrics()
    assert len(metrics) > 0
    assert any("thoughts_active_count" in m.name for m in metrics)
    
    await collector.process_metrics(metrics)
    assert telemetry_service.record_metric.call_count > 0


@pytest.mark.asyncio
async def test_normal_collector():
    """Test normal collector for resource metrics."""
    telemetry_service = AsyncMock()
    resource_monitor = Mock(current_memory_mb=512, current_cpu_percent=25.5)
    
    collector = NormalCollector(
        telemetry_service=telemetry_service,
        resource_monitor=resource_monitor
    )
    
    metrics = await collector.collect_raw_metrics()
    assert len(metrics) > 0
    assert any("resource_memory_mb" in m.name for m in metrics)
    assert any("resource_cpu_percent" in m.name for m in metrics)
    
    await collector.process_metrics(metrics)
    assert telemetry_service.record_metric.call_count > 0


@pytest.mark.asyncio
async def test_slow_collector():
    """Test slow collector with sanitization."""
    telemetry_service = AsyncMock()
    memory_service = Mock(operations_count=100)
    
    collector = SlowCollector(
        telemetry_service=telemetry_service,
        memory_service=memory_service
    )
    
    metrics = await collector.collect_raw_metrics()
    assert len(metrics) > 0
    assert any("memory_operations_total" in m.name for m in metrics)
    
    await collector.process_metrics(metrics)
    assert telemetry_service.record_metric.call_count > 0


@pytest.mark.asyncio
async def test_aggregate_collector():
    """Test aggregate collector with audit logging."""
    telemetry_service = AsyncMock()
    telemetry_service._history = {
        "test_metric": [
            (datetime.utcnow(), 1.0),
            (datetime.utcnow(), 2.0),
            (datetime.utcnow(), 3.0)
        ]
    }
    audit_service = AsyncMock()
    
    collector = AggregateCollector(
        telemetry_service=telemetry_service,
        audit_service=audit_service
    )
    
    metrics = await collector.collect_raw_metrics()
    # Should have aggregated metrics
    assert any("_30s_avg" in m.name for m in metrics)
    
    # Should audit the collection
    await collector.process_metrics(metrics)
    assert audit_service.log_action.called


@pytest.mark.asyncio
async def test_collector_manager():
    """Test collector manager functionality."""
    manager = CollectorManager()
    
    # Add test collectors
    collector1 = MockTestCollector(interval_ms=50)
    collector2 = MockTestCollector(interval_ms=100)
    
    manager.add_collector("fast", collector1)
    manager.add_collector("slow", collector2)
    
    # Start all
    await manager.start_all()
    assert collector1._running
    assert collector2._running
    
    # Let them collect
    await asyncio.sleep(0.15)
    
    # Check stats
    stats = manager.get_stats()
    assert "fast" in stats
    assert "slow" in stats
    assert stats["fast"]["running"]
    assert stats["slow"]["running"]
    
    # Stop all
    await manager.stop_all()
    assert not collector1._running
    assert not collector2._running


@pytest.mark.asyncio
async def test_security_filtering():
    """Test that collectors properly filter metrics."""
    # Create security filter that blocks certain metrics
    security_filter = SecurityFilter(
        bounds={"test_metric": (0, 10)}  # Only allow values 0-10
    )
    
    class FilterTestCollector(BaseCollector):
        def __init__(self):
            super().__init__(interval_ms=100, security_filter=security_filter)
            self.processed_metrics = []
            
        async def collect_raw_metrics(self):
            return [
                MetricData("test_metric", 5.0, datetime.utcnow(), {}),  # Should pass
                MetricData("test_metric", 15.0, datetime.utcnow(), {}),  # Should be blocked by bounds
                MetricData("error_metric", "user@example.com error", datetime.utcnow(), {}),  # Should be blocked by PII
            ]
            
        async def process_metrics(self, metrics):
            self.processed_metrics.extend(metrics)
    
    collector = FilterTestCollector()
    await collector._collect_metrics()
    
    # Should have filtered out metrics that exceed bounds or contain PII
    assert len(collector.processed_metrics) == 1
    assert collector.processed_metrics[0].name == "test_metric"
    assert collector.processed_metrics[0].value == 5.0


def test_metric_data():
    """Test MetricData structure."""
    now = datetime.utcnow()
    metric = MetricData(
        name="test_metric",
        value=42.0,
        timestamp=now,
        tags={"component": "test"}
    )
    
    assert metric.name == "test_metric"
    assert metric.value == 42.0
    assert metric.timestamp == now
    assert metric.tags["component"] == "test"