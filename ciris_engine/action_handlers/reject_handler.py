import logging
from typing import Dict, Any

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RejectParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

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
        parent_task_id = thought.source_task_id
        await self._audit_log(HandlerActionType.REJECT, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        original_event_channel_id = dispatch_context.get("channel_id")

        try:
            params = await self._validate_and_convert_params(params, RejectParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.REJECT, dispatch_context, thought_id, e)
            follow_up_content_key_info = f"REJECT action failed: {e}"
            final_thought_status = ThoughtStatus.FAILED
            follow_up_text = f"REJECT action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. This path of reasoning is terminated. Review and determine if a new approach or task is needed."
            try:
                new_follow_up = create_follow_up_thought(
                    parent=thought,
                    content=follow_up_text,
                )
                context_for_follow_up = {
                    "action_performed": HandlerActionType.REJECT.value,
                    "parent_task_id": parent_task_id,
                    "is_follow_up": True,
                    "error_details": follow_up_content_key_info,
                }
                context_for_follow_up["action_params"] = params if isinstance(params, dict) else str(params)
                new_follow_up.context = context_for_follow_up
                persistence.add_thought(new_follow_up)
                await self._audit_log(HandlerActionType.REJECT, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
            except Exception as e2:
                await self._handle_error(HandlerActionType.REJECT, dispatch_context, thought_id, e2)
                raise FollowUpCreationError from e2
            result_data = result.model_dump() if hasattr(result, 'model_dump') else result
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_thought_status,
                final_action=result_data,
            )
            return
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
            if original_event_channel_id and params.reason:
                comm_service = await self.get_communication_service()
                if comm_service:
                    try:
                        await comm_service.send_message(original_event_channel_id, f"Unable to proceed: {params.reason}")
                    except Exception as e:
                        self.logger.error(f"Failed to send REJECT notification via communication service for thought {thought_id}: {e}")
                elif self.dependencies.action_sink:
                    try:
                        await self.dependencies.action_sink.send_message(original_event_channel_id, f"Unable to proceed: {params.reason}")
                    except Exception as e:
                        self.logger.error(f"Failed to send REJECT notification to channel {original_event_channel_id} for thought {thought_id}: {e}")
        # v1 uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,  # FAILED
            final_action=result_data,  # v1 field
        )
        if parent_task_id:
            persistence.update_task_status(parent_task_id, TaskStatus.FAILED)
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for REJECT action. Info: {follow_up_content_key_info}")

        # Create a follow-up thought indicating failure and reason
        follow_up_text = f"REJECT action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. This path of reasoning is terminated. Review and determine if a new approach or task is needed."
        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
            )

            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {
                "action_performed": HandlerActionType.REJECT.value,
                "parent_task_id": parent_task_id,
                "is_follow_up": True,
                "error_details": follow_up_content_key_info,
            }

            # When serializing for follow-up, convert to dict
            action_params_dump = params.model_dump(mode="json") if hasattr(params, "model_dump") else params
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'

            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after REJECT action."
            )
            await self._audit_log(HandlerActionType.REJECT, {**dispatch_context, "thought_id": thought_id}, outcome="success")
        except Exception as e:
            await self._handle_error(HandlerActionType.REJECT, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e