from typing import Optional, Dict, Any
import logging

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus
from ciris_engine import persistence
from ciris_engine.action_handlers.base_handler import BaseActionHandler, ActionHandlerDependencies

logger = logging.getLogger(__name__)

class PonderHandler(BaseActionHandler):
    def __init__(self, dependencies: ActionHandlerDependencies, max_ponder_rounds: int = 5):
        super().__init__(dependencies)
        self.max_ponder_rounds = max_ponder_rounds

    def should_defer_for_max_ponder(
        self,
        thought: Thought,
        current_ponder_count: int
    ) -> bool:
        """Check if thought has exceeded ponder limits."""
        return current_ponder_count >= self.max_ponder_rounds

    async def handle(
        self,
        thought: Thought,
        ponder_params: PonderParams,
        context: Dict[str, Any] 
    ) -> Optional[Thought]:
        """Process ponder action and update thought."""
        key_questions_list = ponder_params.questions if hasattr(ponder_params, 'questions') else []
        
        epistemic_data = context.get('epistemic_data')
        # Add epistemic notes if present
        if epistemic_data:
            if 'optimization_veto' in epistemic_data:
                veto = epistemic_data['optimization_veto']
                note = f"OptVeto: {veto.get('decision')} - {veto.get('justification')}"
                key_questions_list.append(note)
            if 'epistemic_humility' in epistemic_data:
                hum = epistemic_data['epistemic_humility']
                h_note = f"Humility: {hum.get('recommended_action')} - {hum.get('epistemic_certainty')}"
                key_questions_list.append(h_note)
        
        current_ponder_count = thought.ponder_count
        
        # Special handling: If this is a wakeup step thought, do not re-queue for further pondering
        if getattr(thought, 'thought_type', '').lower() in [
            'verify_identity', 'validate_integrity', 'evaluate_resilience', 'accept_incompleteness', 'express_gratitude', 'signalling_gratitude']:
            logger.info(f"Thought ID {thought.thought_id} is a wakeup step ({thought.thought_type}); not re-queuing for further pondering.")
            persistence.update_thought_status(
                thought_id=thought.thought_id,
                status=ThoughtStatus.COMPLETED,
                final_action={
                    "action": "PONDER",
                    "ponder_count": current_ponder_count + 1,
                    "ponder_notes": key_questions_list,
                    "wakeup_step": True
                }
            )
            # Log audit for wakeup step ponder
            await self._audit_log("PONDER_WAKEUP_STEP", context, {"thought_id": thought.thought_id, "status": "COMPLETED"})
            return None
        
        # Normal ponder logic
        if self.should_defer_for_max_ponder(thought, current_ponder_count):
            logger.warning(f"Thought ID {thought.thought_id} has reached max ponder rounds ({self.max_ponder_rounds}). Marking as DEFERRED.")
            persistence.update_thought_status(
                thought_id=thought.thought_id,
                status=ThoughtStatus.DEFERRED,
                final_action={
                    "action": "DEFER",
                    "reason": f"Maximum ponder rounds ({self.max_ponder_rounds}) reached",
                    "ponder_notes": key_questions_list,
                    "ponder_count": current_ponder_count
                }
            )
            # Log audit for max ponder deferral
            await self._audit_log("PONDER_MAX_ROUNDS_DEFER", context, {"thought_id": thought.thought_id, "status": "DEFERRED"})
            return None
        else:
            new_ponder_count = current_ponder_count + 1
            logger.info(f"Thought ID {thought.thought_id} pondering (count: {new_ponder_count}). Questions: {key_questions_list}")
            
            success = persistence.update_thought_status(
                thought_id=thought.thought_id,
                status=ThoughtStatus.PENDING,  # Back to PENDING for re-processing
                final_action={
                    "action": "PONDER",
                    "ponder_count": new_ponder_count,
                    "ponder_notes": key_questions_list
                }
            )
            
            if success:
                thought.ponder_count = new_ponder_count
                logger.info(f"Thought ID {thought.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for re-processing.")
                # Log audit for successful ponder
                await self._audit_log("PONDER_REPROCESS", context, {"thought_id": thought.thought_id, "status": "PENDING", "new_ponder_count": new_ponder_count})
                return None
            else:
                logger.error(f"Failed to update thought ID {thought.thought_id} for re-processing Ponder.")
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={
                        "action": "PONDER",
                        "error": "Failed to update for re-processing",
                        "ponder_count": current_ponder_count # Reverted to current_ponder_count as update failed
                    }
                )
                # Log audit for failed ponder update
                await self._audit_log("PONDER_UPDATE_FAILED", context, {"thought_id": thought.thought_id, "status": "FAILED"})
                return None
