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
PERSISTENT_TASK_IDS = {} 

class TaskCompleteHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id

        await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="start")

        final_thought_status = ThoughtStatus.COMPLETED
        # action_performed_successfully = True # The decision to complete the task is the action.
        
        self.logger.info(f"Handling TASK_COMPLETE for thought {thought_id} (Task: {parent_task_id}).")
        print(f"[TASK_COMPLETE_HANDLER] Processing TASK_COMPLETE for task {parent_task_id}")

        # Update the current thought that led to TASK_COMPLETE
        # v1 schema uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result_data,  # v1 field
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} for TASK_COMPLETE.")
        print(f"[TASK_COMPLETE_HANDLER] ✓ Thought {thought_id} marked as COMPLETED")
        await self._audit_log(HandlerActionType.TASK_COMPLETE, {**dispatch_context, "thought_id": thought_id}, outcome="success")

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
                    print(f"[TASK_COMPLETE_HANDLER] ✓ Task {parent_task_id} marked as COMPLETED")
                    
                    # Optionally, send a notification if communication service is available
                    original_event_channel_id = dispatch_context.get("channel_id")
                    if original_event_channel_id:
                        parent_task_obj = persistence.get_task_by_id(parent_task_id)
                        task_desc = parent_task_obj.description if parent_task_obj else "Unknown task"
                        message = f"Task '{task_desc[:50]}...' (ID: {parent_task_id}) has been marked as complete by the agent."
                        comm_service = await self.get_communication_service()
                        if comm_service:
                            try:
                                await comm_service.send_message(original_event_channel_id, message)
                                print(f"[TASK_COMPLETE_HANDLER] ✓ Notification sent for completed task {parent_task_id}")
                            except Exception as e:
                                await self._handle_error(HandlerActionType.TASK_COMPLETE, dispatch_context, thought_id, e)
                        elif self.dependencies.action_sink:
                            try:
                                await self.dependencies.action_sink.send_message(self.__class__.__name__, original_event_channel_id, message)
                                print(f"[TASK_COMPLETE_HANDLER] ✓ Notification sent for completed task {parent_task_id}")
                            except Exception as e:
                                await self._handle_error(HandlerActionType.TASK_COMPLETE, dispatch_context, thought_id, e)

                    # Clean up any pending thoughts/resources for this task
                    pending = persistence.get_thoughts_by_task_id(parent_task_id)
                    to_delete = [t.thought_id for t in pending if getattr(t, 'status', None) in {ThoughtStatus.PENDING, ThoughtStatus.PROCESSING}]
                    if to_delete:
                        persistence.delete_thoughts_by_ids(to_delete)
                        self.logger.debug(f"Cleaned up {len(to_delete)} pending thoughts for task {parent_task_id}")
                else: # This else corresponds to "if task_updated:"
                    self.logger.error(f"Failed to update status for parent task {parent_task_id} to COMPLETED.")
                    print(f"[TASK_COMPLETE_HANDLER] ✗ Failed to update task {parent_task_id} status")
        else:
            self.logger.error(f"Could not find parent task ID for thought {thought_id} to mark as complete.")

        # TASK_COMPLETE is a terminal action for this line of thought and for the task.
        # No standard "create_follow_up_thought" is typically generated from here by this handler.
        # The task is done. New work would come from new tasks or events.
