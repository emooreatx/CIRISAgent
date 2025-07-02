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
            # Mark thought as failed and create error follow-up
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED
            )
            error_content = f"RECALL action failed: {str(e)}"
            follow_up_id = self.complete_thought_and_create_followup(
                thought=thought,
                follow_up_content=error_content,
                action_result=result
            )
            return follow_up_id
        # Memory operations will use the memory bus
        
        # Type assertion to help MyPy understand params is RecallParams
        assert isinstance(params, RecallParams)

        # Import MemorySearchFilter for search operations
        from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
        
        nodes = []
        
        # If node_id is provided, try exact match first
        if params.node_id:
            memory_query = MemoryQuery(
                node_id=params.node_id,
                scope=params.scope or GraphScope.LOCAL,
                type=NodeType(params.node_type) if params.node_type else None,
                include_edges=False,
                depth=1
            )
            nodes = await self.bus_manager.memory.recall(
                recall_query=memory_query,
                handler_name=self.__class__.__name__
            )
        
        # If no results with exact match OR if using query, try search
        if not nodes and (params.query or params.node_id):
            # Use the search method for flexible matching
            search_query = params.query or params.node_id or ""
            
            # Build search filter
            search_filter = MemorySearchFilter(
                node_type=params.node_type,
                scope=(params.scope or GraphScope.LOCAL).value,
                limit=params.limit
            )
            
            # Perform search
            nodes = await self.bus_manager.memory.search(
                query=search_query,
                filters=search_filter
            )
            # Trust the search results - don't filter them again

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

            # Convert data to string and check length
            data_str = str(data)
            if len(data_str) > 10000:
                # Truncate to first 10k characters
                truncated_data = data_str[:10000]
                follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{query_desc}' returned over {len(data_str)} characters, first 10000 characters: {truncated_data}"
            else:
                follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{query_desc}' returned: {data}"
        else:
            # Build descriptive query string
            query_desc = params.node_id or params.query or "recall request"
            if params.node_type:
                query_desc = f"{params.node_type} {query_desc}"
            scope_str = (params.scope or GraphScope.LOCAL).value

            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: No memories found for query '{query_desc}' in scope {scope_str}"
        # Use centralized method to complete thought and create follow-up
        follow_up_id = self.complete_thought_and_create_followup(
            thought=thought,
            follow_up_content=follow_up_content,
            action_result=result
        )
        
        await self._audit_log(
            HandlerActionType.RECALL,
            dispatch_context,
            outcome="success" if success and data else "failed",
        )
        return follow_up_id
