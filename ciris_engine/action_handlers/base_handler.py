import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.sinks import MultiServiceActionSink, MultiServiceDeferralSink
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.adapters.discord.discord_observer import DiscordObserver  # For active look
from ciris_engine import persistence
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService

logger = logging.getLogger(__name__)


class ActionHandlerDependencies:
    """Services and context needed by action handlers."""
    def __init__(
        self,
        service_registry: Optional[ServiceRegistry] = None,
        # Legacy services for backward compatibility
        action_sink: Optional[MultiServiceActionSink] = None,
        memory_service: Optional[LocalGraphMemoryService] = None,
        observer_service: Optional[DiscordObserver] = None,
        deferral_sink: Optional[MultiServiceDeferralSink] = None,
        io_adapter: Optional[Any] = None,  # General type, can be cast in handler
        audit_service: Optional[Any] = None,  # Add audit_service
        **legacy_services  # For additional backward compatibility
    ):
        self.service_registry = service_registry
        # Keep legacy services for backward compatibility
        self.action_sink = action_sink
        self.memory_service = memory_service
        self.observer_service = observer_service  # Still useful for its config like monitored_channel_id
        self.deferral_sink = deferral_sink
        self.io_adapter = io_adapter
        self.audit_service = audit_service
        # Store any additional legacy services
        for name, service in legacy_services.items():
            setattr(self, name, service)
    
    async def get_service(self, handler: str, service_type: str, **kwargs) -> Optional[Any]:
        """Get a service from the registry with automatic fallback to legacy services"""
        service = None
        
        # Try to get from service registry first
        if self.service_registry:
            service = await self.service_registry.get_service(handler, service_type, **kwargs)
        
        # Fallback to legacy services if available
        if not service and hasattr(self, service_type):
            service = getattr(self, service_type)
            
        return service


class BaseActionHandler(ABC):
    """Abstract base class for action handlers."""
    def __init__(self, dependencies: ActionHandlerDependencies):
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _audit_log(self, handler_action, context, outcome=None):
        if self.dependencies and getattr(self.dependencies, 'audit_service', None):
            await self.dependencies.audit_service.log_action(handler_action, context, outcome)

    async def get_communication_service(self) -> Optional[CommunicationService]:
        """Get best available communication service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "communication",
            required_capabilities=["send_message"]
        )
    
    async def get_wa_service(self) -> Optional[WiseAuthorityService]:
        """Get best available WA service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "wise_authority"
        )
    
    async def get_memory_service(self) -> Optional[MemoryService]:
        """Get best available memory service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "memory",
            required_capabilities=["memorize", "recall"]
        )
    
    async def get_audit_service(self) -> Optional[Any]:
        """Get best available audit service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "audit"
        )
    
    async def get_llm_service(self) -> Optional[Any]:
        """Get best available LLM service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "llm"
        )

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