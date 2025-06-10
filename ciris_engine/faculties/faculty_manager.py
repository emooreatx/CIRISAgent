import asyncio
import logging
from typing import Dict, Any, Optional, List

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import LLMService
from ciris_engine.protocols.faculties import EpistemicFaculty
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult, FacultyResult
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from . import epistemic as epi_helpers

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "gpt-4o"

class EntropyFaculty(EpistemicFaculty):
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

class CoherenceFaculty(EpistemicFaculty):
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

class OptimizationVetoFaculty(EpistemicFaculty):
    """Evaluate optimization veto for actions."""

    def __init__(self, service_registry: ServiceRegistry, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.service_registry = service_registry
        self.model_name = model_name

    async def _get_llm(self) -> Optional[LLMService]:
        return await self.service_registry.get_service(self.__class__.__name__, "llm")

    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> OptimizationVetoResult:
        """Evaluate action for optimization veto.
        
        Args:
            content: Action description to evaluate
            context: Additional context (not used currently)
            
        Returns:
            OptimizationVetoResult: Veto evaluation result
        """
        llm = await self._get_llm()
        if not llm:
            logger.error("OptimizationVetoFaculty: No LLM service available")
            return OptimizationVetoResult(
                decision="proceed",
                justification="LLM service unavailable",
                entropy_reduction_ratio=0.1,
                affected_values=[],
                confidence=0.0
            )
        try:
            messages = epi_helpers._create_optimization_veto_messages(content)
            data = await llm.generate_structured_response(
                messages,
                OptimizationVetoResult.model_json_schema(),
                model=self.model_name,
            )
            return OptimizationVetoResult(**data)
        except Exception as e:
            logger.error(f"OptimizationVetoFaculty evaluation failed: {e}", exc_info=True)
            return OptimizationVetoResult(
                decision="proceed",
                justification=f"Evaluation error: {str(e)}",
                entropy_reduction_ratio=0.1,
                affected_values=[],
                confidence=0.0
            )

class EpistemicHumilityFaculty(EpistemicFaculty):
    """Evaluate epistemic humility for actions."""

    def __init__(self, service_registry: ServiceRegistry, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.service_registry = service_registry
        self.model_name = model_name

    async def _get_llm(self) -> Optional[LLMService]:
        return await self.service_registry.get_service(self.__class__.__name__, "llm")

    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> EpistemicHumilityResult:
        """Evaluate action for epistemic humility.
        
        Args:
            content: Action description to evaluate
            context: Additional context (not used currently)
            
        Returns:
            EpistemicHumilityResult: Humility evaluation result
        """
        llm = await self._get_llm()
        if not llm:
            logger.error("EpistemicHumilityFaculty: No LLM service available")
            return EpistemicHumilityResult(
                epistemic_certainty=0.0,
                identified_uncertainties=["LLM service unavailable"],
                reflective_justification="LLM service unavailable",
                recommended_action="proceed"
            )
        try:
            messages = epi_helpers._create_epistemic_humility_messages(content)
            data = await llm.generate_structured_response(
                messages,
                EpistemicHumilityResult.model_json_schema(),
                model=self.model_name,
            )
            result = EpistemicHumilityResult(**data)
            
            # Handle string to float conversion for epistemic_certainty if needed
            if isinstance(result.epistemic_certainty, str):
                mapping = {"low": 0.0, "moderate": 0.5, "high": 1.0}
                val = mapping.get(result.epistemic_certainty.lower(), 0.0)
                result.epistemic_certainty = val
                
            return result
        except Exception as e:
            logger.error(f"EpistemicHumilityFaculty evaluation failed: {e}", exc_info=True)
            return EpistemicHumilityResult(
                epistemic_certainty=0.0,
                identified_uncertainties=[f"Evaluation error: {str(e)}"],
                reflective_justification=f"Evaluation error: {str(e)}",
                recommended_action="proceed"
            )

class FacultyManager:
    """Manages all epistemic faculties."""

    def __init__(self, service_registry: ServiceRegistry) -> None:
        self.faculties: Dict[str, EpistemicFaculty] = {}
        self.service_registry = service_registry

    def register_faculty(self, name: str, faculty: EpistemicFaculty) -> None:
        """Register an epistemic faculty.
        
        Args:
            name: Unique name for the faculty
            faculty: Faculty instance implementing EpistemicFaculty protocol
        """
        if not isinstance(faculty, EpistemicFaculty):
            raise TypeError(f"Faculty must implement EpistemicFaculty protocol, got {type(faculty)}")
        self.faculties[name] = faculty

    async def run_all_faculties(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run all registered faculties on the given content.
        
        Args:
            content: Content to evaluate
            context: Optional context for evaluation
            
        Returns:
            Dict mapping faculty names to their evaluation results
        """
        tasks = {
            name: asyncio.create_task(fac.evaluate(content, context)) 
            for name, fac in self.faculties.items()
        }
        results: Dict[str, Any] = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Faculty '{name}' failed: {e}", exc_info=True)
                # Store error information in results
                results[name] = {"error": str(e)}
        return results
    
    def get_available_faculties(self) -> List[str]:
        """Get list of available faculty names."""
        return list(self.faculties.keys())
    
    def create_default_faculties(self) -> None:
        """Create and register default epistemic faculties."""
        self.register_faculty("entropy", EntropyFaculty(self.service_registry))
        self.register_faculty("coherence", CoherenceFaculty(self.service_registry))
        self.register_faculty("optimization_veto", OptimizationVetoFaculty(self.service_registry))
        self.register_faculty("epistemic_humility", EpistemicHumilityFaculty(self.service_registry))
        logger.info(f"Registered {len(self.faculties)} default epistemic faculties")
