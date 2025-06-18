from typing import Optional, Dict, Any
import logging

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import (
    ThoughtStatus,
    HandlerActionType,
    DispatchContext,
)
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from ciris_engine.action_handlers.base_handler import BaseActionHandler, ActionHandlerDependencies

logger = logging.getLogger(__name__)

from ciris_engine.config.config_manager import get_config


class PonderHandler(BaseActionHandler):
    def __init__(self, dependencies: ActionHandlerDependencies, max_rounds: Optional[int] = None) -> None:
        super().__init__(dependencies)
        if max_rounds is None:
            try:
                max_rounds = get_config().workflow.max_rounds
            except Exception:
                max_rounds = 7
        self.max_rounds = max_rounds

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> None:
        """Process ponder action and update thought."""
        params = result.action_parameters
        ponder_params = PonderParams(**params) if isinstance(params, dict) else params
        
        questions_list = ponder_params.questions if hasattr(ponder_params, 'questions') else []
        
        # Note: epistemic_data handling removed - not part of typed DispatchContext
        # If epistemic data is needed, it should be passed through proper typed fields
        
        current_thought_depth = thought.thought_depth
        new_thought_depth = current_thought_depth + 1
        
        logger.info(f"Thought ID {thought.thought_id} pondering (depth: {new_thought_depth}). Questions: {questions_list}")
        
        # The thought depth guardrail will handle max depth enforcement
        # We just need to process the ponder normally
        next_status = ThoughtStatus.COMPLETED
        
        success = persistence.update_thought_status(
            thought_id=thought.thought_id,
            status=next_status,
            final_action={
                "action": HandlerActionType.PONDER.value,
                "thought_depth": new_thought_depth,
                "ponder_notes": questions_list,
            },
        )
        
        if success:
            existing_notes = thought.ponder_notes or []
            thought.ponder_notes = existing_notes + questions_list
            thought.status = next_status
            logger.info(
                f"Thought ID {thought.thought_id} successfully updated (thought_depth: {new_thought_depth}) and marked for {next_status.value}."
            )
            
            # Create a new dict with dispatch_context data and additional fields
            audit_context = dispatch_context.model_dump()
            audit_context.update({
                "thought_id": thought.thought_id,
                "status": next_status.value,
                "new_thought_depth": new_thought_depth,
                "ponder_type": "reprocess"
            })
            await self._audit_log(
                HandlerActionType.PONDER,
                audit_context,
                outcome="success"
            )
            
            original_task = persistence.get_task_by_id(thought.source_task_id)
            task_context = f"Task ID: {thought.source_task_id}"
            if original_task:
                task_context = original_task.description
            
            follow_up_content = self._generate_ponder_follow_up_content(
                task_context, questions_list, new_thought_depth, thought
            )
            from .helpers import create_follow_up_thought
            follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_content,
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.PONDER.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "ponder_notes": questions_list,
            })
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(follow_up)
            return None
        else:
            logger.error(f"Failed to update thought ID {thought.thought_id} for re-processing Ponder.")
            persistence.update_thought_status(
                thought_id=thought.thought_id,
                status=ThoughtStatus.FAILED,
                final_action={
                    "action": HandlerActionType.PONDER.value,
                    "error": "Failed to update for re-processing",
                    "thought_depth": current_thought_depth
                }
            )
            # Create a new dict with dispatch_context data and additional fields
            audit_context = dispatch_context.model_dump()
            audit_context.update({
                "thought_id": thought.thought_id,
                "status": ThoughtStatus.FAILED.value,
                "ponder_type": "update_failed"
            })
            await self._audit_log(
                HandlerActionType.PONDER,
                audit_context,
                outcome="failed"
            )
            original_task = persistence.get_task_by_id(thought.source_task_id)
            task_context = f"Task ID: {thought.source_task_id}"
            if original_task:
                task_context = f"Original Task: {original_task.description}"
                
            follow_up_content = (
                f"This is a follow-up thought from a FAILED PONDER action performed on parent task {task_context}. "
                f"Pondered questions: {questions_list}. "
                "The update failed. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            from .helpers import create_follow_up_thought
            follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_content,
            )
            # Update context properly
            if follow_up.context:
                context_data = follow_up.context.model_dump()
            else:
                context_data = {}
            context_data.update({
                "action_performed": HandlerActionType.PONDER.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "ponder_notes": questions_list,
                "error": "Failed to update for re-processing"
            })
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(follow_up)
            return None
    
    def _generate_ponder_follow_up_content(
        self, 
        task_context: str, 
        questions_list: list, 
        thought_depth: int,
        thought: Thought
    ) -> str:
        """Generate dynamic follow-up content based on ponder count and previous failures."""
        
        base_questions = questions_list.copy()
        
        # Add thought-depth specific guidance
        if thought_depth == 1:
            follow_up_content = (
                f"Continuing work on: \"{task_context}\"\n"
                f"Current considerations: {base_questions}\n"
                f"Please proceed with your next action."
            )
        elif thought_depth == 2:
            follow_up_content = (
                f"Second action for: \"{task_context}\"\n"
                f"Current focus: {base_questions}\n"
                f"You've taken one action already. Continue making progress on this task."
            )
        elif thought_depth == 3:
            follow_up_content = (
                f"Third action for: \"{task_context}\"\n"
                f"Working on: {base_questions}\n"
                f"You're making good progress with multiple actions. Keep going!"
            )
        elif thought_depth == 4:
            follow_up_content = (
                f"Fourth action for: \"{task_context}\"\n"
                f"Current needs: {base_questions}\n"
                f"You've taken several actions (RECALL, OBSERVE, MEMORIZE, etc.). "
                f"Continue if more work is needed, or consider if the task is complete."
            )
        elif thought_depth == 5:
            follow_up_content = (
                f"Fifth action for: \"{task_context}\"\n"
                f"Addressing: {base_questions}\n"
                f"You're deep into this task with multiple actions. Consider: "
                f"1) Is the task nearly complete? "
                f"2) Do you need just a few more steps? "
                f"3) Remember: You have 7 actions total for this task."
            )
        elif thought_depth == 6:
            follow_up_content = (
                f"Sixth action for: \"{task_context}\"\n"
                f"Final steps: {base_questions}\n"
                f"You're approaching the action limit (7 total). Consider: "
                f"1) Can you complete the task with one more action? "
                f"2) Is the task essentially done and ready for TASK_COMPLETE? "
                f"3) Tip: If you need more actions, someone can ask you to continue and you'll get 7 more!"
            )
        elif thought_depth >= 7:
            follow_up_content = (
                f"Seventh action for: \"{task_context}\"\n"
                f"Final action: {base_questions}\n"
                f"This is your last action for this task chain. You should either: "
                f"1) TASK_COMPLETE - If the work is done or substantially complete "
                f"2) DEFER - Only if you truly need human help to proceed "
                f"Remember: If someone asks you to continue working on this, you'll get a fresh set of 7 actions!"
            )
        
        # Add context from previous ponder notes if available
        if thought.ponder_notes:
            follow_up_content += f"\n\nPrevious ponder history: {thought.ponder_notes[-3:]}"  # Last 3 entries
            
        return follow_up_content
