import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from ciris_engine.context.system_snapshot import build_system_snapshot
from ciris_engine.context.secrets_snapshot import build_secrets_snapshot
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType, ThoughtStatus

# Helpers reused from other tests

def make_thought():
    return Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="test content",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
    )


def make_task():
    return Task(
        task_id="t1",
        description="desc",
        status="active",
        priority=0,
        created_at="now",
        updated_at="now",
    )


@pytest.mark.asyncio
async def test_build_system_snapshot_integration():
    memory_service = AsyncMock()
    graphql_provider = AsyncMock()
    telemetry_service = AsyncMock()
    secrets_service = AsyncMock()

    # Configure mocks
    memory_service.recall.return_value = {}
    graphql_provider.enrich_context.return_value = {"extra": 1}

    from ciris_engine.schemas.secrets_schemas_v1 import SecretReference
    secret = SecretReference(
        uuid="test-uuid",
        description="Test secret",
        context_hint="Test API key",
        sensitivity="HIGH",
        auto_decapsulate_actions=[],
        created_at=datetime.now(),
        last_accessed=None,
        detected_pattern="api_key"
    )
    secrets_service.store.list_all_secrets.return_value = [secret]
    secrets_service.filter.config.version = 2

    task = make_task()
    thought = make_thought()
    thought.context = {"channel_id": "xyz"}

    snapshot = await build_system_snapshot(
        task,
        thought,
        memory_service=memory_service,
        graphql_provider=graphql_provider,
        telemetry_service=telemetry_service,
        secrets_service=secrets_service,
    )

    telemetry_service.update_system_snapshot.assert_awaited_once_with(snapshot)
    graphql_provider.enrich_context.assert_awaited_once_with(task, thought)
    memory_service.recall.assert_awaited()
    assert snapshot.extra == 1
    assert len(snapshot.detected_secrets) == 1


@pytest.mark.asyncio
async def test_build_secrets_snapshot_error_handling():
    service = AsyncMock()
    service.store.list_all_secrets.side_effect = Exception("boom")
    service.filter.config.version = 3
    result = await build_secrets_snapshot(service)
    assert result == {
        "detected_secrets": [],
        "secrets_filter_version": 0,
        "total_secrets_stored": 0,
    }
