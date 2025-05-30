import logging
from typing import Dict, Any

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ToolParams  # v1 uses ToolParams instead of ActParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus
import asyncio
import uuid

logger = logging.getLogger(__name__)

class ToolHandler(BaseActionHandler):
    TOOL_RESULT_TIMEOUT = 30  # seconds

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.TOOL, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        follow_up_content_key_info = f"TOOL action for thought {thought_id}"
        action_performed_successfully = False
        new_follow_up = None

        # Always use schema internally
        if isinstance(params, dict):
            try:
                params = ToolParams(**params)
            except Exception as e:
                self.logger.error(f"TOOL action params dict could not be parsed: {e}. Thought ID: {thought_id}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL action failed: Invalid parameters dict for thought {thought_id}. Error: {e}"
                params = None

        # Tool service validation and execution
        tool_service = await self.get_tool_service()
        if not isinstance(params, ToolParams):
            self.logger.error(
                f"TOOL action params are not ToolParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = (
                f"TOOL action failed: Invalid parameters type ({type(params)}) for thought {thought_id}.")
        elif not tool_service:
            self.logger.error("No ToolService available")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = "Tool service unavailable"
        elif not await tool_service.validate_parameters(params.name, params.args):
            self.logger.error(
                f"Arguments for tool '{params.name}' failed validation. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Arguments for tool '{params.name}' invalid."
        else:
            correlation_id = str(uuid.uuid4())
            try:
                await tool_service.execute_tool(params.name, {**params.args, "correlation_id": correlation_id})
                tool_result = await tool_service.get_tool_result(
                    correlation_id, timeout=self.TOOL_RESULT_TIMEOUT
                )
                if tool_result and tool_result.get("error") is None:
                    action_performed_successfully = True
                    follow_up_content_key_info = (
                        f"Tool '{params.name}' executed successfully. Result: {tool_result}"
                    )
                else:
                    final_thought_status = ThoughtStatus.FAILED
                    err = tool_result.get("error") if tool_result else "timeout"
                    follow_up_content_key_info = f"Tool '{params.name}' failed: {err}"
            except Exception as e_tool:
                self.logger.exception(
                    f"Error executing TOOL {params.name} for thought {thought_id}: {e_tool}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL {params.name} execution failed: {str(e_tool)}"

        # v1 uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result_data,  # v1 field
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after TOOL attempt.")

        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = f"TOOL action {params.name} executed for thought {thought_id}. Info: {follow_up_content_key_info}. Awaiting tool results or next steps. If task complete, use TASK_COMPLETE."
        else:
            follow_up_text = f"TOOL action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."
        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
            )
            context_for_follow_up = {"action_performed": HandlerActionType.TOOL.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info
            # When serializing for follow-up, convert to dict
            action_params_dump = params.model_dump(mode="json") if hasattr(params, "model_dump") else params
            context_for_follow_up["action_params"] = action_params_dump
            new_follow_up.context = context_for_follow_up
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after TOOL action."
            )
            await self._audit_log(HandlerActionType.TOOL, {**dispatch_context, "thought_id": thought_id}, outcome="success" if action_performed_successfully else "failed")
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            await self._audit_log(HandlerActionType.TOOL, {**dispatch_context, "thought_id": thought_id}, outcome="failed_followup")
            raise FollowUpCreationError from e
