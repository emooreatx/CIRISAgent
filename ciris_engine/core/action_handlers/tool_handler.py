import logging
from typing import Dict, Any

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ToolParams  # v1 uses ToolParams instead of ActParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.core import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from ..exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class ToolHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id

        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"TOOL action for thought {thought_id}"

        if not isinstance(params, ToolParams):  # v1 uses ToolParams
            self.logger.error(f"TOOL action params are not ToolParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif not self.dependencies.action_sink or not hasattr(self.dependencies.action_sink, 'run_tool'):
            self.logger.error(f"ActionSink or run_tool method not available. Cannot execute TOOL for thought {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: ActionSink or run_tool unavailable for thought {thought_id}."
        else:
            try:
                # The run_tool method on ActionSink is expected to be async if it involves I/O
                # v1 ToolParams has 'name' and 'args' fields instead of 'tool_name' and 'arguments'
                await self.dependencies.action_sink.run_tool(params.name, params.args)
                action_performed_successfully = True
                follow_up_content_key_info = f"Executed tool: {params.name} with args {params.args}."
                # Actual result of the tool execution would typically be an observation event handled elsewhere,
                # or this handler might need to be adapted if tool results are returned directly.
                # For now, we assume the tool execution is fire-and-forget from the handler's perspective,
                # and any results come back as new observations/events.
            except Exception as e_tool:
                self.logger.exception(f"Error executing TOOL {params.name} for thought {thought_id}: {e_tool}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL {params.name} execution failed: {str(e_tool)}"

        # v1 uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action=result.model_dump(),  # Changed from final_action_result
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
                priority_offset=1 if action_performed_successfully else 0,
            )

            # v1 uses 'context' instead of 'processing_context'
            context_for_follow_up = {"action_performed": HandlerActionType.TOOL.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info

            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
            context_for_follow_up["action_params"] = action_params_dump

            new_follow_up.context = context_for_follow_up  # v1 uses 'context'

            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after TOOL action."
            )
        except Exception as e:
            self.logger.critical(
                f"Failed to create follow-up thought for {thought_id}: {e}",
                exc_info=e,
            )
            raise FollowUpCreationError from e