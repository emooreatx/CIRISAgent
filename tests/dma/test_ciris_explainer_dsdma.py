import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from openai import AsyncOpenAI
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import DSDMAResult
from ciris_engine.core.agent_core_schemas import ThoughtStatus
from ciris_engine.dma.ciris_explainer_dsdma import CIRISExplainerDSDMA
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.core.config_schemas import AppConfig, OpenAIConfig, LLMServicesConfig


@pytest.fixture
def mock_openai_client():
    client = MagicMock(spec=AsyncOpenAI)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def sample_thought_item():
    now_iso = datetime.now(timezone.utc).isoformat()
    return ProcessingQueueItem(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="test_explainer_thought",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=5,
        content="Explain CIRIS",
        processing_context={},
        initial_context={}
    )


@pytest.fixture
def explainer_dsdma(mock_openai_client, monkeypatch):
    cfg = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON")))
    monkeypatch.setattr("ciris_engine.dma.dsdma_base.get_config", lambda: cfg)
    evaluator = CIRISExplainerDSDMA(
        domain_name="Explainer",
        aclient=mock_openai_client,
        model_name="m"
    )
    evaluator.aclient.chat.completions.create = AsyncMock(name="patched_create_explainer")
    return evaluator


@pytest.mark.asyncio
async def test_explainer_prompt_structure(explainer_dsdma, sample_thought_item):
    result_obj = BaseDSDMA.LLMOutputForDSDMA(
        domain_alignment_score=1.0,
        recommended_action=None,
        flags=[],
        reasoning="ok",
    )
    result_obj._raw_response = MagicMock()
    explainer_dsdma.aclient.chat.completions.create.return_value = result_obj

    context = {
        "current_task": {"description": "CT", "task_id": "1"},
        "recent_actions": [],
        "completed_tasks": [],
        "system_snapshot": {},
        "user_profiles": {},
        "parent_tasks": [],
        "thoughts_chain": [],
        "actions_taken": 1,
    }

    await explainer_dsdma.evaluate_thought(sample_thought_item, context)

    explainer_dsdma.aclient.chat.completions.create.assert_awaited_once()
    call_args = explainer_dsdma.aclient.chat.completions.create.call_args.kwargs
    system_message = call_args["messages"][0]["content"]
    user_message = call_args["messages"][1]["content"]
    assert system_message.startswith("=== Task History ===")
    assert "CIRIS System Guidance" in system_message
    assert user_message.startswith("=== Parent Task Chain ===")
    assert "Thoughts Under Consideration" in user_message
