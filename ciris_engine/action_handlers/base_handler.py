import logging
from typing import Any, Dict, Optional, Type, Callable
from abc import ABC, abstractmethod

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from ciris_engine.secrets.service import SecretsService
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
        secrets_service: Optional[SecretsService] = None,
        multi_service_sink: Optional[Any] = None,
        memory_service: Optional[Any] = None,
        audit_service: Optional[Any] = None,
    ) -> None:
        self.service_registry = service_registry
        self.io_adapter = io_adapter
        # Shutdown signal mechanism
        self.shutdown_callback = shutdown_callback
        self.secrets_service = secrets_service or None
        self.multi_service_sink = multi_service_sink
        self.memory_service = memory_service
        self.audit_service = audit_service
        self._shutdown_requested = False
    
    def request_graceful_shutdown(self, reason: str = "Handler requested shutdown") -> None:
        """Request a graceful shutdown of the agent runtime."""
        if self._shutdown_requested:
            logger.debug("Shutdown already requested, ignoring duplicate request")
            return
        
        self._shutdown_requested = True
        logger.critical(f"GRACEFUL SHUTDOWN REQUESTED: {reason}")
        
        request_global_shutdown(reason)
        
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
    
    async def get_service(self, handler: str, service_type: str, **kwargs: Any) -> Optional[Any]:
        """Get a service from the registry with automatic fallback to legacy services"""
        service = None
        
        # Try to get from service registry first with timeout to prevent hanging
        if self.service_registry:
            try:
                import asyncio
                service = await asyncio.wait_for(
                    self.service_registry.get_service(handler, service_type, **kwargs),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Service registry lookup timed out for {handler}.{service_type}")
                service = None
            except Exception as e:
                logger.warning(f"Service registry lookup failed for {handler}.{service_type}: {e}")
                service = None
        
        # Fallback to legacy services if available
        if not service and hasattr(self, service_type):
            service = getattr(self, service_type)
            
        return service


class BaseActionHandler(ABC):
    """Abstract base class for action handlers."""
    def __init__(self, dependencies: ActionHandlerDependencies) -> None:
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _audit_log(self, handler_action: Any, context: Any, outcome: Optional[str] = None) -> None:
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
    
    async def get_telemetry_service(self) -> Optional[Any]:
        """Get telemetry service if available"""
        return await self.dependencies.get_service(
            self.__class__.__name__,
            "telemetry"
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
            pass
        return channel_id

    async def _send_notification(self, channel_id: str, content: str) -> bool:
        """Send a notification using the best available service."""
        if not isinstance(content, str):
            self.logger.error(f"_send_notification: content must be a string, got {type(content)}")  # type: ignore[unreachable]
            raise TypeError("_send_notification: content must be a string, not a GraphNode or other type")
        if not channel_id or not content:
            self.logger.error(f"_send_notification failed: missing channel_id ({channel_id}) or content ({bool(content)})")
            return False

        self.logger.debug(f"_send_notification: attempting to send to channel_id={channel_id}, content_length={len(content)}")
        
        self.logger.debug(f"_send_notification: requesting communication service for handler '{self.__class__.__name__}'")
        
        comm_service = await self.get_communication_service()
        self.logger.debug(f"_send_notification: get_communication_service returned: {type(comm_service).__name__ if comm_service else None}")
        
        if comm_service:
            try:
                sanitized_channel_id = str(channel_id).lstrip('#')
                
                class_name = comm_service.__class__.__name__ if hasattr(comm_service, '__class__') else ""
                is_cli_service = 'CLI' in class_name
                is_api_service = 'API' in class_name and 'Communication' in class_name
                is_non_discord_service = is_cli_service or is_api_service
                
                if is_non_discord_service:
                    if sanitized_channel_id.isdigit() and len(sanitized_channel_id) > 10:
                        sanitized_channel_id = "cli"
                        self.logger.debug(f"_send_notification: converted Discord channel ID to 'cli' for non-Discord service")
                    elif sanitized_channel_id in ["default"]:
                        sanitized_channel_id = "cli"
                else:
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
            available_services = self.dependencies.service_registry.get_provider_info(
                handler=self.__class__.__name__,
                service_type="communication"
            )
            self.logger.error(f"_send_notification: Available services: {available_services}")

        self.logger.critical(
            f"CRITICAL COMMUNICATION FAILURE: Unable to send notification to channel {channel_id}. "
            f"No communication services available. This indicates a fundamental system failure."
        )
        
        self.dependencies.request_graceful_shutdown(
            f"Communication service failure - unable to send notifications (channel: {channel_id})"
        )
        
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

    async def _decapsulate_secrets_in_params(
        self, 
        result: ActionSelectionResult,
        action_type: str
    ) -> ActionSelectionResult:
        """
        Automatically decapsulate secrets in action parameters based on action type.
        
        Args:
            result: Original action selection result
            action_type: Type of action being performed
            
        Returns:
            ActionSelectionResult with secrets decapsulated if applicable
        """
        try:
            if not self.dependencies.secrets_service:
                return result
            
            decapsulated_params = await self.dependencies.secrets_service.decapsulate_secrets_in_parameters(
                result.action_parameters,
                action_type,
                {
                    "operation": "action_handler",
                    "handler": self.__class__.__name__,
                    "auto_decrypt": True
                }
            )
            
            if decapsulated_params != result.action_parameters:
                updated_result = ActionSelectionResult(
                    selected_action=result.selected_action,
                    action_parameters=decapsulated_params,
                    rationale=result.rationale,
                    confidence=result.confidence,
                    raw_llm_response=getattr(result, 'raw_llm_response', None),
                    resource_usage=getattr(result, 'resource_usage', None)
                )
                
                self.logger.info(f"Auto-decapsulated secrets in {action_type} action parameters")
                return updated_result
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error decapsulating secrets in action parameters: {e}")
            return result

    @abstractmethod
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,  # The original thought that led to this action
        dispatch_context: Dict[str, Any]  # Context from the dispatcher (e.g., channel_id, author_name)
    ) -> Optional[str]:  # Return follow-up thought ID if created
        """
        Handles the action.
        Implementations should:
        1. Perform the action.
        2. Update the original thought's status in persistence.
        3. Create necessary follow-up thoughts in persistence.
        
        Returns:
            Optional[str]: ID of follow-up thought if one was created
        """
