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
from typing import Optional, Dict, Any

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
            follow_up_id = await self.complete_thought_and_create_followup(
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
        # ALWAYS try search if no exact match found
        if not nodes:
            # Use the search method for flexible matching
            search_query = params.query or params.node_id or params.node_type or ""
            
            # Build search filter
            search_filter = MemorySearchFilter(
                node_type=params.node_type,
                scope=(params.scope or GraphScope.LOCAL).value,
                limit=params.limit
            )
            
            # Perform search - this will search in node IDs and attributes
            logger.info(f"No exact match for recall, trying search with query: '{search_query}', type: {params.node_type}")
            nodes = await self.bus_manager.memory.search(
                query=search_query,
                filters=search_filter
            )
            
            # If still no results and we have a node_type, try getting all nodes of that type
            if not nodes and params.node_type and not params.query and not params.node_id:
                # Get all nodes of the specified type
                wildcard_query = MemoryQuery(
                    node_id="*",  # Wildcard
                    scope=params.scope or GraphScope.LOCAL,
                    type=NodeType(params.node_type),
                    include_edges=False,
                    depth=1
                )
                nodes = await self.bus_manager.memory.recall(
                    recall_query=wildcard_query,
                    handler_name=self.__class__.__name__
                )
                # Apply limit if we got all nodes
                if nodes and len(nodes) > params.limit:
                    nodes = nodes[:params.limit]

        success = bool(nodes)

        if success:
            # Format the recalled nodes with enhanced information
            import json
            enhanced_data = {}
            
            for n in nodes:
                node_info: Dict[str, Any] = {
                    "type": n.type,
                    "scope": n.scope,
                    "attributes": n.attributes if isinstance(n.attributes, dict) else {}
                }
                
                # Get connected nodes for each recalled node
                try:
                    from ciris_engine.logic.persistence.models.graph import get_edges_for_node
                    edges = get_edges_for_node(n.id, n.scope)
                    
                    if edges:
                        connected_nodes = []
                        for edge in edges:
                            # Get the connected node
                            connected_node_id = edge.target if edge.source == n.id else edge.source
                            connected_query = MemoryQuery(
                                node_id=connected_node_id,
                                scope=edge.scope,
                                include_edges=False,
                                depth=1
                            )
                            try:
                                connected_results = await self.bus_manager.memory.recall(
                                    recall_query=connected_query,
                                    handler_name=self.__class__.__name__
                                )
                                if connected_results:
                                    connected_node = connected_results[0]
                                    connected_attrs = connected_node.attributes if isinstance(connected_node.attributes, dict) else {}
                                    connected_nodes.append({
                                        'node_id': connected_node.id,
                                        'node_type': connected_node.type,
                                        'relationship': edge.relationship,
                                        'direction': 'outgoing' if edge.source == n.id else 'incoming',
                                        'attributes': connected_attrs
                                    })
                            except Exception as e:
                                logger.debug(f"Failed to get connected node {connected_node_id}: {e}")
                        
                        if connected_nodes:
                            node_info["connected_nodes"] = connected_nodes
                            
                except Exception as e:
                    logger.warning(f"Failed to get edges for node {n.id}: {e}")
                
                enhanced_data[n.id] = node_info

            # Build descriptive query string
            query_desc = params.node_id or params.query or "recall request"
            if params.node_type:
                query_desc = f"{params.node_type} {query_desc}"

            # Convert data to string and check length
            data_str = json.dumps(enhanced_data, indent=2, default=str)
            if len(data_str) > 10000:
                # Truncate to first 10k characters
                truncated_data = data_str[:10000]
                follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{query_desc}' returned over {len(data_str)} characters, first 10000 characters: {truncated_data}"
            else:
                follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: Memory query '{query_desc}' returned: {data_str}"
        else:
            # Build descriptive query string
            query_desc = params.node_id or params.query or "recall request"
            if params.node_type:
                query_desc = f"{params.node_type} {query_desc}"
            scope_str = (params.scope or GraphScope.LOCAL).value

            follow_up_content = f"CIRIS_FOLLOW_UP_THOUGHT: No memories found for query '{query_desc}' in scope {scope_str}"
        # Use centralized method to complete thought and create follow-up
        follow_up_id = await self.complete_thought_and_create_followup(
            thought=thought,
            follow_up_content=follow_up_content,
            action_result=result
        )
        
        await self._audit_log(
            HandlerActionType.RECALL,
            dispatch_context,
            outcome="success" if success else "failed",
        )
        return follow_up_id
