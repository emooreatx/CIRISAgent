import logging
from typing import Dict, Any

# Updated imports for v1 schemas
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies

# No standard follow-up thought for TASK_COMPLETE as it's a terminal action for the task.

logger = logging.getLogger(__name__)

# List of persistent task IDs that should not be marked as COMPLETED by this handler.
# These tasks are expected to run continuously or be re-activated by other means.
PERSISTENT_TASK_IDS = {"job-discord-monitor"} 

class TaskCompleteHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id

        final_thought_status = ThoughtStatus.COMPLETED
        # action_performed_successfully = True # The decision to complete the task is the action.
        
        self.logger.info(f"Handling TASK_COMPLETE for thought {thought_id} (Task: {parent_task_id}).")

        # Update the current thought that led to TASK_COMPLETE
        # v1 schema uses 'final_action' instead of 'final_action_result'
        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action=result.model_dump(),  # Changed from final_action_result to final_action
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} for TASK_COMPLETE.")

        # Update the parent task status to COMPLETED, unless it's a persistent task
        if parent_task_id:
            if parent_task_id in PERSISTENT_TASK_IDS:
                self.logger.info(f"Task {parent_task_id} is a persistent task. Not marking as COMPLETED by TaskCompleteHandler. It should be re-activated or remain PENDING/ACTIVE.")
                # Optionally, ensure it's PENDING if it was ACTIVE
                # current_task_obj = persistence.get_task_by_id(parent_task_id)
                # if current_task_obj and current_task_obj.status == TaskStatus.ACTIVE:
                #    persistence.update_task_status(parent_task_id, TaskStatus.PENDING)
            else:
                task_updated = persistence.update_task_status(parent_task_id, TaskStatus.COMPLETED)
                if task_updated:
                    self.logger.info(f"Marked parent task {parent_task_id} as COMPLETED due to TASK_COMPLETE action on thought {thought_id}.")
                    # Optionally, send a notification if an action_sink is available
                    if self.dependencies.action_sink:
                        original_event_channel_id = dispatch_context.get("channel_id")
                        if original_event_channel_id:
                            try:
                                parent_task_obj = persistence.get_task_by_id(parent_task_id)
                                task_desc = parent_task_obj.description if parent_task_obj else "Unknown task"
                                await self.dependencies.action_sink.send_message(
                                    original_event_channel_id,
                                    f"Task '{task_desc[:50]}...' (ID: {parent_task_id}) has been marked as complete by the agent."
                                )
                            except Exception as e:
                                self.logger.error(f"Failed to send TASK_COMPLETE notification for task {parent_task_id}: {e}")
                else: # This else corresponds to "if task_updated:"
                    self.logger.error(f"Failed to update status for parent task {parent_task_id} to COMPLETED.")
        else:
            self.logger.error(f"Could not find parent task ID for thought {thought_id} to mark as complete.")

        # TASK_COMPLETE is a terminal action for this line of thought and for the task.
        # No standard "create_follow_up_thought" is typically generated from here by this handler.
        # The task is done. New work would come from new tasks or events.