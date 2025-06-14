import logging
from typing import Dict, Any, Optional # Added Optional


from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought  # Though DEFER might not always create a standard follow-up

logger = logging.getLogger(__name__)



class DeferHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.DEFER, {**dispatch_context, "thought_id": thought_id}, outcome="start")

        final_thought_status = ThoughtStatus.DEFERRED
        action_performed_successfully = False
        follow_up_content_key_info = f"DEFER action for thought {thought_id}"
        
        defer_params_obj: Optional[DeferParams] = None
        try:
            if isinstance(raw_params, dict):
                defer_params_obj = DeferParams(**raw_params)
            elif isinstance(raw_params, DeferParams): # Should not happen if ActionSelectionResult.action_parameters is always dict
                defer_params_obj = raw_params
            else:
                raise ValueError(f"Unexpected type for deferral parameters: {type(raw_params)}")

            follow_up_content_key_info = f"Deferred thought {thought_id}. Reason: {defer_params_obj.reason}"

            wa_service = await self.get_wa_service()
            if wa_service:
                try:
                    deferral_context = {
                        "task_id": thought.source_task_id,
                        "thought_content": thought.content if hasattr(thought, 'content') else "",
                        "priority": getattr(defer_params_obj, 'priority', 'medium'),
                        "attempted_action": dispatch_context.get('attempted_action', 'unknown'),
                        "max_rounds_reached": dispatch_context.get('max_rounds_reached', False)
                    }
                    
                    if thought.source_task_id:
                        task = persistence.get_task_by_id(thought.source_task_id)
                        if task and hasattr(task, 'description'):
                            deferral_context["task_description"] = task.description
                    
                    if "conversation_context" in dispatch_context:
                        deferral_context["conversation_context"] = dispatch_context["conversation_context"]
                    
                    await wa_service.send_deferral(thought_id, defer_params_obj.reason, deferral_context)
                except Exception as e:
                    self.logger.error(f"WiseAuthorityService deferral failed for thought {thought_id}: {e}")
            else:
                self.logger.warning("No WiseAuthorityService available for deferral")
                action_performed_successfully = True  # Deferral still considered processed

        except Exception as param_parse_error:
            self.logger.error(f"DEFER action params parsing error or unexpected structure. Type: {type(raw_params)}, Error: {param_parse_error}. Thought ID: {thought_id}")
            follow_up_content_key_info = f"DEFER action failed: Invalid parameters ({type(raw_params)}) for thought {thought_id}. Error: {param_parse_error}"
            wa_service = await self.get_wa_service()
            if wa_service:
                try:
                    error_context = {
                        "task_id": thought.source_task_id,
                        "thought_content": thought.content if hasattr(thought, 'content') else "",
                        "error_type": "parameter_parsing_error",
                        "attempted_action": dispatch_context.get('attempted_action', 'defer')
                    }
                    await wa_service.send_deferral(thought_id, "parameter_error", error_context)
                except Exception as e_sink_fallback:
                    self.logger.error(
                        f"Fallback deferral submission failed for thought {thought_id}: {e_sink_fallback}"
                    )
            else:
                action_performed_successfully = True

        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,  # Should be DEFERRED
            final_action=result,  # Pass the ActionSelectionResult object directly
        )
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for DEFER action. Info: {follow_up_content_key_info}")
        await self._audit_log(HandlerActionType.DEFER, {**dispatch_context, "thought_id": thought_id}, outcome="success")

        parent_task_id = thought.source_task_id
        if parent_task_id not in ["WAKEUP_ROOT", "SYSTEM_TASK", "DREAM_TASK"]:
            persistence.update_task_status(parent_task_id, TaskStatus.DEFERRED)
            self.logger.info(f"Marked parent task {parent_task_id} as DEFERRED due to child thought deferral.")

