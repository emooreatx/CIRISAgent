from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.actions import RecallParams
from ciris_engine.schemas.services.operations import MemoryQuery
from ciris_engine.schemas.services.graph_core import GraphScope, NodeType
from ciris_engine.logic.infrastructure.handlers.base_handler import BaseActionHandler
from ciris_engine.logic.infrastructure.handlers.helpers import create_follow_up_thought
from ciris_engine.schemas.runtime.enums import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.logic import persistence
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RecallHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionDMAResult, thought: Thought, dispatch_context: DispatchContext) -> Optional[str]:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.RECALL, dispatch_context, outcome="start")
        try:
            params: RecallParams = await self._validate_and_convert_params(raw_params, RecallParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.RECALL, dispatch_context, thought_id, e)
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=ThoughtStatus.PENDING
            )
            persistence.add_thought(follow_up)
            return None
        # Memory operations will use the memory bus
        
        # Type assertion to help MyPy understand params is RecallParams
        assert isinstance(params, RecallParams)

        # Create MemoryQuery from RecallParams
        # If node_id is provided, use it directly
        if params.node_id:
            memory_query = MemoryQuery(
                node_id=params.node_id,
                scope=params.scope or GraphScope.LOCAL,
                type=NodeType(params.node_type) if params.node_type else None,
                include_edges=False,
                depth=1
            )
        else:
            # If no node_id, we need to handle query-based recall
            # For now, we'll create a placeholder query
            # The memory service should handle text-based queries
            memory_query = MemoryQuery(
                node_id=params.query or "query_recall",
                scope=params.scope or GraphScope.LOCAL,
                type=NodeType(params.node_type) if params.node_type else None,
                include_edges=False,
                depth=1
            )

        nodes = await self.bus_manager.memory.recall(
            recall_query=memory_query,
            handler_name=self.__class__.__name__
        )

        success = bool(nodes)

        if success:
            # Format the recalled nodes for display
            data = {}
            for n in nodes:
                # GraphNode object
                if n.attributes:
                    data[n.id] = n.attributes

            # Build descriptive query string
            query_desc = params.node_id or params.query or "recall request"
            if params.node_type:
                query_desc = f"{params.node_type} {query_desc}"

            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{query_desc}' returned: {data}"
        else:
            # Build descriptive query string
            query_desc = params.node_id or params.query or "recall request"
            if params.node_type:
                query_desc = f"{params.node_type} {query_desc}"
            scope_str = (params.scope or GraphScope.LOCAL).value

            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: No memories found for query '{query_desc}' in scope {scope_str}"
        follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=follow_up_content,
        )
        # The follow-up thought already has proper context from create_follow_up_thought
        # No need to modify it
        persistence.add_thought(follow_up)
        await self._audit_log(
            HandlerActionType.RECALL,
            dispatch_context,
            outcome="success" if success and data else "failed",
        )
        return follow_up.thought_id
