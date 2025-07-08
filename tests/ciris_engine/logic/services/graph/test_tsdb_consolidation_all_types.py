"""
Comprehensive end-to-end tests for TSDB consolidation with all node types.

Tests the complete flow of:
1. Generating correlations of all types
2. Validating correlation data
3. Running consolidation
4. Verifying summary nodes are created correctly
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from ciris_engine.logic.services.graph.tsdb_consolidation_service import TSDBConsolidationService
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.conversation_summary_node import ConversationSummaryNode
from ciris_engine.schemas.services.trace_summary_node import TraceSummaryNode
from ciris_engine.schemas.services.audit_summary_node import AuditSummaryNode
from ciris_engine.schemas.services.operations import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation, CorrelationType, ServiceRequestData, ServiceResponseData
)
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint


class MockTimeService(TimeServiceProtocol):
    """Mock time service for testing."""
    def __init__(self, fixed_time: datetime):
        self.fixed_time = fixed_time
    
    def now(self) -> datetime:
        return self.fixed_time
    
    def now_iso(self) -> str:
        return self.fixed_time.isoformat()
    
    def timestamp(self) -> float:
        return self.fixed_time.timestamp()
    
    async def start(self) -> None:
        pass
    
    async def stop(self) -> None:
        pass
    
    async def is_healthy(self) -> bool:
        return True
    
    def get_capabilities(self):
        return None
    
    def get_status(self):
        return None


@pytest.fixture
def mock_time_service():
    """Create a mock time service with fixed time."""
    # Set time to 13:00 so consolidation will process 06:00-12:00 period
    fixed_time = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    return MockTimeService(fixed_time)


@pytest.fixture
def mock_memory_bus():
    """Create a mock memory bus."""
    return AsyncMock(spec=MemoryBus)


@pytest.fixture
def consolidation_service(mock_memory_bus, mock_time_service):
    """Create a TSDB consolidation service with mocks."""
    service = TSDBConsolidationService(
        memory_bus=mock_memory_bus,
        time_service=mock_time_service,
        consolidation_interval_hours=6,
        raw_retention_hours=24
    )
    return service


def create_metric_datapoints(period_start: datetime, period_end: datetime) -> List[TimeSeriesDataPoint]:
    """Create sample METRIC_DATAPOINT correlations."""
    datapoints = []
    
    # Create metrics every 5 minutes
    current = period_start
    while current < period_end:
        # Token usage metric
        datapoints.append(TimeSeriesDataPoint(
            timestamp=current,
            metric_name="llm.tokens_used",
            value=float(100 + (current.minute % 10) * 10),  # Vary between 100-190
            correlation_type="METRIC_DATAPOINT",
            tags={"model": "gpt-4", "service": "llm"}
        ))
        
        # Cost metric
        datapoints.append(TimeSeriesDataPoint(
            timestamp=current,
            metric_name="llm.cost_cents",
            value=float(5 + (current.minute % 5)),  # Vary between 5-9
            correlation_type="METRIC_DATAPOINT",
            tags={"model": "gpt-4", "service": "llm"}
        ))
        
        # Action count metrics
        datapoints.append(TimeSeriesDataPoint(
            timestamp=current,
            metric_name="action.speak.count",
            value=1.0,
            correlation_type="METRIC_DATAPOINT",
            tags={"service": "communication"}
        ))
        
        # Success/error metrics
        if current.minute % 10 == 0:  # Error every 10 minutes
            datapoints.append(TimeSeriesDataPoint(
                timestamp=current,
                metric_name="action.error.count",
                value=1.0,
                correlation_type="METRIC_DATAPOINT",
                tags={"service": "llm", "error_type": "timeout"}
            ))
        else:
            datapoints.append(TimeSeriesDataPoint(
                timestamp=current,
                metric_name="action.success.count",
                value=1.0,
                correlation_type="METRIC_DATAPOINT",
                tags={"service": "llm"}
            ))
        
        current += timedelta(minutes=5)
    
    return datapoints


def create_conversation_datapoints(period_start: datetime, period_end: datetime) -> List[TimeSeriesDataPoint]:
    """Create sample SERVICE_INTERACTION correlations for conversations."""
    datapoints = []
    channels = ["api_127.0.0.1:8000", "discord_123456"]
    
    # Create a conversation in each channel
    for i, channel in enumerate(channels):
        base_time = period_start + timedelta(hours=i+1)
        
        # User message (observe)
        datapoints.append(TimeSeriesDataPoint(
            timestamp=base_time,
            metric_name="service_interaction",
            value=1.0,
            correlation_type="SERVICE_INTERACTION",
            tags={
                "correlation_type": "SERVICE_INTERACTION",
                "action_type": "observe",
                "channel_id": channel,
                "author_id": f"user_{i}",
                "author_name": f"User {i}",
                "content": f"Hello CIRIS, can you help me with task {i}?",
                "correlation_id": f"obs_{i}_1"
            }
        ))
        
        # Agent response (speak)
        datapoints.append(TimeSeriesDataPoint(
            timestamp=base_time + timedelta(seconds=5),
            metric_name="service_interaction",
            value=1.0,
            correlation_type="SERVICE_INTERACTION",
            tags={
                "correlation_type": "SERVICE_INTERACTION",
                "action_type": "speak",
                "channel_id": channel,
                "author_id": "ciris",
                "author_name": "CIRIS",
                "content": f"Hello User {i}! I'd be happy to help with task {i}.",
                "correlation_id": f"spk_{i}_1",
                "execution_time_ms": "1500"
            }
        ))
        
        # Follow-up
        datapoints.append(TimeSeriesDataPoint(
            timestamp=base_time + timedelta(seconds=20),
            metric_name="service_interaction",
            value=1.0,
            correlation_type="SERVICE_INTERACTION",
            tags={
                "correlation_type": "SERVICE_INTERACTION",
                "action_type": "observe",
                "channel_id": channel,
                "author_id": f"user_{i}",
                "author_name": f"User {i}",
                "content": "Thanks! Can you explain how this works?",
                "correlation_id": f"obs_{i}_2"
            }
        ))
        
        # Agent explanation
        datapoints.append(TimeSeriesDataPoint(
            timestamp=base_time + timedelta(seconds=25),
            metric_name="service_interaction",
            value=1.0,
            correlation_type="SERVICE_INTERACTION",
            tags={
                "correlation_type": "SERVICE_INTERACTION",
                "action_type": "speak",
                "channel_id": channel,
                "author_id": "ciris",
                "author_name": "CIRIS",
                "content": "Let me explain the process step by step...",
                "correlation_id": f"spk_{i}_2",
                "execution_time_ms": "2000"
            }
        ))
    
    return datapoints


def create_trace_datapoints(period_start: datetime, period_end: datetime) -> List[TimeSeriesDataPoint]:
    """Create sample TRACE_SPAN correlations."""
    datapoints = []
    
    # Simulate processing 3 tasks
    for task_num in range(3):
        task_id = f"task_{task_num}"
        task_start = period_start + timedelta(hours=task_num*2)
        
        # Agent processor span
        datapoints.append(TimeSeriesDataPoint(
            timestamp=task_start,
            metric_name="trace_span",
            value=1.0,
            correlation_type="TRACE_SPAN",
            tags={
                "correlation_type": "TRACE_SPAN",
                "task_id": task_id,
                "component_type": "agent_processor",
                "trace_depth": "1",
                "task_status": "ACTIVE",
                "execution_time_ms": "5000",
                "success": "true"
            }
        ))
        
        # Thought processor spans (3 thoughts per task)
        for thought_num in range(3):
            thought_id = f"thought_{task_num}_{thought_num}"
            thought_time = task_start + timedelta(seconds=thought_num*10)
            
            datapoints.append(TimeSeriesDataPoint(
                timestamp=thought_time,
                metric_name="trace_span",
                value=1.0,
                correlation_type="TRACE_SPAN",
                tags={
                    "correlation_type": "TRACE_SPAN",
                    "task_id": task_id,
                    "thought_id": thought_id,
                    "component_type": "thought_processor",
                    "thought_type": "REASONING",
                    "trace_depth": "2",
                    "execution_time_ms": "500",
                    "success": "true"
                }
            ))
            
            # DMA span
            datapoints.append(TimeSeriesDataPoint(
                timestamp=thought_time + timedelta(seconds=1),
                metric_name="trace_span",
                value=1.0,
                correlation_type="TRACE_SPAN",
                tags={
                    "correlation_type": "TRACE_SPAN",
                    "task_id": task_id,
                    "thought_id": thought_id,
                    "component_type": "dma",
                    "dma_type": "iterative_dma",
                    "trace_depth": "3",
                    "execution_time_ms": "200",
                    "success": "true"
                }
            ))
            
            # Guardrail span (simulate one violation)
            is_violation = task_num == 1 and thought_num == 1
            datapoints.append(TimeSeriesDataPoint(
                timestamp=thought_time + timedelta(seconds=2),
                metric_name="trace_span",
                value=1.0,
                correlation_type="TRACE_SPAN",
                tags={
                    "correlation_type": "TRACE_SPAN",
                    "task_id": task_id,
                    "thought_id": thought_id,
                    "component_type": "guardrail",
                    "guardrail_type": "content_filter",
                    "violation": "true" if is_violation else "false",
                    "trace_depth": "3",
                    "execution_time_ms": "100",
                    "success": "true"
                }
            ))
            
            # Handler span
            datapoints.append(TimeSeriesDataPoint(
                timestamp=thought_time + timedelta(seconds=3),
                metric_name="trace_span",
                value=1.0,
                correlation_type="TRACE_SPAN",
                tags={
                    "correlation_type": "TRACE_SPAN",
                    "task_id": task_id,
                    "thought_id": thought_id,
                    "component_type": "handler",
                    "action_type": "speak",
                    "trace_depth": "3",
                    "execution_time_ms": "300",
                    "success": "true" if not is_violation else "false"
                }
            ))
        
        # Final task status
        datapoints.append(TimeSeriesDataPoint(
            timestamp=task_start + timedelta(seconds=35),
            metric_name="trace_span",
            value=1.0,
            correlation_type="TRACE_SPAN",
            tags={
                "correlation_type": "TRACE_SPAN",
                "task_id": task_id,
                "component_type": "agent_processor",
                "task_status": "COMPLETED" if task_num != 1 else "FAILED",
                "trace_depth": "1",
                "execution_time_ms": "35000",
                "success": "true" if task_num != 1 else "false"
            }
        ))
    
    return datapoints


def create_audit_datapoints(period_start: datetime, period_end: datetime) -> List[TimeSeriesDataPoint]:
    """Create sample AUDIT_EVENT correlations."""
    datapoints = []
    
    # Auth events
    for i in range(5):
        event_time = period_start + timedelta(minutes=i*30)
        datapoints.append(TimeSeriesDataPoint(
            timestamp=event_time,
            metric_name="audit_event",
            value=1.0,
            correlation_type="AUDIT_EVENT",
            tags={
                "correlation_type": "AUDIT_EVENT",
                "correlation_id": f"audit_{i}_auth",
                "event_type": "AUTH_SUCCESS" if i % 2 == 0 else "AUTH_FAILURE",
                "actor": f"user_{i}",
                "service": "authentication"
            }
        ))
    
    # Permission events
    datapoints.append(TimeSeriesDataPoint(
        timestamp=period_start + timedelta(hours=1),
        metric_name="audit_event",
        value=1.0,
        correlation_type="AUDIT_EVENT",
        tags={
            "correlation_type": "AUDIT_EVENT",
            "correlation_id": "audit_perm_denied",
            "event_type": "PERMISSION_DENIED",
            "actor": "user_3",
            "service": "config_service"
        }
    ))
    
    # Config changes
    for i in range(3):
        event_time = period_start + timedelta(hours=2+i)
        datapoints.append(TimeSeriesDataPoint(
            timestamp=event_time,
            metric_name="audit_event",
            value=1.0,
            correlation_type="AUDIT_EVENT",
            tags={
                "correlation_type": "AUDIT_EVENT",
                "correlation_id": f"audit_config_{i}",
                "event_type": "CONFIG_UPDATE",
                "actor": "admin",
                "service": "config_service"
            }
        ))
    
    return datapoints


def datapoints_to_correlations(datapoints: List[TimeSeriesDataPoint], correlation_type: str) -> List[ServiceCorrelation]:
    """Convert TimeSeriesDataPoint objects to ServiceCorrelation objects for testing."""
    correlations = []
    
    # Map from uppercase tags to lowercase enum values
    type_mapping = {
        "SERVICE_INTERACTION": CorrelationType.SERVICE_INTERACTION,
        "TRACE_SPAN": CorrelationType.TRACE_SPAN,
        "AUDIT_EVENT": CorrelationType.AUDIT_EVENT
    }
    
    for dp in datapoints:
        # Check correlation_type from tags in uppercase
        if dp.tags.get("correlation_type") == correlation_type:
            # Build request data from tags
            request_data = ServiceRequestData(
                service_type=dp.tags.get("service", "unknown"),
                method_name=dp.tags.get("action_type", "unknown"),
                channel_id=dp.tags.get("channel_id"),
                parameters={
                    "content": dp.tags.get("content", ""),
                    "author_id": dp.tags.get("author_id", ""),
                    "author_name": dp.tags.get("author_name", "")
                },
                request_timestamp=dp.timestamp
            )
            
            # Build response data
            exec_time = float(dp.tags.get("execution_time_ms", 0))
            success = dp.tags.get("success", "true") == "true"
            response_data = ServiceResponseData(
                success=success,
                execution_time_ms=exec_time,
                response_timestamp=dp.timestamp
            ) if exec_time > 0 else None
            
            # Use the correct enum value
            enum_type = type_mapping.get(correlation_type, CorrelationType.SERVICE_INTERACTION)
            
            corr = ServiceCorrelation(
                correlation_id=dp.tags.get("correlation_id", f"corr_{dp.timestamp.timestamp()}"),
                correlation_type=enum_type,
                service_type=dp.tags.get("service", "unknown"),
                handler_name="test_handler",
                action_type=dp.tags.get("action_type", "unknown"),
                request_data=request_data,
                response_data=response_data,
                created_at=dp.timestamp,
                updated_at=dp.timestamp,
                timestamp=dp.timestamp,
                tags=dp.tags
            )
            correlations.append(corr)
    
    return correlations


def create_audit_nodes_from_datapoints(datapoints: List[TimeSeriesDataPoint]) -> List[GraphNode]:
    """Convert audit datapoints to actual AUDIT_ENTRY graph nodes."""
    from ciris_engine.schemas.services.nodes import AuditEntry, AuditEntryContext
    
    nodes = []
    for dp in datapoints:
        if dp.tags.get("correlation_type") == "AUDIT_EVENT":
            # Create an AuditEntry node
            event_type = dp.tags.get("event_type", "unknown")
            actor = dp.tags.get("actor", "unknown")
            service = dp.tags.get("service", "unknown")
            
            context = AuditEntryContext(
                service_name=service,
                additional_data={
                    "event_type": event_type,
                    "severity": "warning" if "FAIL" in event_type or "DENIED" in event_type else "info",
                    "outcome": "failure" if "FAIL" in event_type or "DENIED" in event_type else "success"
                }
            )
            
            audit_entry = AuditEntry(
                id=f"audit_{dp.tags.get('correlation_id', dp.timestamp.strftime('%Y%m%d_%H%M%S'))}",
                action=event_type,
                actor=actor,
                timestamp=dp.timestamp,
                context=context,
                created_at=dp.timestamp,
                updated_at=dp.timestamp,
                scope=GraphScope.LOCAL,
                attributes={}  # Required by GraphNode base class
            )
            
            nodes.append(audit_entry.to_graph_node())
    
    return nodes


@pytest.mark.asyncio
async def test_end_to_end_consolidation_all_types(consolidation_service, mock_memory_bus, mock_time_service):
    """Test complete consolidation flow for all correlation types."""
    # Set up test period (06:00-12:00 on 2024-01-01)
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Generate test data for all types
    metric_datapoints = create_metric_datapoints(period_start, period_end)
    conversation_datapoints = create_conversation_datapoints(period_start, period_end)
    trace_datapoints = create_trace_datapoints(period_start, period_end)
    audit_datapoints = create_audit_datapoints(period_start, period_end)
    
    # Mock memory bus responses for each correlation type
    async def mock_recall_timeseries(scope, hours=None, correlation_types=None, start_time=None, end_time=None, handler_name=None):
        # Handle both calling patterns
        if correlation_types is None and hours is not None:
            # Old pattern: (scope, hours, correlation_types) - hours is actually correlation_types
            correlation_types = hours
            hours = None
        
        if "metric_datapoint" in correlation_types:
            return metric_datapoints
        elif "service_interaction" in correlation_types:
            # Convert to correlation objects
            return datapoints_to_correlations(conversation_datapoints, "SERVICE_INTERACTION")
        elif "trace_span" in correlation_types:
            # Convert to correlation objects
            return datapoints_to_correlations(trace_datapoints, "TRACE_SPAN")
        elif "audit_event" in correlation_types:
            # Convert to correlation objects
            return datapoints_to_correlations(audit_datapoints, "AUDIT_EVENT")
        return []
    
    mock_memory_bus.recall_timeseries.side_effect = mock_recall_timeseries
    
    # Mock successful memorize operations
    mock_memory_bus.memorize.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data=None,
        error=None
    )
    
    # Mock query response (no existing summaries for initial check, but audit nodes for wildcard query)
    async def mock_recall(query, handler_name="default"):
        # If querying for audit nodes with wildcard, return the audit nodes
        if hasattr(query, 'node_id') and query.node_id == "audit_*":
            return create_audit_nodes_from_datapoints(audit_datapoints)
        # Otherwise return empty (no existing summaries)
        return []
    
    mock_memory_bus.recall.side_effect = mock_recall
    
    # Mock search response for audit nodes - return actual audit nodes
    audit_nodes = create_audit_nodes_from_datapoints(audit_datapoints)
    mock_memory_bus.search.return_value = audit_nodes
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Verify we got 4 summaries (no LOG_ENTRY)
    assert len(summaries) == 4
    
    # Verify memorize was called at least 4 times (summaries + edges)
    assert mock_memory_bus.memorize.call_count >= 4
    
    # Check each summary type
    memorize_calls = mock_memory_bus.memorize.call_args_list
    stored_nodes = [call[1]['node'] if 'node' in call[1] else call[0][0] for call in memorize_calls]
    
    # Find each summary type
    tsdb_summary = None
    conversation_summary = None
    trace_summary = None
    audit_summary = None
    
    for node in stored_nodes:
        # Only look at nodes with an id attribute (skip edges)
        if hasattr(node, 'id'):
            # Skip edge nodes - they have 'edge_' prefix or contain '_to_'
            if node.id.startswith('edge_') or '_to_' in node.id:
                continue
                
            if node.id.startswith("tsdb_summary_") and node.type == NodeType.TSDB_SUMMARY:
                # Check it's actually a TSDB summary (has metrics field)
                if 'metrics' in node.attributes:
                    tsdb_summary = node
            elif node.id.startswith("conversation_summary_") and node.type == NodeType.CONVERSATION_SUMMARY:
                conversation_summary = node
            elif node.id.startswith("trace_summary_") and node.type == NodeType.TSDB_SUMMARY:
                trace_summary = node
            elif node.id.startswith("audit_summary_") and node.type == NodeType.TSDB_SUMMARY:
                audit_summary = node
    
    # Validate TSDB Summary
    assert tsdb_summary is not None
    assert tsdb_summary.type == NodeType.TSDB_SUMMARY
    tsdb_attrs = tsdb_summary.attributes
    assert tsdb_attrs['total_tokens'] > 0
    assert tsdb_attrs['action_counts']['SPEAK'] > 0
    assert 'llm.tokens_used' in tsdb_attrs['metrics']
    
    # Validate Conversation Summary
    assert conversation_summary is not None
    assert conversation_summary.type == NodeType.CONVERSATION_SUMMARY
    conv_attrs = conversation_summary.attributes
    assert conv_attrs['total_messages'] == 8  # 4 messages per channel, 2 channels
    assert len(conv_attrs['conversations_by_channel']) == 2
    assert conv_attrs['unique_users'] == 3  # user_0, user_1, and ciris
    
    # Validate Trace Summary
    assert trace_summary is not None
    assert trace_summary.type == NodeType.TSDB_SUMMARY  # Note: We're using TSDB_SUMMARY type
    trace_attrs = trace_summary.attributes
    assert trace_attrs['total_tasks_processed'] == 3
    assert trace_attrs['total_thoughts_processed'] == 9  # 3 thoughts per task
    assert trace_attrs['guardrail_violations']['content_filter'] == 1
    assert trace_attrs['component_calls']['agent_processor'] > 0
    
    # Validate Audit Summary
    assert audit_summary is not None
    assert audit_summary.type == NodeType.TSDB_SUMMARY  # Note: We're using TSDB_SUMMARY type
    audit_attrs = audit_summary.attributes
    assert audit_attrs['total_audit_events'] == 9
    assert len(audit_attrs['audit_hash']) == 64  # SHA-256 hash
    assert audit_attrs['failed_auth_attempts'] == 2
    assert audit_attrs['config_changes'] == 3


@pytest.mark.asyncio
async def test_consolidation_with_no_data(consolidation_service, mock_memory_bus, mock_time_service):
    """Test consolidation when no correlations exist for the period."""
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Mock empty responses
    mock_memory_bus.recall_timeseries.return_value = []
    mock_memory_bus.recall.return_value = []
    mock_memory_bus.search.return_value = []
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Should have no summaries
    assert len(summaries) == 0
    
    # Memorize should not be called
    assert mock_memory_bus.memorize.call_count == 0


@pytest.mark.asyncio
async def test_consolidation_idempotency(consolidation_service, mock_memory_bus, mock_time_service):
    """Test that consolidation is idempotent - won't re-consolidate already processed periods."""
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Test the higher-level method that checks for existing summaries
    # Mock that summary already exists
    existing_summary = GraphNode(
        id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
        type=NodeType.TSDB_SUMMARY,
        scope=GraphScope.LOCAL,
        attributes={}
    )
    mock_memory_bus.recall.return_value = [existing_summary]
    
    # Check if period is consolidated
    is_consolidated = await consolidation_service._is_period_consolidated(period_start, period_end)
    assert is_consolidated is True
    
    # Now test direct consolidation - it will still create summaries for other types
    # since each type is consolidated independently
    
    # Mock empty data for all correlation types
    mock_memory_bus.recall_timeseries.return_value = []
    mock_memory_bus.recall.return_value = []
    mock_memory_bus.search.return_value = []  # No audit nodes
    
    # Mock successful memorize operations
    mock_memory_bus.memorize.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data=None,
        error=None
    )
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Should create no summaries since there's no data
    assert len(summaries) == 0
    assert mock_memory_bus.memorize.call_count == 0


