import logging
from typing import Dict, Any

from pydantic import BaseModel

from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, DeferParams, Thought
from ciris_engine.core.foundational_schemas import ThoughtStatus
from ciris_engine.core import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought # Though DEFER might not always create a standard follow-up

logger = logging.getLogger(__name__)

class DeferHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionPDMAResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        original_event_channel_id = dispatch_context.get("channel_id")

        final_thought_status = ThoughtStatus.DEFERRED # Default for DEFER action
        action_performed_successfully = False # Until confirmed
        follow_up_content_key_info = f"DEFER action for thought {thought_id}"

        if not isinstance(params, DeferParams):
            self.logger.error(f"DEFER action params are not DeferParams model. Type: {type(params)}. Thought ID: {thought_id}")
            # Even if params are wrong, we still mark the thought as DEFERRED, but log the issue.
            # The reason might be lost, or we use a generic one.
            follow_up_content_key_info = f"DEFER action failed: Invalid parameters type ({type(params)}) for thought {thought_id}. Original reason might be lost."
            # Keep final_thought_status as DEFERRED
        else:
            follow_up_content_key_info = f"Deferred thought {thought_id}. Reason: {params.reason}"
            # Optionally, send a message to the original channel if an action_sink is available
            if self.dependencies.action_sink and original_event_channel_id and params.reason:
                try:
                    await self.dependencies.action_sink.send_message(original_event_channel_id, f"Action Deferred: {params.reason}")
                    action_performed_successfully = True # Informing user is part of the action
                except Exception as e:
                    self.logger.error(f"Failed to send DEFER notification to channel {original_event_channel_id} for thought {thought_id}: {e}")
                    # Don't mark action as failed for this, just log. The core deferral is DB update.
            else:
                # If no sink or channel, the deferral is silent, which is acceptable.
                action_performed_successfully = True # Deferral itself is successful by updating status

        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status, # Should be DEFERRED
            final_action_result=result.model_dump(),
        )
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for DEFER action. Info: {follow_up_content_key_info}")

        # DEFER actions typically don't create a standard "next step" follow-up thought
        # because the deferral itself is a terminal state for this thought's processing round.
        # A human or another process is expected to review deferred thoughts.
        # However, one might log this to a specific system or create a different kind of notification.
        # For now, no standard follow-up thought is created by this handler.
        # If a follow-up IS needed, it would be specific to the deferral reason/workflow.
