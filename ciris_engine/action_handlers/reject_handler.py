import logging
from typing import Dict, Any
from datetime import datetime, timezone
import re

from ciris_engine.schemas import Thought, RejectParams, ThoughtStatus, TaskStatus, HandlerActionType, ActionSelectionResult, DispatchContext, ServiceType
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
from ciris_engine.utils.channel_utils import extract_channel_id
from ciris_engine.schemas.filter_schemas_v1 import FilterTrigger, TriggerType, FilterPriority
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.agent_core_schemas_v1 import Task, ThoughtType
from ciris_engine import persistence
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class RejectHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id
        await self._audit_log(HandlerActionType.REJECT, dispatch_context, outcome="start")
        original_event_channel_id = extract_channel_id(dispatch_context.channel_context)

        try:
            params = await self._validate_and_convert_params(raw_params, RejectParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.REJECT, dispatch_context, thought_id, e)
            final_thought_status = ThoughtStatus.FAILED
            await self._audit_log(HandlerActionType.REJECT, dispatch_context, outcome="failed")
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_thought_status,
                final_action=result,
            )
            return
        final_thought_status = ThoughtStatus.FAILED 
        action_performed_successfully = False
        follow_up_content_key_info = f"REJECT action for thought {thought_id}"

        if not isinstance(params, RejectParams):
            self.logger.error(f"REJECT action params are not RejectParams model. Type: {type(params)}. Thought ID: {thought_id}")
            follow_up_content_key_info = f"REJECT action failed: Invalid parameters type ({type(params)}) for thought {thought_id}. Original reason might be lost."
        else:
            follow_up_content_key_info = f"Rejected thought {thought_id}. Reason: {params.reason}"
            if original_event_channel_id and params.reason:
                try:
                    # Use the communication bus
                    await self.bus_manager.communication.send_message(
                        channel_id=original_event_channel_id,
                        content=f"Unable to proceed: {params.reason}",
                        handler_name=self.__class__.__name__
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to send REJECT notification via communication service for thought {thought_id}: {e}"
                    )
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        if parent_task_id:
            persistence.update_task_status(parent_task_id, TaskStatus.REJECTED)
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for REJECT action. Info: {follow_up_content_key_info}")

        # Handle adaptive filtering if requested
        if isinstance(params, RejectParams) and params.create_filter:
            await self._create_adaptive_filter(params, thought, dispatch_context)

        # REJECT is a terminal action - no follow-up thoughts should be created
        self.logger.info(f"REJECT action completed for thought {thought_id}. This is a terminal action.")
        await self._audit_log(HandlerActionType.REJECT, dispatch_context, outcome="success")

    async def _create_adaptive_filter(self, params: RejectParams, thought: Thought, dispatch_context: DispatchContext) -> None:
        """Create an adaptive filter based on the rejected content."""
        # TODO: Implement filter bus when needed
        self.logger.info("Adaptive filter creation not implemented in new bus architecture")
