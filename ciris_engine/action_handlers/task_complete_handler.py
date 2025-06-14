import logging
from typing import Dict, Any, Optional

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler


logger = logging.getLogger(__name__)

PERSISTENT_TASK_IDS = {} 

class TaskCompleteHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> Optional[str]:
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id

        await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="start")

        final_thought_status = ThoughtStatus.COMPLETED
        
        self.logger.info(f"Handling TASK_COMPLETE for thought {thought_id} (Task: {parent_task_id}).")
        print(f"[TASK_COMPLETE_HANDLER] Processing TASK_COMPLETE for task {parent_task_id}")

        if parent_task_id:
            is_wakeup = await self._is_wakeup_task(parent_task_id)
            self.logger.debug(f"Task {parent_task_id} is_wakeup_task: {is_wakeup}")
            if is_wakeup:
                has_speak = await self._has_speak_action_completed(parent_task_id)
                self.logger.debug(f"Task {parent_task_id} has_speak_action_completed: {has_speak}")
                if not has_speak:
                    self.logger.error(f"TASK_COMPLETE rejected for wakeup task {parent_task_id}: No SPEAK action has been completed.")
                    print(f"[TASK_COMPLETE_HANDLER] ✗ TASK_COMPLETE rejected for wakeup task {parent_task_id}: Must SPEAK first")
                    
                    from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
                    from ciris_engine.schemas.action_params_v1 import PonderParams
                    
                    ponder_content = (
                        f"WAKEUP TASK COMPLETION BLOCKED: You attempted to mark a wakeup task as complete "
                        f"without first completing a SPEAK action. Each wakeup step requires you to SPEAK "
                        f"an earnest affirmation before marking the task complete. Please review the task "
                        f"requirements and either: 1) SPEAK an authentic affirmation if you can do so earnestly, "
                        f"or 2) REJECT this task if you cannot speak earnestly about it, or 3) DEFER to human "
                        f"wisdom if you are uncertain about the requirements. Task: {parent_task_id}"
                    )
                    
                    ponder_result = ActionSelectionResult(
                        selected_action=HandlerActionType.PONDER,
                        action_parameters=PonderParams(questions=[ponder_content]),
                        rationale="Wakeup task attempted completion without first performing SPEAK action - overriding to PONDER for guidance"
                    )
                    
                    ponder_result_dict = {
                        "selected_action": ponder_result.selected_action.value,
                        "action_parameters": ponder_result.action_parameters.model_dump() if ponder_result.action_parameters else None,
                        "rationale": ponder_result.rationale
                    }
                    
                    persistence.update_thought_status(
                        thought_id=thought_id,
                        status=ThoughtStatus.FAILED,
                        final_action=ponder_result_dict,
                    )
                    await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="blocked_override_to_ponder")
                    return None

        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} for TASK_COMPLETE.")
        print(f"[TASK_COMPLETE_HANDLER] ✓ Thought {thought_id} marked as COMPLETED")
        await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="success")

        if parent_task_id:
            if parent_task_id in PERSISTENT_TASK_IDS:
                self.logger.info(f"Task {parent_task_id} is a persistent task. Not marking as COMPLETED by TaskCompleteHandler. It should be re-activated or remain PENDING/ACTIVE.")
            else:
                task_updated = persistence.update_task_status(parent_task_id, TaskStatus.COMPLETED)
                if task_updated:
                    self.logger.info(f"Marked parent task {parent_task_id} as COMPLETED due to TASK_COMPLETE action on thought {thought_id}.")
                    print(f"[TASK_COMPLETE_HANDLER] ✓ Task {parent_task_id} marked as COMPLETED")

                    pending = persistence.get_thoughts_by_task_id(parent_task_id)
                    to_delete = [t.thought_id for t in pending if getattr(t, 'status', None) in {ThoughtStatus.PENDING, ThoughtStatus.PROCESSING}]
                    if to_delete:
                        persistence.delete_thoughts_by_ids(to_delete)
                        self.logger.debug(f"Cleaned up {len(to_delete)} pending thoughts for task {parent_task_id}")
                else:
                    self.logger.error(f"Failed to update status for parent task {parent_task_id} to COMPLETED.")
                    print(f"[TASK_COMPLETE_HANDLER] ✗ Failed to update task {parent_task_id} status")
        else:
            self.logger.error(f"Could not find parent task ID for thought {thought_id} to mark as complete.")
        
        return None

    async def _is_wakeup_task(self, task_id: str) -> bool:
        """Check if a task is part of the wakeup sequence."""
        task = persistence.get_task_by_id(task_id)
        if not task:
            return False
        
        # Check if this is the root wakeup task
        if task_id == "WAKEUP_ROOT":
            return True
        
        # Check if parent task is the wakeup root
        if getattr(task, 'parent_task_id', None) == "WAKEUP_ROOT":
            return True
        
        # Check if task context indicates it's a wakeup step
        if task.context and isinstance(task.context, dict):
            step_type = task.context.get("step_type")  # type: ignore[unreachable]
            if step_type in ["VERIFY_IDENTITY", "VALIDATE_INTEGRITY", "EVALUATE_RESILIENCE", "ACCEPT_INCOMPLETENESS", "EXPRESS_GRATITUDE"]:
                return True
        
        return False

    async def _has_speak_action_completed(self, task_id: str) -> bool:
        """Check if a SPEAK action has been successfully completed for the given task using correlation system."""
        from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelationStatus
        
        correlations = persistence.get_correlations_by_task_and_action(
            task_id=task_id, 
            action_type="speak",
            status=ServiceCorrelationStatus.COMPLETED
        )
        
        self.logger.debug(f"Found {len(correlations)} completed SPEAK correlations for task {task_id}")
        
        if correlations:
            self.logger.debug(f"Found completed SPEAK action correlation for task {task_id}")
            return True
        
        self.logger.debug(f"No completed SPEAK action correlation found for task {task_id}")
        return False

