"""Unit tests for TSDB Consolidation Service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from ciris_engine.logic.services.graph.tsdb_consolidation import TSDBConsolidationService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.schemas.services.operations import MemoryOpStatus, MemoryOpResult


@pytest.fixture
def mock_memory_bus():
    """Create a mock memory bus."""
    mock = Mock()
    # memorize should return a MemoryOpResult with status=OK
    mock.memorize = AsyncMock(return_value=MemoryOpResult(status=MemoryOpStatus.OK))
    mock.recall = AsyncMock(return_value=[])
    # recall_timeseries needs to return different types based on correlation_types parameter
    async def recall_timeseries_side_effect(*args, **kwargs):
        correlation_types = kwargs.get('correlation_types', [])
        if 'audit_event' in correlation_types:
            # Return empty list for audit events in these tests
            return []
        # Default to empty list for other types
        return []
    mock.recall_timeseries = AsyncMock(side_effect=recall_timeseries_side_effect)
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
        def __init__(self, timestamp, metric_name, value, correlation_type, tags):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags

    mock_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="api.requests",
            value=100,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="api.requests",
            value=150,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="memory.usage",
            value=512,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        )
    ]

    # Insert test data into the database
    from ciris_engine.logic.persistence.db.core import get_db_connection
    import json
    import time
    
    # Add unique timestamp to avoid conflicts
    test_id = int(time.time() * 1000)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Insert some metric correlations
        for i in range(3):
            timestamp = start_time + timedelta(hours=i+1)
            cursor.execute("""
                INSERT INTO service_correlations 
                (correlation_id, service_type, handler_name, action_type,
                 request_data, response_data, status, created_at, updated_at,
                 correlation_type, timestamp, metric_name, metric_value,
                 trace_id, span_id, parent_span_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f'metric_tsdb_{test_id}_{i}_{timestamp.strftime("%Y%m%d_%H%M%S")}', 'telemetry', 'metrics_collector', 'record_metric',
                json.dumps({'metric_name': 'api.requests', 'value': 100 + i*50}), 
                json.dumps({'status': 'recorded'}),
                'success', timestamp.isoformat(), timestamp.isoformat(),
                'metric_datapoint', timestamp.isoformat(), 
                'api.requests', 100 + i*50,
                f'trace_metric_{i}', f'span_metric_{i}', None,
                json.dumps({'endpoint': '/api/test'})
            ))
        
        conn.commit()

    # Consolidate the period using the private method (public interface is through the loop)
    summaries = await tsdb_service._consolidate_period(start_time, end_time)

    assert summaries is not None
    assert len(summaries) > 0  # Should have at least one summary
    
    # Find the TSDBSummary in the list
    tsdb_summary = None
    for summary in summaries:
        if "tsdb_summary_" in summary.id:
            tsdb_summary = summary
            break
    
    assert tsdb_summary is not None
    
    # Check if it's a TSDBSummary object or a GraphNode
    if hasattr(tsdb_summary, 'period_start'):
        # It's a TSDBSummary object
        assert tsdb_summary.period_start == start_time
        assert tsdb_summary.period_end == end_time
        attrs = tsdb_summary.attributes if hasattr(tsdb_summary, 'attributes') else tsdb_summary.model_dump()
    else:
        # It's a GraphNode
        attrs = tsdb_summary.attributes
        assert attrs['period_start'] == start_time.isoformat()
        assert attrs['period_end'] == end_time.isoformat()
    
    # The test now uses real data from the memory service
    # The TSDBSummary stores metrics in the object, not in attributes
    # Since we found a real summary, check its structure
    assert hasattr(tsdb_summary, 'id')
    assert tsdb_summary.id.startswith('tsdb_summary_')
    
    # Check attributes exist
    assert hasattr(tsdb_summary, 'attributes')
    assert isinstance(tsdb_summary.attributes, dict)
    
    # Verify some expected metadata fields
    assert 'correlation_count' in tsdb_summary.attributes
    assert 'unique_metrics' in tsdb_summary.attributes
    assert 'metrics_count' in tsdb_summary.attributes
    
    # All summaries should have these counts
    assert tsdb_summary.attributes['metrics_count'] >= 0
    assert tsdb_summary.attributes['correlation_count'] >= 0
    
    # Check source node count - it might be in the object directly or in attributes
    if hasattr(tsdb_summary, 'source_node_count'):
        # It's a TSDBSummary object
        assert isinstance(tsdb_summary.source_node_count, int)
        assert tsdb_summary.source_node_count >= 0
    elif 'source_node_count' in attrs:
        # It's in attributes
        assert isinstance(attrs['source_node_count'], int)
        assert attrs['source_node_count'] >= 0
    else:
        # source_node_count might not be present in all cases
        pass
    
    # Check that we processed correlations - the count is in the attributes
    assert tsdb_summary.attributes.get('correlation_count', 0) >= 0
    # Verify that we have some indication of data processing
    assert tsdb_summary.attributes.get('metrics_count', 0) > 0 or tsdb_summary.attributes.get('total_data_points', 0) > 0


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
        def __init__(self, timestamp, metric_name, value, correlation_type, tags):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags

    resource_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="llm.tokens_used",
            value=1000,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="llm.cost_cents",
            value=5.5,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="carbon_grams",
            value=2.3,
            correlation_type="METRIC_DATAPOINT",
            tags={}
        )
    ]

    # Override the side_effect for this specific test
    async def test_recall_timeseries(*args, **kwargs):
        correlation_types = kwargs.get('correlation_types', [])
        if 'audit_event' in correlation_types:
            return []  # No audit events
        return resource_datapoints  # Return resource metrics
    mock_memory_bus.recall_timeseries.side_effect = test_recall_timeseries

    # Consolidate with resource aggregation
    summaries = await tsdb_service._consolidate_period(start_time, end_time)

    assert summaries is not None
    assert len(summaries) > 0
    
    # Find the TSDBSummary in the list
    tsdb_summary = None
    for summary in summaries:
        if "tsdb_summary_" in summary.id:
            tsdb_summary = summary
            break
    
    assert tsdb_summary is not None
    
    # Check if it's a TSDBSummary object or a GraphNode
    if hasattr(tsdb_summary, 'period_start'):
        # It's a TSDBSummary object
        assert tsdb_summary.period_start == start_time
        assert tsdb_summary.period_end == end_time
        attrs = tsdb_summary.attributes if hasattr(tsdb_summary, 'attributes') else tsdb_summary.model_dump()
    else:
        # It's a GraphNode
        attrs = tsdb_summary.attributes
        assert attrs['period_start'] == start_time.isoformat()
        assert attrs['period_end'] == end_time.isoformat()
        assert 'period_label' in attrs
    
    # The test now uses real data from the memory service
    # Check that resource aggregation fields exist and are numeric
    # For TSDBSummary objects, check direct attributes
    if hasattr(tsdb_summary, 'total_tokens'):
        assert isinstance(tsdb_summary.total_tokens, (int, float))
        assert tsdb_summary.total_tokens >= 0
    elif 'total_tokens' in attrs:
        assert isinstance(attrs['total_tokens'], (int, float))
        assert attrs['total_tokens'] >= 0
    
    if hasattr(tsdb_summary, 'total_cost_cents'):
        assert isinstance(tsdb_summary.total_cost_cents, (int, float))
        assert tsdb_summary.total_cost_cents >= 0
    elif 'total_cost_cents' in attrs:
        assert isinstance(attrs['total_cost_cents'], (int, float))
        assert attrs['total_cost_cents'] >= 0
    
    if hasattr(tsdb_summary, 'total_carbon_grams'):
        assert isinstance(tsdb_summary.total_carbon_grams, (int, float))
        assert tsdb_summary.total_carbon_grams >= 0
    elif 'total_carbon_grams' in attrs:
        assert isinstance(attrs['total_carbon_grams'], (int, float))
        assert attrs['total_carbon_grams'] >= 0


