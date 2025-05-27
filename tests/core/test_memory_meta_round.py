import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from collections import deque

from ciris_engine.core.processor.main_processor import AgentProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.schemas.config_schemas_v1 import AppConfig, WorkflowConfig, LLMServicesConfig, OpenAIConfig, DatabaseConfig, GuardrailsConfig

@pytest.fixture
def simple_app_config():
    return AppConfig(
        db=DatabaseConfig(db_filename="t.db"),
        llm_services=LLMServicesConfig(openai=OpenAIConfig(model_name="m")),
        workflow=WorkflowConfig(max_active_tasks=1, max_active_thoughts=2, round_delay_seconds=0, max_ponder_rounds=1),
        guardrails=GuardrailsConfig(),
    )

@pytest.fixture
def processor(simple_app_config):
    mock_wc = AsyncMock()
    mock_wc.process_thought = AsyncMock()
    mock_wc.advance_round = MagicMock()
    mock_wc.current_round_number = 0
    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock()
    return AgentProcessor(app_config=simple_app_config, workflow_coordinator=mock_wc, action_dispatcher=dispatcher, services={})

@patch('ciris_engine.core.processor.main_processor.persistence')
@pytest.mark.asyncio
async def test_memory_meta_round_isolated(mock_persistence, processor: AgentProcessor):
    memory_thought = Thought(
        thought_id="m1",
        source_task_id="t1",
        thought_type="memory_meta",
        status=ThoughtStatus.PENDING,
        created_at="",
        updated_at="",
        round_created=0,
        content="",
    )
    normal_thought = Thought(
        thought_id="n1",
        source_task_id="t2",
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at="",
        updated_at="",
        round_created=0,
        content="",
    )
    mock_persistence.get_pending_thoughts_for_active_tasks.return_value = [memory_thought, normal_thought]
    mock_persistence.count_active_tasks.return_value = 0
    mock_persistence.get_pending_tasks_for_activation.return_value = []
    mock_persistence.get_tasks_needing_seed_thought.return_value = []

    await processor._populate_round_queue()

    assert len(processor.processing_queue) == 1
    assert processor.processing_queue[0].thought_id == "m1"
