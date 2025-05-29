import pytest
from unittest.mock import MagicMock, AsyncMock
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem

@pytest.mark.asyncio
async def test_pdma_init_and_evaluate(monkeypatch):
    aclient = MagicMock()
    evaluator = EthicalPDMAEvaluator(aclient=aclient, model_name="m")
    # Use a real EthicalDMAResult for the mock return value
    mock_result = EthicalDMAResult(
        alignment_check={"SPEAK": "ok"},
        decision="Allow",
        rationale="rationale"
    )
    evaluator.aclient.chat.completions.create = AsyncMock(return_value=mock_result)
    item = ProcessingQueueItem(
        thought_id="t1",
        source_task_id="s1",
        thought_type="test",
        content="test",
    )
    result = await evaluator.evaluate(item)
    assert isinstance(result, EthicalDMAResult)
    assert result.alignment_check == {"SPEAK": "ok"}
    assert result.decision == "Allow"
    assert result.rationale == "rationale"
