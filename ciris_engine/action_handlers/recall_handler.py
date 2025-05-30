from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RecallParams
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class RecallHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: dict) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        params = None
        if isinstance(raw_params, dict):
            try:
                params = RecallParams(**raw_params)
            except ValidationError as e:
                logger.error(f"RecallHandler: Invalid params dict: {e}")
                follow_up = create_follow_up_thought(
                    parent=thought,
                    content=f"RECALL action failed: Invalid parameters. {e}"
                )
                self.dependencies.persistence.add_thought(follow_up)
                await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
                return
        elif isinstance(raw_params, RecallParams):
            params = raw_params
        else:
            logger.error(f"RecallHandler: Invalid params type: {type(raw_params)}")
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"RECALL action failed: Invalid parameters type: {type(raw_params)}"
            )
            self.dependencies.persistence.add_thought(follow_up)
            await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
            return
        scope = GraphScope(params.scope)
        # Build a GraphNode for the query (id is the query string)
        node = GraphNode(
            id=params.query,
            type=NodeType.CONCEPT if params.scope == "identity" else NodeType.USER,
            scope=scope,
            attributes={}
        )
        memory_result = await self.dependencies.memory_service.recall(node)
        if memory_result.status == MemoryOpStatus.OK and memory_result.data:
            follow_up_content = f"Memory query '{params.query}' returned: {memory_result.data}"
        else:
            follow_up_content = f"No memories found for query '{params.query}' in scope {params.scope}"
        follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_content,
        )
        # Always set action_performed and is_follow_up in context
        follow_up_context = follow_up.context if isinstance(follow_up.context, dict) else {}
        follow_up_context["action_performed"] = "RECALL"
        follow_up_context["is_follow_up"] = True
        # Optionally add error or memory details if available
        if memory_result and hasattr(memory_result, "status") and memory_result.status != "OK":
            follow_up_context["error_details"] = str(memory_result.status)
        follow_up.context = follow_up_context
        self.dependencies.persistence.add_thought(follow_up)
        await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="success" if memory_result.status == MemoryOpStatus.OK and memory_result.data else "failed")
