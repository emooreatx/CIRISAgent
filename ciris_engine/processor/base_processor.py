"""
Base processor abstract class defining the interface for all processor types.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime, timezone

from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states_v1 import AgentState

if TYPE_CHECKING:
    from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """Abstract base class for all processor types."""
    
    def __init__(
        self,
        app_config: AppConfig,
        thought_processor: ThoughtProcessor,
        action_dispatcher: "ActionDispatcher",
        services: Dict[str, Any]
    ) -> None:
        """Initialize base processor with common dependencies."""
        self.app_config = app_config
        self.thought_processor = thought_processor
        self.action_dispatcher = action_dispatcher
        self.services = services
        if services and "discord_service" in services:
            self.discord_service = services["discord_service"]
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
    
    @abstractmethod
    async def can_process(self, state: AgentState) -> bool:
        """Check if this processor can handle the current state."""
    
    @abstractmethod
    async def process(self, round_number: int) -> Dict[str, Any]:
        """
        Execute processing for one round.
        Returns metrics/results from the processing.
        """
    
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
    
    def update_metrics(self, updates: Dict[str, Any]) -> None:
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
        Implements DMA failure fallback: force PONDER or DEFER as appropriate.
        """
        try:
            result = await self.thought_processor.process_thought(item, context)
            self.metrics["items_processed"] += 1
            return result
        except Exception as e:
            logger.error(f"Error processing thought {item.thought_id}: {e}", exc_info=True)
            self.metrics["errors"] += 1
            if hasattr(e, "is_dma_failure") and getattr(e, "is_dma_failure", False):
                if hasattr(self, "force_ponder"):
                    logger.warning(f"DMA failure for {item.thought_id}, forcing PONDER fallback.")
                    return await self.force_ponder(item, context)
                elif hasattr(self, "force_defer"):
                    logger.warning(f"DMA failure for {item.thought_id}, forcing DEFER fallback.")
                    return await self.force_defer(item, context)
            raise

    async def force_ponder(self, item: ProcessingQueueItem, context: Optional[Dict[str, Any]] = None) -> None:
        """Force a PONDER action for the given thought item. Override in subclass for custom logic."""
        logger.info(f"Forcing PONDER for thought {item.thought_id}")
        # Implement actual logic in subclass

    async def force_defer(self, item: ProcessingQueueItem, context: Optional[Dict[str, Any]] = None) -> None:
        """Force a DEFER action for the given thought item. Override in subclass for custom logic."""
        logger.info(f"Forcing DEFER for thought {item.thought_id}")
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"