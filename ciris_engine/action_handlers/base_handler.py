import logging
from typing import Any, Dict, Optional, Type
from abc import ABC, abstractmethod

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine import persistence
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ActionHandlerDependencies:
    """Services and context needed by action handlers."""
    def __init__(self, service_registry: Optional[ServiceRegistry] = None):
        self.service_registry = service_registry

    async def get_service(self, handler: str, service_type: str, **kwargs) -> Optional[Any]:
        """Get a service from the registry"""
        if self.service_registry:
            return await self.service_registry.get_service(handler, service_type, **kwargs)
        return None


class BaseActionHandler(ABC):
    """Abstract base class for action handlers."""
    def __init__(self, dependencies: ActionHandlerDependencies):
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _audit_log(self, handler_action, context, outcome=None):
        audit_service = await self.get_audit_service()
        if audit_service:
            await audit_service.log_action(handler_action, context, outcome)

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

    async def get_observer_service(self) -> Optional[Any]:
        """Get best available observer service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "observer",
            required_capabilities=["observe_messages"],
        )

    async def get_tool_service(self) -> Optional[Any]:
        """Get best available tool service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "tool",
            required_capabilities=["execute_tool"]
        )

    async def _get_channel_id(self, thought: Thought, dispatch_context: Dict[str, Any]) -> Optional[str]:
        """Get channel ID from dispatch or thought context."""
        channel_id = dispatch_context.get("channel_id")
        if not channel_id and getattr(thought, "context", None):
            channel_id = thought.context.get("channel_id")
        return channel_id

    async def _send_notification(self, channel_id: str, content: str) -> bool:
        """Send a notification using the best available service."""
        if not channel_id or not content:
            return False
        comm_service = await self.get_communication_service()
        if comm_service:
            try:
                await comm_service.send_message(str(channel_id).lstrip('#'), content)
                return True
            except Exception as e:
                self.logger.error(f"Communication service failed to send message: {e}")
        return False


    async def _validate_and_convert_params(self, params: Any, param_class: Type[BaseModel]) -> BaseModel:
        """Ensure params is an instance of ``param_class``."""
        if isinstance(params, param_class):
            return params
        if isinstance(params, dict):
            try:
                return param_class(**params)
            except ValidationError as e:
                raise e
        raise TypeError(f"Parameters must be {param_class.__name__} or dict")

    async def _handle_error(
        self,
        action: HandlerActionType,
        dispatch_context: Dict[str, Any],
        thought_id: str,
        error: Exception,
    ) -> None:
        """Centralized error handling with audit logging."""
        self.logger.exception(f"{action.value} handler error for {thought_id}: {error}")
        await self._audit_log(action, {**dispatch_context, "thought_id": thought_id}, outcome="failed")


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