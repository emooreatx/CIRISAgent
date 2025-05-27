import logging
import os
from typing import Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError
from .discord_observe_handler import handle_discord_observe_event
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ObserveHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"OBSERVE action for thought {thought_id}"

        if not isinstance(params, ObserveParams):
            self.logger.error(f"OBSERVE action params are not ObserveParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"OBSERVE action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif params.active:  # v1 uses 'active'
            # Use the Discord observe handler in active mode
            try:
                await handle_discord_observe_event(
                    payload={
                        "channel_id": params.sources[0] if params.sources else None,
                        "offset": params.offset if hasattr(params, 'offset') else 0,
                        "limit": params.limit if hasattr(params, 'limit') else 10,
                        "include_agent": True
                    },
                    mode="active",
                    context={
                        "discord_service": getattr(self.dependencies, "discord_service", None),
                        "default_channel_id": os.getenv("DISCORD_CHANNEL_ID"),
                        "agent_id": getattr(self.dependencies, "agent_id", None)
                    }
                )
                action_performed_successfully = True
                follow_up_content_key_info = f"Active Discord observe handler invoked for sources: {params.sources}"
            except Exception as e:
                self.logger.exception(f"Error during active Discord observe handler for thought {thought_id}: {e}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"Active Discord observe handler error: {str(e)}"
        else:  # Passive observe
            # Use the Discord observe handler in passive mode
            try:
                await handle_discord_observe_event(
                    payload={
                        "message_id": thought.thought_id,
                        "content": thought.content,
                        "context": getattr(thought, "context", {}),
                        "task_description": getattr(thought, "content", None)
                    },
                    mode="passive"
                )
                action_performed_successfully = True
                follow_up_content_key_info = f"Passive Discord observe handler invoked for sources: {params.sources}"
            except Exception as e:
                self.logger.exception(f"Error during passive Discord observe handler for thought {thought_id}: {e}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"Passive Discord observe handler error: {str(e)}"

        # v1 uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action=result.model_dump(),  # v1 field
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after OBSERVE attempt.")

        # Create a follow-up thought ONLY if it's not an active look that successfully created its own result thought.
        # Or if any OBSERVE action failed.
        should_create_standard_follow_up = True
        if params and params.active and action_performed_successfully:  # v1 uses 'active'
            should_create_standard_follow_up = False  # Active look created its own specific follow-up

        if final_thought_status == ThoughtStatus.FAILED:  # Always create follow-up for failures
            should_create_standard_follow_up = True

        if should_create_standard_follow_up:
            follow_up_text = ""
            if action_performed_successfully:  # This implies passive observe success
                follow_up_text = f"OBSERVE action ({'passive' if params else 'unknown type'}) for thought {thought_id} completed. Info: {follow_up_content_key_info}. Review if this completes the task or if further steps are needed."
            else:  # Failed
                follow_up_text = f"OBSERVE action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."

            try:
                new_follow_up = create_follow_up_thought(
                    parent=thought,
                    content=follow_up_text,
                    priority_offset=1 if action_performed_successfully else 0,
                )

                # v1 uses 'context' instead of 'processing_context'
                context_for_follow_up = {
                    "action_performed": HandlerActionType.OBSERVE.value
                }
                if final_thought_status == ThoughtStatus.FAILED:
                    context_for_follow_up["error_details"] = follow_up_content_key_info

                action_params_dump = result.action_parameters
                if isinstance(action_params_dump, BaseModel):
                    action_params_dump = action_params_dump.model_dump(mode="json")
                context_for_follow_up["action_params"] = action_params_dump

                new_follow_up.context = context_for_follow_up  # v1 uses 'context'

                persistence.add_thought(new_follow_up)
                self.logger.info(
                    f"Created standard follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after OBSERVE action."
                )
                await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="success" if action_performed_successfully else "failed")
            except Exception as e:
                self.logger.critical(
                    f"Failed to create follow-up thought for {thought_id}: {e}",
                    exc_info=e,
                )
                await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="failed_followup")
                raise FollowUpCreationError from e