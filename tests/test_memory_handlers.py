import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone
from ciris_engine.logic.handlers.memory.memorize_handler import MemorizeHandler
from ciris_engine.logic.handlers.memory.recall_handler import RecallHandler
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.logic.buses.bus_manager import BusManager
from ciris_engine.logic.infrastructure.handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.actions.parameters import MemorizeParams, RecallParams
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphNodeAttributes, GraphScope
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.runtime.models import Thought, ThoughtContext
from ciris_engine.schemas.runtime.enums import ThoughtStatus
from ciris_engine.schemas.runtime.system_context import SystemSnapshot, ChannelContext, ConscienceResult
# Import ActionSelectionDMAResult last to avoid circular import issues
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult

# Rebuild DispatchContext to resolve forward references
DispatchContext.model_rebuild()


def create_channel_context(channel_id: str) -> ChannelContext:
    """Helper to create a valid ChannelContext for tests."""
    return ChannelContext(
        channel_id=channel_id,
        channel_name=f"Channel {channel_id}",
        channel_type="text",
        created_at=datetime.now(timezone.utc)
    )


def create_dispatch_context(thought_id: str, task_id: str, channel_id: str = "test_channel") -> DispatchContext:
    """Helper to create a valid DispatchContext for tests."""
    return DispatchContext(
        channel_context=create_channel_context(channel_id),
        author_id="test_author",
        author_name="Test Author",
        origin_service="test_service",
        handler_name="test_handler",
        action_type=HandlerActionType.MEMORIZE,
        task_id=task_id,
        thought_id=thought_id,
        source_task_id=task_id,
        event_summary="Test action",
        event_timestamp=datetime.now(timezone.utc).isoformat(),
        correlation_id="test_correlation_id"
    )


def create_test_system_snapshot() -> SystemSnapshot:
    """Helper to create a valid SystemSnapshot for tests."""
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        runtime_phase="WAKEUP",
        active_services={"memory": True, "llm": True},
        memory_usage_mb=100.0,
        cpu_usage_percent=10.0,
        active_thoughts=1,
        active_tasks=1,
        avg_response_time_ms=50.0,
        error_rate=0.0,
        queue_depth=0
    )


def create_test_thought(thought_id: str = "test_thought", task_id: str = "test_task") -> Thought:
    """Helper to create a valid Thought for tests."""
    return Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        content="Test thought content",
        status=ThoughtStatus.PROCESSING,
        thought_depth=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=ThoughtContext(
            task_id=task_id,
            round_number=1,
            depth=1,
            correlation_id="test_correlation"
        )
    )


@pytest.mark.asyncio
async def test_memorize_handler_with_graph_node(monkeypatch):
    """Test memorize handler with proper GraphNode schema."""
    # Mock persistence to avoid database operations
    mock_persistence = Mock()
    mock_persistence.add_thought = Mock()
    mock_persistence.update_thought_status = Mock()
    monkeypatch.setattr('ciris_engine.logic.handlers.memory.memorize_handler.persistence', mock_persistence)
    
    # Setup
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="ok")))
    
    mock_service_registry = AsyncMock()
    mock_time_service = Mock()
    mock_time_service.now = Mock(return_value=datetime.now(timezone.utc))
    
    bus_manager = BusManager(mock_service_registry, time_service=mock_time_service)
    
    # Mock the memory bus to use our memory_service
    mock_memory_bus = AsyncMock()
    mock_memory_bus.memorize = memory_service.memorize
    bus_manager.memory = mock_memory_bus
    
    # Mock the audit bus
    mock_audit_bus = AsyncMock()
    mock_audit_bus.log_event = AsyncMock()
    bus_manager.audit = mock_audit_bus
    
    deps = ActionHandlerDependencies(
        bus_manager=bus_manager,
        time_service=mock_time_service
    )
    
    handler = MemorizeHandler(deps)
    
    # Create proper GraphNode
    node_attrs = GraphNodeAttributes(
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="test_user",
        tags=["test", "memory"]
    )
    
    node = GraphNode(
        id="test_node_id",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes=node_attrs
    )
    
    # Create parameters
    params = MemorizeParams(node=node)
    
    # Create DMA result
    result = ActionSelectionDMAResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters=params,
        rationale="Testing memorize action",
        confidence=0.95,
        reasoning="This is a test memorization",
        evaluation_time_ms=100
    )
    
    # Create thought and dispatch context
    thought = create_test_thought()
    dispatch_context = create_dispatch_context(thought.thought_id, thought.source_task_id)
    
    # Execute handler
    handler_result = await handler.handle(result, thought, dispatch_context)
    
    # Verify memory service was called correctly
    assert memory_service.memorize.called
    call_args = memory_service.memorize.call_args
    assert call_args is not None
    assert call_args.kwargs['node'] == node  # Check keyword argument
    assert call_args.kwargs['handler_name'] == 'MemorizeHandler'


