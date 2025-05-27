import logging
from typing import Dict, Any

from pydantic import BaseModel

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
        params = result.action_parameters
        thought_id = thought.thought_id
        # channel_id from the original event context, if available
        original_event_channel_id = dispatch_context.get("channel_id")

        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"Failed SPEAK for thought {thought_id}"  # Default for errors

        speak_content: str = None
        target_channel_id_from_params: str = None

        if isinstance(params, SpeakParams):
            speak_content = params.content
            target_channel_id_from_params = params.channel_id  # v1 uses 'channel_id' instead of 'target_channel'
        elif isinstance(params, dict):  # Fallback for raw dict
            speak_content = params.get("content")
            target_channel_id_from_params = params.get("channel_id") or params.get("target_channel")  # Support both
            self.logger.warning(f"SPEAK params were dict, not SpeakParams model for thought {thought_id}")
        else:
            self.logger.error(f"SPEAK action params are neither SpeakParams nor dict. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"SPEAK action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
            # No action_performed_successfully update here, it's already False

        if final_thought_status != ThoughtStatus.FAILED:
            final_channel_id_to_speak = target_channel_id_from_params or original_event_channel_id
            
            if not final_channel_id_to_speak and self.snore_channel_id:
                self.logger.info(f"No target_channel in params or event_channel_id. Using SNORE_CHANNEL_ID: {self.snore_channel_id}. Thought ID: {thought_id}")
                final_channel_id_to_speak = self.snore_channel_id

            if speak_content and final_channel_id_to_speak:
                if self.dependencies.action_sink:
                    try:
                        numeric_channel_id_str = str(final_channel_id_to_speak).lstrip('#')
                        await self.dependencies.action_sink.send_message(numeric_channel_id_str, speak_content)
                        action_performed_successfully = True
                        follow_up_content_key_info = f"Spoke: '{str(speak_content)[:50]}...' in channel #{numeric_channel_id_str}"
                    except Exception as send_ex:
                        self.logger.exception(f"Error sending SPEAK message to channel {final_channel_id_to_speak}. Thought ID: {thought_id}: {send_ex}")
                        final_thought_status = ThoughtStatus.FAILED
                        follow_up_content_key_info = f"SPEAK action failed during send to {final_channel_id_to_speak}: {str(send_ex)}"
                else:
                    self.logger.error(f"ActionSink not available. Cannot send SPEAK message for thought {thought_id}")
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"SPEAK action failed: ActionSink unavailable for thought {thought_id}."
            else:
                err_msg = "SPEAK action failed: "
                if not speak_content: err_msg += "Missing content. "
                if not final_channel_id_to_speak: err_msg += "Missing channel."
                self.logger.error(f"{err_msg} Thought ID: {thought_id}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = err_msg.strip()

        # Update original thought status
        # v1 uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action=result.model_dump(),  # Changed from final_action_result
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after SPEAK attempt.")

        # Create follow-up thought
        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = f"Successfully spoke: '{speak_content[:70]}...'. The original user request may now be addressed. Consider if any further memory operations or actions are needed. If the task is complete, the next action should be TASK_COMPLETE."
        else:  # Failed
            follow_up_text = f"SPEAK action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."

        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
                priority_offset=1 if action_performed_successfully else 0,
            )
            
            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {"action_performed": HandlerActionType.SPEAK.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after SPEAK action."
            )
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            raise FollowUpCreationError from e