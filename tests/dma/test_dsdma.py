import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from openai import AsyncOpenAI
from instructor.exceptions import InstructorRetryException

from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.schemas.dma_results_v1 import DSDMAResult
from ciris_engine.schemas.agent_core_schemas_v1 import ThoughtStatus
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.config_schemas_v1 import AppConfig, OpenAIConfig, LLMServicesConfig


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
        thought_type="test_dsdma_thought",
        status=ThoughtStatus.PENDING,
        created_at=now_iso,
        updated_at=now_iso,
        round_created=1,
        priority=5,
        content={"text": "Sample content"},
        processing_context={},
        initial_context={"channel_name": "#general"}
    )


@pytest.fixture
def base_dsdma(mock_openai_client, monkeypatch):
    cfg = AppConfig(llm_services=LLMServicesConfig(openai=OpenAIConfig(instructor_mode="JSON")))
    monkeypatch.setattr("ciris_engine.dma.dsdma_base.get_config", lambda: cfg)
    evaluator = BaseDSDMA(
        domain_name="TestDomain",
        aclient=mock_openai_client,
        model_name="test-model",
        domain_specific_knowledge={"rules_summary": "Be nice"},
        prompt_template="Test prompt. Context: {context_str} Rules: {rules_summary_str}"
    )
    evaluator.aclient.chat.completions.create = AsyncMock(name="patched_create")
    return evaluator


@pytest.mark.asyncio
async def test_evaluate_success(base_dsdma, sample_thought_item):
    expected = BaseDSDMA.LLMOutputForDSDMA(
        domain_alignment_score=0.8,
        recommended_action="Proceed",
        flags=["ok"],
        reasoning="fine"
    )
    mock_raw = MagicMock()
    expected._raw_response = mock_raw
    base_dsdma.aclient.chat.completions.create.return_value = expected

    result = await base_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

    assert isinstance(result, DSDMAResult)
    assert result.domain_alignment_score == expected.domain_alignment_score
    assert result.recommended_action == expected.recommended_action
    assert result.flags == expected.flags
    assert result.raw_llm_response == str(mock_raw)
    base_dsdma.aclient.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_instructor_error(base_dsdma, sample_thought_item):
    err = InstructorRetryException("boom", n_attempts=1, total_usage=None)
    base_dsdma.aclient.chat.completions.create.side_effect = err

    result = await base_dsdma.evaluate_thought(sample_thought_item, sample_thought_item.initial_context)

    assert isinstance(result, DSDMAResult)
    assert result.domain_alignment_score == 0.0
    assert "Instructor_ValidationError" in result.flags
    assert "boom" in result.raw_llm_response


def test_repr(base_dsdma):
    assert "TestDomain" in repr(base_dsdma)
