from unittest.mock import MagicMock, AsyncMock
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import CSDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from openai import AsyncOpenAI

def test_csdma_init_and_patch(monkeypatch):
    aclient = MagicMock(spec=AsyncOpenAI)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = CSDMAEvaluator(aclient=aclient, model_name="m", prompt_overrides={"csdma_system_prompt": "PROMPT"})
    assert evaluator.model_name == "m"
    assert evaluator.prompt_overrides["csdma_system_prompt"] == "PROMPT"
    assert evaluator.aclient is aclient

async def test_csdma_evaluate_thought(monkeypatch):
    aclient = MagicMock()
    evaluator = CSDMAEvaluator(aclient=aclient, model_name="m")
    # Use a real CSDMAResult for the mock return value
    mock_result = CSDMAResult(plausibility_score=0.8, flags=["f1"], reasoning="r")
    evaluator.aclient.chat.completions.create = AsyncMock(return_value=mock_result)
    item = ProcessingQueueItem(
        thought_id="t1",
        source_task_id="s1",
        thought_type="test",
        content="test",
    )
    result = await evaluator.evaluate_thought(item)
    assert isinstance(result, CSDMAResult)
    assert result.plausibility_score == 0.8
    assert result.flags == ["f1"]
    assert result.reasoning == "r"
