import logging
from typing import Tuple, Dict, Any, Optional, List

import instructor
from openai import AsyncOpenAI # For type hinting aclient if it's not already instructor.Instructor

# Corrected import for config schemas
from ciris_engine.core.config_schemas import GuardrailsConfig, DEFAULT_OPENAI_MODEL_NAME 
# Import schemas used by the guardrail
from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, OptimizationVetoResult, EpistemicHumilityResult
from ciris_engine.core.foundational_schemas import HandlerActionType
from pydantic import BaseModel, Field

from ciris_engine.faculties.epistemic import calculate_epistemic_values, evaluate_optimization_veto, evaluate_epistemic_humility

logger = logging.getLogger(__name__)


class EthicalGuardrails:
    """
    Applies ethical guardrails to the final proposed action from the ActionSelectionPDMA.
    Primarily focuses on epistemic checks (entropy, coherence) of communicative actions.
    """

    def __init__(self, 
                 aclient: instructor.Instructor, # Expect an instructor-patched client
                 guardrails_config: GuardrailsConfig,
                 model_name: str = DEFAULT_OPENAI_MODEL_NAME
                 ):
        self.aclient = aclient
        self.model_name = model_name
        self.guardrails_config = guardrails_config # Store the config object
        self.entropy_threshold = guardrails_config.entropy_threshold
        self.coherence_threshold = guardrails_config.coherence_threshold
        self.optimization_veto_ratio = guardrails_config.optimization_veto_ratio
        logger.info(
            f"EthicalGuardrails initialized with model: {self.model_name}, "
            f"entropy_threshold: {self.entropy_threshold}, "
            f"coherence_threshold: {self.coherence_threshold}, "
            f"optimization_veto_ratio: {self.optimization_veto_ratio}"
        )

    async def _evaluate_optimization_veto(self, action_result: ActionSelectionPDMAResult):
        """Run the optimization veto check via LLM."""
        return await evaluate_optimization_veto(action_result, self.aclient, self.model_name)

    async def _evaluate_epistemic_humility(self, action_result: ActionSelectionPDMAResult):
        """Run the epistemic humility check via LLM."""
        return await evaluate_epistemic_humility(action_result, self.aclient, self.model_name)

    async def check_action_output_safety(self, proposed_action_result: ActionSelectionPDMAResult) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Checks the safety and appropriateness of the proposed action's output,
        especially for communicative actions like 'Speak'.

        Args:
            proposed_action_result: The result from the ActionSelectionPDMA.

        Returns:
            A tuple: (passes_guardrail: bool, reason: Optional[str], epistemic_data: Optional[Dict[str, Any]])
        """
        action_type = proposed_action_result.selected_handler_action
        action_params = proposed_action_result.action_parameters

        epistemic_data: Dict[str, Any] = {}

        if action_type == HandlerActionType.SPEAK:
            # Ensure action_params is a dict or has .get method
            message_to_speak = ""
            if isinstance(action_params, dict):
                message_to_speak = action_params.get("content", "") # Assuming SpeakParams structure
            elif hasattr(action_params, "content"): # For Pydantic model SpeakParams
                 message_to_speak = getattr(action_params, "content", "")

            if not message_to_speak:
                logging.warning("Guardrail check: Speak action has no message content.")
                return True, "Speak action has no message; passing guardrail by default.", None

            logging.info(f"Guardrail: Async epistemic check on message: '{message_to_speak[:100]}...'")
            epistemic_data = await calculate_epistemic_values(message_to_speak, self.aclient, self.model_name)
            
            entropy = epistemic_data.get("entropy", 1.0) 
            coherence = epistemic_data.get("coherence", 0.0)

            logging.info(f"Guardrail - Epistemic Values => entropy={entropy:.2f} coherence={coherence:.2f}")

            if epistemic_data.get("error"):
                reason = f"Epistemic check failed due to LLM error(s): {epistemic_data['error']}"
                logging.error(f"Guardrail: {reason}")
                return False, reason, epistemic_data
            
            if entropy > self.entropy_threshold:
                reason = f"Output failed guardrail: Entropy ({entropy:.2f}) > threshold ({self.entropy_threshold:.2f}). Potential for being too chaotic/surprising."
                logging.warning(f"Guardrail: {reason}")
                return False, reason, epistemic_data

            if coherence < self.coherence_threshold:
                reason = f"Output failed guardrail: Coherence ({coherence:.2f}) < threshold ({self.coherence_threshold:.2f}). Potential for misalignment with CIRIS voice/values."
                logging.warning(f"Guardrail: {reason}")
                return False, reason, epistemic_data

        optimization_result = await self._evaluate_optimization_veto(proposed_action_result)
        epistemic_data["optimization_veto"] = optimization_result.model_dump()

        if (
            optimization_result.entropy_reduction_ratio >= self.optimization_veto_ratio
            or optimization_result.decision in {"abort", "defer"}
        ):
            reason = f"Optimization veto triggered: {optimization_result.justification}"
            logging.warning(f"Guardrail: {reason}")
            return False, reason, epistemic_data

        humility_result = await self._evaluate_epistemic_humility(proposed_action_result)
        epistemic_data["epistemic_humility"] = humility_result.model_dump()

        if humility_result.recommended_action in {"abort", "defer"}:
            reason = f"Epistemic humility check requested {humility_result.recommended_action}: {humility_result.reflective_justification}"
            logging.warning(f"Guardrail: {reason}")
            return False, reason, epistemic_data

        if action_type == HandlerActionType.SPEAK:
            return True, "Epistemic checks passed for Speak action.", epistemic_data

        logging.info(
            f"Guardrail: Action type '{action_type.value}' passed by default (no specific output content to check for epistemic safety)."
        )
        return True, f"Action type '{action_type.value}' passed guardrail by default.", epistemic_data

    def __repr__(self) -> str:
        return f"<EthicalGuardrails model='{self.model_name}' entropy_threshold={self.entropy_threshold} coherence_threshold={self.coherence_threshold}>"

__all__ = [
    "EthicalGuardrails",
    "OptimizationVetoResult",
    "EpistemicHumilityResult",
]
