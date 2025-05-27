from typing import Optional, Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams, RejectParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine import persistence
import logging

logger = logging.getLogger(__name__)

class PonderManager:
    def __init__(self, max_ponder_rounds: int = 5):
        self.max_ponder_rounds = max_ponder_rounds
        
    def should_defer_for_max_ponder(
        self,
        thought: Thought,
        current_ponder_count: int
    ) -> bool:
        """Check if thought has exceeded ponder limits."""
        return current_ponder_count >= self.max_ponder_rounds
    
    async def handle_ponder_action(
        self,
        thought: Thought,
        ponder_params: PonderParams,
        epistemic_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Thought]:
        """Process ponder action and update thought."""
        key_questions_list = ponder_params.key_questions if hasattr(ponder_params, 'key_questions') else []
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
        if self.should_defer_for_max_ponder(thought, current_ponder_count):
            logger.warning(f"Thought ID {thought.thought_id} has reached max ponder rounds ({self.max_ponder_rounds}). Overriding to DEFER.")
            persistence.update_thought_status(
                thought_id=thought.thought_id,
                new_status=ThoughtStatus.DEFERRED,
                ponder_notes=key_questions_list,
                ponder_count=current_ponder_count,
                final_action=None,
            )
            return None
        else:
            new_ponder_count = current_ponder_count + 1
            logger.info(f"Thought ID {thought.thought_id} resulted in PONDER action (count: {new_ponder_count}). Questions: {key_questions_list}. Re-queueing.")
            success = persistence.update_thought_status(
                thought_id=thought.thought_id,
                new_status=ThoughtStatus.PENDING,
                ponder_notes=key_questions_list,
                ponder_count=new_ponder_count,
                final_action=None,
            )
            if success:
                logger.info(f"Thought ID {thought.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for re-processing.")
                return None
            else:
                logger.error(f"Failed to update thought ID {thought.thought_id} for re-processing Ponder. Returning Ponder action as terminal.")
                return Thought(
                    **thought.model_dump(),
                    status=ThoughtStatus.FAILED
                )
