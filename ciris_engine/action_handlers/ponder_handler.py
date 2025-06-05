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
    def __init__(self, dependencies: ActionHandlerDependencies, max_rounds: Optional[int] = None):
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
        # Extract ponder parameters from the result
        params = result.action_parameters
        ponder_params = PonderParams(**params) if isinstance(params, dict) else params
        
        questions_list = ponder_params.questions if hasattr(ponder_params, 'questions') else []
        
        epistemic_data = dispatch_context.get('epistemic_data')
        # Add epistemic notes if present
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
        
        # Check if we've reached max rounds after this ponder
        if new_ponder_count >= self.max_rounds:
            logger.warning(f"Thought ID {thought.thought_id} has reached max rounds ({self.max_rounds}) after this ponder. Deferring to defer handler.")
            
            # Update the thought with the ponder results first
            thought.ponder_count = new_ponder_count
            existing_notes = thought.ponder_notes or []
            thought.ponder_notes = existing_notes + questions_list
            
            # Create a defer action result and pass to defer handler
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
            
            # Get the defer handler and pass the thought to it
            defer_handler = self.dependencies.action_dispatcher.get_handler(HandlerActionType.DEFER)
            if defer_handler:
                await defer_handler.handle(defer_result, thought, dispatch_context)
                return None
            else:
                # Fallback if defer handler not available - mark as DEFERRED directly
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
            # Normal ponder completion - mark as COMPLETED for re-processing
            next_status = ThoughtStatus.COMPLETED
        
        # Normal ponder completion - update thought and create follow-up
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
            thought.ponder_count = new_ponder_count
            existing_notes = thought.ponder_notes or []
            thought.ponder_notes = existing_notes + questions_list
            thought.status = next_status
            logger.info(
                f"Thought ID {thought.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for {next_status.value}."
            )
            
            # Log audit for successful ponder
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
            
            # Create a follow-up thought for the ponder action
            follow_up_content = (
                f"CIRIS_FOLLOW_UP_THOUGHT: This is a follow-up thought from a PONDER action performed on parent task {thought.source_task_id}. "
                f"Pondered questions: {questions_list}. "
                "If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            #PROMPT_FOLLOW_UP_THOUGHT
            from .helpers import create_follow_up_thought
            follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_content,
            )
            # Update context using Pydantic model_copy with additional fields
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
            # Note: The thought is already set to PENDING status, so it will be automatically
            # picked up in the next processing round when the queue is populated from the database
            return None
        else:
            logger.error(f"Failed to update thought ID {thought.thought_id} for re-processing Ponder.")
            persistence.update_thought_status(
                thought_id=thought.thought_id,
                status=ThoughtStatus.FAILED,
                final_action={
                    "action": HandlerActionType.PONDER.value,
                    "error": "Failed to update for re-processing",
                    "ponder_count": current_ponder_count # Reverted to current_ponder_count as update failed
                }
            )
            # Log audit for failed ponder update
            await self._audit_log(
                HandlerActionType.PONDER,
                dispatch_context,
                {"thought_id": thought.thought_id, "status": ThoughtStatus.FAILED.value, "ponder_type": "update_failed"},
            )
            # Create a follow-up thought for the failed ponder action
            follow_up_content = (
                f"This is a follow-up thought from a FAILED PONDER action performed on parent task {thought.source_task_id}. "
                f"Pondered questions: {questions_list}. "
                "The update failed. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            #PROMPT_FOLLOW_UP_THOUGHT
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
