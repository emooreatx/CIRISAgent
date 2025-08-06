"""Tests for system_snapshot.py - properly testing the actual function signature."""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
from typing import List, Dict

from ciris_engine.logic.context.system_snapshot import build_system_snapshot
from ciris_engine.schemas.runtime.system_context import SystemSnapshot
from ciris_engine.schemas.adapters.tools import ToolInfo, ToolParameterSchema
from ciris_engine.schemas.runtime.models import Task, TaskContext
from ciris_engine.schemas.runtime.enums import TaskStatus


@pytest.fixture
def mock_resource_monitor():
    """Create a mock resource monitor - REQUIRED parameter."""
    monitor = Mock()
    monitor.snapshot = Mock()
    monitor.snapshot.critical = []
    monitor.snapshot.healthy = True
    return monitor


@pytest.fixture
def mock_task_with_channel():
    """Create a task with channel context."""
    task = Task(
        task_id="test_task",
        channel_id="test_channel",
        description="Test task",
        status=TaskStatus.ACTIVE,
        priority=10,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=TaskContext(
            correlation_id="test_correlation",
            channel_id="test_channel"
        )
    )
    return task


@pytest.fixture
def mock_thought():
    """Create a mock thought."""
    thought = Mock()
    thought.thought_id = "test_thought"
    thought.content = "Test thought content"
    thought.status = Mock(value="PROCESSING")
    thought.source_task_id = "test_task"
    thought.thought_type = "ANALYSIS"
    thought.thought_depth = 1
    thought.context = Mock(channel_id="test_channel")
    return thought


@pytest.fixture
def mock_runtime_with_tools():
    """Create runtime with tool services."""
    runtime = Mock()
    
    # Setup adapter manager for channels
    runtime.adapter_manager = Mock()
    runtime.adapter_manager._adapters = {}
    
    # Setup service registry for tools
    runtime.service_registry = Mock()
    
    # Create a mock tool service
    tool_service = Mock()
    tool_service.adapter_id = "test_adapter"
    tool_service.get_available_tools = Mock(return_value=["test_tool"])
    
    # Create valid ToolInfo
    tool_info = ToolInfo(
        name="test_tool",
        description="A test tool",
        parameters=ToolParameterSchema(
            type="object",
            properties={"param1": {"type": "string"}},
            required=["param1"]
        ),
        category="general",
        cost=0.0
    )
    tool_service.get_tool_info = Mock(return_value=tool_info)
    
    # Registry returns tool services
    runtime.service_registry.get_services_by_type = Mock(return_value=[tool_service])
    
    # Setup bus_manager (needed for tool discovery)
    runtime.bus_manager = Mock()
    
    return runtime


@pytest.mark.asyncio
async def test_build_system_snapshot_minimal(mock_resource_monitor):
    """Test minimal snapshot with only required parameters."""
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=mock_resource_monitor
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.channel_id is None  # No channel without task/thought
    assert snapshot.resource_alerts == []  # No alerts with healthy monitor


