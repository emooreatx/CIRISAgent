import logging
import asyncio
import uuid
import inspect
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Coroutine, TYPE_CHECKING, Optional, Union

from ciris_engine.utils.constants import NEED_MEMORY_METATHOUGHT
from . import persistence
from .agent_core_schemas import (
    HandlerActionType,
    Thought,
    ThoughtStatus,
)
from .action_params import SpeakParams, MemorizeParams
from .dma_results import ActionSelectionPDMAResult
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
        self.audit_service = audit_service or AuditService()
        # Stores handlers keyed by the service name (e.g., "discord", "slack", "memory")
        self.service_handlers: Dict[str, ServiceHandlerCallable] = {}
        self.action_filter: Optional[Callable[['ActionSelectionPDMAResult', Dict[str, Any]], Union[bool, Coroutine[Any, Any, bool]]]] = None
        logger.info("ActionDispatcher initialized.")

    async def _enqueue_acknowledgment_thought(
        self,
        original_context: Dict[str, Any],
        result: "ActionSelectionPDMAResult",
        handler_type: str = "memory_handler" # To distinguish log messages
    ):
        """Helper method to enqueue a system_acknowledgment thought after MEMORIZE."""
        try:
            source_task_id = original_context.get("source_task_id")
            if not source_task_id:
                logger.warning(f"Could not enqueue acknowledgment thought ({handler_type}): source_task_id missing.")
                return

            ack_thought_id = f"ack_{uuid.uuid4().hex[:8]}"
            ack_content = "Okay, I've noted that down."  # Generic acknowledgment
            user_nick = original_context.get("author_name")

            if user_nick:
                if isinstance(result.action_parameters, MemorizeParams) and \
                   hasattr(result.action_parameters, 'knowledge_unit_description') and \
                   result.action_parameters.knowledge_unit_description:
                    ack_content = f"Okay {user_nick}, I've noted that down about {result.action_parameters.knowledge_unit_description}."
                else:
                    ack_content = f"Okay {user_nick}, I've noted that down."
            
            ack_thought = Thought(
                thought_id=ack_thought_id,
                source_task_id=source_task_id,
                thought_type="system_acknowledgment",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_created=original_context.get("round", 0) + 1,
                content=ack_content,
                processing_context={
                    "target_action": HandlerActionType.SPEAK.value,
                    "speak_content": ack_content,
                    "original_context": original_context  # Consider if the full original_context is needed here
                },
                priority=original_context.get("priority", 1) + 1
            )
            await asyncio.to_thread(persistence.add_thought, ack_thought)
            logger.info(f"Enqueued acknowledgment thought {ack_thought_id} for task {source_task_id} after MEMORIZE ({handler_type}).")

        except Exception as e_ack:
            logger.exception(f"Error enqueuing acknowledgment thought after MEMORIZE ({handler_type}): {e_ack}")

    async def _enqueue_memory_metathought(
        self,
        context: Dict[str, Any],
        result: "ActionSelectionPDMAResult",
    ):
        """Create a MEMORY meta-thought if warranted."""
        user_nick = context.get("author_name")
        if not user_nick:
            logger.warning("Skipping memory meta-thought due to missing user name")
            context[NEED_MEMORY_METATHOUGHT] = False
            return

        # Determine whether the previous action warrants a memory meta-thought
        rationale = (result.action_selection_rationale or "").lower()
        needs_update = False
        if result.selected_handler_action == HandlerActionType.MEMORIZE:
            needs_update = True
        elif any(k in rationale for k in ["learn", "memor", "remember"]):
            needs_update = True

        if not needs_update:
            context[NEED_MEMORY_METATHOUGHT] = False
            return

        original_context_for_meta = {
            "origin_service": context.get("origin_service"),
            "message_id": context.get("message_id"),
            "channel_id": context.get("channel_id"),
            "author_id": context.get("author_id"),
            "author_name": context.get("author_name"),
            "source_task_id": context.get("source_task_id"),
            "event_summary": context.get("event_summary"),
            "task_description": context.get("task_description"),
        }

        meta_thought = Thought(
            thought_id=f"mem_{uuid.uuid4().hex[:8]}",
            source_task_id=context.get("source_task_id", "unknown"),
            thought_type="memory_meta",
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            round_created=context.get("round", 0), # The round number when the original action occurred
            content=(
                "This is a memory meta-reflection. Your current role is 'teacher'. "
                "Review the details of the preceding interaction: "
                "The original user message context is in 'processing_context.initial_context'. "
                "The action taken by the agent in response to that message is detailed in 'processing_context.final_action_result'. "
                "Critically evaluate this interaction. Based on your role and the information exchanged, "
                "determine if any specific facts, user preferences, or contextual details should be MEMORIZED "
                "to improve future interactions or understanding. "
                "If memorization is appropriate, select the MEMORIZE action and provide the necessary parameters. "
                "If nothing warrants memorization from this interaction, you MUST REJECT this meta-thought."
            ),
            processing_context={
                "user_nick": user_nick, # User from the original interaction
                "channel_id": context.get("channel_id"), # Channel from original interaction
                # "metadata": {}, # Retained for now, LLM might populate or it's used by MEMORIZE handler
                "initial_context": original_context_for_meta, # Context of the original user message
                "trigger_thought_id": context.get("thought_id"), # ID of the thought that triggered this meta
                "final_action_result": result.model_dump(mode="json"), # ASPDMA result of the triggering thought
                "agent_role_for_reflection": "teacher" # Explicitly pass the role for this reflection
            },
            priority=0, # Meta-thoughts might have different priority
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
        action_type = result.selected_handler_action
        # Determine the originating service from the context, default to 'unknown'
        origin_service = original_context.get("origin_service", "unknown")

        if self.action_filter:
            if inspect.iscoroutinefunction(self.action_filter):
                should_skip = await self.action_filter(result, original_context)
            else:
                should_skip = self.action_filter(result, original_context)

            if should_skip:
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

            if action_type in [HandlerActionType.SPEAK, HandlerActionType.ACT, HandlerActionType.DEFER]:
                if not original_context.get("skip_memory_update"):
                    original_context[NEED_MEMORY_METATHOUGHT] = True
                    await self._enqueue_memory_metathought(original_context, result)

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
                    if not original_context.get("skip_memory_update"):
                        original_context[NEED_MEMORY_METATHOUGHT] = True
                        await self._enqueue_memory_metathought(original_context, result)

                        # After MEMORIZE and its meta-thought, enqueue an acknowledgment thought
                        if action_type == HandlerActionType.MEMORIZE:
                            await self._enqueue_acknowledgment_thought(original_context, result, handler_type="memory_handler")

                except Exception as e:
                    logger.exception(f"Error executing memory handler for action '{action_type.value}': {e}")
            else:
                logger.warning(
                    f"Received memory action '{action_type.value}' but no 'memory' handler registered. Action may not be fully processed."
                )
                if not original_context.get("skip_memory_update"):
                    original_context[NEED_MEMORY_METATHOUGHT] = True
                    await self._enqueue_memory_metathought(original_context, result)

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

        thought_id = original_context.get("thought_id")
        if thought_id:
            thought = persistence.get_thought_by_id(thought_id)
            if thought:
                thought.action_count += 1
                thought.history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": action_type.value,
                    "service": origin_service,
                })
                if action_type == HandlerActionType.DEFER:
                    thought.escalations.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "defer",
                    })
