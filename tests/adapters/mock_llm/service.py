from types import SimpleNamespace
from typing import Any, Optional, List, Dict, Type, Tuple
import instructor
import logging

from ciris_engine.protocols.services import LLMService
from ciris_engine.schemas.runtime.resources import ResourceUsage
from pydantic import BaseModel

from .responses import create_response

logger = logging.getLogger(__name__)


class MockInstructorClient:
    """Mock instructor-patched client that properly handles response_model parameter."""
    
    def __init__(self, base_client) -> None:
        self.base_client = base_client
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
    
    async def _create(self, *args, response_model=None, **kwargs) -> Any:
        # This is the instructor-patched version that should always receive response_model
        if response_model is None:
            # This should NOT happen - instructor always passes response_model
            logger.error("MockInstructorClient received response_model=None - this indicates a bug!")
            raise ValueError("Instructor client should always receive response_model")
        
        # Forward to base client with response_model preserved
        return await self.base_client._create(*args, response_model=response_model, **kwargs)


class MockLLMClient:
    """Lightweight stand-in for an OpenAI-compatible client that supports instructor patching."""

    def __init__(self) -> None:
        self.model_name = "mock-model"
        self.client = self
        # Create a proper instructor client that enforces response_model
        self.instruct_client = MockInstructorClient(self)
        
        # Create the chat.completions interface that instructor expects
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        
        # Store original for debugging
        self._original_create = self._create

    async def _create(self, *args, response_model=None, **kwargs) -> Any:
        """
        Create method that instructor.patch() will call.
        Must return responses in OpenAI API format for instructor to parse correctly.
        """
        logger.debug(f"_create called with response_model: {response_model}")
        
        # Extract messages for context analysis  
        messages = kwargs.get('messages', [])
        
        # Remove messages from kwargs to avoid duplicate parameter error
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'messages'}
        
        # Call our response generator with messages as explicit parameter
        response = create_response(response_model, messages=messages, **filtered_kwargs)
        
        logger.debug(f"Generated response type: {type(response)}")
        return response
    
    def __getattr__(self, name):
        """Support dynamic attribute access for instructor compatibility."""
        if name in ['_acreate']:
            # instructor sometimes looks for _acreate - redirect to our _create
            return self._create
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class MockLLMService(LLMService):
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

    def _get_client(self) -> MockLLMClient:
        if not self._client:
            raise RuntimeError("MockLLMService has not been started")
        return self._client

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Tuple[BaseModel, ResourceUsage]:
        """
        Make a structured LLM call with Pydantic model response.
        
        Args:
            messages: Conversation messages
            response_model: Pydantic model class for response structure
            max_tokens: Maximum tokens in response
            temperature: Response randomness (0.0-1.0)
            **kwargs: Additional LLM parameters
            
        Returns:
            Tuple of (structured response, resource usage)
        """
        if not self._client:
            raise RuntimeError("MockLLMService has not been started")
        
        # Use the mock client to generate the response
        response = await self._client._create(
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        # Create mock resource usage
        resource_usage = ResourceUsage(
            tokens=sum(len(msg.get('content', '').split()) for msg in messages) + 50,  # prompt + completion
            estimated_cost=0.001,  # Mock cost
            energy_kwh=0.0001  # Mock energy usage
        )
        
        return response, resource_usage

