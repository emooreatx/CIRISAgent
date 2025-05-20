"""Dispatch actions and ensure follow-up Thought creation."""

import logging

logger = logging.getLogger(__name__)

from typing import Callable, Awaitable, Any, Dict # Added Dict
from datetime import datetime, timezone
import uuid

from .foundational_schemas import HandlerActionType
from .agent_core_schemas import Thought, ThoughtStatus, ActionSelectionPDMAResult, SpeakParams # Added ActionSelectionPDMAResult, SpeakParams
from . import persistence
from pydantic import BaseModel # Added BaseModel for params type check

from .action_handlers.speak_handler import handle_speak
from .action_handlers.observe_handler import handle_observe
from .action_handlers.memorize_handler import handle_memorize
from .action_handlers.defer_handler import handle_defer
from .action_handlers.tool_handler import handle_tool
from .action_handlers.task_complete_handler import handle_task_complete

handler_map = {
    HandlerActionType.SPEAK: handle_speak,
    HandlerActionType.OBSERVE: handle_observe,
    HandlerActionType.MEMORIZE: handle_memorize,
    HandlerActionType.DEFER: handle_defer,
    HandlerActionType.TOOL: handle_tool,
    HandlerActionType.TASK_COMPLETE: handle_task_complete,
}

ServiceHandlerCallable = Callable[[ActionSelectionPDMAResult, Dict[str, Any]], Awaitable[Any]] # Updated signature

# Renamed to avoid conflict with the method name
async def _core_dispatch(action_type: HandlerActionType, thought: Thought, params: dict, services: dict):
    """Execute a core handler and persist a follow-up Thought when required."""
    handler = handler_map.get(action_type)
    if not handler:
        logger.error(f"No core handler found for action type: {action_type}. Thought ID: {thought.thought_id}")
        # Potentially create a failed thought or handle error
        return None # Or raise an exception

    # Ensure params is a dict for core handlers
    if isinstance(params, BaseModel):
        params_dict = params.model_dump()
    elif isinstance(params, dict):
        params_dict = params
    else:
        logger.error(f"Invalid params type for core dispatch: {type(params)}. Expected Pydantic model or dict. Thought ID: {thought.thought_id}")
        params_dict = {} # Fallback to empty dict to avoid further errors, or raise

    try:
        handler_result = await handler(thought, params_dict, **services)
    except Exception as e:
        logger.exception(f"Error executing core handler for action {action_type} on thought {thought.thought_id}: {e}")
        # Mark thought as failed or handle error
        return None


    if action_type == HandlerActionType.TASK_COMPLETE:
        # handle_task_complete returns None and modifies thought.is_terminal
        # No follow-up thought needed from here for TASK_COMPLETE
        return None

    if isinstance(handler_result, Thought): # If handler returned a thought (e.g. PONDER)
        persistence.add_thought(handler_result)
        return handler_result

    # Fallback: create a minimal follow-up if handler didn't return one and it's not TASK_COMPLETE
    # This is typical for actions like SPEAK, MEMORIZE, OBSERVE, DEFER, TOOL from core handlers
    new_follow_up_thought = Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=thought.source_task_id,
        thought_type="follow_up", # Generic follow-up
        status=ThoughtStatus.PENDING,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        round_created=thought.round_created, # Or current round from context if available
        content=f"Follow-up to action {action_type.value} for thought {thought.thought_id}",
        related_thought_id=thought.thought_id,
        priority=thought.priority,
    )
    persistence.add_thought(new_follow_up_thought)
    return new_follow_up_thought

class ActionDispatcher:
    def __init__(self, audit_service=None):
        self.service_handlers: Dict[str, ServiceHandlerCallable] = {}
        self.action_filter = None

    def register_service_handler(self, service_name: str, handler_callback: ServiceHandlerCallable):
        self.service_handlers[service_name.lower()] = handler_callback # Store service name in lowercase for consistent lookup

    async def dispatch(self, 
                       action_selection_result: ActionSelectionPDMAResult, 
                       thought: Thought, # Still needed for core handlers and context
                       dispatch_context: Dict[str, Any], 
                       services: Dict[str, Any]):
        
        action_type = action_selection_result.selected_handler_action
        action_params = action_selection_result.action_parameters # This can be a Pydantic model or dict

        if self.action_filter:
            # The action_filter might need adjustment if it expects only action_type and params dict
            # For now, let's assume it can work with ActionSelectionPDMAResult or adapt it.
            # Simplified: construct what filter expects if it's rigid.
            # class _Res: def __init__(self, act): self.selected_handler_action = act
            # filter_params_dict = action_params.model_dump() if hasattr(action_params, 'model_dump') else action_params
            # should_skip = await self.action_filter(_Res(action_type), {"params": filter_params_dict})
            # if should_skip:
            #     logger.info(f"Action {action_type} for thought {thought.thought_id} skipped by action_filter.")
            #     return
            pass # Placeholder for now, filter logic might need review

        origin_service = dispatch_context.get("origin_service")
        service_handler_to_call = None

        if origin_service:
            service_handler_to_call = self.service_handlers.get(origin_service.lower())

        if service_handler_to_call:
            logger.info(f"Dispatching action {action_type} for thought {thought.thought_id} to service handler for '{origin_service}'.")
            try:
                # Service handlers expect (ActionSelectionPDMAResult, dispatch_context)
                await service_handler_to_call(action_selection_result, dispatch_context)
                # Service handlers are responsible for their own follow-up logic / thought status updates
            except Exception as e:
                logger.exception(f"Error executing service handler for '{origin_service}' on thought {thought.thought_id}: {e}")
                # Mark thought as failed or handle error
                persistence.update_thought_status(thought.thought_id, ThoughtStatus.FAILED, final_action_result={"error": f"Service handler {origin_service} failed: {str(e)}"})
        else:
            logger.info(f"No specific service handler for origin '{origin_service}'. Using core handler for action {action_type} on thought {thought.thought_id}.")
            # Fallback to core generic handlers
            # _core_dispatch expects (action_type, thought, params_dict, services)
            
            params_for_core = action_params
            if isinstance(action_params, BaseModel):
                params_for_core = action_params.model_dump()
            elif not isinstance(action_params, dict): # Ensure it's a dict if not a BaseModel
                logger.error(f"Action parameters for core dispatch are neither BaseModel nor dict: {type(action_params)}. Thought ID: {thought.thought_id}")
                # Fallback or raise error. For now, try to convert to string dict.
                try:
                    params_for_core = dict(action_params) if hasattr(action_params, '__iter__') and not isinstance(action_params, str) else {"error_param": str(action_params)}
                except: # Broad except to catch various conversion failures
                    params_for_core = {"error_param": "unconvertible_action_parameters"}


            await _core_dispatch(action_type, thought, params_for_core, services)
