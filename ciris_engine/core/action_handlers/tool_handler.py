import logging
from typing import Dict, Any

from pydantic import BaseModel

from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, ActParams, Thought
from ciris_engine.core.foundational_schemas import ThoughtStatus, HandlerActionType # Added HandlerActionType
from ciris_engine.core import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought

logger = logging.getLogger(__name__)

class ToolHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionPDMAResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id

        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"TOOL action for thought {thought_id}"

        if not isinstance(params, ActParams):
            self.logger.error(f"TOOL action params are not ActParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif not self.dependencies.action_sink or not hasattr(self.dependencies.action_sink, 'run_tool'):
            self.logger.error(f"ActionSink or run_tool method not available. Cannot execute TOOL for thought {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: ActionSink or run_tool unavailable for thought {thought_id}."
        else:
            try:
                # The run_tool method on ActionSink is expected to be async if it involves I/O
                await self.dependencies.action_sink.run_tool(params.tool_name, params.arguments)
                action_performed_successfully = True
                follow_up_content_key_info = f"Executed tool: {params.tool_name} with args {params.arguments}."
                # Actual result of the tool execution would typically be an observation event handled elsewhere,
                # or this handler might need to be adapted if tool results are returned directly.
                # For now, we assume the tool execution is fire-and-forget from the handler's perspective,
                # and any results come back as new observations/events.
            except Exception as e_tool:
                self.logger.exception(f"Error executing TOOL {params.tool_name} for thought {thought_id}: {e_tool}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL {params.tool_name} execution failed: {str(e_tool)}"

        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action_result=result.model_dump(),
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after TOOL attempt.")

        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = f"TOOL action {params.tool_name} executed for thought {thought_id}. Info: {follow_up_content_key_info}. Awaiting tool results or next steps. If task complete, use TASK_COMPLETE."
        else:
            follow_up_text = f"TOOL action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."
        
        new_follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_text,
            priority_offset= 1 if action_performed_successfully else 0 # Higher if success, normal if fail
        )
        
        processing_ctx_for_follow_up = {"action_performed": HandlerActionType.TOOL.value}
        if final_thought_status == ThoughtStatus.FAILED:
            processing_ctx_for_follow_up["error_details"] = follow_up_content_key_info
        
        action_params_dump = result.action_parameters
        if isinstance(action_params_dump, BaseModel):
            action_params_dump = action_params_dump.model_dump(mode="json")
        processing_ctx_for_follow_up["action_params"] = action_params_dump
        
        new_follow_up.processing_context = processing_ctx_for_follow_up
        
        persistence.add_thought(new_follow_up)
        self.logger.info(f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after TOOL action.")
