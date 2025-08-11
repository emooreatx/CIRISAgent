"""Extended tests for system_snapshot.py to improve coverage."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ciris_engine.logic.context.system_snapshot import build_system_snapshot
from ciris_engine.schemas.runtime.enums import TaskStatus
from ciris_engine.schemas.runtime.models import Task, TaskContext
from ciris_engine.schemas.runtime.system_context import (
    ChannelContext,
    SystemSnapshot,
    TaskSummary,
    ThoughtSummary,
    UserProfile,
)
from ciris_engine.schemas.services.graph_core import GraphScope, NodeType


class TestSystemSnapshotExtended:
    """Extended test suite for build_system_snapshot function."""

    @pytest.fixture
    def mock_resource_monitor(self):
        """Create a mock resource monitor."""
        monitor = Mock()
        monitor.snapshot = Mock()
        monitor.snapshot.critical = []
        monitor.snapshot.healthy = True
        monitor.snapshot.resources = {"cpu_percent": 45.2, "memory_percent": 62.1, "disk_percent": 35.0}
        return monitor

    @pytest.fixture
    def mock_memory_service(self):
        """Create a mock memory service."""
        service = AsyncMock()
        service.query = AsyncMock(return_value=[])
        service.get_node = AsyncMock(return_value=None)
        return service

    @pytest.fixture
    def mock_graphql_provider(self):
        """Create a mock GraphQL provider."""
        provider = Mock()
        provider.get_context = Mock(return_value={"channel_id": "graphql_channel", "additional": "context"})
        return provider

    @pytest.fixture
    def mock_telemetry_service(self):
        """Create a mock telemetry service."""
        service = Mock()
        service.get_recent_metrics = Mock(return_value=[])
        service.get_health_status = Mock(return_value="healthy")
        return service

    @pytest.fixture
    def mock_secrets_service(self):
        """Create a mock secrets service."""
        service = Mock()
        service.list_secrets = Mock(return_value=[])
        service.get_secret_metadata = Mock(return_value={})
        return service

    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime."""
        runtime = Mock()
        runtime.config = Mock()
        runtime.config.get = Mock(return_value=None)
        runtime.agent_identity = Mock()
        runtime.agent_identity.name = "TestAgent"
        runtime.agent_identity.wa_id = "test_wa_123"
        return runtime

    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry."""
        registry = Mock()
        registry.get_service_health = Mock(return_value={})
        registry.list_services = Mock(return_value=[])
        return registry

    @pytest.fixture
    def complex_thought(self):
        """Create a complex thought with all attributes."""
        thought = Mock()
        thought.thought_id = "complex_thought_123"
        thought.content = "Complex thought content"
        thought.status = Mock(value="PROCESSING")
        thought.source_task_id = "source_task_456"
        thought.thought_type = "DEEP_ANALYSIS"
        thought.thought_depth = 3
        thought.created_at = datetime.now(timezone.utc).isoformat()
        thought.metadata = {"key": "value"}
        return thought

    @pytest.fixture
    def complex_task(self):
        """Create a complex task with nested context."""
        context = TaskContext(correlation_id="correlation_789", channel_id="task_channel", user_id="user_123")

        task = Task(
            task_id="complex_task_456",
            channel_id="task_channel",
            description="Complex test task",
            status=TaskStatus.ACTIVE,
            priority=15,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            context=context,
        )
        return task

    @pytest.mark.asyncio
    async def test_build_snapshot_with_all_services(
        self,
        complex_task,
        complex_thought,
        mock_resource_monitor,
        mock_memory_service,
        mock_graphql_provider,
        mock_telemetry_service,
        mock_secrets_service,
        mock_runtime,
        mock_service_registry,
    ):
        """Test building snapshot with all services provided."""
        snapshot = await build_system_snapshot(
            task=complex_task,
            thought=complex_thought,
            resource_monitor=mock_resource_monitor,
            memory_service=mock_memory_service,
            graphql_provider=mock_graphql_provider,
            telemetry_service=mock_telemetry_service,
            secrets_service=mock_secrets_service,
            runtime=mock_runtime,
            service_registry=mock_service_registry,
        )

        assert isinstance(snapshot, SystemSnapshot)
        assert snapshot.thought_summary is not None
        assert snapshot.thought_summary.thought_id == "complex_thought_123"
        assert snapshot.channel_id == "task_channel"

    @pytest.mark.asyncio
    async def test_build_snapshot_minimal(self, mock_resource_monitor):
        """Test building snapshot with only required parameters."""
        snapshot = await build_system_snapshot(task=None, thought=None, resource_monitor=mock_resource_monitor)

        assert isinstance(snapshot, SystemSnapshot)
        assert snapshot.thought_summary is None
        assert snapshot.channel_id is None

    @pytest.mark.asyncio
    async def test_channel_context_extraction_from_task(self, complex_task, mock_resource_monitor):
        """Test channel context extraction from task."""
        snapshot = await build_system_snapshot(task=complex_task, thought=None, resource_monitor=mock_resource_monitor)

        assert snapshot.channel_id == "task_channel"
        assert snapshot.channel_context is not None

    @pytest.mark.asyncio
    async def test_channel_context_from_graphql(self, mock_resource_monitor, mock_graphql_provider):
        """Test channel context from GraphQL provider."""
        snapshot = await build_system_snapshot(
            task=None, thought=None, resource_monitor=mock_resource_monitor, graphql_provider=mock_graphql_provider
        )

        # GraphQL context should be checked
        mock_graphql_provider.get_context.assert_called()

    @pytest.mark.asyncio
    async def test_thought_without_status_enum(self, mock_resource_monitor):
        """Test thought with string status instead of enum."""
        thought = Mock()
        thought.thought_id = "string_status_thought"
        thought.content = "Test content"
        thought.status = "PENDING"  # String instead of enum
        thought.source_task_id = None
        thought.thought_type = "BASIC"
        thought.thought_depth = 1

        snapshot = await build_system_snapshot(task=None, thought=thought, resource_monitor=mock_resource_monitor)

        assert snapshot.thought_summary.status == "PENDING"

    @pytest.mark.asyncio
    async def test_thought_with_missing_id(self, mock_resource_monitor):
        """Test thought with missing thought_id."""
        thought = Mock()
        thought.thought_id = None  # Missing ID
        thought.content = "Content without ID"
        thought.status = Mock(value="PROCESSING")
        thought.source_task_id = "task_123"
        thought.thought_type = "ANALYSIS"
        thought.thought_depth = 2

        snapshot = await build_system_snapshot(task=None, thought=thought, resource_monitor=mock_resource_monitor)

        # Should provide default value for missing ID
        assert snapshot.thought_summary.thought_id == "unknown"

    @pytest.mark.asyncio
    async def test_memory_service_query(self, mock_resource_monitor, mock_memory_service, complex_task):
        """Test memory service query for channel context."""
        mock_memory_service.query.return_value = [
            {
                "id": "channel_node",
                "type": NodeType.CHANNEL,
                "attributes": {"channel_id": "memory_channel", "name": "Memory Channel"},
            }
        ]

        snapshot = await build_system_snapshot(
            task=complex_task, thought=None, resource_monitor=mock_resource_monitor, memory_service=mock_memory_service
        )

        # Memory service should be queried
        mock_memory_service.query.assert_called()

    @pytest.mark.asyncio
    async def test_secrets_snapshot_integration(self, mock_resource_monitor, mock_secrets_service):
        """Test secrets snapshot integration."""
        mock_secrets_service.list_secrets.return_value = ["secret1", "secret2"]

        with patch("ciris_engine.logic.context.system_snapshot.build_secrets_snapshot") as mock_build_secrets:
            mock_build_secrets.return_value = {"encrypted_count": 2, "total_secrets": 2}

            snapshot = await build_system_snapshot(
                task=None, thought=None, resource_monitor=mock_resource_monitor, secrets_service=mock_secrets_service
            )

            mock_build_secrets.assert_called_once_with(mock_secrets_service)

    @pytest.mark.asyncio
    async def test_runtime_agent_identity(self, mock_resource_monitor, mock_runtime):
        """Test agent identity extraction from runtime."""
        snapshot = await build_system_snapshot(
            task=None, thought=None, resource_monitor=mock_resource_monitor, runtime=mock_runtime
        )

        assert snapshot.agent_identity is not None
        assert snapshot.agent_identity["name"] == "TestAgent"
        assert snapshot.agent_identity["wa_id"] == "test_wa_123"

    @pytest.mark.asyncio
    async def test_exception_handling_in_channel_extraction(self, mock_resource_monitor):
        """Test exception handling during channel extraction."""
        # Create a task with context that will raise an exception
        bad_task = Mock()
        bad_task.context = Mock()
        bad_task.context.__getattr__ = Mock(side_effect=Exception("Context error"))

        # Should not crash, but handle gracefully
        snapshot = await build_system_snapshot(task=bad_task, thought=None, resource_monitor=mock_resource_monitor)

        assert isinstance(snapshot, SystemSnapshot)

    @pytest.mark.asyncio
    async def test_nested_channel_context_extraction(self, mock_resource_monitor):
        """Test extraction from deeply nested context."""
        task = Mock()
        task.context = Mock()
        task.context.system_snapshot = Mock()
        task.context.system_snapshot.channel_context = Mock()
        task.context.system_snapshot.channel_context.channel_id = "nested_channel"
        task.context.system_snapshot.channel_context.channel_name = "Nested Channel"

        snapshot = await build_system_snapshot(task=task, thought=None, resource_monitor=mock_resource_monitor)

        # Should extract from nested structure
        assert snapshot.channel_id == "nested_channel"

    @pytest.mark.asyncio
    async def test_service_health_integration(self, mock_resource_monitor, mock_service_registry):
        """Test service health status integration."""
        mock_service_registry.get_service_health.return_value = {
            "service1": "healthy",
            "service2": "degraded",
            "service3": "unhealthy",
        }

        snapshot = await build_system_snapshot(
            task=None, thought=None, resource_monitor=mock_resource_monitor, service_registry=mock_service_registry
        )

        mock_service_registry.get_service_health.assert_called()

    @pytest.mark.asyncio
    async def test_telemetry_metrics_integration(self, mock_resource_monitor, mock_telemetry_service):
        """Test telemetry metrics integration."""
        mock_telemetry_service.get_recent_metrics.return_value = [
            {"metric": "cpu", "value": 45.2},
            {"metric": "memory", "value": 62.1},
        ]

        snapshot = await build_system_snapshot(
            task=None, thought=None, resource_monitor=mock_resource_monitor, telemetry_service=mock_telemetry_service
        )

        mock_telemetry_service.get_recent_metrics.assert_called()