@pytest.mark.asyncio
async def test_recall_handler_with_query(monkeypatch):
    """Test recall handler with proper query parameters."""
    # Mock persistence
    mock_persistence = Mock()
    mock_persistence.add_thought = Mock()
    mock_persistence.update_thought_status = Mock()
    monkeypatch.setattr('ciris_engine.logic.handlers.memory.recall_handler.persistence', mock_persistence)
    
    # Setup
    memory_service = Mock()
    test_nodes = [
        GraphNode(
            id="node1",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes=GraphNodeAttributes(
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="test_user"
            )
        ),
        GraphNode(
            id="node2",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes=GraphNodeAttributes(
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                created_by="test_user"
            )
        )
    ]
    memory_service.recall = AsyncMock(return_value=test_nodes)
    
    mock_service_registry = AsyncMock()
    mock_time_service = Mock()
    mock_time_service.now = Mock(return_value=datetime.now(timezone.utc))
    
    bus_manager = BusManager(mock_service_registry, time_service=mock_time_service)
    
    # Mock the memory bus
    mock_memory_bus = AsyncMock()
    mock_memory_bus.recall = memory_service.recall
    bus_manager.memory = mock_memory_bus
    
    # Mock the audit bus
    mock_audit_bus = AsyncMock()
    mock_audit_bus.log_event = AsyncMock()
    bus_manager.audit = mock_audit_bus
    
    deps = ActionHandlerDependencies(
        bus_manager=bus_manager,
        time_service=mock_time_service
    )
    
    handler = RecallHandler(deps)
    
    # Create parameters
    params = RecallParams(
        query="test memory",
        node_type=NodeType.CONCEPT,
        limit=10
    )
    
    # Create DMA result
    result = ActionSelectionDMAResult(
        selected_action=HandlerActionType.RECALL,
        action_parameters=params,
        rationale="Testing recall action",
        confidence=0.95,
        reasoning="This is a test recall",
        evaluation_time_ms=100
    )
    
    # Create thought and dispatch context
    thought = create_test_thought()
    dispatch_context = create_dispatch_context(thought.thought_id, thought.source_task_id)
    
    # Execute handler
    handler_result = await handler.handle(result, thought, dispatch_context)
    
    # Verify memory service was called correctly
    assert memory_service.recall.called
    call_args = memory_service.recall.call_args
    assert call_args is not None
    # Check that query parameters were passed correctly via kwargs
    assert "recall_query" in call_args.kwargs
    memory_query = call_args.kwargs["recall_query"]
    assert memory_query.node_id == "test memory"  # query gets used as node_id
    assert memory_query.type == NodeType.CONCEPT
    assert call_args.kwargs['handler_name'] == 'RecallHandler'


@pytest.mark.asyncio
async def test_memorize_handler_error_handling(monkeypatch):
    """Test memorize handler when memory service returns error."""
    # Mock persistence
    mock_persistence = Mock()
    mock_persistence.add_thought = Mock()
    mock_persistence.update_thought_status = Mock()
    monkeypatch.setattr('ciris_engine.logic.handlers.memory.memorize_handler.persistence', mock_persistence)
    
    # Setup
    memory_service = Mock()
    memory_service.memorize = AsyncMock(return_value=Mock(status=Mock(value="error"), error="Memory service unavailable"))
    
    mock_service_registry = AsyncMock()
    mock_time_service = Mock()
    mock_time_service.now = Mock(return_value=datetime.now(timezone.utc))
    
    bus_manager = BusManager(mock_service_registry, time_service=mock_time_service)
    
    # Mock the memory bus
    mock_memory_bus = AsyncMock()
    mock_memory_bus.memorize = memory_service.memorize
    bus_manager.memory = mock_memory_bus
    
    # Mock the audit bus
    mock_audit_bus = AsyncMock()
    mock_audit_bus.log_event = AsyncMock()
    bus_manager.audit = mock_audit_bus
    
    deps = ActionHandlerDependencies(
        bus_manager=bus_manager,
        time_service=mock_time_service
    )
    
    handler = MemorizeHandler(deps)
    
    # Create node
    node = GraphNode(
        id="error_test_node",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes=GraphNodeAttributes(
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="test_user"
        )
    )
    
    params = MemorizeParams(node=node)
    
    result = ActionSelectionDMAResult(
        selected_action=HandlerActionType.MEMORIZE,
        action_parameters=params,
        rationale="Testing error handling",
        confidence=0.95,
        reasoning="This should fail",
        evaluation_time_ms=100
    )
    
    thought = create_test_thought()
    dispatch_context = create_dispatch_context(thought.thought_id, thought.source_task_id)
    
    # Execute handler - should handle error gracefully
    handler_result = await handler.handle(result, thought, dispatch_context)
    
    # Verify memory service was called
    assert memory_service.memorize.called
    # Handler should return a result even on error
    assert handler_result is not None