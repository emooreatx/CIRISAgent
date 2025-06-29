"""
Memorize handler - clean implementation using BusManager
"""

import logging
from typing import Optional

from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.actions import MemorizeParams
from ciris_engine.schemas.runtime.enums import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.services.graph_core import NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryOpStatus
from ciris_engine.logic import persistence
from ciris_engine.logic.infrastructure.handlers.base_handler import BaseActionHandler
from ciris_engine.logic.infrastructure.handlers.helpers import create_follow_up_thought
from ciris_engine.logic.infrastructure.handlers.exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)

class MemorizeHandler(BaseActionHandler):
    """Handler for MEMORIZE actions."""

    async def handle(
        self,
        result: ActionSelectionDMAResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """Handle a memorize action."""
        thought_id = thought.thought_id

        # Start audit logging
        await self._audit_log(HandlerActionType.MEMORIZE, dispatch_context, outcome="start")

        # Validate parameters
        try:
            params: MemorizeParams = await self._validate_and_convert_params(
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
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=f"MEMORIZE action failed: {e}"
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
                "WA authorization required for MEMORIZE to identity graph. "
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
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content="MEMORIZE action failed: WA authorization required for identity changes"
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
                # Extract meaningful content from the node
                content_preview = ""
                if hasattr(node, 'attributes') and node.attributes:
                    if 'content' in node.attributes:
                        content_preview = f": {node.attributes['content'][:100]}"
                    elif 'name' in node.attributes:
                        content_preview = f": {node.attributes['name']}"
                    elif 'value' in node.attributes:
                        content_preview = f": {node.attributes['value']}"

                follow_up_content = (
                    f"MEMORIZE COMPLETE - stored {node.type.value} '{node.id}'{content_preview}. "
                    "ACTION REQUIRED: Your next action should be SPEAK to inform the user that the information has been stored, "
                    "followed by TASK_COMPLETE. Do NOT memorize again - the information is already stored."
                )
            else:
                follow_up_content = (
                    f"Failed to memorize node '{node.id}': "
                    f"{memory_result.reason or memory_result.error or 'Unknown error'}"
                )

            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=follow_up_content
            )

            # The follow-up thought already has proper context from create_follow_up_thought
            # No need to modify it

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
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=f"MEMORIZE action failed with error: {e}")
            persistence.add_thought(follow_up)

            raise FollowUpCreationError from e
