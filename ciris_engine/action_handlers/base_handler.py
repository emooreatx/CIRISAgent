import logging
from typing import Any, Dict, Optional, Type, Callable
from abc import ABC, abstractmethod
import asyncio

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

from ciris_engine import persistence
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from ciris_engine.utils.shutdown_manager import (
    request_global_shutdown, 
    request_shutdown_communication_failure,
    is_global_shutdown_requested
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ActionHandlerDependencies:
    """Services and context needed by action handlers."""
    def __init__(
        self,
        service_registry: Optional[ServiceRegistry] = None,
        io_adapter: Optional[Any] = None,
        # Shutdown signal mechanism
        shutdown_callback: Optional[Callable[[], None]] = None,
    ):
        self.service_registry = service_registry
        self.io_adapter = io_adapter
        # Shutdown signal mechanism
        self.shutdown_callback = shutdown_callback
        self._shutdown_requested = False
    
    def request_graceful_shutdown(self, reason: str = "Handler requested shutdown"):
        """Request a graceful shutdown of the agent runtime."""
        if self._shutdown_requested:
            logger.debug("Shutdown already requested, ignoring duplicate request")
            return
        
        self._shutdown_requested = True
        logger.critical(f"GRACEFUL SHUTDOWN REQUESTED: {reason}")
        
        # Use global shutdown manager as primary mechanism
        request_global_shutdown(reason)
        
        # Also execute local callback if available (for backwards compatibility)
        if self.shutdown_callback:
            try:
                self.shutdown_callback()
                logger.info("Local shutdown callback executed successfully")
            except Exception as e:
                logger.error(f"Error executing local shutdown callback: {e}")
        else:
            logger.debug("No local shutdown callback available - using global shutdown manager only")
    
    def is_shutdown_requested(self) -> bool:
        """Check if a shutdown has been requested."""
        # Check both local and global shutdown states
        return self._shutdown_requested or is_global_shutdown_requested()

    async def wait_registry_ready(
        self, timeout: float = 30.0, service_types: Optional[list[str]] = None
    ) -> bool:
        """Wait until the service registry is ready or timeout expires."""
        if not self.service_registry:
            logger.warning("No service registry configured; assuming ready")
            return True
        try:
            return await self.service_registry.wait_ready(timeout=timeout, service_types=service_types)
        except Exception as exc:
            logger.error(f"Error waiting for registry readiness: {exc}")
            return False
    
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

    async def _audit_log(self, handler_action, context, outcome: Optional[str] = None):
        audit_service = await self.get_audit_service()
        if audit_service:
            await audit_service.log_action(handler_action, context, outcome)

    async def get_communication_service(
        self, required_capabilities: Optional[list[str]] = None
    ) -> Optional[CommunicationService]:
        """Get best available communication service"""
        caps = ["send_message"]
        if required_capabilities:
            caps.extend(required_capabilities)
            
        self.logger.debug(f"get_communication_service: requesting for handler '{self.__class__.__name__}' with capabilities {caps}")
        
        service = await self.dependencies.get_service(
            self.__class__.__name__,
            "communication",
            required_capabilities=caps,
        )
        
        self.logger.debug(f"get_communication_service: service registry returned {type(service).__name__ if service else None}")
        return service
    
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



    async def get_tool_service(self) -> Optional[Any]:
        """Get best available tool service"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "tool",
            required_capabilities=["execute_tool"]
        )

    def get_multi_service_sink(self) -> Optional[Any]:
        """Get multi-service sink from dependencies."""
        return getattr(self.dependencies, 'multi_service_sink', None)

    async def _get_channel_id(self, thought: Thought, dispatch_context: Dict[str, Any]) -> Optional[str]:
        """Get channel ID from dispatch or thought context."""
        channel_id = dispatch_context.get("channel_id")
        if not channel_id and getattr(thought, "context", None):
            system_snapshot = getattr(thought.context, "system_snapshot", None) if thought.context else None
            channel_id = getattr(system_snapshot, "channel_id", None) if system_snapshot else None
        if not channel_id:
            # No fallback needed since observer functionality is at adapter level
            pass
        return channel_id

    async def _send_notification(self, channel_id: str, content: str) -> bool:
        """Send a notification using the best available service."""
        if not channel_id or not content:
            self.logger.error(f"_send_notification failed: missing channel_id ({channel_id}) or content ({bool(content)})")
            return False

        # Log the attempt for debugging
        self.logger.debug(f"_send_notification: attempting to send to channel_id={channel_id}, content_length={len(content)}")
        
        # Enhanced debugging for service registry lookup
        self.logger.debug(f"_send_notification: requesting communication service for handler '{self.__class__.__name__}'")
        
        comm_service = await self.get_communication_service()
        self.logger.debug(f"_send_notification: get_communication_service returned: {type(comm_service).__name__ if comm_service else None}")
        
        if comm_service:
            try:
                # Smart channel ID handling based on communication service type
                sanitized_channel_id = str(channel_id).lstrip('#')
                
                # Detect CLI mode and adjust channel IDs accordingly
                is_cli_service = hasattr(comm_service, '__class__') and 'CLI' in comm_service.__class__.__name__
                
                if is_cli_service:
                    # For CLI services, convert Discord channel IDs to CLI-appropriate values
                    if sanitized_channel_id.isdigit() and len(sanitized_channel_id) > 10:
                        # This looks like a Discord channel ID - convert to CLI
                        sanitized_channel_id = "cli"
                        self.logger.debug(f"_send_notification: converted Discord channel ID to 'cli' for CLI service")
                    elif sanitized_channel_id in ["default"]:
                        sanitized_channel_id = "cli"
                else:
                    # For Discord services, validate numeric channel IDs
                    if sanitized_channel_id in ["CLI", "default", "cli"]:
                        self.logger.error(f"Invalid channel_id '{sanitized_channel_id}' - cannot send to Discord with string literal")
                        return False
                    
                self.logger.debug(f"_send_notification: calling send_message on {type(comm_service).__name__} with channel_id={sanitized_channel_id}")
                await comm_service.send_message(sanitized_channel_id, content)
                self.logger.debug(f"_send_notification: successfully sent via communication service")
                return True
            except Exception as e:
                self.logger.error(f"Communication service failed to send message to channel {channel_id}: {e}")
        else:
            self.logger.error("No communication service available - this indicates a service registry lookup failure")

        self.logger.error(f"_send_notification: all notification methods failed for channel_id={channel_id}")
        self.logger.error(
            f"_send_notification: Available services debug - handler='{self.__class__.__name__}', service_type='communication'"
        )
        if self.dependencies.service_registry:
            available_services = await self.dependencies.service_registry.get_provider_info(
                handler=self.__class__.__name__,
                service_type="communication"
            )
            self.logger.error(f"_send_notification: Available services: {available_services}")

        # CRITICAL: If we cannot send notifications, the agent cannot communicate effectively
        # This is a fundamental failure that requires graceful shutdown
        self.logger.critical(
            f"CRITICAL COMMUNICATION FAILURE: Unable to send notification to channel {channel_id}. "
            f"No communication services available. This indicates a fundamental system failure."
        )
        
        # Use both local and global shutdown mechanisms for maximum reliability
        # Local shutdown callback for immediate runtime response
        self.dependencies.request_graceful_shutdown(
            f"Communication service failure - unable to send notifications (channel: {channel_id})"
        )
        
        # Global shutdown for broader coordination
        request_shutdown_communication_failure(
            f"Unable to send notifications to channel {channel_id}"
        )
        
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