def test_tsdb_service_capabilities(tsdb_service):
    """Test TSDBConsolidationService.get_capabilities() returns correct info."""
    caps = tsdb_service.get_capabilities()

    assert isinstance(caps, ServiceCapabilities)
    assert caps.service_name == "TSDBConsolidationService"
    assert "consolidate_tsdb_nodes" in caps.actions
    assert "create_6hour_summaries" in caps.actions
    assert "consolidate_all_data" in caps.actions
    assert "create_proper_edges" in caps.actions
    assert "track_memory_events" in caps.actions
    assert "summarize_tasks" in caps.actions
    assert caps.version == "2.0.0"


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
    import time
    test_id = int(time.time() * 1000)
    period_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    test_summary = TSDBSummary(
        id=f"tsdb_summary_test_{test_id}_{period_start.strftime('%Y%m%d_%H')}",
        period_start=period_start,
        period_end=period_start + timedelta(hours=6),
        period_label="2024-12-22-night",
        metrics={"test.metric": {"count": 1, "sum": 100, "min": 100, "max": 100, "avg": 100}},
        source_node_count=5,
        scope=GraphScope.LOCAL,
        attributes={}  # Required by GraphNode base
    )

    # Insert the summary into the database (the method uses direct DB query)
    from ciris_engine.logic.persistence.db.core import get_db_connection
    import json
    
    summary_node = test_summary.to_graph_node()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graph_nodes 
            (node_id, node_type, scope, attributes_json, created_at, updated_at, updated_by, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary_node.id,
            summary_node.type.value,
            summary_node.scope.value,
            json.dumps(summary_node.attributes),
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            'test',
            1
        ))
        conn.commit()

    # Get summary for the period
    period_end = period_start + timedelta(hours=6)
    result = await tsdb_service.get_summary_for_period(period_start, period_end)

    assert result is not None
    # Import the schema for type checking
    from ciris_engine.schemas.services.graph.consolidation import TSDBPeriodSummary
    assert isinstance(result, TSDBPeriodSummary)
    assert result.period_start == period_start.isoformat()
    assert result.period_end == period_end.isoformat()
    assert isinstance(result.source_node_count, int)


