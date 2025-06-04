import pytest
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry, Priority

@pytest.mark.asyncio
async def test_pdma_init_and_evaluate(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(instruct_client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    evaluator = EthicalPDMAEvaluator(service_registry=service_registry, model_name="m")
    # Use a real EthicalDMAResult for the mock return value
    mock_result = EthicalDMAResult(
        alignment_check={"SPEAK": "ok"},
        decision="Allow",
        rationale="rationale"
    )
    dummy_client.instruct_client.chat.completions.create = AsyncMock(return_value=mock_result)
    dummy_client.instruct_client.chat.completions.create = AsyncMock(return_value=mock_result)
    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="t1",
        source_task_id="s1",
        thought_type="test",
        content=ThoughtContent(text="test"),
    )
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
    ctx = ThoughtContext(system_snapshot=SystemSnapshot(system_counts={}))
    result = await evaluator.evaluate(item, ctx)
    assert isinstance(result, EthicalDMAResult)
    assert result.alignment_check == {"SPEAK": "ok"}
    assert result.decision == "Allow"
    assert result.rationale == "rationale"
