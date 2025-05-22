import logging
from typing import Dict, Any, Optional

from pydantic import BaseModel

from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, MemorizeParams, Thought
from ciris_engine.core.foundational_schemas import ThoughtStatus, HandlerActionType # Added HandlerActionType
from ciris_engine.core import persistence
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from ..exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)

class MemorizeHandler(BaseActionHandler):
    async def _get_user_nick_for_memory(self, params: MemorizeParams, dispatch_context: Dict[str, Any], thought_id: Optional[str]) -> Optional[str]:
        """Helper to determine user nickname for memory operations."""
        user_nick: Optional[str] = None
        if isinstance(params.knowledge_data, dict):
            user_nick = params.knowledge_data.get("nick")
            if user_nick: return user_nick
            user_nick = params.knowledge_data.get("user_id") # Check for user_id as well
            if user_nick: return user_nick
        
        user_nick = dispatch_context.get("author_name") # From original event context
        if user_nick: return user_nick

        # Fallback to checking parent task context if thought_id is available
        if thought_id:
            try:
                current_thought = persistence.get_thought_by_id(thought_id)
                if current_thought and current_thought.source_task_id:
                    parent_task = persistence.get_task_by_id(current_thought.source_task_id)
                    if parent_task and isinstance(parent_task.context, dict):
                        user_nick = parent_task.context.get("author_name")
                        if user_nick: return user_nick
                        # Could also check for a user_id in task context if that's a pattern
                        user_nick = parent_task.context.get("user_id")
                        if user_nick: return user_nick
            except Exception as e_fetch:
                self.logger.error(f"Error fetching parent task context for thought {thought_id} to find user_nick: {e_fetch}")
        
        self.logger.warning(f"Could not determine user_nick for MEMORIZE operation related to thought {thought_id}.")
        return None

    async def handle(
        self,
        result: ActionSelectionPDMAResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id

        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"MEMORIZE action for thought {thought_id}"

        if not isinstance(params, MemorizeParams):
            self.logger.error(f"MEMORIZE action params are not MemorizeParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"MEMORIZE action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif not self.dependencies.memory_service:
            self.logger.error(f"MemoryService not available. Cannot perform MEMORIZE for thought {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"MEMORIZE action failed: MemoryService unavailable for thought {thought_id}."
        else:
            user_nick = await self._get_user_nick_for_memory(params, dispatch_context, thought_id)
            # Channel from params.channel_metadata, fallback to dispatch_context.channel_id
            channel_from_meta = params.channel_metadata.get("channel") if isinstance(params.channel_metadata, dict) else None
            channel = channel_from_meta or dispatch_context.get("channel_id")
            
            metadata = params.knowledge_data if isinstance(params.knowledge_data, dict) else {"data": str(params.knowledge_data)}

            if not user_nick or not channel:
                self.logger.error(f"MEMORIZE failed for thought {thought_id}: Missing user_nick ('{user_nick}') or channel ('{channel}').")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"MEMORIZE action failed: Missing user_nick or channel for thought {thought_id}."
            else:
                try:
                    mem_op_result = await self.dependencies.memory_service.memorize(
                        user_nick=str(user_nick),
                        channel=str(channel),
                        metadata=metadata,
                        channel_metadata=params.channel_metadata, # Pass full channel_metadata
                        is_correction=dispatch_context.get("is_wa_correction", False) # from original context
                    )
                    if mem_op_result.status == MemoryOpStatus.SAVED:
                        action_performed_successfully = True
                        follow_up_content_key_info = f"Memorization successful. Knowledge: '{str(params.knowledge_data)[:50]}...'"
                    else:
                        self.logger.error(f"Memorization operation status: {mem_op_result.status.name}. Reason: {mem_op_result.reason}. Thought ID: {thought_id}")
                        final_thought_status = ThoughtStatus.FAILED if mem_op_result.status == MemoryOpStatus.FAILED else ThoughtStatus.DEFERRED
                        follow_up_content_key_info = f"Memorization status {mem_op_result.status.name}: {mem_op_result.reason}"
                except Exception as e_mem:
                    self.logger.exception(f"Error during MEMORIZE operation for thought {thought_id}: {e_mem}")
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"MEMORIZE action failed due to exception: {str(e_mem)}"
        
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action_result=result.model_dump(),
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after MEMORIZE attempt.")

        # Create follow-up thought
        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = (
                f"Memorization successful for original thought {thought_id} (Task: {thought.source_task_id}). "
                f"Info: {follow_up_content_key_info}. "
                "Consider informing the user with SPEAK or select TASK_COMPLETE if the overall task is finished."
            )
        else: # Failed or Deferred
            follow_up_text = f"MEMORIZE action for thought {thought_id} resulted in status {final_thought_status.value}. Info: {follow_up_content_key_info}. Review and determine next steps."

        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
                priority_offset=1 if action_performed_successfully else 0,
            )

            processing_ctx_for_follow_up = {
                "action_performed": HandlerActionType.MEMORIZE.value
            }
            if final_thought_status != ThoughtStatus.COMPLETED:
                processing_ctx_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
            processing_ctx_for_follow_up["action_params"] = action_params_dump

            new_follow_up.processing_context = processing_ctx_for_follow_up
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after MEMORIZE action."
            )
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            raise FollowUpCreationError from e
