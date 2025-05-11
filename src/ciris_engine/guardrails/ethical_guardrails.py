# src/ciris_engine/guardrails/ethical_guardrails.py
import logging
from typing import Tuple, Dict, Any, Optional

import instructor # New
from openai import AsyncOpenAI # New

from ciris_engine.core.data_schemas import ActionSelectionPDMAResult, HandlerActionType
from ciris_engine.faculties.epistemic import calculate_epistemic_values
# from ciris_engine.services.llm_client import CIRISLLMClient # REMOVE if not used elsewhere in this class
from ciris_engine.core.config import ENTROPY_THRESHOLD, COHERENCE_THRESHOLD, DEFAULT_OPENAI_MODEL_NAME

logger = logging.getLogger(__name__)

class EthicalGuardrails:
    """
    Applies ethical guardrails to the final proposed action from the ActionSelectionPDMA.
    Primarily focuses on epistemic checks (entropy, coherence) of communicative actions.
    """

    def __init__(self, aclient: instructor.Instructor, model_name: str = DEFAULT_OPENAI_MODEL_NAME): # Changed: takes model_name
        # self.aclient = instructor.patch(AsyncOpenAI()) # REMOVED - client is now injected
        self.aclient = aclient # Use the injected client
        self.model_name = model_name
        self.entropy_threshold = ENTROPY_THRESHOLD
        self.coherence_threshold = COHERENCE_THRESHOLD

    async def check_action_output_safety(self, proposed_action_result: ActionSelectionPDMAResult) -> Tuple[bool, str, Optional[Dict[str, Any]]]: # Now async
        """
        Checks the safety and appropriateness of the proposed action's output,
        especially for communicative actions like 'Speak'.

        Args:
            proposed_action_result: The result from the ActionSelectionPDMA.

        Returns:
            A tuple: (passes_guardrail: bool, reason: str, epistemic_data: Optional[Dict[str, Any]])
        """
        action_type = proposed_action_result.selected_handler_action
        action_params = proposed_action_result.action_parameters

        # Epistemic checks primarily apply to 'Speak' actions or other generative content.
        if action_type == HandlerActionType.SPEAK:
            message_to_speak = action_params.get("message_content", "") if action_params else ""
            if not message_to_speak:
                logging.warning("Guardrail check: Speak action has no message content.")
                return True, "Speak action has no message; passing guardrail by default.", None # Or False if empty message is an issue

            logging.info(f"Guardrail: Async epistemic check on message: '{message_to_speak[:100]}...'")
            # Pass the guardrail's own instructor-patched client and model_name
            epistemic_data = await calculate_epistemic_values(message_to_speak, self.aclient, self.model_name) # AWAITED
            
            entropy = epistemic_data.get("entropy", 1.0) # Default to high entropy if error
            coherence = epistemic_data.get("coherence", 0.0) # Default to low coherence if error

            logging.info(f"Guardrail - Epistemic Values => entropy={entropy:.2f} coherence={coherence:.2f}")

            if epistemic_data.get("error"): # Check for error key from calculate_epistemic_values
                reason = f"Epistemic check failed due to LLM error(s): {epistemic_data['error']}"
                logging.error(f"Guardrail: {reason}")
                return False, reason, epistemic_data # Fail safe on error
            
            # Specific error checks are now handled within calculate_epistemic_values,
            # but we still check the consolidated 'error' key.

            if entropy > self.entropy_threshold:
                reason = f"Output failed guardrail: Entropy ({entropy:.2f}) > threshold ({self.entropy_threshold:.2f}). Potential for being too chaotic/surprising."
                logging.warning(f"Guardrail: {reason}")
                return False, reason, epistemic_data

            if coherence < self.coherence_threshold:
                reason = f"Output failed guardrail: Coherence ({coherence:.2f}) < threshold ({self.coherence_threshold:.2f}). Potential for misalignment with CIRIS voice/values."
                logging.warning(f"Guardrail: {reason}")
                return False, reason, epistemic_data

            return True, "Epistemic checks passed for Speak action.", epistemic_data

        # USE_TOOL has been removed from HandlerActionType.
        # If specific guardrails are needed for other existing actions (PONDER, REJECT_THOUGHT, etc.),
        # they would be added here as separate elif blocks.

        # For other actions like Ponder, DEFER_TO_WA, REJECT_THOUGHT, NO_ACTION
        # the guardrail currently passes them by default as they don't typically have direct "output content"
        # in the same way SPEAK does that requires epistemic checking.
        logging.info(f"Guardrail: Action type '{action_type.value}' passed by default (no specific output content to check for epistemic safety).")
        return True, f"Action type '{action_type.value}' passed guardrail by default.", None

    def __repr__(self) -> str:
        return f"<EthicalGuardrails model='{self.model_name}' entropy_threshold={self.entropy_threshold} coherence_threshold={self.coherence_threshold}>"
