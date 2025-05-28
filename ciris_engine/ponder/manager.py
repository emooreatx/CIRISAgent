from typing import Optional, Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine import persistence
import logging

logger = logging.getLogger(__name__)

class PonderManager:
    def __init__(self, max_ponder_rounds: int = 5):
        self.max_ponder_rounds = max_ponder_rounds
    
    async def ponder(self, thought: Thought, context: Dict[str, Any]) -> None:
        """
        Handle the ponder action for a thought.
        This method is called by ThoughtProcessor when PONDER is selected.
        """
        # Extract ponder questions from context
        ponder_questions = []
        
        # Try to get questions from the action result in context
        if 'action_result' in context:
            action_result = context['action_result']
            if hasattr(action_result, 'action_parameters'):
                params = action_result.action_parameters
                if isinstance(params, dict) and 'questions' in params:
                    ponder_questions = params['questions']
                elif hasattr(params, 'questions'):
                    ponder_questions = params.questions
        
        # If no questions found, create default ones
        if not ponder_questions:
            ponder_questions = [
                "What is the core issue I need to address?",
                "What additional context would help me provide a better response?",
                "Are there any assumptions I should reconsider?"
            ]
        
        # Create PonderParams if not already present
        ponder_params = PonderParams(questions=ponder_questions)
        
        # Delegate to the existing handle method
        await self.handle_ponder_action(
            thought=thought,
            ponder_params=ponder_params,
            epistemic_data=context.get('epistemic_data')
        )
    
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
        key_questions_list = ponder_params.questions if hasattr(ponder_params, 'questions') else []
        
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
            return None
        else:
            new_ponder_count = current_ponder_count + 1
            logger.info(f"Thought ID {thought.thought_id} pondering (count: {new_ponder_count}). Questions: {key_questions_list}")
            
            # Update the thought with new ponder count and notes
            # Note: The persistence layer might need adjustment to support updating ponder_notes
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
                logger.info(f"Thought ID {thought.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for re-processing.")
                return None
            else:
                logger.error(f"Failed to update thought ID {thought.thought_id} for re-processing Ponder.")
                # Mark as FAILED instead of returning a new thought
                persistence.update_thought_status(
                    thought_id=thought.thought_id,
                    status=ThoughtStatus.FAILED,
                    final_action={
                        "action": "PONDER",
                        "error": "Failed to update for re-processing",
                        "ponder_count": new_ponder_count
                    }
                )
                return None