@pytest.mark.asyncio
async def test_build_system_snapshot_with_task(mock_resource_monitor, mock_task_with_channel):
    """Test snapshot with task that has channel context."""
    snapshot = await build_system_snapshot(
        task=mock_task_with_channel,
        thought=None,
        resource_monitor=mock_resource_monitor
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.channel_id == "test_channel"
    assert snapshot.current_task_details is not None
    assert snapshot.current_task_details.task_id == "test_task"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_thought(mock_resource_monitor, mock_thought):
    """Test snapshot with thought."""
    snapshot = await build_system_snapshot(
        task=None,
        thought=mock_thought,
        resource_monitor=mock_resource_monitor
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.current_thought_summary is not None
    assert snapshot.current_thought_summary.thought_id == "test_thought"
    assert snapshot.channel_id == "test_channel"  # Extracted from thought context


@pytest.mark.asyncio
async def test_build_system_snapshot_with_tools(mock_resource_monitor, mock_runtime_with_tools):
    """Test snapshot with runtime that provides tools."""
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=mock_resource_monitor,
        runtime=mock_runtime_with_tools
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    # Tools are in model_extra as they're not defined fields
    assert "available_tools" in snapshot.model_extra
    tools = snapshot.model_extra["available_tools"]
    assert "test_adapter" in tools
    assert len(tools["test_adapter"]) == 1
    assert tools["test_adapter"][0].name == "test_tool"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_unhealthy_resources(mock_resource_monitor):
    """Test snapshot with critical resource alerts."""
    # Make resources unhealthy
    mock_resource_monitor.snapshot.critical = ["Memory usage above 90%"]
    mock_resource_monitor.snapshot.healthy = False
    
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=mock_resource_monitor
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    assert len(snapshot.resource_alerts) == 2  # One for critical, one for unhealthy
    assert "CRITICAL" in snapshot.resource_alerts[0]
    assert "UNHEALTHY" in snapshot.resource_alerts[1]


@pytest.mark.asyncio
async def test_build_system_snapshot_with_memory_service():
    """Test snapshot with memory service for identity retrieval."""
    # Mock resource monitor
    resource_monitor = Mock()
    resource_monitor.snapshot = Mock(critical=[], healthy=True)
    
    # Mock memory service
    memory_service = AsyncMock()
    
    # Create identity node
    identity_node = Mock()
    identity_node.attributes = Mock()
    identity_node.attributes.model_dump = Mock(return_value={
        "agent_id": "test_agent",
        "description": "Test Agent",
        "role_description": "Testing",
        "trust_level": 0.9,
        "permitted_actions": ["test"],
        "restricted_capabilities": []
    })
    
    memory_service.recall = AsyncMock(return_value=[identity_node])
    
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=resource_monitor,
        memory_service=memory_service
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    # Identity is in model_extra
    assert "agent_identity" in snapshot.model_extra
    identity = snapshot.model_extra["agent_identity"]
    assert identity["agent_id"] == "test_agent"


@pytest.mark.asyncio
async def test_build_system_snapshot_type_safety():
    """Test that invalid types fail fast and loud."""
    # Mock resource monitor
    resource_monitor = Mock()
    resource_monitor.snapshot = Mock(critical=[], healthy=True)
    
    # Create runtime with invalid tool type
    runtime = Mock()
    runtime.adapter_manager = Mock(_adapters={})
    runtime.service_registry = Mock()
    runtime.bus_manager = Mock()
    
    # Tool service returns wrong type
    tool_service = Mock()
    tool_service.adapter_id = "bad_adapter"
    tool_service.get_available_tools = Mock(return_value=["bad_tool"])
    tool_service.get_tool_info = Mock(return_value={"not": "a_tool_info"})  # Wrong type!
    
    runtime.service_registry.get_services_by_type = Mock(return_value=[tool_service])
    
    # Should raise TypeError - FAIL FAST AND LOUD
    with pytest.raises(TypeError, match="returned invalid type"):
        await build_system_snapshot(
            task=None,
            thought=None,
            resource_monitor=resource_monitor,
            runtime=runtime
        )


@pytest.mark.asyncio
async def test_build_system_snapshot_with_service_registry():
    """Test service health collection from service registry."""
    # Mock resource monitor
    resource_monitor = Mock()
    resource_monitor.snapshot = Mock(critical=[], healthy=True)
    
    # Mock service registry
    service_registry = Mock()
    
    # Create mock service with health status
    healthy_service = Mock()
    healthy_service.get_health_status = AsyncMock(return_value=Mock(
        service_name="healthy_service",
        is_healthy=True,
        uptime_seconds=100.0
    ))
    
    # Registry returns services
    service_registry.get_provider_info = Mock(return_value={
        "handlers": {
            "test_handler": {
                "service": [healthy_service]
            }
        },
        "global_services": {}
    })
    
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=resource_monitor,
        service_registry=service_registry
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    # Service health is in model_extra
    assert "service_health" in snapshot.model_extra
    health = snapshot.model_extra["service_health"]
    assert "test_handler.service" in health


@pytest.mark.asyncio
async def test_build_system_snapshot_with_version_info():
    """Test that version information is included in snapshot."""
    resource_monitor = Mock()
    resource_monitor.snapshot = Mock(critical=[], healthy=True)
    
    snapshot = await build_system_snapshot(
        task=None,
        thought=None,
        resource_monitor=resource_monitor
    )
    
    assert isinstance(snapshot, SystemSnapshot)
    # Version info should be present
    assert snapshot.agent_version == "1.0.4-beta"
    assert snapshot.agent_codename == "Graceful Guardian"
    # code_hash might be None in tests