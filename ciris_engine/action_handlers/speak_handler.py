import logging
from typing import Dict, Any, Optional


from ciris_engine.schemas import Thought, SpeakParams, ThoughtStatus, HandlerActionType, ActionSelectionResult, DispatchContext
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


def _build_speak_error_context(params: SpeakParams, thought_id: str, error_type: str = "notification_failed") -> str:
    """Build a descriptive error context string for speak failures."""
    # Use attribute access for content if it's a GraphNode
    content_str = params.content
    if hasattr(params.content, 'value'):
        content_str = getattr(params.content, 'value', str(params.content))
    elif hasattr(params.content, '__str__'):
        content_str = str(params.content)
    error_contexts = {
        "notification_failed": f"Failed to send notification to channel '{params.channel_id}' with content: '{content_str[:100]}{'...' if len(content_str) > 100 else ''}'",
        "channel_unavailable": f"Channel '{params.channel_id}' is not available or accessible",
        "content_rejected": f"Content was rejected by the communication service: '{content_str[:100]}{'...' if len(content_str) > 100 else ''}'",
        "service_timeout": f"Communication service timed out while sending to channel '{params.channel_id}'",
        "unknown": f"Unknown error occurred while speaking to channel '{params.channel_id}'"
    }
    
    base_context = error_contexts.get(error_type, error_contexts["unknown"])
    return f"Thought {thought_id}: {base_context}"


class SpeakHandler(BaseActionHandler):
    def __init__(self, dependencies: ActionHandlerDependencies, snore_channel_id: Optional[str] = None) -> None:
        super().__init__(dependencies)
        self.snore_channel_id = snore_channel_id

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        thought_id = thought.thought_id

        try:
            # Auto-decapsulate any secrets in the action parameters
            processed_result = await self._decapsulate_secrets_in_params(result, "speak")
            
            params = await self._validate_and_convert_params(processed_result.action_parameters, SpeakParams)
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
                # Update context using Pydantic model_copy with additional fields
                context_data = fu.context.model_dump() if fu.context else {}
                context_data.update({
                    "action_performed": HandlerActionType.SPEAK.value,
                    "error_details": str(e),
                    "action_params": result.action_parameters,
                })
                from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
                fu.context = ThoughtContext.model_validate(context_data)
                persistence.add_thought(fu)
                return fu.thought_id
            except Exception as fe:
                await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, fe)
                raise FollowUpCreationError from fe

        if not params.channel_id:  # type: ignore[attr-defined]
            params.channel_id = await self._get_channel_id(thought, dispatch_context) or self.snore_channel_id  # type: ignore[attr-defined]

        event_summary = params.content  # type: ignore[attr-defined]
        await self._audit_log(
            HandlerActionType.SPEAK,
            dispatch_context.model_copy(update={"thought_id": thought_id, "event_summary": event_summary}),
            outcome="start",
        )

        # Extract string from GraphNode for notification
        content_str = params.content.attributes.get('text', str(params.content)) if hasattr(params.content, 'attributes') else str(params.content)  # type: ignore[attr-defined]
        success = await self._send_notification(params.channel_id, content_str)  # type: ignore[attr-defined]

        final_thought_status = ThoughtStatus.COMPLETED if success else ThoughtStatus.FAILED
        
        # Build error context if needed
        assert isinstance(params, SpeakParams)  # Type assertion - validated earlier
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

        # Create correlation for tracking action completion
        from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus
        import uuid
        from datetime import datetime, timezone
        
        correlation = ServiceCorrelation(
            correlation_id=str(uuid.uuid4()),
            service_type="communication",
            handler_name="SpeakHandler",
            action_type="speak",
            request_data={
                "task_id": thought.source_task_id,
                "thought_id": thought_id,
                "channel_id": params.channel_id,  # type: ignore[attr-defined]
                "content": str(params.content)  # type: ignore[attr-defined]
            },
            response_data={"success": success, "final_status": final_thought_status.value},
            status=ServiceCorrelationStatus.COMPLETED if success else ServiceCorrelationStatus.FAILED,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        persistence.add_correlation(correlation)

        follow_up_text = (
            f"""
            NEXT ACTION IS TASK COMPLETE!
            CIRIS_FOLLOW_UP_THOUGHT: YOU Spoke, as a result of your action: '{params.content}' in channel
            {params.channel_id} as a response to task: {task_description}. The next
            action is probably TASK COMPLETE to mark the original task as handled.
            Do NOT speak again unless DRASTICALLY necessary.
            NEXT ACTION IS TASK COMPLETE UNLESS YOU NEED TO MEMORIZE SOMETHING!
            """
            if success
            else f"CIRIS_FOLLOW_UP_THOUGHT: SPEAK action failed for thought {thought_id}."
        )

        try:
            new_follow_up = create_follow_up_thought(parent=thought, content=follow_up_text)
            context_data = new_follow_up.context.model_dump() if new_follow_up.context else {}
            ctx = {
                "action_performed": HandlerActionType.SPEAK.value,
                "action_params": params,
            }
            if not success:
                ctx["error_details"] = follow_up_error_context
            context_data.update(ctx)
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            new_follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(new_follow_up)
            await self._audit_log(
                HandlerActionType.SPEAK,
                dispatch_context.model_copy(update={"thought_id": thought_id, "event_summary": event_summary}),
                outcome="success" if success else "failed",
            )
            follow_up_thought_id = new_follow_up.thought_id
        except Exception as e:
            await self._handle_error(HandlerActionType.SPEAK, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e

        if hasattr(thought, "context"):
            if not thought.context:
                from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
                thought.context = ThoughtContext(system_snapshot=SystemSnapshot(channel_id=params.channel_id))  # type: ignore[attr-defined]
            if not getattr(thought.context.system_snapshot, "channel_id", None):
                thought.context.system_snapshot.channel_id = params.channel_id  # type: ignore[attr-defined]
        
        return follow_up_thought_id

