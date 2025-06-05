import logging
from typing import Dict, Any

from pydantic import ValidationError

# Updated imports for v1 schemas
from ciris_engine.schemas import Thought, SpeakParams, ThoughtStatus, HandlerActionType, ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


def _build_speak_error_context(params: SpeakParams, thought_id: str, error_type: str = "notification_failed") -> str:
    """Build a descriptive error context string for speak failures."""
    error_contexts = {
        "notification_failed": f"Failed to send notification to channel '{params.channel_id}' with content: '{params.content[:100]}{'...' if len(params.content) > 100 else ''}'",
        "channel_unavailable": f"Channel '{params.channel_id}' is not available or accessible",
        "content_rejected": f"Content was rejected by the communication service: '{params.content[:100]}{'...' if len(params.content) > 100 else ''}'",
        "service_timeout": f"Communication service timed out while sending to channel '{params.channel_id}'",
        "unknown": f"Unknown error occurred while speaking to channel '{params.channel_id}'"
    }
    
    base_context = error_contexts.get(error_type, error_contexts["unknown"])
    return f"Thought {thought_id}: {base_context}"


class SpeakHandler(BaseActionHandler):
    def __init__(self, dependencies: ActionHandlerDependencies, snore_channel_id: str = None):
        super().__init__(dependencies)
        self.snore_channel_id = snore_channel_id

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        thought_id = thought.thought_id

        try:
            params = await self._validate_and_convert_params(result.action_parameters, SpeakParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, e)
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result,
            )
            follow_up_text = f"SPEAK action failed for thought {thought_id}. Reason: {e}"
            try:
                fu = create_follow_up_thought(parent=thought, content=follow_up_text)
                fu_context = {
                    "action_performed": HandlerActionType.SPEAK.value,
                    "error_details": str(e),
                    "action_params": result.action_parameters,
                }
                for k, v in fu_context.items():
                    setattr(fu.context, k, v)
                persistence.add_thought(fu)
            except Exception as fe:
                await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, fe)
                raise FollowUpCreationError from fe
            return

        if not params.channel_id:
            params.channel_id = await self._get_channel_id(thought, dispatch_context) or self.snore_channel_id

        event_summary = params.content
        await self._audit_log(
            HandlerActionType.SPEAK,
            {**dispatch_context, "thought_id": thought_id, "event_summary": event_summary},
            outcome="start",
        )

        success = await self._send_notification(params.channel_id, params.content)

        final_thought_status = ThoughtStatus.COMPLETED if success else ThoughtStatus.FAILED
        
        # Build error context if needed
        follow_up_error_context = None if success else _build_speak_error_context(params, thought_id)
        
        # Get the actual task content instead of just the ID
        task = persistence.get_task_by_id(thought.source_task_id)
        task_description = task.description if task else f"task {thought.source_task_id}"


        # Pass ActionSelectionResult directly to persistence - it handles serialization
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )

        follow_up_text = (
            f"""
            CIRIS_FOLLOW_UP_THOUGHT: YOU Spoke, as a result of your action: '{params.content}' in channel 
            {params.channel_id} as a response to task: {task_description}. The next 
            action is probably TASK COMPLETE to mark the original task as handled.
            Do NOT speak again unless DRASTICALLY necessary.
            """
            if success
            else f"CIRIS_FOLLOW_UP_THOUGHT: SPEAK action failed for thought {thought_id}."
        )  #PROMPT_FOLLOW_UP_THOUGHT

        try:
            new_follow_up = create_follow_up_thought(parent=thought, content=follow_up_text)
            ctx = {
                "action_performed": HandlerActionType.SPEAK.value,
                "action_params": params,
            }
            if not success:
                ctx["error_details"] = follow_up_error_context
            for k, v in ctx.items():
                setattr(new_follow_up.context, k, v)
            persistence.add_thought(new_follow_up)
            await self._audit_log(
                HandlerActionType.SPEAK,
                {**dispatch_context, "thought_id": thought_id, "event_summary": event_summary},
                outcome="success" if success else "failed",
            )
        except Exception as e:
            await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e

        if hasattr(thought, "context"):
            if not thought.context:
                from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
                thought.context = ThoughtContext(system_snapshot=SystemSnapshot(channel_id=params.channel_id))
            if not getattr(thought.context.system_snapshot, "channel_id", None):
                thought.context.system_snapshot.channel_id = params.channel_id

