from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import RecallParams
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.adapters.local_graph_memory import MemoryOpResult, MemoryOpStatus
from ciris_engine.protocols.services import MemoryService
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
        params = raw_params
        if not isinstance(params, RecallParams):
            try:
                params = RecallParams(**params) if isinstance(params, dict) else params
            except ValidationError as e:
                logger.error(f"RecallHandler: Invalid params dict: {e}")
                follow_up = create_follow_up_thought(
                    parent=thought,
                    content=f"RECALL action failed: Invalid parameters. {e}"
                )
                self.dependencies.persistence.add_thought(follow_up)
                await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
                return
        if not isinstance(params, RecallParams):
            logger.error(f"RecallHandler: Invalid params type: {type(raw_params)}")
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"RECALL action failed: Invalid parameters type: {type(raw_params)}"
            )
            self.dependencies.persistence.add_thought(follow_up)
            await self._audit_log(HandlerActionType.RECALL, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
            return
        memory_service: Optional[MemoryService] = await self.get_memory_service()

        if not memory_service:
            logger.error(
                "RecallHandler: MemoryService not available"
            )
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"RECALL action failed: MemoryService unavailable for thought {thought_id}"
            )
            self.dependencies.persistence.add_thought(follow_up)
            await self._audit_log(
                HandlerActionType.RECALL,
                {**dispatch_context, "thought_id": thought_id},
                outcome="failed_no_memory_service",
            )
            return

        scope = GraphScope(params.scope)

        node = GraphNode(
            id=params.query,
            type=NodeType.CONCEPT if scope == GraphScope.IDENTITY else NodeType.USER,
            scope=scope,
            attributes={}
        )

        memory_result = await memory_service.recall(node)
        success = False
        data = None
        if isinstance(memory_result, bool):
            success = memory_result
        elif hasattr(memory_result, "status"):
            success = memory_result.status == MemoryOpStatus.OK
            data = getattr(memory_result, "data", None)
        else:
            success = bool(memory_result)
            data = memory_result if success else None

        if success and data:
            follow_up_content = f"Memory query '{params.query}' returned: {data}"
        else:
            follow_up_content = f"No memories found for query '{params.query}' in scope {params.scope}"
        follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_content,
        )
        # Always set action_performed and is_follow_up in context
        follow_up_context = follow_up.context if isinstance(follow_up.context, dict) else {}
        follow_up_context["action_performed"] = HandlerActionType.RECALL.name
        follow_up_context["is_follow_up"] = True
        # Optionally add error or memory details if available
        if not success:
            if isinstance(memory_result, MemoryOpResult):
                follow_up_context["error_details"] = str(memory_result.status)
            else:
                follow_up_context["error_details"] = "recall_failed"
        follow_up.context = follow_up_context
        self.dependencies.persistence.add_thought(follow_up)
        await self._audit_log(
            HandlerActionType.RECALL,
            {**dispatch_context, "thought_id": thought_id},
            outcome="success" if success and data else "failed",
        )
