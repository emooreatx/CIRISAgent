"""
Memorize handler - clean implementation using BusManager
"""

import logging
from typing import Optional

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType, DispatchContext
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from ciris_engine import persistence
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class MemorizeHandler(BaseActionHandler):
    """Handler for MEMORIZE actions."""
    
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """Handle a memorize action."""
        thought_id = thought.thought_id
        
        # Start audit logging
        await self._audit_log(HandlerActionType.MEMORIZE, dispatch_context, outcome="start")
        
        # Validate parameters
        try:
            params = await self._validate_and_convert_params(
                result.action_parameters,
                MemorizeParams
            )
        except Exception as e:
            await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result,
            )
            
            # Create failure follow-up
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"MEMORIZE action failed: {e}"
            )
            persistence.add_thought(follow_up)
            return follow_up.thought_id
        
        # Extract node from params - params is MemorizeParams
        assert isinstance(params, MemorizeParams)
        node = params.node
        scope = node.scope
        
        # Check if this is an identity node that requires WA authorization
        is_identity_node = (
            scope == GraphScope.IDENTITY or 
            node.id.startswith("agent/identity") or
            node.type == NodeType.AGENT
        )
        
        if is_identity_node and not dispatch_context.wa_authorized:
            self.logger.warning(
                f"WA authorization required for MEMORIZE to identity graph. "
                f"Thought {thought_id} denied."
            )
            
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result,
            )
            
            await self._audit_log(
                HandlerActionType.MEMORIZE,
                dispatch_context,
                outcome="failed_wa_required"
            )
            
            # Create follow-up for WA requirement
            follow_up = create_follow_up_thought(
                parent=thought,
                content="MEMORIZE action failed: WA authorization required for identity changes"
            )
            persistence.add_thought(follow_up)
            return follow_up.thought_id
        
        # Perform the memory operation through the bus
        try:
            memory_result = await self.bus_manager.memory.memorize(
                node=node,
                handler_name=self.__class__.__name__
            )
            
            success = memory_result.status == MemoryOpStatus.SUCCESS
            final_status = ThoughtStatus.COMPLETED if success else ThoughtStatus.FAILED
            
            # Update thought status
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_status,
                final_action=result,
            )
            
            # Create appropriate follow-up
            if success:
                follow_up_content = (
                    f"Successfully memorized node '{node.id}' "
                    f"of type {node.type.value} in scope {scope.value}"
                )
            else:
                follow_up_content = (
                    f"Failed to memorize node '{node.id}': "
                    f"{memory_result.reason or memory_result.error or 'Unknown error'}"
                )
            
            follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_content
            )
            
            # Add context to follow-up
            if follow_up.context:
                context_data = follow_up.context.model_dump()
            else:
                context_data = {}
                
            context_data.update({
                "action_performed": HandlerActionType.MEMORIZE.value,
                "memorized_node_id": node.id,
                "success": success
            })
            
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            
            persistence.add_thought(follow_up)
            
            # Final audit log
            await self._audit_log(
                HandlerActionType.MEMORIZE,
                dispatch_context,
                outcome="success" if success else "failed"
            )
            
            return follow_up.thought_id
            
        except Exception as e:
            await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
            
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result,
            )
            
            # Create error follow-up
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"MEMORIZE action failed with error: {e}"
            )
            persistence.add_thought(follow_up)
            
            raise FollowUpCreationError from e