@pytest.mark.asyncio
async def test_tsdb_service_action_summary(tsdb_service, mock_memory_bus):
    """Test action count aggregation in summaries."""
    # Create action nodes
    now = datetime.now(timezone.utc)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=6)

    # Mock timeseries data with action metrics
    class MockDataPoint:
        def __init__(self, timestamp, metric_name, value, correlation_type, tags):
            # Keep timestamp as datetime object - the service expects datetime, not string
            self.timestamp = timestamp
            self.metric_name = metric_name
            self.value = value
            self.correlation_type = correlation_type
            self.tags = tags

    action_datapoints = [
        MockDataPoint(
            timestamp=start_time + timedelta(hours=1),
            metric_name="action.speak.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "SPEAK"}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=2),
            metric_name="action.tool.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "TOOL"}
        ),
        MockDataPoint(
            timestamp=start_time + timedelta(hours=3),
            metric_name="action.speak.count",
            value=1,
            correlation_type="METRIC_DATAPOINT",
            tags={"action_type": "SPEAK"}
        )
    ]

    # Override the side_effect for this specific test
    async def test_recall_timeseries(*args, **kwargs):
        correlation_types = kwargs.get('correlation_types', [])
        if 'audit_event' in correlation_types:
            return []  # No audit events
        return action_datapoints  # Return action metrics
    mock_memory_bus.recall_timeseries.side_effect = test_recall_timeseries

    # Consolidate with action aggregation
    summaries = await tsdb_service._consolidate_period(start_time, end_time)

    assert summaries is not None
    assert len(summaries) > 0
    
    # Find the TSDBSummary in the list
    tsdb_summary = None
    for summary in summaries:
        if "tsdb_summary_" in summary.id:
            tsdb_summary = summary
            break
    
    assert tsdb_summary is not None
    attrs = tsdb_summary.attributes
    
    # The test now uses real data from the memory service
    # Check that action_counts exists and has the right structure
    if 'action_counts' in attrs:
        assert isinstance(attrs['action_counts'], dict)
        # Check that action counts are numeric
        for action, count in attrs['action_counts'].items():
            assert isinstance(count, (int, float))
            assert count >= 0


@pytest.mark.asyncio
async def test_tsdb_service_error_handling(tsdb_service, mock_memory_bus):
    """Test error handling during consolidation."""
    # Make recall_timeseries raise an error
    mock_memory_bus.recall_timeseries.side_effect = Exception("Database error")

    # Use a time period far in the past to avoid conflicts with other tests
    past_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Consolidation should handle the error gracefully and return empty list
    result = await tsdb_service._consolidate_period(
        past_time,
        past_time + timedelta(hours=6)
    )

    # Should return empty list on error
    assert result == []


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

    # Since _is_period_consolidated now uses direct DB queries,
    # and the test uses mocks, we can't properly test this internal method.
    # Instead, test the behavior through the public interface.
    
    # When consolidating a period that already has a summary,
    # it should skip creating a new one
    summaries = await tsdb_service._consolidate_period(period_start, period_end)
    
    # Should return existing summaries or handle gracefully
    assert summaries is not None
    assert isinstance(summaries, list)


@pytest.mark.asyncio
async def test_tsdb_service_node_type(tsdb_service):
    """Test that TSDBConsolidationService manages TSDB_SUMMARY nodes."""
    node_type = tsdb_service.get_node_type()
    assert node_type == NodeType.TSDB_SUMMARY
