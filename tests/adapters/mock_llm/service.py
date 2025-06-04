from types import SimpleNamespace
from typing import Any, Optional

from ciris_engine.adapters.base import Service

from .responses import create_response


class MockLLMClient:
    """Lightweight stand-in for an OpenAI-compatible client."""

    def __init__(self) -> None:
        self.model_name = "mock-model"
        self.client = self
        self.instruct_client = self
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, *args, response_model=None, **kwargs) -> Any:  # noqa: D401
        # Extract messages for context analysis  
        messages = kwargs.get('messages', [])
        # Remove messages from kwargs to avoid duplicate parameter
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'messages'}
        return create_response(response_model, messages=messages, **filtered_kwargs)


class MockLLMService(Service):
    """Mock LLM service used for offline testing."""

    def __init__(self, *_, **__) -> None:
        super().__init__()
        self._client: Optional[MockLLMClient] = None

    async def start(self) -> None:
        await super().start()
        self._client = MockLLMClient()

    async def stop(self) -> None:
        self._client = None
        await super().stop()

    def get_client(self) -> MockLLMClient:
        if not self._client:
            raise RuntimeError("MockLLMService has not been started")
        return self._client

