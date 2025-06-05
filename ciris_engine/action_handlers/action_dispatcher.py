import logging
import inspect
from typing import Dict, Any, Optional, Callable, Awaitable

from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from . import BaseActionHandler
from .. import persistence
from ciris_engine.action_handlers.exceptions import FollowUpCreationError


logger = logging.getLogger(__name__)

class ActionDispatcher:
    def __init__(
        self,
        handlers: Dict[HandlerActionType, BaseActionHandler]
    ) -> None:
        """
        Initializes the ActionDispatcher with a map of action types to their handler instances.

        Args:
            handlers: A dictionary mapping HandlerActionType to an instance of a BaseActionHandler subclass.
        """
        self.handlers: Dict[HandlerActionType, BaseActionHandler] = handlers
        self.action_filter: Optional[Callable[[ActionSelectionResult, Dict[str, Any]], Awaitable[bool] | bool]] = None

        for action_type, handler_instance in self.handlers.items():
            logger.info(f"ActionDispatcher: Registered handler for {action_type.value}: {handler_instance.__class__.__name__}")

    def get_handler(self, action_type: HandlerActionType) -> Optional[BaseActionHandler]:
        """Get a handler by action type."""
        return self.handlers.get(action_type)  # type: ignore[union-attr]

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

        # Defensive: ensure selected_action is a HandlerActionType
        action_type = action_selection_result.selected_action
        if not isinstance(action_type, HandlerActionType):
            try:
                action_type = HandlerActionType(action_type)
            except Exception as e:
                logger.error(f"ActionDispatcher: selected_action {action_type} is not a valid HandlerActionType: {e}")
                return

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
                    status=ThoughtStatus.FAILED,
                    final_action={
                        "error": f"No handler for action {action_type.value}",
                        "original_result": action_selection_result
                    }
                )
                # Consider creating a follow-up error thought here if handlers normally do
            except Exception as e_persist:
                logger.error(f"Failed to update thought {thought.thought_id} to FAILED after no handler found: {e_persist}")
            return

        logger.info(
            f"Dispatching action {action_type.value} for thought {thought.thought_id} to handler {handler_instance.__class__.__name__}"
        )

        # Wait for service registry readiness before invoking the handler
        dependencies = getattr(handler_instance, "dependencies", None)
        if dependencies and hasattr(dependencies, "wait_registry_ready"):
            ready = await dependencies.wait_registry_ready(
                timeout=dispatch_context.get("registry_timeout", 30.0)
            )
            if not ready:
                logger.error(
                    f"Service registry not ready for handler {handler_instance.__class__.__name__}; action aborted"
                )
                return
        print(f"[DISPATCHER] Dispatching action {action_type.value} for thought {thought.thought_id} to handler {handler_instance.__class__.__name__}")
        
        try:
            # The handler's `handle` method will take care of everything.
            await handler_instance.handle(action_selection_result, thought, dispatch_context)
            print(f"[DISPATCHER] Handler {handler_instance.__class__.__name__} completed for action {action_type.value} on thought {thought.thought_id}")
        except Exception as e:
            logger.exception(
                f"Error executing handler {handler_instance.__class__.__name__} for action {action_type.value} on thought {thought.thought_id}: {e}"
            )
            try:
                persistence.update_thought_status(
                    thought_id=thought.thought_id,                status=ThoughtStatus.FAILED,
                final_action={
                    "error": f"Handler {handler_instance.__class__.__name__} failed: {str(e)}",
                    "original_result": action_selection_result,
                },
                )
            except Exception as e_persist:
                logger.error(
                    f"Failed to update thought {thought.thought_id} to FAILED after handler exception: {e_persist}"
                )


