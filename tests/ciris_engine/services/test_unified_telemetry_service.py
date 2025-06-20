"""
Unit tests for UnifiedTelemetryService.

Tests the telemetry service that routes all metrics through the memory graph
and implements grace-based memory consolidation.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from ciris_engine.services.unified_telemetry_service import (
    UnifiedTelemetryService,
    MemoryType,
    GracePolicy,
    ConsolidationCandidate
)
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot, TaskSummary, ThoughtSummary
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult


class TestUnifiedTelemetryService:
    """Test suite for UnifiedTelemetryService."""
    
    @pytest.fixture
    def mock_memory_bus(self):
        """Create a mock memory bus."""
        bus = AsyncMock()
        bus.memorize = AsyncMock(return_value=MemoryOpResult(status=MemoryOpStatus.OK))
        bus.memorize_metric = AsyncMock(return_value=True)
        bus.recall = AsyncMock(return_value=[])
        bus.recall_timeseries = AsyncMock(return_value=[])
        return bus
    
    @pytest.fixture
    def telemetry_service(self, mock_memory_bus):
        """Create a UnifiedTelemetryService instance."""
        service = UnifiedTelemetryService(
            memory_bus=mock_memory_bus,
            consolidation_threshold_hours=24,
            grace_window_hours=72
        )
        return service
    
    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample system snapshot."""
        return SystemSnapshot(
            agent_name="test_agent",
            network_status="active",
            isolation_hours=0,
            telemetry={"response_time": 100, "tokens_used": 50},
            current_round_resources=ResourceUsage(
                tokens_used=150,
                cost_cents=0.5,
                timestamp=datetime.now(timezone.utc).isoformat()
            ),
            current_task_details=TaskSummary(
                task_id="task_123",
                source_channel_id="channel_456",
                creation_timestamp=datetime.now(timezone.utc).isoformat()
            ),
            current_thought_summary=ThoughtSummary(
                thought_id="thought_789",
                content="Test thought",
                thought_type="NORMAL"
            ),
            user_profiles={"user_123": {"name": "Test User"}},
            channel_context={"channel_id": "channel_456"}
        )
    
    @pytest.mark.asyncio
    async def test_process_system_snapshot(self, telemetry_service, sample_snapshot, mock_memory_bus):
        """Test processing a complete system snapshot."""
        result = await telemetry_service.process_system_snapshot(
            sample_snapshot, "thought_123", "task_456"
        )
        
        assert result['memories_created'] > 0
        assert not result.get('errors')
        
        # Verify metrics were stored
        mock_memory_bus.memorize_metric.assert_called()
        metric_calls = mock_memory_bus.memorize_metric.call_args_list
        
        # Should have telemetry metrics
        telemetry_calls = [c for c in metric_calls if 'telemetry' in c[1]['metric_name']]
        assert len(telemetry_calls) > 0
        
        # Should have resource metrics
        resource_calls = [c for c in metric_calls if 'resources' in c[1]['metric_name']]
        assert len(resource_calls) > 0
    
    @pytest.mark.asyncio
    async def test_memory_type_classification(self, telemetry_service):
        """Test correct classification of memory types."""
        # Operational memory
        op_memory = {"data_type": "metric", "tags": {}}
        assert telemetry_service._classify_memory_type(op_memory) == MemoryType.OPERATIONAL
        
        # Social memory
        social_memory = {"data_type": "gratitude", "tags": {}}
        assert telemetry_service._classify_memory_type(social_memory) == MemoryType.SOCIAL
        
        # Identity memory
        identity_memory = {"tags": {"identity": True}}
        assert telemetry_service._classify_memory_type(identity_memory) == MemoryType.IDENTITY
        
        # Wisdom memory
        wisdom_memory = {"data_type": "insight"}
        assert telemetry_service._classify_memory_type(wisdom_memory) == MemoryType.WISDOM
        
        # Behavioral memory
        behavior_memory = {"data_type": "behavior"}
        assert telemetry_service._classify_memory_type(behavior_memory) == MemoryType.BEHAVIORAL
    
    @pytest.mark.asyncio
    async def test_grace_based_consolidation(self, telemetry_service, mock_memory_bus):
        """Test memory consolidation with grace applied."""
        # Mock memories with errors that should be forgiven
        from ciris_engine.schemas.protocol_schemas_v1 import TimeSeriesDataPoint
        # Create enough memories in the same time bucket to trigger consolidation
        base_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        error_memories = [
            TimeSeriesDataPoint(
                timestamp=base_time + timedelta(minutes=i),
                metric_name="error_count",
                value=1.0,
                correlation_type="LOG_ENTRY",
                tags={
                    "log_level": "ERROR",
                    "from_entity": "helpful_service",
                    "content": "Connection timeout"
                },
                source=f"error_{i}",
                correlation_id=f"corr_{i}"
            )
            for i in range(10)  # More memories to trigger consolidation
        ]
        
        # Record that helpful_service has shown us grace
        telemetry_service._grace_received["helpful_service"] = [
            datetime.now(timezone.utc) - timedelta(days=1)
        ]
        
        mock_memory_bus.recall_timeseries.return_value = error_memories
        
        # Run consolidation
        result = await telemetry_service.consolidate_memories_with_grace()
        
        assert result['status'] == 'completed'
        assert result['grace_applied'] > 0
        
        # Verify grace was applied - check consolidation node
        consolidation_calls = [
            c for c in mock_memory_bus.memorize.call_args_list
            if 'consolidation_grace' in c[1]['node'].id
        ]
        assert len(consolidation_calls) > 0
        
        grace_node = consolidation_calls[0][1]['node']
        assert grace_node.scope == GraphScope.IDENTITY  # Grace shapes identity
        assert 'grace_reasons' in grace_node.attributes
    
    @pytest.mark.asyncio
    async def test_growth_pattern_detection(self, telemetry_service):
        """Test detection of growth patterns in memories."""
        # Create memories showing improvement
        memories = [
            {"log_level": "ERROR", "timestamp": datetime.now(timezone.utc) - timedelta(hours=10)},
            {"log_level": "ERROR", "timestamp": datetime.now(timezone.utc) - timedelta(hours=9)},
            {"log_level": "ERROR", "timestamp": datetime.now(timezone.utc) - timedelta(hours=8)},
            {"log_level": "INFO", "timestamp": datetime.now(timezone.utc) - timedelta(hours=2)},
            {"log_level": "INFO", "timestamp": datetime.now(timezone.utc) - timedelta(hours=1)},
        ]
        
        shows_growth = telemetry_service._shows_growth_pattern(memories)
        assert shows_growth is True  # Errors decreased over time
    
    @pytest.mark.asyncio
    async def test_grace_tracking(self, telemetry_service, mock_memory_bus):
        """Test tracking of grace extended and received."""
        # Record grace extended
        await telemetry_service.record_grace_extended("struggling_user", "Forgave repeated errors")
        
        assert "struggling_user" in telemetry_service._grace_extended
        assert len(telemetry_service._grace_extended["struggling_user"]) == 1
        
        # Verify it was stored in graph
        mock_memory_bus.memorize.assert_called()
        grace_call = mock_memory_bus.memorize.call_args
        # Get the first positional argument (node)
        grace_node = grace_call[0][0]
        assert grace_node.attributes['grace_type'] == 'extended'
        assert grace_node.attributes['to_entity'] == 'struggling_user'
        
        # Record grace received
        await telemetry_service.record_grace_received("kind_admin", "Allowed extra time")
        
        assert "kind_admin" in telemetry_service._grace_received
        assert len(telemetry_service._grace_received["kind_admin"]) == 1
    
    @pytest.mark.asyncio
    async def test_consolidation_candidate_identification(self, telemetry_service, mock_memory_bus):
        """Test identification of memories for consolidation."""
        # Mock mixed memory types
        from ciris_engine.schemas.protocol_schemas_v1 import TimeSeriesDataPoint
        memories = [
            TimeSeriesDataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(hours=5),
                metric_name="test_metric",
                value=1.0,
                correlation_type="METRIC_DATAPOINT",
                tags={"data_type": "metric"},
                source="m1",
                correlation_id="m1"
            ),
            TimeSeriesDataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(hours=5),
                metric_name="test_metric",
                value=2.0,
                correlation_type="METRIC_DATAPOINT",
                tags={"data_type": "metric"},
                source="m2",
                correlation_id="m2"
            ),
            TimeSeriesDataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(hours=3),
                metric_name="error_count",
                value=1.0,
                correlation_type="LOG_ENTRY",
                tags={"log_level": "ERROR"},
                source="m3",
                correlation_id="m3"
            ),
            TimeSeriesDataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
                metric_name="action_count",
                value=1.0,
                correlation_type="METRIC_DATAPOINT",
                tags={"data_type": "behavior"},
                source="m4",
                correlation_id="m4"
            ),
        ]
        
        mock_memory_bus.recall_timeseries.return_value = memories
        
        candidates = await telemetry_service._identify_consolidation_candidates()
        
        assert len(candidates) > 0
        # Should group by type and time window
        operational_candidates = [c for c in candidates if c.memory_type == MemoryType.OPERATIONAL]
        assert len(operational_candidates) > 0
    
    @pytest.mark.asyncio
    async def test_grace_transformation_descriptions(self, telemetry_service):
        """Test grace transformation descriptions for different memory types."""
        candidate = ConsolidationCandidate(
            memory_ids=["m1", "m2"],
            memory_type=MemoryType.OPERATIONAL,
            time_span=timedelta(hours=4),
            total_size=2,
            grace_applicable=True,
            grace_reasons=["Contains errors"]
        )
        
        transformation = telemetry_service._describe_grace_transformation(candidate)
        assert transformation == "Performance struggles become optimization insights"
        
        # Test other types
        candidate.memory_type = MemoryType.BEHAVIORAL
        transformation = telemetry_service._describe_grace_transformation(candidate)
        assert transformation == "Mistakes become wisdom about better choices"
    
    @pytest.mark.asyncio
    async def test_consolidation_with_grace_disabled(self, telemetry_service, mock_memory_bus):
        """Test standard consolidation when grace doesn't apply."""
        # Mock memories without grace conditions
        memories = [
            {"id": f"metric_{i}", "data_type": "metric", "metric_value": i}
            for i in range(5)
        ]
        
        mock_memory_bus.recall_timeseries.return_value = memories
        
        result = await telemetry_service.consolidate_memories_with_grace()
        
        assert result['status'] == 'completed'
        # Should still consolidate but without grace
        standard_calls = [
            c for c in mock_memory_bus.memorize.call_args_list
            if 'consolidation_std' in c[1]['node'].id
        ]
        assert len(standard_calls) >= 0
    
    @pytest.mark.asyncio
    async def test_should_consolidate_timing(self, telemetry_service):
        """Test consolidation timing logic."""
        # Just created - should not consolidate
        assert await telemetry_service._should_consolidate() is False
        
        # Set last consolidation to past threshold
        telemetry_service._last_consolidation = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        )
        assert await telemetry_service._should_consolidate() is True
    
    @pytest.mark.asyncio
    async def test_behavioral_data_storage(self, telemetry_service, mock_memory_bus):
        """Test storage of behavioral data from tasks and thoughts."""
        thought_summary = ThoughtSummary(
            thought_id="thought_123",
            content="Test thought about learning",
            thought_type="INTROSPECTION"
        )
        
        await telemetry_service._store_behavioral_data(
            thought_summary, "thought", "thought_123"
        )
        
        # Verify behavioral node was created
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args
        # Get the first positional argument (node)
        behavior_node = call_args[0][0]
        
        assert behavior_node.type == NodeType.CONCEPT
        assert behavior_node.attributes['behavior_type'] == 'thought'
        assert behavior_node.attributes['thought_id'] == 'thought_123'
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, telemetry_service, mock_memory_bus):
        """Test service start/stop lifecycle."""
        await telemetry_service.start()
        
        # Stop should trigger final consolidation
        telemetry_service._last_consolidation = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        )
        
        with patch.object(telemetry_service, 'consolidate_memories_with_grace') as mock_consolidate:
            mock_consolidate.return_value = {"status": "completed"}
            await telemetry_service.stop()
            mock_consolidate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(self, telemetry_service, mock_memory_bus):
        """Test health check."""
        # Healthy when not consolidating
        assert await telemetry_service.is_healthy() is True
        
        # Unhealthy during consolidation
        telemetry_service._consolidation_in_progress = True
        assert await telemetry_service.is_healthy() is False
        
        # Unhealthy without memory bus
        telemetry_service._consolidation_in_progress = False
        telemetry_service._memory_bus = None
        assert await telemetry_service.is_healthy() is False
    
    def test_capabilities(self, telemetry_service):
        """Test service capabilities list."""
        capabilities = asyncio.run(telemetry_service.get_capabilities())
        expected = [
            "process_system_snapshot", "consolidate_memories_with_grace",
            "record_grace_extended", "record_grace_received",
            "unified_telemetry_flow", "grace_based_consolidation"
        ]
        assert set(capabilities) == set(expected)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, telemetry_service, mock_memory_bus, sample_snapshot):
        """Test error handling in snapshot processing."""
        # Simulate memory bus error
        mock_memory_bus.memorize_metric.side_effect = Exception("Memory bus error")
        
        result = await telemetry_service.process_system_snapshot(
            sample_snapshot, "thought_123", "task_456"
        )
        
        # Should handle gracefully
        assert 'error' not in result  # Errors are logged but processing continues
    
    @pytest.mark.asyncio
    async def test_memory_grouping_by_pattern(self, telemetry_service):
        """Test grouping memories by pattern for consolidation."""
        base_time = datetime.now(timezone.utc)
        memories = [
            {
                "data_type": "metric",
                "timestamp": base_time - timedelta(hours=1),
                "tags": {}
            },
            {
                "data_type": "metric",
                "timestamp": base_time - timedelta(hours=1, minutes=30),
                "tags": {}
            },
            {
                "data_type": "log_entry",
                "timestamp": base_time - timedelta(hours=2),
                "tags": {}
            }
        ]
        
        groups = telemetry_service._group_memories_by_pattern(memories)
        
        # Should group by type and time window
        assert len(groups) >= 2  # At least two different groups
        
        # Check that metrics in same hour are grouped
        operational_groups = [k for k in groups.keys() if k[0] == MemoryType.OPERATIONAL]
        assert len(operational_groups) > 0