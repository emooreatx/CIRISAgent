from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import CSDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType

def test_csdma_init_and_patch():
    service_registry = ServiceRegistry()
    # Mock LLM service with call_llm_structured method
    dummy_service = MagicMock()
    dummy_service.call_llm_structured = AsyncMock()
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    
    evaluator = CSDMAEvaluator(service_registry=service_registry, model_name="m", prompt_overrides={"csdma_system_prompt": "PROMPT"})
    assert evaluator.model_name == "m"
    assert evaluator.prompt_overrides["csdma_system_prompt"] == "PROMPT"

async def test_csdma_evaluate_thought():
    service_registry = ServiceRegistry()
    # Mock LLM service with call_llm_structured method
    dummy_service = AsyncMock()
    mock_result = CSDMAResult(plausibility_score=0.8, flags=["f1"], reasoning="r")
    from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
    dummy_service.call_llm_structured = AsyncMock(return_value=(mock_result, ResourceUsage(tokens=100)))
    dummy_service.is_healthy = AsyncMock(return_value=True)
    dummy_service.get_capabilities = AsyncMock(return_value=["call_llm_structured"])
    # Register for the specific handler class name
    service_registry.register("CSDMAEvaluator", "llm", dummy_service, priority=Priority.HIGH)
    
    evaluator = CSDMAEvaluator(service_registry=service_registry, model_name="m")
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
