from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RecallParams
from ciris_engine.services.memory_service import MemoryOpStatus
from ciris_engine.protocols.services import MemoryService
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, DispatchContext
from ciris_engine import persistence
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RecallHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: DispatchContext) -> Optional[str]:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.RECALL, dispatch_context, outcome="start")
        try:
            params = await self._validate_and_convert_params(raw_params, RecallParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.RECALL, dispatch_context, thought_id, e)
            follow_up = create_follow_up_thought(
                parent=thought,
                content=ThoughtStatus.PENDING
            )
            persistence.add_thought(follow_up)
            return None
        # Memory operations will use the memory bus

        node = params.node  # type: ignore[attr-defined]
        scope = node.scope

        memory_result = await self.bus_manager.memory.recall(
            node=node,
            handler_name=self.__class__.__name__
        )
        success = memory_result.status == MemoryOpStatus.OK
        data = memory_result.data

        if success and data:
            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{node.id}' returned: {data}"
        else:
            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: No memories found for query '{node.id}' in scope {node.scope.value}"
        follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_content,
        )
        context_data = follow_up.context.model_dump() if follow_up.context else {}
        follow_up_context = {
            "action_performed": HandlerActionType.RECALL.name,
            "is_follow_up": True,
        }
        if not success:
            follow_up_context["error_details"] = str(memory_result.status)
        context_data.update(follow_up_context)
        from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
        follow_up.context = ThoughtContext.model_validate(context_data)
        persistence.add_thought(follow_up)
        await self._audit_log(
            HandlerActionType.RECALL,
            dispatch_context,
            outcome="success" if success and data else "failed",
        )
        return follow_up.thought_id
