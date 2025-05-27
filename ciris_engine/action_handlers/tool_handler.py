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
from ciris_engine.services.tool_registry import ToolRegistry
from ciris_engine.services.discord_tools import register_discord_tools
import discord
import asyncio
import uuid

logger = logging.getLogger(__name__)

class ToolHandler(BaseActionHandler):
    TOOL_RESULT_TIMEOUT = 30  # seconds
    _pending_results: Dict[str, asyncio.Future] = {}
    _tool_registry: ToolRegistry = ToolRegistry()

    @classmethod
    def set_tool_registry(cls, registry: ToolRegistry):
        cls._tool_registry = registry

    async def register_tool_result(self, correlation_id: str, result: ToolResult) -> None:
        fut = self._pending_results.get(correlation_id)
        if fut and not fut.done():
            fut.set_result(result)

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

        # Tool registry validation
        if not isinstance(params, ToolParams):  # v1 uses ToolParams
            self.logger.error(f"TOOL action params are not ToolParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif not self.dependencies.action_sink or not hasattr(self.dependencies.action_sink, 'run_tool'):
            self.logger.error(f"ActionSink or run_tool method not available. Cannot execute TOOL for thought {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: ActionSink or run_tool unavailable for thought {thought_id}."
        elif not self._tool_registry.get_tool_schema(params.name):
            self.logger.error(f"Tool '{params.name}' not found in registry. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Tool '{params.name}' not registered."
        elif not self._tool_registry.validate_arguments(params.name, params.args):
            self.logger.error(f"Arguments for tool '{params.name}' failed validation. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"TOOL action failed: Arguments for tool '{params.name}' invalid."
        else:
            correlation_id = str(uuid.uuid4())
            fut = asyncio.get_event_loop().create_future()
            self._pending_results[correlation_id] = fut
            try:
                # The run_tool method on ActionSink is expected to be async if it involves I/O
                # v1 ToolParams has 'name' and 'args' fields instead of 'tool_name' and 'arguments'
                await self.dependencies.action_sink.run_tool(params.name, {**params.args, "correlation_id": correlation_id})
                try:
                    tool_result: ToolResult = await asyncio.wait_for(fut, timeout=self.TOOL_RESULT_TIMEOUT)
                    if tool_result.execution_status == ToolExecutionStatus.SUCCESS:
                        action_performed_successfully = True
                        follow_up_content_key_info = f"Tool '{params.name}' executed successfully. Result: {tool_result.result_data}"
                    else:
                        final_thought_status = ThoughtStatus.FAILED
                        follow_up_content_key_info = f"Tool '{params.name}' failed: {tool_result.error_message}"
                except asyncio.TimeoutError:
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"TOOL action timed out waiting for result from '{params.name}'."
            except Exception as e_tool:
                self.logger.exception(f"Error executing TOOL {params.name} for thought {thought_id}: {e_tool}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"TOOL {params.name} execution failed: {str(e_tool)}"
            finally:
                self._pending_results.pop(correlation_id, None)

        # v1 uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action=result.model_dump(),  # v1 field
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
            context_for_follow_up = {"action_performed": HandlerActionType.TOOL.value}
            if final_thought_status == ThoughtStatus.FAILED:
                context_for_follow_up["error_details"] = follow_up_content_key_info
            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
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

# Set up the global ToolRegistry and register Discord tools if not already set
_tool_registry = ToolRegistry()
# Discord bot instance will be set at runtime; placeholder for registration
# register_discord_tools(_tool_registry, bot)
ToolHandler.set_tool_registry(_tool_registry)