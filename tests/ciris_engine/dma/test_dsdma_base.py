import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.dma_results_v1 import DSDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry, Priority

class DummyDSDMA(BaseDSDMA):
    async def evaluate_thought(self, thought_item, current_context):
        return DSDMAResult(domain="d", alignment_score=1.0, recommended_action="a", flags=["f"], reasoning="r")

def test_dsdma_init(monkeypatch):
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr("instructor.patch", lambda c, mode: c)
    dsdma = DummyDSDMA(domain_name="d", service_registry=service_registry, model_name="m", domain_specific_knowledge={"rules_summary": "r"}, prompt_template="t")
    assert dsdma.domain_name == "d"
    assert dsdma.model_name == "m"
    assert dsdma.domain_specific_knowledge["rules_summary"] == "r"
    assert dsdma.prompt_template == "t"
