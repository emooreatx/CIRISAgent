"""
Base processor abstract class defining the interface for all processor types.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states import AgentState
from ciris_engine.core.thought_processor import ThoughtProcessor
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """Abstract base class for all processor types."""
    
    def __init__(
        self,
        app_config: AppConfig,
        thought_processor: ThoughtProcessor,
        action_dispatcher: ActionDispatcher,
        services: Dict[str, Any]
    ):
        """Initialize base processor with common dependencies."""
        self.app_config = app_config
        self.thought_processor = thought_processor
        self.action_dispatcher = action_dispatcher
        self.services = services
        self.metrics: Dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "items_processed": 0,
            "errors": 0,
            "rounds_completed": 0
        }
    
    @abstractmethod
    def get_supported_states(self) -> List[AgentState]:
        """Return list of states this processor can handle."""
        pass
    
    @abstractmethod
    async def can_process(self, state: AgentState) -> bool:
        """Check if this processor can handle the current state."""
        pass
    
    @abstractmethod
    async def process(self, round_number: int) -> Dict[str, Any]:
        """
        Execute processing for one round.
        Returns metrics/results from the processing.
        """
        pass
    
    async def initialize(self) -> bool:
        """
        Initialize the processor.
        Override in subclasses for specific initialization.
        """
        self.metrics["start_time"] = datetime.now(timezone.utc).isoformat()
        return True
    
    async def cleanup(self) -> bool:
        """
        Clean up processor resources.
        Override in subclasses for specific cleanup.
        """
        self.metrics["end_time"] = datetime.now(timezone.utc).isoformat()
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get processor metrics."""
        return self.metrics.copy()
    
    def update_metrics(self, updates: Dict[str, Any]):
        """Update processor metrics."""
        self.metrics.update(updates)
    
    async def dispatch_action(
        self,
        result: Any,
        thought: Any,
        context: Dict[str, Any]
    ) -> bool:
        """
        Common action dispatch logic.
        Returns True if dispatch succeeded.
        """
        try:
            await self.action_dispatcher.dispatch(
                action_selection_result=result,
                thought=thought,
                dispatch_context=context
            )
            return True
        except Exception as e:
            logger.error(f"Error dispatching action: {e}", exc_info=True)
            self.metrics["errors"] += 1
            return False
    
    async def process_thought_item(
        self,
        item: ProcessingQueueItem,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Process a single thought item through the thought processor.
        Returns the processing result.
        """
        try:
            result = await self.thought_processor.process_thought(item, context)
            self.metrics["items_processed"] += 1
            return result
        except Exception as e:
            logger.error(f"Error processing thought {item.thought_id}: {e}", exc_info=True)
            self.metrics["errors"] += 1
            raise
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"