import logging
from typing import Dict, Any

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies


logger = logging.getLogger(__name__)

PERSISTENT_TASK_IDS = {} 

class TaskCompleteHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id

        await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="start")

        final_thought_status = ThoughtStatus.COMPLETED
        
        self.logger.info(f"Handling TASK_COMPLETE for thought {thought_id} (Task: {parent_task_id}).")
        print(f"[TASK_COMPLETE_HANDLER] Processing TASK_COMPLETE for task {parent_task_id}")

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

