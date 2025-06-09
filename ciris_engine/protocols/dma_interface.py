from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, TypeVar, Generic, Union
from pathlib import Path
from pydantic import BaseModel

from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.schemas.dma_results_v1 import (
    ActionSelectionResult,
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.faculties import EpistemicFaculty

# Type variables for DMA result types
DMAResultT = TypeVar('DMAResultT', bound=BaseModel, covariant=True)
InputT = TypeVar('InputT', contravariant=True)

class DMAProtocol(Protocol, Generic[InputT, DMAResultT]):
    """Generic protocol for all Decision Making Algorithms."""
    
    async def evaluate(self, input_data: InputT, **kwargs: Any) -> DMAResultT:
        """Evaluate input and return structured result."""
        ...

class BaseDMAInterface(ABC, Generic[InputT, DMAResultT]):
    """Abstract base class for all Decision Making Algorithms.
    
    This provides the foundation for creating modular, type-safe DMAs with:
    - Standardized initialization patterns
    - Optional prompt separation from logic
    - Service registry integration
    - Faculty integration support
    """
    
    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        prompt_overrides: Optional[Dict[str, str]] = None,
        faculties: Optional[Dict[str, EpistemicFaculty]] = None,
        **kwargs: Any
    ) -> None:
        """Initialize DMA with common dependencies.
        
        Args:
            service_registry: Registry for accessing services (LLM, etc.)
            model_name: LLM model to use
            max_retries: Maximum retry attempts for LLM calls
            prompt_overrides: Optional prompt customizations
            faculties: Optional epistemic faculties for enhanced evaluation
            **kwargs: Additional DMA-specific configuration
        """
        self.service_registry = service_registry
        self.model_name = model_name
        self.max_retries = max_retries
        self.faculties = faculties or {}
        self._load_prompts(prompt_overrides)
    
    def _load_prompts(self, overrides: Optional[Dict[str, str]] = None) -> None:
        """Load prompts from YAML file or use defaults.
        
        DMAs should implement this to load from their prompts/<dma_name>.yml file.
        """
        self.prompts: Dict[str, str] = overrides or {}
    
    async def get_llm_service(self) -> Any:
        """Get LLM service from registry."""
        return await self.service_registry.get_service(
            handler=self.__class__.__name__,
            service_type="llm",
        )
    
    async def apply_faculties(
        self, 
        content: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, BaseModel]:
        """Apply available epistemic faculties to content.
        
        Args:
            content: Content to evaluate
            context: Optional context for evaluation
            
        Returns:
            Dictionary mapping faculty name to evaluation result
        """
        results = {}
        for name, faculty in self.faculties.items():
            try:
                result = await faculty.evaluate(content, context)
                results[name] = result
            except Exception as e:
                # Log error but don't fail the entire evaluation
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Faculty {name} evaluation failed: {e}")
        return results
    
    @abstractmethod
    async def evaluate(self, input_data: InputT, **kwargs: Any) -> DMAResultT:
        """Evaluate input and return structured result.
        
        Args:
            input_data: The input to evaluate (varies by DMA type)
            **kwargs: Additional evaluation parameters
            
        Returns:
            Structured result specific to this DMA type
        """
        raise NotImplementedError

# Specific DMA interfaces for type safety
class EthicalDMAInterface(BaseDMAInterface[ProcessingQueueItem, EthicalDMAResult]):
    """Interface for Ethical/Principled Decision Making Algorithms."""
    
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem, 
        context: Optional[ThoughtContext] = None,
        **kwargs: Any
    ) -> EthicalDMAResult:
        """Evaluate thought against ethical principles."""
        raise NotImplementedError

class CSDMAInterface(BaseDMAInterface[ProcessingQueueItem, CSDMAResult]):
    """Interface for Common Sense Decision Making Algorithms."""
    
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem,
        **kwargs: Any
    ) -> CSDMAResult:
        """Evaluate thought for common sense alignment."""
        raise NotImplementedError

class DSDMAInterface(BaseDMAInterface[ProcessingQueueItem, DSDMAResult]):
    """Interface for Domain-Specific Decision Making Algorithms."""
    
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem, 
        current_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> DSDMAResult:
        """Evaluate thought within domain-specific context."""
        raise NotImplementedError

class ActionSelectionDMAInterface(BaseDMAInterface[Dict[str, Any], ActionSelectionResult]):
    """Interface for Action Selection Decision Making Algorithms.
    
    This is the most complex DMA that can optionally use faculties for
    recursive evaluation on guardrail failures.
    """
    
    async def evaluate(
        self, 
        triaged_inputs: Dict[str, Any],
        enable_recursive_evaluation: bool = False,
        **kwargs: Any
    ) -> ActionSelectionResult:
        """Select optimal action based on previous DMA results.
        
        Args:
            triaged_inputs: Combined inputs from previous DMAs
            enable_recursive_evaluation: If True, use faculties for recursive
                evaluation on guardrail failures instead of PONDER
            **kwargs: Additional evaluation parameters
            
        Returns:
            Selected action with parameters and rationale
        """
        raise NotImplementedError
    
    async def recursive_evaluate_with_faculties(
        self,
        triaged_inputs: Dict[str, Any],
        guardrail_failure_context: Dict[str, Any]
    ) -> ActionSelectionResult:
        """Perform recursive evaluation using epistemic faculties.
        
        Called when guardrails fail and recursive evaluation is enabled.
        Uses faculties to provide additional insight before action selection.
        """
        # Apply faculties to the problematic content
        original_thought = triaged_inputs.get("original_thought")
        if original_thought:
            faculty_results = await self.apply_faculties(
                str(original_thought.content),
                guardrail_failure_context
            )
            # Add faculty insights to triaged inputs
            triaged_inputs["faculty_evaluations"] = faculty_results
        
        # Perform enhanced evaluation with faculty insights
        return await self.evaluate(triaged_inputs, enable_recursive_evaluation=False)
