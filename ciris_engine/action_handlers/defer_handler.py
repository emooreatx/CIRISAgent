import logging
from typing import Dict, Any, Optional # Added Optional

from pydantic import BaseModel

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.schemas.deferral_schemas_v1 import DeferralPackage, DeferralReason
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought  # Though DEFER might not always create a standard follow-up

logger = logging.getLogger(__name__)

# NOTE: The CIRIS agent uses three special root job/task IDs that should never be marked DEFERRED by observation deferral logic:
#   - "WAKEUP_ROOT": The main wakeup ritual root task
#   - "SYSTEM_TASK": Used for system-level operations (if present)
#   - "job-discord-monitor": The persistent Discord monitoring background job
# If you add new root job types, update this exclusion logic accordingly.

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
            

            
            if self.dependencies.deferral_sink:
                try:
                    source_task_id = dispatch_context.get("source_task_id", thought.source_task_id)
                    pkg = DeferralPackage(
                        thought_id=thought_id,
                        task_id=source_task_id,
                        deferral_reason=DeferralReason.UNKNOWN,
                        reason_description=defer_params_obj.reason,
                        thought_content=thought.content,
                        task_description=dispatch_context.get("task_description"),
                        ethical_assessment=defer_params_obj.context.get("ethical") if defer_params_obj.context else None,
                        csdma_assessment=defer_params_obj.context.get("csdma") if defer_params_obj.context else None,
                        dsdma_assessment=defer_params_obj.context.get("dsdma") if defer_params_obj.context else None,
                    )
                    await self.dependencies.deferral_sink.send_deferral(
                        source_task_id,
                        thought_id,
                        defer_params_obj.reason,
                        {"deferral_package": pkg.model_dump()}
                    )
                except Exception as e:
                    self.logger.error(f"DeferralSink failed for thought {thought_id}: {e}")
            else:
                action_performed_successfully = True # Deferral itself is successful by updating status

        except Exception as param_parse_error:
            self.logger.error(f"DEFER action params parsing error or unexpected structure. Type: {type(raw_params)}, Error: {param_parse_error}. Thought ID: {thought_id}")
            follow_up_content_key_info = f"DEFER action failed: Invalid parameters ({type(raw_params)}) for thought {thought_id}. Error: {param_parse_error}"
            # Deferral still proceeds, but with potentially less context for the sink.
            if self.dependencies.deferral_sink:  # Attempt to send minimal deferral info
                 try:
                    source_task_id = dispatch_context.get("source_task_id", thought.source_task_id)
                    pkg = DeferralPackage(
                        thought_id=thought_id,
                        task_id=source_task_id,
                        deferral_reason=DeferralReason.UNKNOWN,
                        reason_description="parameter_error",
                        thought_content=thought.content,
                    )
                    await self.dependencies.deferral_sink.send_deferral(
                        source_task_id,
                        thought_id,
                        "Deferral due to parameter processing error.",
                        {"deferral_package": pkg.model_dump()}
                    )
                 except Exception as e_sink_fallback:
                     self.logger.error(f"Fallback DeferralSink failed for thought {thought_id}: {e_sink_fallback}")
            else:
                # If no sink or channel, the deferral is silent, which is acceptable.
                action_performed_successfully = True  # Deferral itself is successful by updating status

        # v1 uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,  # Should be DEFERRED
            final_action=result_data,  # v1 field
        )
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for DEFER action. Info: {follow_up_content_key_info}")
        await self._audit_log(HandlerActionType.DEFER, {**dispatch_context, "thought_id": thought_id}, outcome="success")

        # If this is an observation (not a root/system task), defer the parent task as well
        # Fixed: Use TaskStatus.DEFERRED not ThoughtStatus.DEFERRED for tasks
        if thought.source_task_id not in ["WAKEUP_ROOT", "SYSTEM_TASK", "job-discord-monitor", "DREAM_TASK"]:
            persistence.update_task_status(thought.source_task_id, TaskStatus.DEFERRED)
            self.logger.info(f"Marked parent task {thought.source_task_id} as DEFERRED due to child thought deferral.")

        # DEFER actions typically don't create a standard "next step" follow-up thought
        # because the deferral itself is a terminal state for this thought's processing round.
        # A human or another process is expected to review deferred thoughts.
        # However, one might log this to a specific system or create a different kind of notification.
        # For now, no standard follow-up thought is created by this handler.
        # If a follow-up IS needed, it would be specific to the deferral reason/workflow.
