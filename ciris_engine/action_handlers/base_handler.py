import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.ports import ActionSink, DeferralSink
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.services.discord_observer import DiscordObserver  # For active look
from ciris_engine import persistence

logger = logging.getLogger(__name__)


class ActionHandlerDependencies:
    """Services and context needed by action handlers."""
    def __init__(
        self,
        action_sink: Optional[ActionSink] = None,
        memory_service: Optional[CIRISLocalGraph] = None,
        observer_service: Optional[DiscordObserver] = None,
        deferral_sink: Optional[DeferralSink] = None,
        # For Discord-specific active look, we might need the DiscordAdapter or its client
        # Let's pass the io_adapter (which could be DiscordAdapter)
        io_adapter: Optional[Any] = None,  # General type, can be cast in handler
    ):
        self.action_sink = action_sink
        self.memory_service = memory_service
        self.observer_service = observer_service  # Still useful for its config like monitored_channel_id
        self.deferral_sink = deferral_sink
        self.io_adapter = io_adapter


class BaseActionHandler(ABC):
    """Abstract base class for action handlers."""
    def __init__(self, dependencies: ActionHandlerDependencies):
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,  # The original thought that led to this action
        dispatch_context: Dict[str, Any]  # Context from the dispatcher (e.g., channel_id, author_name)
    ) -> None:  # Handlers will manage their own follow-ups and status updates
        """
        Handles the action.
        Implementations should:
        1. Perform the action.
        2. Update the original thought's status in persistence.
        3. Create necessary follow-up thoughts in persistence.
        """
        pass