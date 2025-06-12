from __future__ import annotations

import instructor
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Any, Dict, TypeVar, Generic, TYPE_CHECKING

from pydantic import BaseModel

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import LLMService
from ciris_engine.protocols.faculties import EpistemicFaculty

if TYPE_CHECKING:
    pass

# Type variables for backward compatibility
InputT = TypeVar('InputT')
DMAResultT = TypeVar('DMAResultT', bound=BaseModel)

class BaseDMA(ABC, Generic[InputT, DMAResultT]):
    """Concrete base class for Decision Making Algorithms.
    
    This class provides the implementation of the BaseDMAInterface
    with backward compatibility for existing DMAs.
    """

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        prompt_overrides: Optional[Dict[str, str]] = None,
        faculties: Optional[Dict[str, EpistemicFaculty]] = None,
        *,
        instructor_mode: instructor.Mode = instructor.Mode.JSON,
        **kwargs: Any
    ) -> None:
        self.service_registry = service_registry
        self.model_name = model_name
        self.max_retries = max_retries
        self.faculties = faculties or {}
        self.instructor_mode = instructor_mode
        
        # Store any additional kwargs for subclasses
        self.kwargs = kwargs
        
        # Load prompts
        self.prompts: Dict[str, str] = {}
        self._load_prompts(prompt_overrides)
        
    def _load_prompts(self, overrides: Optional[Dict[str, str]] = None) -> None:
        """Load prompts from YAML file or use defaults.
        
        Looks for prompts/<class_name>.yml file in the same directory as the DMA.
        Falls back to DEFAULT_PROMPT or DEFAULT_PROMPT_TEMPLATE if defined.
        """
        # Try to load from YAML file
        dma_file = Path(self.__class__.__module__.replace('.', '/'))
        prompt_file = dma_file.parent / "prompts" / f"{self.__class__.__name__.lower()}.yml"
        
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r') as f:
                    file_prompts = yaml.safe_load(f) or {}
                self.prompts = {**file_prompts, **(overrides or {})}
                return
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load prompts from {prompt_file}: {e}")
        
        # Fall back to class-defined defaults
        defaults = {}
        if hasattr(self, 'DEFAULT_PROMPT'):
            defaults = getattr(self, 'DEFAULT_PROMPT')
        elif hasattr(self, 'DEFAULT_PROMPT_TEMPLATE'):
            defaults = getattr(self, 'DEFAULT_PROMPT_TEMPLATE')
            
        self.prompts = {**defaults, **(overrides or {})}

    async def get_llm_service(self) -> Optional[LLMService]:
        """Return the LLM service for this DMA from the service registry."""
        service = await self.service_registry.get_service(
            handler=self.__class__.__name__,
            service_type="llm",
        )
        return service

    async def apply_faculties(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, BaseModel]:
        """Apply available epistemic faculties to content.
        
        Args:
            content: The content to analyze
            context: Optional context for analysis
            
        Returns:
            Dictionary mapping faculty name to evaluation result
        """
        results = {}
        
        if not self.faculties:
            return results
            
        for name, faculty in self.faculties.items():
            try:
                result = await faculty.evaluate(content, context)
                results[name] = result
            except Exception as e:
                # Log error but don't fail the entire evaluation
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Faculty {name} failed to evaluate: {e}")
                continue
                
        return results

    @abstractmethod
    async def evaluate(self, *args: Any, **kwargs: Any) -> BaseModel:
        """Execute DMA evaluation and return a pydantic model.
        
        Note: This maintains the old signature for backward compatibility.
        New DMAs should use the typed interface methods.
        """
        raise NotImplementedError