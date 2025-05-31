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

    async def _create(self, *_, response_model=None, **__) -> Any:  # noqa: D401
        return create_response(response_model)


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

