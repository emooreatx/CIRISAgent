import logging
import asyncio
from typing import Dict, Any, Callable, Coroutine, TYPE_CHECKING, Optional

from ciris_engine.utils.constants import NEED_MEMORY_METATHOUGHT

# Conditional import for type hinting
if TYPE_CHECKING:
    from .agent_core_schemas import ActionSelectionPDMAResult, HandlerActionType
    from ciris_engine.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Define the expected signature for a service handler callback
# It receives the result and the original context dict
ServiceHandlerCallable = Callable[['ActionSelectionPDMAResult', Dict[str, Any]], Coroutine[Any, Any, None]]

class ActionDispatcher:
    """
    Dispatches completed ActionSelectionPDMAResults to registered service handlers
    based on the action type and originating context.
    """
    def __init__(self, audit_service: Optional['AuditService'] = None):
        """Initialize the dispatcher with an optional :class:`AuditService`."""
        # Import locally to avoid circular imports at module load time
        from ciris_engine.services.audit_service import AuditService

        self.audit_service = audit_service or AuditService()
        # Stores handlers keyed by the service name (e.g., "discord", "slack", "memory")
        self.service_handlers: Dict[str, ServiceHandlerCallable] = {}
        self.action_filter: Optional[Callable[['ActionSelectionPDMAResult', Dict[str, Any]], bool]] = None
        logger.info("ActionDispatcher initialized.")

    async def _enqueue_memory_metathought(self, context: Dict[str, Any]):
        """Create a MEMORY meta-thought for later processing."""
        from .agent_core_schemas import Thought, ThoughtStatus
        from . import persistence
        import uuid
        from datetime import datetime, timezone

        user_nick = context.get("author_name")
        if not user_nick:
            logger.warning("Skipping memory meta-thought due to missing user name")
            context[NEED_MEMORY_METATHOUGHT] = False
            return

        original_context_for_meta = {
            "origin_service": context.get("origin_service"),
            "message_id": context.get("message_id"),
            "channel_id": context.get("channel_id"),
            "author_id": context.get("author_id"),
            "author_name": context.get("author_name"),
        }

        meta_thought = Thought(
            thought_id=f"mem_{uuid.uuid4().hex[:8]}",
            source_task_id=context.get("source_task_id", "unknown"),
            thought_type="memory_meta",
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            round_created=context.get("round", 0),
            content="Auto memory update",
            processing_context={
                "user_nick": user_nick,
                "channel": context.get("channel_id"),
                "metadata": {},
                "initial_context": original_context_for_meta,
            },
            priority=0,
        )
        await asyncio.to_thread(persistence.add_thought, meta_thought)
        context[NEED_MEMORY_METATHOUGHT] = False

    def register_service_handler(self, service_name: str, handler_callback: ServiceHandlerCallable):
        """Registers a handler coroutine for a specific service."""
        if service_name in self.service_handlers:
            logger.warning(
                f"Handler for service '{service_name}' already registered. Overwriting."
            )

        async def wrapped_handler(result: 'ActionSelectionPDMAResult', ctx: Dict[str, Any]):
            await handler_callback(result, ctx)
            if self.audit_service:
                await self.audit_service.log_action(result.selected_handler_action, ctx)

        self.service_handlers[service_name] = wrapped_handler
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

        if self.action_filter and not await self.action_filter(result, original_context):
            logger.info("Action filtered and not dispatched")
            return

        logger.info(f"Dispatching action '{action_type.value}' originating from service '{origin_service}'.")

        # --- Route based on Action Type ---

        # 1. External Actions (routed to originating service)
        # These actions typically require interaction with the external platform where the request originated.
        if action_type in [
            HandlerActionType.SPEAK,
            HandlerActionType.ACT,
            HandlerActionType.DEFER,
            HandlerActionType.DEFER_TO_WA,
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

            if action_type in [HandlerActionType.SPEAK, HandlerActionType.ACT, HandlerActionType.DEFER, HandlerActionType.DEFER_TO_WA]:
                original_context[NEED_MEMORY_METATHOUGHT] = True
                await self._enqueue_memory_metathought(original_context)

        # 2. Memory Actions (routed to a dedicated 'memory' service/handler, if registered)
        elif action_type in [
            HandlerActionType.MEMORIZE,
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

        # Handle any other unexpected action types
        else:
            logger.error(f"Unhandled action type received by ActionDispatcher: {action_type.value}")
