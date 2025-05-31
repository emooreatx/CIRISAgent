import logging
from typing import Dict, Any

from pydantic import ValidationError

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


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
            result_data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result_data,
            )
            follow_up_text = f"SPEAK action failed for thought {thought_id}. Reason: {e}"
            try:
                fu = create_follow_up_thought(parent=thought, content=follow_up_text)
                fu.context = {
                    "action_performed": HandlerActionType.SPEAK.value,
                    "error_details": str(e),
                    "action_params": result_data.get("action_parameters") if isinstance(result_data, dict) else str(result_data),
                }
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
        follow_up_content_key_info = (
            f"Spoke: '{params.content[:50]}...' in channel #{params.channel_id}"
            if success
            else f"Failed to send message to {params.channel_id}"
        )

        result_data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result_data,
        )

        follow_up_text = (
            f"Successfully spoke: '{params.content[:70]}...'"
            if success
            else f"SPEAK action failed for thought {thought_id}. Reason: {follow_up_content_key_info}."
        )

        try:
            new_follow_up = create_follow_up_thought(parent=thought, content=follow_up_text)
            ctx = {
                "action_performed": HandlerActionType.SPEAK.value,
                "action_params": params.model_dump(mode="json"),
            }
            if not success:
                ctx["error_details"] = follow_up_content_key_info
            new_follow_up.context = ctx
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
                thought.context = {}
            if not thought.context.get("channel_id"):
                thought.context["channel_id"] = params.channel_id

