import logging
from typing import Dict, Any, Optional


# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from ciris_engine.protocols.services import MemoryService
from ciris_engine.adapters.local_graph_memory import MemoryOpResult, MemoryOpStatus
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

        try:
            params = await self._validate_and_convert_params(raw_params, MemorizeParams)
        except Exception as e:
            if isinstance(raw_params, dict) and "knowledge_unit_description" in raw_params:
                from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
                scope = GraphScope(raw_params.get("scope", "local"))
                node = GraphNode(
                    id=raw_params.get("knowledge_unit_description", "memory"),
                    type=NodeType.CONCEPT if scope == GraphScope.IDENTITY else NodeType.USER,
                    scope=scope,
                    attributes={"value": raw_params.get("knowledge_data", {})}
                )
                params = MemorizeParams(node=node)
            else:
                logger.error(f"Invalid memorize params: {e}")
                await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"MEMORIZE action failed: {e}"
                persistence.update_thought_status(
                    thought_id=thought_id,
                    status=final_thought_status,
                    final_action=result,
                )
                return

        from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

        memory_service: Optional[MemoryService] = await self.get_memory_service()

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
            scope = params.node.scope
            if scope in (GraphScope.IDENTITY, GraphScope.ENVIRONMENT) and not dispatch_context.get("wa_authorized"):
                self.logger.warning(
                    f"WA authorization required for MEMORIZE in scope {scope}. Thought {thought_id} denied."
                )
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = "WA authorization missing"
            else:
                node = params.node
                node.attributes.setdefault("source", thought.source_task_id)
                try:
                    mem_op = await memory_service.memorize(node)
                    success = False
                    reason = None
                    if isinstance(mem_op, bool):
                        success = mem_op
                    elif hasattr(mem_op, "status"):
                        success = str(getattr(mem_op, "status")) in {"ok", "OK", "saved", "SAVED"}
                        reason = getattr(mem_op, "reason", None)
                    else:
                        success = bool(mem_op)

                    if success:
                        action_performed_successfully = True
                        follow_up_content_key_info = f"Memorization successful. Key: '{node.id}'"
                    else:
                        final_thought_status = ThoughtStatus.DEFERRED
                        follow_up_content_key_info = reason or "Memory operation failed"
                except Exception as e_mem:
                    await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e_mem)
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"Exception during memory operation: {e_mem}"

        # Pass ActionSelectionResult directly to persistence - it handles serialization
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,  # Pass the ActionSelectionResult object directly
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
        #PROMPT_FOLLOW_UP_THOUGHT

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

            # Pass action parameters directly - persistence will handle serialization
            context_for_follow_up["action_params"] = result.action_parameters

            if isinstance(new_follow_up.context, dict):
                new_follow_up.context.update(context_for_follow_up)  # v1 uses 'context'
            else:
                new_follow_up.context = context_for_follow_up
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after MEMORIZE action."
            )
            await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="success")
        except Exception as e:
            await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e
