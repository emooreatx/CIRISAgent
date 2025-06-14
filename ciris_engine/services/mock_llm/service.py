from types import SimpleNamespace
from typing import Any, Optional, List, Dict, Type, Tuple
import instructor
import logging

from pydantic import BaseModel
from ciris_engine.adapters.base import Service
from ciris_engine.protocols.services import LLMService
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage

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


class MockPatchedClient:
    """A client that mimics instructor.patch() behavior for our mock."""
    
    def __init__(self, original_client, mode=None):
        self.original_client = original_client
        self.mode = mode
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._patched_create))
    
    async def _patched_create(self, *args, **kwargs):
        """Intercept instructor-patched calls and route to our mock."""
        logger.debug(f"Patched client _create called with kwargs: {list(kwargs.keys())}")
        
        # Extract the response_model from kwargs
        response_model = kwargs.get('response_model')
        logger.debug(f"Patched client response_model: {response_model}")
        
        # Route to the original mock client's _create method
        return await self.original_client._create(*args, **kwargs)


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
        
        # Hook into instructor.patch to return our mock patched client
        self._original_instructor_patch = instructor.patch
        # Store self reference for the static method
        MockLLMClient._instance = self
        instructor.patch = lambda *args, **kwargs: MockLLMClient._mock_instructor_patch(*args, **kwargs)

    @staticmethod
    def _mock_instructor_patch(*args, **kwargs):
        """Override instructor.patch to return our mock patched client."""
        # Extract client from args if provided
        client = args[0] if args else kwargs.get('client')
        mode = args[1] if len(args) > 1 else kwargs.get('mode')
        
        logger.debug(f"instructor.patch called on {type(client) if client else 'None'} with mode {mode}")
        
        # Get the instance reference
        instance = getattr(MockLLMClient, '_instance', None)
        if not instance:
            raise RuntimeError("MockLLMClient instance not available for patch")
        
        # If they're trying to patch our mock client, return our special patched version
        if client is instance or client is instance.client:
            return MockPatchedClient(instance, mode)
        
        # Otherwise, use the original instructor.patch (for real clients)
        if client:
            return instance._original_instructor_patch(client, mode=mode, **kwargs)
        else:
            # If no client provided, call original with args and kwargs
            return instance._original_instructor_patch(*args, **kwargs)

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
        self.model_name = "mock-model"

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

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Tuple[BaseModel, ResourceUsage]:
        """Mock implementation of structured LLM call."""
        if not self._client:
            raise RuntimeError("MockLLMService has not been started")
        
        logger.debug(f"Mock call_llm_structured with response_model: {response_model}")
        
        # Use the mock client's _create method
        response = await self._client._create(
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        # Mock resource usage
        usage = ResourceUsage(tokens=100)  # Mock token count
        
        return response, usage

