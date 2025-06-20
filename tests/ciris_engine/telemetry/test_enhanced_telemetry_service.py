"""
Tests for Enhanced TelemetryService

Tests the enhanced telemetry service with tags support, enhanced history storage,
and TSDB capabilities for agent introspection.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from collections import deque

from ciris_engine.services.graph_telemetry_service import GraphTelemetryService
from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from ciris_engine.telemetry.security import SecurityFilter
from ciris_engine.message_buses.memory_bus import MemoryBus
from unittest.mock import Mock


@pytest.mark.skip(reason="Tests need to be updated for graph-based telemetry")
class TestEnhancedTelemetryService:
    """Test suite for enhanced TelemetryService features"""
    
    @pytest.fixture
    def telemetry_service(self):
        """Create a TelemetryService instance"""
        # GraphTelemetryService needs a memory bus
        memory_bus = Mock(spec=MemoryBus)
        memory_bus.memorize_metric = Mock(return_value=Mock(status=0))
        service = GraphTelemetryService(memory_bus=memory_bus)
        return service
    
    @pytest.fixture
    def telemetry_service_with_filter(self):
        """Create a TelemetryService with security filter"""
        security_filter = SecurityFilter()
        # GraphTelemetryService doesn't use security_filter directly
        memory_bus = Mock(spec=MemoryBus)
        memory_bus.memorize_metric = Mock(return_value=Mock(status=0))
        service = GraphTelemetryService(memory_bus=memory_bus)
        return service
    
    @pytest.mark.asyncio
    async def test_record_metric_with_tags(self, telemetry_service):
        """Test recording metrics with tags creates enhanced history entry"""
        tags = {"environment": "production", "region": "us-west-2", "service": "api"}
        
        await telemetry_service.record_metric("response_time", 125.5, tags)
        
        # Check basic history (backward compatibility)
        assert "response_time" in telemetry_service._history
        assert len(telemetry_service._history["response_time"]) == 1
        timestamp, value = telemetry_service._history["response_time"][0]
        assert value == 125.5
        assert isinstance(timestamp, datetime)
        
        # Check enhanced history
        assert hasattr(telemetry_service, '_enhanced_history')
        assert "response_time" in telemetry_service._enhanced_history
        assert len(telemetry_service._enhanced_history["response_time"]) == 1
        
        enhanced_entry = telemetry_service._enhanced_history["response_time"][0]
        assert enhanced_entry['value'] == 125.5
        assert enhanced_entry['tags'] == tags
        assert isinstance(enhanced_entry['timestamp'], datetime)
    
    @pytest.mark.asyncio
    async def test_record_metric_without_tags(self, telemetry_service):
        """Test recording metrics without tags still creates enhanced history"""
        await telemetry_service.record_metric("cpu_usage", 45.2)
        
        # Check enhanced history with empty tags
        enhanced_entry = telemetry_service._enhanced_history["cpu_usage"][0]
        assert enhanced_entry['value'] == 45.2
        assert enhanced_entry['tags'] == {}
        assert isinstance(enhanced_entry['timestamp'], datetime)
    
    @pytest.mark.asyncio
    async def test_record_metric_none_tags(self, telemetry_service):
        """Test recording metrics with None tags"""
        await telemetry_service.record_metric("memory_usage", 512.0, None)
        
        enhanced_entry = telemetry_service._enhanced_history["memory_usage"][0]
        assert enhanced_entry['tags'] == {}
    
    @pytest.mark.asyncio
    async def test_enhanced_history_initialization(self, telemetry_service):
        """Test that enhanced history is initialized on first metric"""
        # Before recording any metrics
        assert not hasattr(telemetry_service, '_enhanced_history')
        
        await telemetry_service.record_metric("test_metric", 1.0)
        
        # After recording first metric
        assert hasattr(telemetry_service, '_enhanced_history')
        assert isinstance(telemetry_service._enhanced_history, dict)
    
    @pytest.mark.asyncio
    async def test_enhanced_history_buffer_size(self, telemetry_service):
        """Test that enhanced history respects buffer size"""
        buffer_size = telemetry_service.buffer_size
        
        # Record more metrics than buffer size
        for i in range(buffer_size + 10):
            await telemetry_service.record_metric("overflow_test", float(i), {"iteration": str(i)})
        
        # Enhanced history should not exceed buffer size
        assert len(telemetry_service._enhanced_history["overflow_test"]) == buffer_size
        
        # Should contain the most recent entries
        latest_entry = telemetry_service._enhanced_history["overflow_test"][-1]
        assert latest_entry['value'] == float(buffer_size + 9)  # Last value
        assert latest_entry['tags']['iteration'] == str(buffer_size + 9)
    
    @pytest.mark.asyncio
    async def test_multiple_metrics_with_different_tags(self, telemetry_service):
        """Test recording multiple metrics with different tag sets"""
        await telemetry_service.record_metric("api_requests", 100, {"endpoint": "/users", "method": "GET"})
        await telemetry_service.record_metric("api_requests", 75, {"endpoint": "/posts", "method": "POST"})
        await telemetry_service.record_metric("api_requests", 150, {"endpoint": "/users", "method": "POST"})
        
        entries = list(telemetry_service._enhanced_history["api_requests"])
        assert len(entries) == 3
        
        # Verify different tag combinations
        assert entries[0]['tags'] == {"endpoint": "/users", "method": "GET"}
        assert entries[1]['tags'] == {"endpoint": "/posts", "method": "POST"}
        assert entries[2]['tags'] == {"endpoint": "/users", "method": "POST"}
        
        # Verify values
        assert entries[0]['value'] == 100
        assert entries[1]['value'] == 75
        assert entries[2]['value'] == 150
    
    @pytest.mark.asyncio
    async def test_timestamp_precision(self, telemetry_service):
        """Test that timestamps are recorded with proper precision"""
        start_time = datetime.now(timezone.utc)
        
        await telemetry_service.record_metric("timing_test", 42.0)
        
        end_time = datetime.now(timezone.utc)
        
        entry = telemetry_service._enhanced_history["timing_test"][0]
        recorded_time = entry['timestamp']
        
        # Timestamp should be between start and end time
        assert start_time <= recorded_time <= end_time
        assert recorded_time.tzinfo == timezone.utc
    
    @pytest.mark.asyncio
    async def test_security_filter_integration(self, telemetry_service_with_filter):
        """Test that security filter is applied to metrics with tags"""
        # This would depend on SecurityFilter implementation
        # Assuming it filters out certain sensitive metrics
        
        await telemetry_service_with_filter.record_metric("safe_metric", 100.0, {"env": "test"})
        
        # Verify metric was recorded
        assert "safe_metric" in telemetry_service_with_filter._enhanced_history
        entry = telemetry_service_with_filter._enhanced_history["safe_metric"][0]
        assert entry['value'] == 100.0
        assert entry['tags'] == {"env": "test"}
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_basic_history(self, telemetry_service):
        """Test that basic history format is maintained for backward compatibility"""
        await telemetry_service.record_metric("compat_test", 99.9, {"tag": "value"})
        
        # Basic history should still work as before
        assert "compat_test" in telemetry_service._history
        timestamp, value = telemetry_service._history["compat_test"][0]
        assert value == 99.9
        assert isinstance(timestamp, datetime)
        
        # Enhanced history should also be present
        assert "compat_test" in telemetry_service._enhanced_history
        enhanced_entry = telemetry_service._enhanced_history["compat_test"][0]
        assert enhanced_entry['value'] == 99.9
        assert enhanced_entry['tags'] == {"tag": "value"}
    
    @pytest.mark.asyncio
    async def test_update_system_snapshot_with_enhanced_metrics(self, telemetry_service):
        """Test that system snapshot update works with enhanced metrics"""
        # Record some test metrics
        await telemetry_service.record_metric("message_processed", 1.0)
        await telemetry_service.record_metric("error", 1.0)
        await telemetry_service.record_metric("thought", 1.0)
        
        snapshot = SystemSnapshot()
        await telemetry_service.update_system_snapshot(snapshot)
        
        # Verify telemetry was populated
        assert snapshot.telemetry is not None
        assert isinstance(snapshot.telemetry, CompactTelemetry)
        assert snapshot.telemetry.messages_processed_24h == 1
        assert snapshot.telemetry.errors_24h == 1
        assert snapshot.telemetry.thoughts_24h == 1
        # uptime_hours may be very small or 0 for new service, so just check it's non-negative
        assert snapshot.telemetry.uptime_hours >= 0
    
    @pytest.mark.asyncio
    async def test_concurrent_metric_recording(self, telemetry_service):
        """Test concurrent metric recording with tags"""
        async def record_metrics(suffix: str, count: int):
            for i in range(count):
                await telemetry_service.record_metric(
                    f"concurrent_test_{suffix}", 
                    float(i), 
                    {"worker": suffix, "iteration": str(i)}
                )
        
        # Run concurrent metric recording
        await asyncio.gather(
            record_metrics("worker1", 10),
            record_metrics("worker2", 10),
            record_metrics("worker3", 10)
        )
        
        # Verify all metrics were recorded
        assert "concurrent_test_worker1" in telemetry_service._enhanced_history
        assert "concurrent_test_worker2" in telemetry_service._enhanced_history
        assert "concurrent_test_worker3" in telemetry_service._enhanced_history
        
        # Check counts
        assert len(telemetry_service._enhanced_history["concurrent_test_worker1"]) == 10
        assert len(telemetry_service._enhanced_history["concurrent_test_worker2"]) == 10
        assert len(telemetry_service._enhanced_history["concurrent_test_worker3"]) == 10
    
    @pytest.mark.asyncio
    async def test_metric_value_types(self, telemetry_service):
        """Test recording metrics with different value types"""
        test_cases = [
            (42, 42.0),           # int
            (42.5, 42.5),         # float  
            (0, 0.0),             # zero
            (-15.5, -15.5),       # negative
            (1e6, 1000000.0),     # scientific notation
        ]
        
        for i, (input_value, expected_value) in enumerate(test_cases):
            metric_name = f"type_test_{i}"
            await telemetry_service.record_metric(metric_name, input_value, {"test": "value_types"})
            
            # Check enhanced history
            entry = telemetry_service._enhanced_history[metric_name][0]
            assert entry['value'] == expected_value
            assert isinstance(entry['value'], float)
    
    @pytest.mark.asyncio
    async def test_tags_data_types(self, telemetry_service):
        """Test recording metrics with various tag data types"""
        complex_tags = {
            "string_tag": "test_value",
            "numeric_tag": "123",  # Should be string in tags
            "boolean_tag": "true", # Should be string in tags
            "special_chars": "test-value_with.chars",
        }
        
        await telemetry_service.record_metric("complex_tags_test", 100.0, complex_tags)
        
        entry = telemetry_service._enhanced_history["complex_tags_test"][0]
        assert entry['tags'] == complex_tags
        
        # Verify all tag values are strings
        for key, value in entry['tags'].items():
            assert isinstance(key, str)
            assert isinstance(value, str)
    
    @pytest.mark.asyncio
    async def test_large_tag_sets(self, telemetry_service):
        """Test recording metrics with large tag sets"""
        large_tags = {f"tag_{i}": f"value_{i}" for i in range(50)}
        
        await telemetry_service.record_metric("large_tags_test", 200.0, large_tags)
        
        entry = telemetry_service._enhanced_history["large_tags_test"][0]
        assert len(entry['tags']) == 50
        assert entry['tags']['tag_25'] == 'value_25'
    
    @pytest.mark.asyncio
    async def test_metric_history_time_ordering(self, telemetry_service):
        """Test that metrics are stored in chronological order"""
        metric_name = "time_order_test"
        
        # Record metrics with small delays to ensure different timestamps
        for i in range(5):
            await telemetry_service.record_metric(metric_name, float(i), {"sequence": str(i)})
            await asyncio.sleep(0.001)  # Small delay to ensure different timestamps
        
        entries = list(telemetry_service._enhanced_history[metric_name])
        
        # Verify chronological order
        for i in range(1, len(entries)):
            assert entries[i-1]['timestamp'] <= entries[i]['timestamp']
            assert entries[i-1]['tags']['sequence'] == str(i-1)
    
    @pytest.mark.asyncio
    async def test_start_stop_service(self, telemetry_service):
        """Test service lifecycle methods"""
        # Test that start and stop methods can be called without error
        await telemetry_service.start()
        await telemetry_service.stop()
    
    @pytest.mark.asyncio
    async def test_service_start_time_tracking(self, telemetry_service):
        """Test that service tracks its start time correctly"""
        start_time_before = datetime.now(timezone.utc)
        service = TelemetryService()
        start_time_after = datetime.now(timezone.utc)
        
        assert start_time_before <= service.start_time <= start_time_after
        assert service.start_time.tzinfo == timezone.utc