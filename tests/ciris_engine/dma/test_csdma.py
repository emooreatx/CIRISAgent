from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import CSDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType

def test_csdma_init_and_patch(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    evaluator = CSDMAEvaluator(service_registry=service_registry, model_name="m", prompt_overrides={"csdma_system_prompt": "PROMPT"})
    assert evaluator.model_name == "m"
    assert evaluator.prompt_overrides["csdma_system_prompt"] == "PROMPT"

async def test_csdma_evaluate_thought(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=MagicMock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    evaluator = CSDMAEvaluator(service_registry=service_registry, model_name="m")
    mock_result = CSDMAResult(plausibility_score=0.8, flags=["f1"], reasoning="r")
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    dummy_client.client.chat.completions.create = AsyncMock(return_value=mock_result)
    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="t1",
        source_task_id="s1",
        thought_type=ThoughtType.STANDARD,
        content=ThoughtContent(text="test"),
    )
    result = await evaluator.evaluate_thought(item)
    assert isinstance(result, CSDMAResult)
    assert result.plausibility_score == 0.8
    assert result.flags == ["f1"]
    assert result.reasoning == "r"