@pytest.mark.asyncio
async def test_conversation_summary_preserves_full_content(consolidation_service, mock_memory_bus, mock_time_service):
    """Test that conversation summaries preserve full message content."""
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Create detailed conversation
    conversation_datapoints = create_conversation_datapoints(period_start, period_end)
    
    # Mock responses
    mock_memory_bus.recall.return_value = []
    mock_memory_bus.search.return_value = []
    async def mock_recall_timeseries_conv(scope, hours=None, correlation_types=None, start_time=None, end_time=None, handler_name=None):
        # Handle both calling patterns
        if correlation_types is None and hours is not None:
            # Old pattern: (scope, hours, correlation_types) - hours is actually correlation_types
            correlation_types = hours
            hours = None
        
        if "service_interaction" in correlation_types:
            return datapoints_to_correlations(conversation_datapoints, "SERVICE_INTERACTION")
        return []
    
    mock_memory_bus.recall_timeseries.side_effect = mock_recall_timeseries_conv
    # Ensure memorize returns a proper result for async calls
    memorize_result = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data=None,
        error=None
    )
    mock_memory_bus.memorize.return_value = memorize_result
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Find conversation summary
    conv_summary = None
    for call in mock_memory_bus.memorize.call_args_list:
        node = call[1]['node'] if 'node' in call[1] else call[0][0]
        if "conversation_summary_" in node.id:
            conv_summary = node
            break
    
    assert conv_summary is not None
    
    # Verify full content is preserved
    conversations = conv_summary.attributes['conversations_by_channel']
    assert len(conversations) == 2
    
    # Check first channel has all messages with content
    first_channel = list(conversations.keys())[0]
    messages = conversations[first_channel]
    assert len(messages) == 4
    
    # Verify message content is preserved
    for msg in messages:
        assert 'content' in msg
        assert msg['content'] != ""
        assert 'timestamp' in msg
        assert 'author_id' in msg


