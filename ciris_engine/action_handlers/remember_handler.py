from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RememberParams
from ciris_engine.schemas.graph_schemas_v1 import GraphScope
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
import logging

logger = logging.getLogger(__name__)

class RememberHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: dict) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.REMEMBER, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        if not isinstance(params, RememberParams):
            logger.error(f"RememberHandler: Invalid params type: {type(params)}")
            return
        scope = GraphScope(params.scope)
        memory_result = await self.dependencies.memory_service.remember(
            params.query,
            scope
        )
        if memory_result.status == MemoryOpStatus.OK and memory_result.data:
            follow_up_content = f"Memory query '{params.query}' returned: {memory_result.data}"
        else:
            follow_up_content = f"No memories found for query '{params.query}' in scope {params.scope}"
        follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_content,
        )
        self.dependencies.persistence.add_thought(follow_up)
        await self._audit_log(HandlerActionType.REMEMBER, {**dispatch_context, "thought_id": thought_id}, outcome="success" if memory_result.status == MemoryOpStatus.OK and memory_result.data else "failed")
