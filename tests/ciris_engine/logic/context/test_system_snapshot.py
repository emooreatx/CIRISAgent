"""Tests for system_snapshot.py to ensure proper type handling and full coverage."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from typing import List, Dict

from ciris_engine.logic.context.system_snapshot import build_system_snapshot
from ciris_engine.schemas.runtime.system_context import SystemSnapshot, ChannelContext
from ciris_engine.schemas.adapters.tools import ToolInfo, ToolParameterSchema
from ciris_engine.schemas.infrastructure.bus import ServiceRegistration
from ciris_engine.logic.buses.bus_manager import BusManager


@pytest.fixture
def mock_channel_context():
    """Create a mock channel context."""
    return ChannelContext(
        channel_id="test_channel",
        channel_type="test",
        channel_metadata={}
    )


@pytest.fixture
def mock_tool_info():
    """Create a valid ToolInfo instance."""
    return ToolInfo(
        name="test_tool",
        description="A test tool",
        schema=ToolParameterSchema(
            type="object",
            properties={
                "param1": {"type": "string", "description": "Test parameter"}
            },
            required=["param1"]
        ),
        cost=0.0
    )


@pytest.fixture
def mock_tool_service(mock_tool_info):
    """Create a mock tool service that returns ToolInfo objects."""
    service = Mock()
    service.get_available_tools = Mock(return_value=["test_tool"])
    service.get_tool_info = Mock(return_value=mock_tool_info)
    return service


@pytest.fixture
def mock_adapter_with_tools(mock_tool_service):
    """Create a mock adapter with tool service."""
    adapter = Mock()
    adapter.get_service = Mock(return_value=mock_tool_service)
    adapter.get_type = Mock(return_value="test_adapter")
    return adapter


@pytest.fixture
def mock_bus_manager(mock_adapter_with_tools):
    """Create a mock bus manager with adapters."""
    bus_manager = Mock(spec=BusManager)
    
    # Mock service registry with adapters
    service_registry = Mock()
    service_registry.get_all_services = Mock(return_value=[
        ServiceRegistration(
            service_id="test_adapter",
            service_type="adapter",
            service_instance=mock_adapter_with_tools,
            tags={"adapter_type": "test"}
        )
    ])
    bus_manager.service_registry = service_registry
    
    # Mock other required services
    bus_manager.time_service = Mock()
    bus_manager.time_service.now = Mock(return_value=datetime.now(timezone.utc))
    
    bus_manager.memory = Mock()
    bus_manager.memory.get_node = AsyncMock(return_value=None)
    
    return bus_manager


@pytest.mark.asyncio
async def test_build_system_snapshot_with_tools(mock_bus_manager, mock_channel_context, mock_tool_info):
    """Test that build_system_snapshot properly handles ToolInfo objects."""
    # Build the snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify it's a valid SystemSnapshot
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.channel_context == mock_channel_context
    
    # Verify available_tools contains ToolInfo objects, not dicts
    assert "available_tools" in snapshot.model_extra
    assert isinstance(snapshot.model_extra["available_tools"], dict)
    assert "test_adapter" in snapshot.model_extra["available_tools"]
    
    # Verify the tools are ToolInfo instances
    tools = snapshot.model_extra["available_tools"]["test_adapter"]
    assert isinstance(tools, list)
    assert len(tools) == 1
    assert isinstance(tools[0], ToolInfo)
    assert tools[0].name == "test_tool"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_async_tool_service(mock_bus_manager, mock_channel_context, mock_tool_info):
    """Test handling of async tool service methods."""
    # Make tool service methods async
    tool_service = mock_bus_manager.service_registry.get_all_services()[0].service_instance.get_service()
    tool_service.get_available_tools = AsyncMock(return_value=["async_tool"])
    tool_service.get_tool_info = AsyncMock(return_value=mock_tool_info)
    
    # Build the snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify async methods were called
    tool_service.get_available_tools.assert_called_once()
    tool_service.get_tool_info.assert_called_once_with("async_tool")
    
    # Verify result
    assert "available_tools" in snapshot.model_extra
    tools = snapshot.model_extra["available_tools"]["test_adapter"]
    assert len(tools) == 1
    assert isinstance(tools[0], ToolInfo)


@pytest.mark.asyncio
async def test_build_system_snapshot_handles_tool_errors(mock_bus_manager, mock_channel_context):
    """Test graceful handling of tool service errors."""
    # Make tool service raise an exception
    tool_service = mock_bus_manager.service_registry.get_all_services()[0].service_instance.get_service()
    tool_service.get_available_tools = Mock(side_effect=Exception("Tool service error"))
    
    # Build should not crash
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Should have empty tools for that adapter
    assert "available_tools" in snapshot.model_extra
    assert snapshot.model_extra["available_tools"] == {}


@pytest.mark.asyncio
async def test_build_system_snapshot_type_validation(mock_bus_manager, mock_channel_context):
    """Test that improper types raise TypeError as expected."""
    # Make tool service return wrong type
    tool_service = mock_bus_manager.service_registry.get_all_services()[0].service_instance.get_service()
    tool_service.get_available_tools = Mock(return_value=["test_tool"])
    tool_service.get_tool_info = Mock(return_value={"not": "a_tool_info"})  # Wrong type!
    
    # This should raise TypeError due to our type checking
    with pytest.raises(TypeError, match="returned invalid tool info type"):
        await build_system_snapshot(
            bus_manager=mock_bus_manager,
            channel_context=mock_channel_context
        )


@pytest.mark.asyncio
async def test_build_system_snapshot_with_identity_retrieval(mock_bus_manager, mock_channel_context):
    """Test identity retrieval from memory graph."""
    from ciris_engine.schemas.services.graph_core import GraphNode, GraphNodeAttributes, NodeType, GraphScope
    from ciris_engine.schemas.runtime.identity import AgentIdentityRoot
    
    # Create mock identity node
    identity_root = AgentIdentityRoot(
        agent_id="test_agent",
        agent_name="Test Agent",
        purpose="Testing",
        core_profile="Tester",
        allowed_capabilities=["test"],
        restricted_capabilities=[]
    )
    
    identity_attrs = GraphNodeAttributes(
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="test",
        data=identity_root.model_dump()
    )
    
    identity_node = GraphNode(
        id="agent/identity",
        type=NodeType.IDENTITY,
        scope=GraphScope.IDENTITY,
        attributes=identity_attrs,
        updated_by="test",
        updated_at=datetime.now(timezone.utc)
    )
    
    # Mock memory service to return identity
    mock_bus_manager.memory.get_node = AsyncMock(return_value=identity_node)
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify identity was retrieved
    assert "agent_identity" in snapshot.model_extra
    identity = snapshot.model_extra["agent_identity"]
    assert identity.agent_id == "test_agent"
    assert identity.agent_name == "Test Agent"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_service_health(mock_bus_manager, mock_channel_context):
    """Test service health status collection."""
    from ciris_engine.schemas.services.core.runtime import ServiceHealthStatus
    
    # Create mock services with health status
    healthy_service = Mock()
    healthy_service.get_health_status = Mock(return_value=ServiceHealthStatus(
        service_name="healthy_service",
        is_healthy=True,
        uptime_seconds=100.0,
        last_check=datetime.now(timezone.utc)
    ))
    
    unhealthy_service = Mock()
    unhealthy_service.get_health_status = Mock(return_value=ServiceHealthStatus(
        service_name="unhealthy_service",
        is_healthy=False,
        uptime_seconds=50.0,
        last_check=datetime.now(timezone.utc),
        error="Connection failed"
    ))
    
    # Add services to registry
    mock_bus_manager.service_registry.get_all_services = Mock(return_value=[
        ServiceRegistration(
            service_id="healthy",
            service_type="core",
            service_instance=healthy_service,
            tags={}
        ),
        ServiceRegistration(
            service_id="unhealthy",
            service_type="core",
            service_instance=unhealthy_service,
            tags={}
        )
    ])
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify health status
    assert "service_health" in snapshot.model_extra
    health_dict = snapshot.model_extra["service_health"]
    assert "healthy_service" in health_dict
    assert health_dict["healthy_service"].is_healthy is True
    assert "unhealthy_service" in health_dict
    assert health_dict["unhealthy_service"].is_healthy is False


@pytest.mark.asyncio
async def test_build_system_snapshot_with_channels(mock_bus_manager, mock_channel_context):
    """Test adapter channel collection."""
    # Create mock adapter with channels
    channel1 = ChannelContext(
        channel_id="channel1",
        channel_type="discord",
        channel_metadata={"guild": "test_guild"}
    )
    channel2 = ChannelContext(
        channel_id="channel2",
        channel_type="discord",
        channel_metadata={"guild": "test_guild"}
    )
    
    adapter = Mock()
    adapter.get_type = Mock(return_value="discord")
    adapter.get_channels = Mock(return_value=[channel1, channel2])
    
    # Add adapter to registry
    mock_bus_manager.service_registry.get_all_services = Mock(return_value=[
        ServiceRegistration(
            service_id="discord_adapter",
            service_type="adapter",
            service_instance=adapter,
            tags={"adapter_type": "discord"}
        )
    ])
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify channels
    assert "adapter_channels" in snapshot.model_extra
    channels_dict = snapshot.model_extra["adapter_channels"]
    assert "discord" in channels_dict
    assert len(channels_dict["discord"]) == 2
    assert all(isinstance(ch, ChannelContext) for ch in channels_dict["discord"])


@pytest.mark.asyncio
async def test_build_system_snapshot_with_circuit_breakers(mock_bus_manager, mock_channel_context):
    """Test circuit breaker status collection."""
    from ciris_engine.schemas.services.runtime_control import CircuitBreakerStatus
    
    # Create mock runtime control with circuit breakers
    runtime_control = Mock()
    runtime_control.get_circuit_breaker_status = Mock(return_value={
        "llm_service": CircuitBreakerStatus(
            service_name="llm_service",
            state="CLOSED",
            failure_count=0,
            last_failure_time=None,
            consecutive_successes=10
        ),
        "memory_service": CircuitBreakerStatus(
            service_name="memory_service",
            state="OPEN",
            failure_count=5,
            last_failure_time=datetime.now(timezone.utc),
            consecutive_successes=0
        )
    })
    
    mock_bus_manager.runtime_control = runtime_control
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify circuit breakers
    assert "circuit_breaker_status" in snapshot.model_extra
    breakers = snapshot.model_extra["circuit_breaker_status"]
    assert "llm_service" in breakers
    assert breakers["llm_service"].state == "CLOSED"
    assert "memory_service" in breakers
    assert breakers["memory_service"].state == "OPEN"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_user_enrichment(mock_bus_manager, mock_channel_context):
    """Test user profile enrichment."""
    from ciris_engine.schemas.services.graph_core import GraphNode, GraphNodeAttributes, NodeType, GraphScope
    
    # Create mock user node
    user_attrs = GraphNodeAttributes(
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="system",
        data={
            "user_id": "test_user",
            "username": "TestUser",
            "display_name": "Test User",
            "is_verified": True,
            "metadata": {"level": "admin"}
        }
    )
    
    user_node = GraphNode(
        id="user/test_user",
        type=NodeType.USER,
        scope=GraphScope.GLOBAL,
        attributes=user_attrs,
        updated_by="system",
        updated_at=datetime.now(timezone.utc)
    )
    
    # Mock memory query for user
    mock_bus_manager.memory.query = AsyncMock(return_value=[user_node])
    
    # Build snapshot with author context
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context,
        author_id="test_user"
    )
    
    # Verify user enrichment
    assert "enriched_users" in snapshot.model_extra
    users = snapshot.model_extra["enriched_users"]
    assert "test_user" in users
    user_profile = users["test_user"]
    assert user_profile["username"] == "TestUser"
    assert user_profile["is_verified"] is True


@pytest.mark.asyncio
async def test_build_system_snapshot_minimal(mock_bus_manager, mock_channel_context):
    """Test minimal snapshot with only required fields."""
    # Remove all optional services
    mock_bus_manager.memory = None
    mock_bus_manager.runtime_control = None
    mock_bus_manager.service_registry.get_all_services = Mock(return_value=[])
    
    # Build minimal snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Should still be valid
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.channel_context == mock_channel_context
    
    # Optional fields should be empty or have defaults
    assert snapshot.model_extra.get("available_tools", {}) == {}
    assert snapshot.model_extra.get("service_health", {}) == {}
    assert snapshot.model_extra.get("adapter_channels", {}) == {}


@pytest.mark.asyncio
async def test_build_system_snapshot_error_resilience(mock_bus_manager, mock_channel_context):
    """Test that snapshot building is resilient to service errors."""
    # Make various services throw errors
    mock_bus_manager.memory.get_node = AsyncMock(side_effect=Exception("Memory error"))
    
    # Add a failing service
    failing_service = Mock()
    failing_service.get_health_status = Mock(side_effect=Exception("Health check failed"))
    
    mock_bus_manager.service_registry.get_all_services = Mock(return_value=[
        ServiceRegistration(
            service_id="failing",
            service_type="core",
            service_instance=failing_service,
            tags={}
        )
    ])
    
    # Should not crash
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Should still have basic structure
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.channel_context == mock_channel_context
    
    # Failed services should be handled gracefully
    assert "agent_identity" not in snapshot.model_extra  # Memory failed
    assert snapshot.model_extra.get("service_health", {}) == {}  # Health check failed


@pytest.mark.asyncio
async def test_build_system_snapshot_with_task_and_thought():
    """Test snapshot with task and thought context."""
    from ciris_engine.schemas.runtime.models import Task, Thought
    from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
    from ciris_engine.schemas.runtime.contexts import TaskContext, ThoughtContext
    
    # Create mock task
    task = Task(
        task_id="test_task",
        description="Test task description",
        status=TaskStatus.ACTIVE,
        priority=10,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        context=TaskContext()
    )
    
    # Create mock thought
    thought = Thought(
        thought_id="test_thought",
        source_task_id="test_task",
        content="Test thought content",
        status=ThoughtStatus.PROCESSING,
        thought_depth=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=ThoughtContext(
            task_id="test_task",
            round_number=1,
            depth=1,
            correlation_id="test_correlation"
        )
    )
    
    # Mock bus manager
    bus_manager = Mock()
    bus_manager.time_service = Mock()
    bus_manager.time_service.now = Mock(return_value=datetime.now(timezone.utc))
    bus_manager.service_registry = Mock()
    bus_manager.service_registry.get_all_services = Mock(return_value=[])
    bus_manager.memory = None
    
    # Build snapshot with task and thought
    snapshot = await build_system_snapshot(
        bus_manager=bus_manager,
        channel_context=ChannelContext(
            channel_id="test",
            channel_type="test",
            channel_metadata={}
        ),
        task=task,
        thought=thought
    )
    
    # Verify task and thought summaries are present
    assert snapshot.current_task_details is not None
    assert snapshot.current_task_details.task_id == "test_task"
    assert snapshot.current_thought_summary is not None
    assert snapshot.current_thought_summary.thought_id == "test_thought"


@pytest.mark.asyncio
async def test_build_system_snapshot_with_secrets_context(mock_bus_manager, mock_channel_context):
    """Test secrets context integration."""
    from ciris_engine.logic.secrets.service import SecretsService
    
    # Mock secrets service
    secrets_service = Mock(spec=SecretsService)
    secrets_service.detect_secrets = Mock(return_value=["SECRET_KEY"])
    secrets_service.get_safe_pattern = Mock(return_value="S***_KEY")
    
    # Add secrets to bus manager
    mock_bus_manager.secrets = secrets_service
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context,
        content="This contains SECRET_KEY in text"
    )
    
    # Verify secrets were detected
    assert "detected_secrets" in snapshot.model_extra
    secrets = snapshot.model_extra["detected_secrets"]
    assert len(secrets) == 1
    assert "SECRET_KEY" in secrets


@pytest.mark.asyncio  
async def test_build_system_snapshot_with_resource_monitoring(mock_bus_manager, mock_channel_context):
    """Test resource monitoring integration."""
    from ciris_engine.schemas.runtime.resources import ResourceUsage
    
    # Mock resource monitor
    resource_monitor = Mock()
    resource_monitor.get_resource_usage = Mock(return_value=ResourceUsage(
        memory_usage_mb=512.0,
        cpu_usage_percent=25.5,
        disk_usage_gb=10.2,
        active_threads=5
    ))
    
    # Add to bus manager
    mock_bus_manager.resource_monitor = resource_monitor
    
    # Build snapshot
    snapshot = await build_system_snapshot(
        bus_manager=mock_bus_manager,
        channel_context=mock_channel_context
    )
    
    # Verify resource usage
    assert snapshot.memory_usage_mb == 512.0
    assert snapshot.cpu_usage_percent == 25.5