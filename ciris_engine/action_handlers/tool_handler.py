import logging
from typing import Dict, Any


from ciris_engine.schemas import Thought, ToolParams, ThoughtStatus, HandlerActionType, ActionSelectionResult
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus
from ciris_engine import persistence
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError
import uuid

logger = logging.getLogger(__name__)

class ToolHandler(BaseActionHandler):
    TOOL_RESULT_TIMEOUT = 30

    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.TOOL, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        follow_up_content_key_info = f"TOOL action for thought {thought_id}"
        action_performed_successfully = False
        new_follow_up = None

        try:
            # Auto-decapsulate any secrets in the action parameters
            processed_result = await self._decapsulate_secrets_in_params(result, "tool")
            
            params = await self._validate_and_convert_params(processed_result.action_parameters, ToolParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.TOOL, dispatch_context, thought_id, e)
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: {e}"
            params = None

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
        elif not await tool_service.validate_parameters(params.name, params.parameters):
            self.logger.error(
                f"Arguments for tool '{params.name}' failed validation. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Arguments for tool '{params.name}' invalid."
        else:
            correlation_id = str(uuid.uuid4())
            try:
                await tool_service.execute_tool(params.name, {**params.parameters, "correlation_id": correlation_id})
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
                await self._handle_error(HandlerActionType.TOOL, dispatch_context, thought_id, e_tool)
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL {params.name} execution failed: {str(e_tool)}"

        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after TOOL attempt.")

        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = f"CIRIS_FOLLOW_UP_THOUGHT: TOOL action {params.name} executed for thought {thought_id}. Info: {follow_up_content_key_info}. Awaiting tool results or next steps. If task complete, use TASK_COMPLETE."
        else:
            follow_up_text = f"CIRIS_FOLLOW_UP_THOUGHT: TOOL action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."
        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
            )
            context_for_follow_up = {"action_performed": HandlerActionType.TOOL.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info
            context_for_follow_up["action_params"] = params
            if isinstance(new_follow_up.context, dict):
                new_follow_up.context.update(context_for_follow_up)
            else:
                new_follow_up.context = context_for_follow_up
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after TOOL action."
            )
            await self._audit_log(HandlerActionType.TOOL, {**dispatch_context, "thought_id": thought_id}, outcome="success" if action_performed_successfully else "failed")
        except Exception as e:
            await self._handle_error(HandlerActionType.TOOL, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e
