import asyncio
import logging
from typing import Dict, Any, Optional

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import LLMService
from ciris_engine.protocols.faculties import EpistemicFaculty
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult, FacultyResult
from . import epistemic as epi_helpers

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "gpt-4o"

class EntropyFaculty:
    """Measure entropy/chaos in content."""

    def __init__(self, service_registry: ServiceRegistry, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.service_registry = service_registry
        self.model_name = model_name

    async def _get_llm(self) -> Optional[LLMService]:
        return await self.service_registry.get_service(self.__class__.__name__, "llm")

    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> EntropyResult:
        llm = await self._get_llm()
        if not llm:
            logger.error("EntropyFaculty: No LLM service available")
            return EntropyResult(entropy=0.0)
        try:
            messages = epi_helpers._create_entropy_messages_for_instructor(content)
            data = await llm.generate_structured_response(
                messages,
                EntropyResult.model_json_schema(),
                model=self.model_name,
            )
            return EntropyResult(**data)
        except Exception as e:
            logger.error(f"EntropyFaculty evaluation failed: {e}", exc_info=True)
            return EntropyResult(entropy=0.0)

class CoherenceFaculty:
    """Assess coherence/alignment in content."""

    def __init__(self, service_registry: ServiceRegistry, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.service_registry = service_registry
        self.model_name = model_name

    async def _get_llm(self) -> Optional[LLMService]:
        return await self.service_registry.get_service(self.__class__.__name__, "llm")

    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> CoherenceResult:
        llm = await self._get_llm()
        if not llm:
            logger.error("CoherenceFaculty: No LLM service available")
            return CoherenceResult(coherence=0.0)
        try:
            messages = epi_helpers._create_coherence_messages_for_instructor(content)
            data = await llm.generate_structured_response(
                messages,
                CoherenceResult.model_json_schema(),
                model=self.model_name,
            )
            return CoherenceResult(**data)
        except Exception as e:
            logger.error(f"CoherenceFaculty evaluation failed: {e}", exc_info=True)
            return CoherenceResult(coherence=0.0)

class FacultyManager:
    """Manages all epistemic faculties."""

    def __init__(self, service_registry: ServiceRegistry) -> None:
        self.faculties: Dict[str, EpistemicFaculty] = {}
        self.service_registry = service_registry

    def register_faculty(self, name: str, faculty: EpistemicFaculty) -> None:
        self.faculties[name] = faculty

    async def run_all_faculties(self, content: str) -> Dict[str, FacultyResult]:
        tasks = {name: asyncio.create_task(fac.evaluate(content)) for name, fac in self.faculties.items()}
        results: Dict[str, FacultyResult] = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Faculty '{name}' failed: {e}", exc_info=True)
        return results