@pytest.mark.asyncio
async def test_audit_hash_generation(consolidation_service, mock_memory_bus, mock_time_service):
    """Test that audit summaries generate correct hashes."""
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Create audit events
    audit_datapoints = create_audit_datapoints(period_start, period_end)
    
    # Mock responses
    # Return actual audit nodes for recall (for wildcard queries)
    audit_nodes = create_audit_nodes_from_datapoints(audit_datapoints)
    mock_memory_bus.recall.return_value = audit_nodes
    mock_memory_bus.search.return_value = audit_nodes
    async def mock_recall_timeseries_audit(scope, hours=None, correlation_types=None, start_time=None, end_time=None, handler_name=None):
        # Handle both calling patterns
        if correlation_types is None and hours is not None:
            # Old pattern: (scope, hours, correlation_types) - hours is actually correlation_types
            correlation_types = hours
            hours = None
        
        if "audit_event" in correlation_types:
            return datapoints_to_correlations(audit_datapoints, "AUDIT_EVENT")
        return []
    
    mock_memory_bus.recall_timeseries.side_effect = mock_recall_timeseries_audit
    # Ensure memorize returns a proper result for async calls
    memorize_result = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data=None,
        error=None
    )
    mock_memory_bus.memorize.return_value = memorize_result
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Find audit summary
    audit_summary = None
    for call in mock_memory_bus.memorize.call_args_list:
        node = call[1]['node'] if 'node' in call[1] else call[0][0]
        if "audit_summary_" in node.id:
            audit_summary = node
            break
    
    assert audit_summary is not None
    
    # Verify hash properties
    audit_attrs = audit_summary.attributes
    assert 'audit_hash' in audit_attrs
    assert len(audit_attrs['audit_hash']) == 64  # SHA-256 produces 64 hex chars
    assert audit_attrs['hash_algorithm'] == 'sha256'
    
    # Verify event counts
    assert audit_attrs['total_audit_events'] == 9
    assert audit_attrs['failed_auth_attempts'] == 2
    assert audit_attrs['permission_denials'] == 1
    assert audit_attrs['config_changes'] == 3


