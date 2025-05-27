import logging
from typing import Dict, Any

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RejectParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.core import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from ..exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class RejectHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        original_event_channel_id = dispatch_context.get("channel_id")

        # REJECT actions usually mean the thought processing has failed for a stated reason.
        final_thought_status = ThoughtStatus.FAILED 
        action_performed_successfully = False  # The agent couldn't proceed.
        follow_up_content_key_info = f"REJECT action for thought {thought_id}"

        if not isinstance(params, RejectParams):
            self.logger.error(f"REJECT action params are not RejectParams model. Type: {type(params)}. Thought ID: {thought_id}")
            follow_up_content_key_info = f"REJECT action failed: Invalid parameters type ({type(params)}) for thought {thought_id}. Original reason might be lost."
        else:
            follow_up_content_key_info = f"Rejected thought {thought_id}. Reason: {params.reason}"
            # Optionally, send a message to the original channel
            if self.dependencies.action_sink and original_event_channel_id and params.reason:
                try:
                    await self.dependencies.action_sink.send_message(original_event_channel_id, f"Unable to proceed: {params.reason}")
                    # Not marking action_performed_successfully = True, as REJECT is a failure state.
                except Exception as e:
                    self.logger.error(f"Failed to send REJECT notification to channel {original_event_channel_id} for thought {thought_id}: {e}")
        
        # v1 uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,  # FAILED
            final_action=result.model_dump(),  # Changed from final_action_result
        )
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for REJECT action. Info: {follow_up_content_key_info}")

        # Create a follow-up thought indicating failure and reason
        follow_up_text = f"REJECT action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. This path of reasoning is terminated. Review and determine if a new approach or task is needed."
        
        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
                priority_offset=1,
            )

            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {"action_performed": HandlerActionType.REJECT.value}
            context_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'

            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after REJECT action."
            )
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            raise FollowUpCreationError from e