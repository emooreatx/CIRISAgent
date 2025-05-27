import logging
import inspect
from typing import Dict, Any, Optional, Callable, Awaitable

from .foundational_schemas import HandlerActionType
from .agent_core_schemas import Thought, ThoughtStatus
from ..schemas.dma_results_v1 import ActionSelectionResult
from .action_handlers import BaseActionHandler
from . import persistence
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)

class ActionDispatcher:
    def __init__(
        self,
        handlers: Dict[HandlerActionType, BaseActionHandler],
        audit_service: Optional[Any] = None # Keep audit_service if used, though not in current logic
    ):
        """
        Initializes the ActionDispatcher with a map of action types to their handler instances.

        Args:
            handlers: A dictionary mapping HandlerActionType to an instance of a BaseActionHandler subclass.
            audit_service: Optional audit service.
        """
        self.handlers: Dict[HandlerActionType, BaseActionHandler] = handlers
        self.audit_service = audit_service
        self.action_filter: Optional[Callable[[ActionSelectionResult, Dict[str, Any]], Awaitable[bool] | bool]] = None

        # Log the registered handlers for clarity during startup
        for action_type, handler_instance in self.handlers.items():
            logger.info(f"ActionDispatcher: Registered handler for {action_type.value}: {handler_instance.__class__.__name__}")

    async def dispatch(
        self,
        action_selection_result: ActionSelectionResult,
        thought: Thought, # The original thought that led to this action
        dispatch_context: Dict[str, Any], # Context from the caller (e.g., channel_id, author_name, services)
        # Services are now expected to be part of ActionHandlerDependencies,
        # but dispatch_context can still carry event-specific data.
    ) -> None:
        """
        Dispatches the selected action to its registered handler.
        The handler is responsible for executing the action, updating thought status,
        and creating follow-up thoughts.
        """
        action_type = action_selection_result.selected_handler_action

        if self.action_filter:
            try:
                should_skip = self.action_filter(action_selection_result, dispatch_context)
                if inspect.iscoroutine(should_skip):
                    should_skip = await should_skip
                if should_skip:
                    logger.info(
                        f"ActionDispatcher: action {action_type.value} for thought {thought.thought_id} skipped by filter"
                    )
                    return
            except Exception as filter_ex:
                logger.error(f"Action filter error for action {action_type.value}: {filter_ex}")

        handler_instance = self.handlers.get(action_type)

        if not handler_instance:
            logger.error(f"No handler registered for action type: {action_type.value}. Thought ID: {thought.thought_id}")
            # Fallback: Mark thought as FAILED
            try:
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    new_status=ThoughtStatus.FAILED,
                    final_action_result={
                        "error": f"No handler for action {action_type.value}",
                        "original_result": action_selection_result.model_dump()
                    }
                )
                # Consider creating a follow-up error thought here if handlers normally do
            except Exception as e_persist:
                logger.error(f"Failed to update thought {thought.thought_id} to FAILED after no handler found: {e_persist}")
            return

        logger.info(f"Dispatching action {action_type.value} for thought {thought.thought_id} to handler {handler_instance.__class__.__name__}")
        
        try:
            # The handler's `handle` method will take care of everything.
            # It has access to dependencies (like action_sink, memory_service) via its constructor.
            await handler_instance.handle(action_selection_result, thought, dispatch_context)
        except Exception as e:
            logger.exception(
                f"Error executing handler {handler_instance.__class__.__name__} for action {action_type.value} on thought {thought.thought_id}: {e}"
            )
            try:
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    new_status=ThoughtStatus.FAILED,
                    final_action_result={
                        "error": f"Handler {handler_instance.__class__.__name__} failed: {str(e)}",
                        "original_result": action_selection_result.model_dump(),
                    },
                )
            except Exception as e_persist:
                logger.error(
                    f"Failed to update thought {thought.thought_id} to FAILED after handler exception: {e_persist}"
                )

            if isinstance(e, FollowUpCreationError):
                raise

    # If service_handlers are still needed for very specific, non-core actions,
    # that logic could be re-added, but the primary path is via self.handlers.
    # For this refactor, we assume all actions previously in _discord_handler and _memory_handler
    # are now covered by the new centralized handlers.
