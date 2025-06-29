import logging
from typing import Dict, Optional

from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.runtime.enums import ThoughtStatus, TaskStatus, HandlerActionType
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.logic import persistence
from ciris_engine.logic.infrastructure.handlers.base_handler import BaseActionHandler

logger = logging.getLogger(__name__)

PERSISTENT_TASK_IDS: Dict[str, str] = {}  # Maps task_id to persistence reason

class TaskCompleteHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionDMAResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id

        await self._audit_log(HandlerActionType.TASK_COMPLETE, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="start")

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

                    from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
                    from ciris_engine.schemas.actions import PonderParams

                    ponder_content = (
                        "WAKEUP TASK COMPLETION BLOCKED: You attempted to mark a wakeup task as complete "
                        "without first completing a SPEAK action. Each wakeup step requires you to SPEAK "
                        "an earnest affirmation before marking the task complete. Please review the task "
                        "requirements and either: 1) SPEAK an authentic affirmation if you can do so earnestly, "
                        "or 2) REJECT this task if you cannot speak earnestly about it, or 3) DEFER to human "
                        f"wisdom if you are uncertain about the requirements. Task: {parent_task_id}"
                    )

                    ponder_result = ActionSelectionDMAResult(
                        selected_action=HandlerActionType.PONDER,
                        action_parameters=PonderParams(questions=[ponder_content]).model_dump(),
                        selection_reasoning="Wakeup task attempted completion without first performing SPEAK action - overriding to PONDER for guidance"
                    )

                    ponder_result_dict = {
                        "selected_action": ponder_result.selected_action.value,
                        "action_parameters": ponder_result.action_parameters.model_dump() if hasattr(ponder_result.action_parameters, 'model_dump') else ponder_result.action_parameters,
                        "rationale": ponder_result.selection_reasoning
                    }

                    persistence.update_thought_status(
                        thought_id=thought_id,
                        status=ThoughtStatus.FAILED,
                        final_action=ponder_result_dict,
                    )
                    await self._audit_log(HandlerActionType.TASK_COMPLETE, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="blocked_override_to_ponder")
                    return None

        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} for TASK_COMPLETE.")
        print(f"[TASK_COMPLETE_HANDLER] ✓ Thought {thought_id} marked as COMPLETED")

        # Check if there's a positive moment to memorize
        if hasattr(result, 'action_parameters') and hasattr(result.action_parameters, 'positive_moment'):
            positive_moment = result.action_parameters.positive_moment
            if positive_moment:
                await self._memorize_positive_moment(positive_moment, parent_task_id, dispatch_context)

        await self._audit_log(HandlerActionType.TASK_COMPLETE, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="success")

        if parent_task_id:
            if parent_task_id in PERSISTENT_TASK_IDS:
                self.logger.info(f"Task {parent_task_id} is a persistent task. Not marking as COMPLETED by TaskCompleteHandler. It should be re-activated or remain PENDING/ACTIVE.")
            else:
                task_updated = persistence.update_task_status(parent_task_id, TaskStatus.COMPLETED, self.time_service)
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
        if task.context and hasattr(task.context, 'step_type'):
            step_type = getattr(task.context, 'step_type', None)
            if step_type in ["VERIFY_IDENTITY", "VALIDATE_INTEGRITY", "EVALUATE_RESILIENCE", "ACCEPT_INCOMPLETENESS", "EXPRESS_GRATITUDE"]:
                return True

        return False

    async def _has_speak_action_completed(self, task_id: str) -> bool:
        """Check if a SPEAK action has been successfully completed for the given task using correlation system."""
        from ciris_engine.schemas.telemetry.core import ServiceCorrelationStatus

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

    async def _memorize_positive_moment(self, positive_moment: str, task_id: Optional[str], dispatch_context: DispatchContext) -> None:
        """Memorize a positive moment as a community vibe."""
        try:
            from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope

            # Create a positive vibe node
            vibe_node = GraphNode(
                id=f"positive_vibe_{int(self.time_service.timestamp())}",
                type=NodeType.CONCEPT,
                scope=GraphScope.COMMUNITY,
                attributes={
                    "vibe_type": "task_completion_joy",
                    "description": positive_moment[:500],  # Keep it brief
                    "task_id": task_id or "unknown",
                    "channel_id": dispatch_context.channel_id or "somewhere",
                    "timestamp": self.time_service.now_iso()
                }
            )

            # Memorize via the memory bus
            await self.bus_manager.memory.memorize(
                node=vibe_node,
                handler_name="task_complete_handler",
                metadata={"positive_vibes": True}
            )

            self.logger.info(f"✨ Memorized positive moment: {positive_moment[:100]}...")

        except Exception as e:
            # Don't let positive moment tracking break task completion
            self.logger.debug(f"Couldn't memorize positive moment: {e}")
