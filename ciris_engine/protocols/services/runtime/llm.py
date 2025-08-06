"""LLM Service Protocol."""

from abc import abstractmethod
from typing import List, Protocol, Tuple, Type, TypedDict

from pydantic import BaseModel

from ....schemas.runtime.resources import ResourceUsage
from ...runtime.base import ServiceProtocol


class MessageDict(TypedDict):
    """Typed dict for LLM messages."""

    role: str
    content: str


class LLMServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for LLM service.

    This protocol defines the contract that all LLM services must implement.
    The primary method is call_llm_structured which uses instructor for
    structured output parsing.
    """

    @abstractmethod
    async def call_llm_structured(
        self,
        messages: List[MessageDict],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Tuple[BaseModel, ResourceUsage]:
        """Make a structured LLM call.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            response_model: Pydantic model class for the expected response
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            Tuple of (parsed response model instance, resource usage)
        """
        ...