@pytest.mark.asyncio
async def test_trace_summary_metrics(consolidation_service, mock_memory_bus, mock_time_service):
    """Test that trace summaries calculate metrics correctly."""
    period_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Create trace events
    trace_datapoints = create_trace_datapoints(period_start, period_end)
    
    # Mock responses
    mock_memory_bus.recall.return_value = []
    mock_memory_bus.search.return_value = []
    async def mock_recall_timeseries_trace(scope, hours=None, correlation_types=None, start_time=None, end_time=None, handler_name=None):
        # Handle both calling patterns
        if correlation_types is None and hours is not None:
            # Old pattern: (scope, hours, correlation_types) - hours is actually correlation_types
            correlation_types = hours
            hours = None
        
        if "trace_span" in correlation_types:
            return datapoints_to_correlations(trace_datapoints, "TRACE_SPAN")
        return []
    
    mock_memory_bus.recall_timeseries.side_effect = mock_recall_timeseries_trace
    # Ensure memorize returns a proper result for async calls
    memorize_result = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data=None,
        error=None
    )
    mock_memory_bus.memorize.return_value = memorize_result
    
    # Run consolidation
    summaries = await consolidation_service._consolidate_period(period_start, period_end)
    
    # Find trace summary
    trace_summary = None
    for call in mock_memory_bus.memorize.call_args_list:
        node = call[1]['node'] if 'node' in call[1] else call[0][0]
        if "trace_summary_" in node.id:
            trace_summary = node
            break
    
    assert trace_summary is not None
    
    # Verify trace metrics
    trace_attrs = trace_summary.attributes
    assert trace_attrs['total_tasks_processed'] == 3
    assert trace_attrs['total_thoughts_processed'] == 9
    assert trace_attrs['avg_thoughts_per_task'] == 3.0
    
    # Verify component metrics
    assert trace_attrs['component_calls']['agent_processor'] > 0
    assert trace_attrs['component_calls']['thought_processor'] > 0
    assert trace_attrs['component_calls']['dma'] > 0
    assert trace_attrs['component_calls']['guardrail'] > 0
    assert trace_attrs['component_calls']['handler'] > 0
    
    # Verify patterns
    assert trace_attrs['dma_decisions']['iterative_dma'] == 9
    assert trace_attrs['guardrail_violations']['content_filter'] == 1
    assert trace_attrs['handler_actions']['speak'] == 9
    
    # Verify trace depth
    assert trace_attrs['max_trace_depth'] == 3
    assert trace_attrs['avg_trace_depth'] > 0