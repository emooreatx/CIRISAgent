import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.agent_core_schemas import Task, Thought
from ciris_engine.core.config_schemas import (
    AppConfig,
    WorkflowConfig,
    LLMServicesConfig,
    OpenAIConfig,
    DatabaseConfig,
    GuardrailsConfig,
    SerializableAgentProfile,
)
from ciris_engine.core.foundational_schemas import HandlerActionType
from ciris_engine.core.foundational_schemas import TaskStatus, ThoughtStatus


@pytest.fixture
def simple_app_config():
    return AppConfig(
        db=DatabaseConfig(db_filename="wc_context.db"),
        llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name="test-model")),
        workflow=WorkflowConfig(max_active_tasks=2, max_active_thoughts=2, round_delay_seconds=0, max_ponder_rounds=1),
        guardrails=GuardrailsConfig(),
        agent_profiles={
            "default_profile": SerializableAgentProfile(
                name="default_profile",
                permitted_actions=[HandlerActionType.SPEAK],
            )
        },
        agent_profile=SerializableAgentProfile(
            name="default_profile",
            permitted_actions=[HandlerActionType.SPEAK]
        )
    )


@pytest.fixture
def workflow_coordinator_instance(simple_app_config) -> WorkflowCoordinator:
    return WorkflowCoordinator(
        llm_client=AsyncMock(),
        ethical_pdma_evaluator=AsyncMock(),
        csdma_evaluator=AsyncMock(),
        action_selection_pdma_evaluator=AsyncMock(),
        ethical_guardrails=AsyncMock(),
        app_config=simple_app_config,
        memory_service=None,
    )


@pytest.fixture
def sample_thought():
    now_iso = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=0,
        content="ctx",
    )

@pytest.mark.asyncio
@patch('ciris_engine.core.workflow_coordinator.persistence')
async def test_build_context_includes_recent_tasks_and_profiles(
    mock_persistence,
    workflow_coordinator_instance: WorkflowCoordinator,
    sample_thought: Thought,
):
    now = datetime.now(timezone.utc).isoformat()
    task = Task(task_id='t1', description='desc', created_at=now, updated_at=now)
    completed = Task(
        task_id='c1',
        description='done',
        status=TaskStatus.COMPLETED,
        created_at=now,
        updated_at=now,
        outcome={'result': 'ok'}
    )

    mock_persistence.count_tasks.return_value = 1
    mock_persistence.count_thoughts.return_value = 1
    mock_persistence.get_top_tasks.return_value = [task]
    mock_persistence.get_recent_completed_tasks.return_value = [completed]

    workflow_coordinator_instance.graphql_context_provider.enrich_context = AsyncMock(
        return_value={'user_profiles': {'alice': {'nick': 'Alice', 'channel': 'general'}}}
    )

    ctx = await workflow_coordinator_instance.build_context(task, sample_thought)

    assert ctx['recently_completed_tasks_summary'][0]['task_id'] == 'c1'
    assert ctx['recently_completed_tasks_summary'][0]['outcome'] == {'result': 'ok'}
    assert ctx['user_profiles']['alice']['nick'] == 'Alice'
