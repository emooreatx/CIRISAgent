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
        # channel_id from the original event context or thought context
        original_event_channel_id = dispatch_context.get("channel_id")
        if not original_event_channel_id and getattr(thought, "context", None):
            original_event_channel_id = thought.context.get("channel_id")

        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"Failed SPEAK for thought {thought_id}"  # Default for errors

        speak_content: str = None
        channel_id_from_params: str = None

        # Ensure channel_id is set in params, using dispatch_context if missing
        if isinstance(params, SpeakParams):
            if not params.channel_id:
                params.channel_id = original_event_channel_id
        elif isinstance(params, dict):
            if not params.get("channel_id"):
                params["channel_id"] = original_event_channel_id
        # --- Ensure event_summary is set for audit log ---
        event_summary = None
        if isinstance(params, SpeakParams):
            event_summary = params.content
        elif isinstance(params, dict):
            event_summary = params.get("content")

        await self._audit_log(
            HandlerActionType.SPEAK,
            {**dispatch_context, "thought_id": thought_id, "event_summary": event_summary},
            outcome="start"
        )

        if isinstance(params, SpeakParams):
            speak_content = params.content
            channel_id_from_params = params.channel_id  # v1 uses 'channel_id' instead of 'target_channel'
        elif isinstance(params, dict):  # Fallback for raw dict
            speak_content = params.get("content")
            channel_id_from_params = params.get("channel_id")  # Only use 'channel_id' for v1
            self.logger.warning(f"SPEAK params were dict, not SpeakParams model for thought {thought_id}")
        else:
            self.logger.error(f"SPEAK action params are neither SpeakParams nor dict. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"SPEAK action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
            # No action_performed_successfully update here, it's already False

        if final_thought_status != ThoughtStatus.FAILED:
            final_channel_id_to_speak = channel_id_from_params or original_event_channel_id
            
            if not final_channel_id_to_speak and self.snore_channel_id:
                self.logger.info(f"No channel_id in params or event_channel_id. Using SNORE_CHANNEL_ID: {self.snore_channel_id}. Thought ID: {thought_id}")
                final_channel_id_to_speak = self.snore_channel_id

            if speak_content and final_channel_id_to_speak:
                # New way with automatic fallback via service registry
                comm_service = await self.get_communication_service()
                if comm_service:
                    try:
                        numeric_channel_id_str = str(final_channel_id_to_speak).lstrip('#')
                        success = await comm_service.send_message(numeric_channel_id_str, speak_content)
                        if success:
                            action_performed_successfully = True
                            follow_up_content_key_info = f"Spoke: '{str(speak_content)[:50]}...' in channel #{numeric_channel_id_str}"
                            logger.info(f"Message sent via service registry to channel {numeric_channel_id_str}")
                        else:
                            logger.warning(f"Communication service failed to send message, trying fallbacks")
                            # The registry automatically tries fallback services, but if all fail:
                            final_thought_status = ThoughtStatus.FAILED
                            follow_up_content_key_info = f"All communication services failed for channel {final_channel_id_to_speak}"
                    except Exception as send_ex:
                        logger.exception(f"Error with communication service for thought {thought_id}: {send_ex}")
                        # Try ultimate fallback to legacy action sink
                        if self.dependencies.action_sink:
                            try:
                                logger.info("Falling back to legacy action sink")
                                await self.dependencies.action_sink.send_message(numeric_channel_id_str, speak_content)
                                action_performed_successfully = True
                                follow_up_content_key_info = f"Spoke via fallback: '{str(speak_content)[:50]}...' in channel #{numeric_channel_id_str}"
                            except Exception as fallback_ex:
                                logger.exception(f"Legacy fallback also failed for thought {thought_id}: {fallback_ex}")
                                final_thought_status = ThoughtStatus.FAILED
                                follow_up_content_key_info = f"SPEAK action failed (all services): {str(fallback_ex)}"
                        else:
                            final_thought_status = ThoughtStatus.FAILED
                            follow_up_content_key_info = f"SPEAK action failed: {str(send_ex)}"
                else:
                    # Ultimate fallback to legacy action sink for backward compatibility
                    if self.dependencies.action_sink:
                        try:
                            logger.info("No communication service available, using legacy action sink")
                            numeric_channel_id_str = str(final_channel_id_to_speak).lstrip('#')
                            await self.dependencies.action_sink.send_message(numeric_channel_id_str, speak_content)
                            action_performed_successfully = True
                            follow_up_content_key_info = f"Spoke via legacy: '{str(speak_content)[:50]}...' in channel #{numeric_channel_id_str}"
                        except Exception as send_ex:
                            logger.exception(f"Error sending SPEAK message to channel {final_channel_id_to_speak}. Thought ID: {thought_id}: {send_ex}")
                            final_thought_status = ThoughtStatus.FAILED
                            follow_up_content_key_info = f"SPEAK action failed during send to {final_channel_id_to_speak}: {str(send_ex)}"
                    else:
                        logger.error(f"No communication services or ActionSink available. Cannot send SPEAK message for thought {thought_id}")
                        final_thought_status = ThoughtStatus.FAILED
                        follow_up_content_key_info = f"SPEAK action failed: No communication services or ActionSink available for thought {thought_id}."
            else:
                err_msg = "SPEAK action failed: "
                if not speak_content: err_msg += "Missing content. "
                if not final_channel_id_to_speak: err_msg += "Missing channel."
                self.logger.error(f"{err_msg} Thought ID: {thought_id}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = err_msg.strip()

        # Update original thought status
        # v1 uses 'status' instead of 'new_status'
        # Ensure final_action is always a dict for persistence (avoid Pydantic serialization warning)
        final_action_dump = {}
        if hasattr(result, 'model_dump'):
            final_action_dump = result.model_dump(mode="json")
        elif isinstance(result, dict):
            final_action_dump = result
        else:
            final_action_dump = {"result": str(result)}
            
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=final_action_dump,  # v1 field
        )
        logger.info(f"[SPEAK_HANDLER] Updated thought {thought_id} to status {final_thought_status.value} after SPEAK attempt.")
        print(f"[SPEAK_HANDLER] Updated thought {thought_id} to status {final_thought_status.value} after SPEAK attempt.")

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
            )
            
            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {"action_performed": HandlerActionType.SPEAK.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if hasattr(action_params_dump, 'model_dump'):
                action_params_dump = action_params_dump.model_dump(mode="json")
            elif not isinstance(action_params_dump, (dict, list, str, int, float, bool, type(None))):
                action_params_dump = str(action_params_dump)
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'
            persistence.add_thought(new_follow_up)
            
            # Follow-up thoughts are automatically picked up by the main processing loop
            # as PENDING thoughts, so no manual queueing is needed
            
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after SPEAK action."
            )
            print(f"[SPEAK_HANDLER] Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after SPEAK action.")
            await self._audit_log(
                HandlerActionType.SPEAK,
                {**dispatch_context, "thought_id": thought_id, "event_summary": event_summary},
                outcome="success" if action_performed_successfully else "failed"
            )
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            await self._audit_log(
                HandlerActionType.SPEAK,
                {**dispatch_context, "thought_id": thought_id, "event_summary": event_summary},
                outcome="failed_followup"
            )
            raise FollowUpCreationError from e

        # Ensure channel_id is set in the thought context for downstream consumers (e.g., guardrails)
        if hasattr(thought, "context"):
            if not thought.context:
                thought.context = {}
            if "channel_id" not in thought.context or not thought.context["channel_id"]:
                thought.context["channel_id"] = channel_id_from_params or original_event_channel_id or self.snore_channel_id
