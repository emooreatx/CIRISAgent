from __future__ import annotations

import instructor
from abc import ABC, abstractmethod
from typing import Optional, Any

from pydantic import BaseModel

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import LLMService


class BaseDMA(ABC):
    """Abstract base class for Decision Making Algorithms."""

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        *,
        instructor_mode: instructor.Mode = instructor.Mode.JSON,
    ) -> None:
        self.service_registry = service_registry
        self.model_name = model_name
        self.max_retries = max_retries
        self.instructor_mode = instructor_mode

    async def get_llm_service(self) -> Optional[LLMService]:
        """Return the LLM service for this DMA from the service registry."""
        service = await self.service_registry.get_service(
            handler=self.__class__.__name__,
            service_type="llm",
        )
        return service

    @abstractmethod
    async def evaluate(self, *args: Any, **kwargs: Any) -> BaseModel:
        """Execute DMA evaluation and return a pydantic model."""
        raise NotImplementedError
