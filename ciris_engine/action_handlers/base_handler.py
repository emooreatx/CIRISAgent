"""
Base action handler - clean architecture with BusManager
"""

import logging
from typing import Any, Dict, Optional, Type, Callable
from abc import ABC, abstractmethod

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, DispatchContext
from ciris_engine.schemas.audit_schemas_v1 import AuditEventType
from ciris_engine.utils.channel_utils import extract_channel_id

from ciris_engine.secrets.service import SecretsService
from ciris_engine.message_buses import BusManager
from ciris_engine.utils.shutdown_manager import (
    request_global_shutdown, 
    is_global_shutdown_requested
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ActionHandlerDependencies:
    """Dependencies for action handlers - clean and simple."""
    def __init__(
        self,
        bus_manager: BusManager,
        secrets_service: Optional[SecretsService] = None,
        shutdown_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.bus_manager = bus_manager
        self.secrets_service = secrets_service
        self.shutdown_callback = shutdown_callback
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
                logger.error(f"Error executing shutdown callback: {e}")


class BaseActionHandler(ABC):
    """Abstract base class for all action handlers."""
    
    def __init__(self, dependencies: ActionHandlerDependencies) -> None:
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Quick access to bus manager
        self.bus_manager = dependencies.bus_manager
    
    @abstractmethod
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """
        Handle the action and return follow-up thought ID if created.
        
        Args:
            result: The action selection result from DMA
            thought: The thought being processed
            dispatch_context: Context for the dispatch
            
        Returns:
            Optional thought ID of any follow-up thought created
        """
        pass
    
    async def _audit_log(
        self,
        action_type: HandlerActionType,
        dispatch_context: DispatchContext,
        outcome: str = "success"
    ) -> None:
        """Log an audit event through the audit bus."""
        try:
            # Convert to proper audit event type
            audit_event_type = AuditEventType(f"handler_action_{action_type.value}")
            
            await self.bus_manager.audit.log_event(
                event_type=str(audit_event_type),
                event_data={
                    "handler_name": self.__class__.__name__,
                    "thought_id": dispatch_context.thought_id,
                    "task_id": dispatch_context.task_id,
                    "action": action_type.value,
                    "outcome": outcome,
                    "wa_authorized": dispatch_context.wa_authorized
                },
                handler_name=self.__class__.__name__
            )
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
            # Audit failures should not break handler execution
    
    async def _handle_error(
        self,
        action_type: HandlerActionType,
        dispatch_context: DispatchContext,
        thought_id: str,
        error: Exception
    ) -> None:
        """Handle and log errors consistently."""
        self.logger.error(
            f"Error in {self.__class__.__name__} for {action_type.value} "
            f"on thought {thought_id}: {error}",
            exc_info=True
        )
        
        await self._audit_log(
            action_type,
            dispatch_context,
            outcome=f"error:{type(error).__name__}"
        )
    
    async def _validate_and_convert_params(
        self,
        params: Any,
        param_class: Type[BaseModel]
    ) -> BaseModel:
        """Validate and convert parameters to the expected type."""
        if isinstance(params, param_class):
            return params
            
        if isinstance(params, dict):
            try:
                return param_class.model_validate(params)
            except ValidationError as e:
                raise ValueError(f"Invalid parameters for {param_class.__name__}: {e}")
        
        # Try to convert BaseModel to dict first
        if hasattr(params, 'model_dump'):
            try:
                return param_class.model_validate(params.model_dump())
            except ValidationError as e:
                raise ValueError(f"Invalid parameters for {param_class.__name__}: {e}")
        
        raise TypeError(
            f"Expected {param_class.__name__} or dict, got {type(params).__name__}"
        )
    
    async def _decapsulate_secrets_in_params(
        self,
        result: ActionSelectionResult,
        action_name: str
    ) -> ActionSelectionResult:
        """Auto-decapsulate any secrets in action parameters."""
        if not self.dependencies.secrets_service:
            return result
            
        try:
            # Decapsulate secrets in action parameters
            if result.action_parameters:
                decapsulated_params = await self.dependencies.secrets_service.decapsulate_secrets_in_parameters(
                    parameters=result.action_parameters,
                    action_type=action_name,
                    context={"source": "action_handler", "handler": self.__class__.__name__}
                )
                # Create a new result with decapsulated parameters
                return ActionSelectionResult(
                    selected_action=result.selected_action,
                    action_parameters=decapsulated_params,
                    rationale=result.rationale,
                    confidence=result.confidence
                )
            return result
        except Exception as e:
            self.logger.error(f"Error decapsulating secrets: {e}")
            return result
    
    async def _get_channel_id(
        self,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """Extract channel ID from dispatch context or thought context."""
        # First try dispatch context
        channel_id = extract_channel_id(dispatch_context.channel_context)
        
        # Fallback to thought context if needed
        if not channel_id and hasattr(thought, "context") and thought.context:
            # Try initial_task_context first
            if hasattr(thought.context, "initial_task_context"):
                initial_task_context = thought.context.initial_task_context
                if initial_task_context and hasattr(initial_task_context, "channel_context"):
                    channel_id = extract_channel_id(initial_task_context.channel_context)
            
            # Then try system_snapshot as fallback
            if not channel_id and hasattr(thought.context, "system_snapshot"):
                system_snapshot = thought.context.system_snapshot
                if system_snapshot and hasattr(system_snapshot, "channel_context"):
                    channel_id = extract_channel_id(system_snapshot.channel_context)
        
        return channel_id
    
    async def _send_notification(
        self,
        channel_id: str,
        content: str
    ) -> bool:
        """Send a notification using the communication bus."""
        if not isinstance(content, str):
            self.logger.error(f"Content must be a string, got {type(content)}")  # type: ignore[unreachable]
            return False
        
        if not channel_id or not content:
            self.logger.error(f"Missing channel_id or content")
            return False
        
        try:
            # Use the communication bus
            return await self.bus_manager.communication.send_message(
                channel_id=channel_id,
                content=content,
                handler_name=self.__class__.__name__
            )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}", exc_info=True)
            return False