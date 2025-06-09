from typing import Optional, Dict, Any
import logging

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import (
    ThoughtStatus,
    HandlerActionType,
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
                max_rounds = 5
        self.max_rounds = max_rounds

    def should_defer_for_max_rounds(
        self,
        thought: Thought,
        current_ponder_count: int
    ) -> bool:
        """Check if thought has exceeded action round limits."""
        return current_ponder_count >= self.max_rounds

    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        """Process ponder action and update thought."""
        params = result.action_parameters
        ponder_params = PonderParams(**params) if isinstance(params, dict) else params
        
        questions_list = ponder_params.questions if hasattr(ponder_params, 'questions') else []
        
        epistemic_data = dispatch_context.get('epistemic_data')
        if epistemic_data:
            if 'optimization_veto' in epistemic_data:
                veto = epistemic_data['optimization_veto']
                note = f"OptVeto: {veto.get('decision')} - {veto.get('justification')}"
                questions_list.append(note)
            if 'epistemic_humility' in epistemic_data:
                hum = epistemic_data['epistemic_humility']
                h_note = f"Humility: {hum.get('recommended_action')} - {hum.get('epistemic_certainty')}"
                questions_list.append(h_note)
        
        current_ponder_count = thought.ponder_count
        new_ponder_count = current_ponder_count + 1
        
        logger.info(f"Thought ID {thought.thought_id} pondering (count: {new_ponder_count}). Questions: {questions_list}")
        
        if new_ponder_count >= self.max_rounds:
            logger.warning(f"Thought ID {thought.thought_id} has reached max rounds ({self.max_rounds}) after this ponder. Deferring to defer handler.")
            
            existing_notes = thought.ponder_notes or []
            thought.ponder_notes = existing_notes + questions_list
            
            from ciris_engine.schemas.action_params_v1 import DeferParams
            
            defer_params = DeferParams(
                reason=f"Maximum action rounds ({self.max_rounds}) reached after {new_ponder_count} actions"
            )
            defer_result = ActionSelectionResult(
                selected_action=HandlerActionType.DEFER,
                action_parameters=defer_params.model_dump(mode='json'),
                rationale=f"Auto-defer after reaching max ponder count of {new_ponder_count}",
                raw_llm_response=None
            )
            
            defer_handler = self.dependencies.action_dispatcher.get_handler(HandlerActionType.DEFER)
            if defer_handler:
                # Enhance dispatch context with max rounds information
                enhanced_context = dispatch_context.copy()
                enhanced_context.update({
                    "max_rounds_reached": True,
                    "attempted_action": "ponder_max_rounds",
                    "ponder_count": new_ponder_count,
                    "ponder_notes": questions_list
                })
                await defer_handler.handle(defer_result, thought, enhanced_context)
                return None
            else:
                logger.error("Defer handler not available. Setting status to DEFERRED directly.")
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.DEFERRED,
                    final_action={
                        "action": HandlerActionType.DEFER.value,
                        "reason": f"Maximum action rounds ({self.max_rounds}) reached",
                        "ponder_notes": questions_list,
                        "ponder_count": new_ponder_count,
                    },
                )
                thought.status = ThoughtStatus.DEFERRED
                await self._audit_log(
                    HandlerActionType.PONDER,
                    dispatch_context,
                    {"thought_id": thought.thought_id, "status": ThoughtStatus.DEFERRED.value, "ponder_type": "max_rounds_defer_fallback"},
                )
                return None
        else:
            next_status = ThoughtStatus.COMPLETED
        
        success = persistence.update_thought_status(
            thought_id=thought.thought_id,
            status=next_status,
            final_action={
                "action": HandlerActionType.PONDER.value,
                "ponder_count": new_ponder_count,
                "ponder_notes": questions_list,
            },
        )
        
        if success:
            existing_notes = thought.ponder_notes or []
            thought.ponder_notes = existing_notes + questions_list
            thought.status = next_status
            logger.info(
                f"Thought ID {thought.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for {next_status.value}."
            )
            
            await self._audit_log(
                HandlerActionType.PONDER,
                dispatch_context,
                {
                    "thought_id": thought.thought_id,
                    "status": next_status.value,
                    "new_ponder_count": new_ponder_count,
                    "ponder_type": "reprocess",
                },
            )
            
            # Get the original task context to maintain thread
            original_task = persistence.get_task_by_id(thought.source_task_id)
            task_context = f"Task ID: {thought.source_task_id}"
            if original_task:
                task_context = original_task.description
            
            # Generate more dynamic follow-up content based on ponder count
            follow_up_content = self._generate_ponder_follow_up_content(
                task_context, questions_list, new_ponder_count, thought
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
                    "ponder_count": current_ponder_count
                }
            )
            await self._audit_log(
                HandlerActionType.PONDER,
                dispatch_context,
                {"thought_id": thought.thought_id, "status": ThoughtStatus.FAILED.value, "ponder_type": "update_failed"},
            )
            # Get the original task context to maintain thread  
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
            ctx2 = {
                "action_performed": HandlerActionType.PONDER.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "ponder_notes": questions_list,
                "error": "Failed to update for re-processing"
            }
            for k, v in ctx2.items():
                setattr(follow_up.context, k, v)
            persistence.add_thought(follow_up)
            return None
    
    def _generate_ponder_follow_up_content(
        self, 
        task_context: str, 
        questions_list: list, 
        ponder_count: int,
        thought: Thought
    ) -> str:
        """Generate dynamic follow-up content based on ponder count and previous failures."""
        
        base_questions = questions_list.copy()
        
        # Add ponder-count specific guidance
        if ponder_count == 1:
            follow_up_content = (
                f"You are considering how to act on: \"{task_context}\"\n"
                f"Initial concerns: {base_questions}\n"
                f"Please re-evaluate and choose an appropriate response."
            )
        elif ponder_count == 2:
            follow_up_content = (
                f"Second consideration for: \"{task_context}\"\n"
                f"Previous concerns: {base_questions}\n"
                f"Your first attempt didn't pass guardrails. Try a different approach - perhaps more conservative, "
                f"more detailed, or consider if no action is needed."
            )
        elif ponder_count == 3:
            follow_up_content = (
                f"Third attempt at: \"{task_context}\"\n"
                f"Ongoing concerns: {base_questions}\n"
                f"Two previous attempts failed guardrails. Consider: Is this task actually necessary? "
                f"Would a completely different action type work better? Should you defer for human guidance?"
            )
        elif ponder_count >= 4:
            follow_up_content = (
                f"Multiple attempts ({ponder_count}) at: \"{task_context}\"\n"
                f"Persistent issues: {base_questions}\n"
                f"This task has been repeatedly blocked by guardrails. Consider: "
                f"1) Is the task inherently problematic? "
                f"2) Should you defer to human oversight? "
                f"3) Is there a fundamentally different approach? "
                f"4) Should this task be marked as complete without action?"
            )
        
        # Add context from previous ponder notes if available
        if thought.ponder_notes:
            follow_up_content += f"\n\nPrevious ponder history: {thought.ponder_notes[-3:]}"  # Last 3 entries
            
        return follow_up_content
