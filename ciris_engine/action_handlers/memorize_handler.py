import logging
from typing import Dict, Any, Optional

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from ciris_engine.adapters.local_graph_memory import MemoryOpStatus
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError
from ciris_engine.utils import extract_user_nick

logger = logging.getLogger(__name__)


class MemorizeHandler(BaseActionHandler):

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"MEMORIZE action for thought {thought_id}"

        # Handle both dict and MemorizeParams
        from pydantic import ValidationError
        params = raw_params
        if not isinstance(params, MemorizeParams):
            try:
                params = MemorizeParams(**params) if isinstance(params, dict) else params
            except ValidationError as e:
                # Try to map old format to new
                if "knowledge_unit_description" in raw_params:
                    params = MemorizeParams(
                        key=raw_params.get("knowledge_unit_description", "memory"),
                        value=raw_params.get("knowledge_data", {}),
                        scope=raw_params.get("scope", "local")
                    )
                else:
                    logger.error(f"Invalid memorize params: {e}")
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"MEMORIZE action failed: Invalid parameters type ({type(raw_params)}) for thought {thought_id}. Error: {e}"
                    await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="failed_invalid_params")
                    # v1 uses 'final_action' instead of 'final_action_result'
                    result_data = result.model_dump() if hasattr(result, 'model_dump') else result
                    persistence.update_thought_status(
                        thought_id=thought_id,
                        status=final_thought_status,
                        final_action=result_data,  # v1 field
                    )
                    return
        if not isinstance(params, MemorizeParams):
            logger.error(f"Invalid params type: {type(raw_params)}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"MEMORIZE action failed: Invalid parameters type ({type(raw_params)}) for thought {thought_id}."
            await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="failed_invalid_params")
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_thought_status,
                final_action=result.model_dump() if hasattr(result, 'model_dump') else result,
            )
            return

        from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

        memory_service = await self.get_memory_service()

        if not memory_service:
            self.logger.error(
                f"MemoryService not available. Cannot perform MEMORIZE for thought {thought_id}"
            )
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = (
                f"MEMORIZE action failed: MemoryService unavailable for thought {thought_id}."
            )
            await self._audit_log(
                HandlerActionType.MEMORIZE,
                {**dispatch_context, "thought_id": thought_id},
                outcome="failed_no_memory_service",
            )
        else:
            user_nick = await extract_user_nick(
                params=params,
                dispatch_context=dispatch_context,
                thought_id=thought_id,
            )
            channel = dispatch_context.get("channel_id")
            # --- v1 graph node creation ---
            node = GraphNode(
                id=params.key,
                type=NodeType.CONCEPT if params.scope == "identity" else NodeType.USER,
                scope=GraphScope(params.scope),
                attributes={"value": params.value, "source": thought.source_task_id}
            )
            try:
                mem_op_result = await memory_service.memorize(node)
                if mem_op_result.status == MemoryOpStatus.OK:
                    action_performed_successfully = True
                    follow_up_content_key_info = f"Memorization successful. Key: '{params.key}', Value: '{str(params.value)[:50]}...'"
                else:
                    status_str = mem_op_result.status.name if hasattr(mem_op_result.status, 'name') else str(mem_op_result.status)
                    self.logger.error(f"Memorization operation status: {status_str}. Reason: {mem_op_result.reason}. Thought ID: {thought_id}")
                    final_thought_status = ThoughtStatus.FAILED if mem_op_result.status == MemoryOpStatus.DENIED else ThoughtStatus.DEFERRED
                    follow_up_content_key_info = f"Memorization status {status_str}: {mem_op_result.reason}"
            except Exception as e_mem:
                self.logger.exception(f"Error during MEMORIZE operation for thought {thought_id}: {e_mem}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"MEMORIZE action failed due to exception: {str(e_mem)}"

        # v1 uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result_data,  # v1 field
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
        else:  # Failed or Deferred
            follow_up_text = f"MEMORIZE action for thought {thought_id} resulted in status {final_thought_status.value}. Info: {follow_up_content_key_info}. Review and determine next steps."

        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
            )

            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {
                "action_performed": HandlerActionType.MEMORIZE.value
            }
            if final_thought_status != ThoughtStatus.COMPLETED:
                context_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if hasattr(action_params_dump, 'model_dump'):
                action_params_dump = action_params_dump.model_dump(mode="json")
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after MEMORIZE action."
            )
            await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="success")
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            raise FollowUpCreationError from e