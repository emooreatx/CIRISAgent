import logging
import asyncio
from typing import Dict, Any, Callable, Coroutine, TYPE_CHECKING

# Conditional import for type hinting
if TYPE_CHECKING:
    from .agent_core_schemas import ActionSelectionPDMAResult, HandlerActionType

logger = logging.getLogger(__name__)

# Define the expected signature for a service handler callback
# It receives the result and the original context dict
ServiceHandlerCallable = Callable[['ActionSelectionPDMAResult', Dict[str, Any]], Coroutine[Any, Any, None]]

class ActionDispatcher:
    """
    Dispatches completed ActionSelectionPDMAResults to registered service handlers
    based on the action type and originating context.
    """
    def __init__(self):
        # Stores handlers keyed by the service name (e.g., "discord", "slack", "memory")
        self.service_handlers: Dict[str, ServiceHandlerCallable] = {}
        logger.info("ActionDispatcher initialized.")

    def register_service_handler(self, service_name: str, handler_callback: ServiceHandlerCallable):
        """Registers a handler coroutine for a specific service."""
        if service_name in self.service_handlers:
            logger.warning(f"Handler for service '{service_name}' already registered. Overwriting.")
        self.service_handlers[service_name] = handler_callback
        logger.info(f"Registered handler for service: {service_name}")

    async def dispatch(self, result: 'ActionSelectionPDMAResult', original_context: Dict[str, Any]):
        """
        Dispatches the action result to the appropriate handler based on context and action type.
        """
        # Import locally to avoid potential circular dependency issues at module level
        from .agent_core_schemas import HandlerActionType

        action_type = result.selected_handler_action
        # Determine the originating service from the context, default to 'unknown'
        origin_service = original_context.get("origin_service", "unknown")

        logger.info(f"Dispatching action '{action_type.value}' originating from service '{origin_service}'.")

        # --- Route based on Action Type ---

        # 1. External Actions (routed to originating service)
        # These actions typically require interaction with the external platform where the request originated.
        if action_type in [
            HandlerActionType.SPEAK,
            HandlerActionType.TOOL, # Corrected: USE_TOOL was not defined, TOOL is.
            HandlerActionType.DEFER, # Corrected: DEFER_TO_WA was not defined, DEFER is.
            HandlerActionType.REJECT # Corrected: REJECT_THOUGHT was not defined, REJECT is.
        ]:
            handler = self.service_handlers.get(origin_service)
            if handler:
                try:
                    logger.debug(f"Invoking handler for service '{origin_service}' for action '{action_type.value}'.")
                    await handler(result, original_context)
                    logger.debug(f"Handler for service '{origin_service}' completed action '{action_type.value}'.")
                except Exception as e:
                    logger.exception(f"Error executing handler for service '{origin_service}' action '{action_type.value}': {e}")
                    # Consider adding error handling state update in persistence here
            else:
                logger.error(f"No handler registered for origin service '{origin_service}' to handle action '{action_type.value}'. Action not executed.")

        # 2. Memory Actions (routed to a dedicated 'memory' service/handler, if registered)
        elif action_type in [
            HandlerActionType.LEARN,
            HandlerActionType.REMEMBER,
            HandlerActionType.FORGET
        ]:
            memory_handler = self.service_handlers.get("memory")
            if memory_handler:
                try:
                    logger.debug(f"Invoking memory handler for action '{action_type.value}'.")
                    await memory_handler(result, original_context) # Pass context in case needed
                    logger.debug(f"Memory handler completed action '{action_type.value}'.")
                except Exception as e:
                    logger.exception(f"Error executing memory handler for action '{action_type.value}': {e}")
            else:
                logger.warning(f"Received memory action '{action_type.value}' but no 'memory' handler registered. Action may not be fully processed.")
                # Fallback: Direct persistence calls could be added here if necessary

        # 3. Internal/Control Flow Actions (handled upstream or logged here)
        elif action_type == HandlerActionType.PONDER:
            # PONDER results in WorkflowCoordinator returning None, so this shouldn't be hit in normal flow.
            logger.warning(f"ActionDispatcher received PONDER action result. This might indicate an issue upstream (e.g., failed re-queue). Logging only.")

        elif action_type == HandlerActionType.OBSERVE:
            # Observation initiation might be handled internally or by a dedicated service.
            observer_handler = self.service_handlers.get("observer")
            if observer_handler:
                try:
                    logger.debug(f"Invoking observer handler for action '{action_type.value}'.")
                    await observer_handler(result, original_context)
                    logger.debug(f"Observer handler completed action '{action_type.value}'.")
                except Exception as e:
                    logger.exception(f"Error executing observer handler for action '{action_type.value}': {e}")
            else:
                logger.info(f"Received OBSERVE action. No specific 'observer' handler registered.")

        # Handle any other unexpected action types
        else:
            logger.error(f"Unhandled action type received by ActionDispatcher: {action_type.value}")
