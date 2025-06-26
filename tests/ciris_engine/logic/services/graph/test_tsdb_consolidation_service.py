"""Unit tests for TSDB Consolidation Service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from ciris_engine.logic.services.graph.tsdb_consolidation_service import TSDBConsolidationService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.schemas.services.operations import MemoryOpStatus


@pytest.fixture
def mock_memory_bus():
    """Create a mock memory bus."""
    mock = Mock()
    mock.memorize = AsyncMock(return_value=Mock(status=Mock(value="OK")))
    mock.recall = AsyncMock(return_value=[])
    mock.recall_timeseries = AsyncMock(return_value=[])
    mock.search = AsyncMock(return_value=[])
    mock.forget = AsyncMock(return_value=Mock(status="ok"))
    return mock


@pytest.fixture
def mock_time_service():
    """Create a mock time service."""
    mock = Mock()
    mock.now = Mock(return_value=datetime.now(timezone.utc))
    return mock


@pytest.fixture
def tsdb_service(mock_memory_bus, mock_time_service):
    """Create a TSDB consolidation service for testing."""
    return TSDBConsolidationService(
        memory_bus=mock_memory_bus,
        time_service=mock_time_service
    )


@pytest.mark.asyncio
async def test_tsdb_service_lifecycle(tsdb_service):
    """Test TSDBConsolidationService start/stop lifecycle."""
    # Start
    await tsdb_service.start()
    assert tsdb_service._running is True
    
    # Stop
    await tsdb_service.stop()
    assert tsdb_service._running is False


@pytest.mark.asyncio
async def test_tsdb_service_consolidate_period(tsdb_service, mock_memory_bus):
    """Test consolidating TSDB data for a period."""
    # Create mock TSDB nodes
    now = datetime.now(timezone.utc)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=6)
    
    # Create mock datapoints that match what the implementation expects
    class MockDataPoint:
        def __init__(self, timestamp, metric_name, value, correlation_type, tags, correlation_id):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags
            # Remove correlation_id as TimeSeriesDataPoint doesn't have this field
    
    mock_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="api.requests",
            value=100,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="corr1"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="api.requests",
            value=150,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="corr2"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="memory.usage",
            value=512,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="corr3"
        )
    ]
    
    mock_memory_bus.recall_timeseries.return_value = mock_datapoints
    
    # Consolidate the period using the private method (public interface is through the loop)
    summary = await tsdb_service._consolidate_period(start_time, end_time)
    
    assert summary is not None
    assert isinstance(summary, TSDBSummary)
    assert summary.period_start == start_time
    assert summary.period_end == end_time
    assert "api.requests" in summary.metrics
    assert summary.metrics["api.requests"]["count"] == 2
    assert summary.metrics["api.requests"]["sum"] == 250
    assert summary.metrics["api.requests"]["avg"] == 125
    assert summary.source_node_count == 3


@pytest.mark.asyncio
async def test_tsdb_service_auto_consolidation(tsdb_service, mock_memory_bus, mock_time_service):
    """Test automatic consolidation scheduling."""
    # The service has a _calculate_next_run_time method we can test
    current_time = datetime(2024, 12, 22, 14, 30, 0, tzinfo=timezone.utc)
    mock_time_service.now.return_value = current_time
    
    # Calculate next run time
    next_run = tsdb_service._calculate_next_run_time()
    
    # Should be at 18:00 (next 6-hour boundary)
    assert next_run.hour == 18
    assert next_run.minute == 0
    assert next_run.second == 0
    assert next_run.day == 22
    
    # Test midnight rollover
    current_time = datetime(2024, 12, 22, 23, 30, 0, tzinfo=timezone.utc)
    mock_time_service.now.return_value = current_time
    
    next_run = tsdb_service._calculate_next_run_time()
    
    # Should be at 00:00 next day
    assert next_run.hour == 0
    assert next_run.minute == 0
    assert next_run.second == 0
    assert next_run.day == 23


@pytest.mark.asyncio
async def test_tsdb_service_cleanup_old_data(tsdb_service, mock_memory_bus):
    """Test cleanup of old TSDB data after consolidation."""
    # Note: Current implementation doesn't actually delete nodes yet
    # It returns 0 as a placeholder
    
    # Cleanup old data using the private method
    deleted_count = await tsdb_service._cleanup_old_nodes()
    
    # Current implementation returns 0
    assert deleted_count == 0
    # No forget calls should be made in current implementation
    assert mock_memory_bus.forget.call_count == 0


@pytest.mark.asyncio
async def test_tsdb_service_resource_aggregation(tsdb_service, mock_memory_bus):
    """Test resource usage aggregation in summaries."""
    # Create resource metric nodes
    now = datetime.now(timezone.utc)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=6)
    
    # Mock timeseries data with resource metrics
    class MockDataPoint:
        def __init__(self, timestamp, metric_name, value, correlation_type, tags, correlation_id):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags
            # Remove correlation_id as TimeSeriesDataPoint doesn't have this field
    
    resource_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="llm.tokens_used",
            value=1000,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="res1"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="llm.cost_cents",
            value=5.5,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="res2"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="carbon_grams",
            value=2.3,
            correlation_type="METRIC_DATAPOINT",
            tags={},
            correlation_id="res3"
        )
    ]
    
    mock_memory_bus.recall_timeseries.return_value = resource_datapoints
    
    # Consolidate with resource aggregation
    summary = await tsdb_service._consolidate_period(start_time, end_time)
    
    assert summary.total_tokens == 1000
    assert summary.total_cost_cents == 5.5
    assert summary.total_carbon_grams == 2.3


def test_tsdb_service_capabilities(tsdb_service):
    """Test TSDBConsolidationService.get_capabilities() returns correct info."""
    caps = tsdb_service.get_capabilities()
    
    assert isinstance(caps, ServiceCapabilities)
    assert caps.service_name == "TSDBConsolidationService"
    assert "consolidate_tsdb_nodes" in caps.actions
    assert "create_6hour_summaries" in caps.actions
    assert "cleanup_old_telemetry" in caps.actions
    assert "permanent_memory_creation" in caps.actions
    assert caps.version == "1.0.0"


def test_tsdb_service_status(tsdb_service):
    """Test TSDBConsolidationService.get_status() returns correct status."""
    status = tsdb_service.get_status()
    
    assert isinstance(status, ServiceStatus)
    assert status.service_name == "TSDBConsolidationService"
    assert status.service_type == "graph_service"
    assert "last_consolidation_timestamp" in status.metrics
    assert "task_running" in status.metrics
    assert isinstance(status.metrics["last_consolidation_timestamp"], float)
    assert isinstance(status.metrics["task_running"], float)


@pytest.mark.asyncio
async def test_tsdb_service_get_summary_for_period(tsdb_service, mock_memory_bus):
    """Test retrieving a specific TSDB summary for a period."""
    # Create a test summary
    period_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    test_summary = TSDBSummary(
        id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
        period_start=period_start,
        period_end=period_start + timedelta(hours=6),
        period_label="2024-12-22-night",
        metrics={"test.metric": {"count": 1, "sum": 100, "min": 100, "max": 100, "avg": 100}},
        source_node_count=5,
        scope=GraphScope.LOCAL,
        attributes={}  # Required by GraphNode base
    )
    
    # Mock the recall to return the summary as a GraphNode
    mock_memory_bus.recall.return_value = [test_summary.to_graph_node()]
    
    # Get summary for the period
    result = await tsdb_service.get_summary_for_period(period_start)
    
    assert result is not None
    assert isinstance(result, TSDBSummary)
    assert result.period_start == period_start
    assert result.source_node_count == 5
    
    # Verify the query was made correctly
    mock_memory_bus.recall.assert_called_once()


@pytest.mark.asyncio
async def test_tsdb_service_action_summary(tsdb_service, mock_memory_bus):
    """Test action count aggregation in summaries."""
    # Create action nodes
    now = datetime.now(timezone.utc)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=6)
    
    # Mock timeseries data with action metrics
    class MockDataPoint:
        def __init__(self, timestamp, metric_name, value, correlation_type, tags, correlation_id):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags
            # Remove correlation_id as TimeSeriesDataPoint doesn't have this field
    
    action_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="action.speak.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "SPEAK"},
            correlation_id="act1"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="action.tool.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "TOOL"},
            correlation_id="act2"
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=3),
            metric_name="action.speak.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "SPEAK"},
            correlation_id="act3"
        )
    ]
    
    mock_memory_bus.recall_timeseries.return_value = action_datapoints
    
    # Consolidate with action aggregation
    summary = await tsdb_service._consolidate_period(start_time, end_time)
    
    assert "SPEAK" in summary.action_counts
    assert summary.action_counts["SPEAK"] == 2
    assert "TOOL" in summary.action_counts
    assert summary.action_counts["TOOL"] == 1


@pytest.mark.asyncio
async def test_tsdb_service_error_handling(tsdb_service, mock_memory_bus):
    """Test error handling during consolidation."""
    # Make recall_timeseries raise an error
    mock_memory_bus.recall_timeseries.side_effect = Exception("Database error")
    
    # Consolidation should raise the error (error handling is in run method)
    with pytest.raises(Exception) as exc_info:
        await tsdb_service._consolidate_period(
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) + timedelta(hours=6)
        )
    
    # Should raise the database error
    assert str(exc_info.value) == "Database error"


@pytest.mark.asyncio
async def test_tsdb_service_typed_node_conversion(tsdb_service):
    """Test TSDBSummary TypedGraphNode conversion."""
    # Create a test summary
    summary = TSDBSummary(
        id="test_summary_20241222_00",
        scope=GraphScope.LOCAL,
        attributes={},
        period_start=datetime(2024, 12, 22, 0, 0, 0, tzinfo=timezone.utc),
        period_end=datetime(2024, 12, 22, 6, 0, 0, tzinfo=timezone.utc),
        period_label="2024-12-22-night",
        metrics={
            "test.metric": {
                "count": 10.0,
                "sum": 1000.0,
                "min": 50.0,
                "max": 150.0,
                "avg": 100.0
            }
        },
        total_tokens=5000,
        total_cost_cents=10.5,
        total_carbon_grams=15.3,
        action_counts={"SPEAK": 5, "TOOL": 3},
        error_count=1,
        success_rate=0.95,
        source_node_count=100
    )
    
    # Convert to GraphNode
    graph_node = summary.to_graph_node()
    
    assert graph_node.id == "test_summary_20241222_00"
    assert graph_node.type == NodeType.TSDB_SUMMARY  # TSDBSummary uses TSDB_SUMMARY type
    assert graph_node.scope == GraphScope.LOCAL
    assert isinstance(graph_node.attributes, dict)
    assert graph_node.attributes["period_label"] == "2024-12-22-night"
    assert graph_node.attributes["total_tokens"] == 5000
    assert graph_node.attributes["_node_class"] == "TSDBSummary"
    
    # Convert back from GraphNode
    reconstructed = TSDBSummary.from_graph_node(graph_node)
    
    assert reconstructed.id == summary.id
    assert reconstructed.period_start == summary.period_start
    assert reconstructed.period_end == summary.period_end
    assert reconstructed.period_label == summary.period_label
    assert reconstructed.metrics == summary.metrics
    assert reconstructed.total_tokens == summary.total_tokens
    assert reconstructed.total_cost_cents == summary.total_cost_cents
    assert reconstructed.action_counts == summary.action_counts
    assert reconstructed.source_node_count == summary.source_node_count


@pytest.mark.asyncio
async def test_tsdb_service_period_already_consolidated(tsdb_service, mock_memory_bus):
    """Test skipping already consolidated periods."""
    period_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(hours=6)
    
    # Mock that a summary already exists
    existing_summary = TSDBSummary(
        id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
        scope=GraphScope.LOCAL,
        attributes={},
        period_start=period_start,
        period_end=period_end,
        period_label="already-exists",
        source_node_count=10
    )
    mock_memory_bus.recall.return_value = [existing_summary.to_graph_node()]
    
    # Check if period is consolidated
    is_consolidated = await tsdb_service._is_period_consolidated(period_start, period_end)
    
    assert is_consolidated is True
    
    # Verify it queried for the summary
    mock_memory_bus.recall.assert_called_once()


@pytest.mark.asyncio
async def test_tsdb_service_node_type(tsdb_service):
    """Test that TSDBConsolidationService manages TSDB_SUMMARY nodes."""
    node_type = tsdb_service.get_node_type()
    assert node_type == NodeType.TSDB_SUMMARY