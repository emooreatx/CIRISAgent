import logging # Add logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import instructor # For instructor.Mode
from openai import AsyncOpenAI # For type hinting raw client

# Corrected imports based on project structure
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.agent_core_schemas import DSDMAResult
from ciris_engine.core.config_manager import get_config # To access global config

logger = logging.getLogger(__name__) # Add logger

class BaseDSDMA(ABC):
    """
    Abstract Base Class for Domain-Specific Decision-Making Algorithms.
    Handles instructor client patching based on global config.
    """
    DEFAULT_TEMPLATE: Optional[str] = "" # Subclasses should override this

    def __init__(self,
                 domain_name: str,
                 aclient: AsyncOpenAI, # Expect raw AsyncOpenAI client
                 model_name: Optional[str] = None, # Allow override, else use config
                 domain_specific_knowledge: Optional[Dict[str, Any]] = None,
                 prompt_template: Optional[str] = None):
        
        app_config = get_config()
        self.model_name = model_name or app_config.llm_services.openai.model_name
        
        try:
            configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
            self.instructor_mode = instructor.Mode[configured_mode_str]
        except KeyError:
            logger.warning(f"Invalid instructor_mode '{app_config.llm_services.openai.instructor_mode}' in config for DSDMA {domain_name}. Defaulting to JSON.")
            self.instructor_mode = instructor.Mode.JSON

        self.aclient: instructor.Instructor = instructor.patch(aclient, mode=self.instructor_mode)
        
        self.domain_name = domain_name
        self.domain_specific_knowledge = domain_specific_knowledge if domain_specific_knowledge else {}
        # Use provided template, fallback to class default, then empty string
        self.prompt_template = prompt_template if prompt_template is not None else (self.DEFAULT_TEMPLATE if self.DEFAULT_TEMPLATE is not None else "")
        
        logger.info(f"BaseDSDMA '{self.domain_name}' initialized with model: {self.model_name}, instructor_mode: {self.instructor_mode.name}")
        super().__init__()

    @abstractmethod
    async def evaluate_thought(self, thought_item: ProcessingQueueItem, current_context: Dict[str, Any]) -> DSDMAResult: # Changed to async def, Return DSDMAResult, Use ProcessingQueueItem
        """
        Evaluate a thought within the DSDMA's specific domain.
        """
        pass

    def __repr__(self) -> str:
        return f"<BaseDSDMA domain='{self.domain_name}'>"
