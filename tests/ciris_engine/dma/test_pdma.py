import pytest
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace
from typing import List, Dict, Any, Type, Tuple
from pydantic import BaseModel
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType, ResourceUsage
from ciris_engine.protocols.services import LLMService

class MockLLMService(LLMService):
    """Mock LLM service for testing."""
    
    def __init__(self):
        self.started = False
        self.stopped = False
        self.mock_result = None
        self.mock_resource_usage = None
    
    async def start(self) -> None:
        """Start the service."""
        self.started = True
    
    async def stop(self) -> None:
        """Stop the service."""
        self.stopped = True
    
    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Tuple[BaseModel, ResourceUsage]:
        """Mock implementation returning predefined result."""
        return self.mock_result, self.mock_resource_usage
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["call_llm_structured"]
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return ["test-model"]


@pytest.mark.asyncio
async def test_pdma_init_and_evaluate(monkeypatch):
    service_registry = ServiceRegistry()
    
    # Create a mock LLM service that implements the protocol
    mock_llm_service = MockLLMService()
    
    # Use a real EthicalDMAResult for the mock return value
    mock_result = EthicalDMAResult(
        alignment_check={"SPEAK": "ok"},
        decision="Allow",
        rationale="rationale"
    )
    
    # Mock resource usage
    mock_resource_usage = ResourceUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=None,
        cost_usd=0.001
    )
    
    # Set up the mock to return the structured response
    mock_llm_service.mock_result = mock_result
    mock_llm_service.mock_resource_usage = mock_resource_usage
    
    # Register the LLM service properly according to new service protocol
    service_registry.register_global("llm", mock_llm_service, priority=Priority.HIGH)
    
    evaluator = EthicalPDMAEvaluator(service_registry=service_registry, model_name="m")
    
    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="t1",
        source_task_id="s1",
        thought_type=ThoughtType.STANDARD,
        content=ThoughtContent(text="test"),
    )
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
    ctx = ThoughtContext(system_snapshot=SystemSnapshot(system_counts={}))
    result = await evaluator.evaluate(item, ctx)
    assert isinstance(result, EthicalDMAResult)
    assert result.alignment_check == {"SPEAK": "ok"}
    assert result.decision == "Allow"
    assert result.rationale == "rationale"
