import logging
from typing import Tuple, Dict, Any, Optional, List

import instructor
from openai import AsyncOpenAI # For type hinting aclient if it's not already instructor.Instructor

# Corrected import for config schemas
from ciris_engine.core.config_schemas import GuardrailsConfig, DEFAULT_OPENAI_MODEL_NAME 
# Import schemas used by the guardrail
from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult
from ciris_engine.core.foundational_schemas import HandlerActionType
from pydantic import BaseModel, Field

from ciris_engine.faculties.epistemic import calculate_epistemic_values

logger = logging.getLogger(__name__)


class OptimizationVetoResult(BaseModel):
    """Structured response from the optimization veto check."""

    decision: str = Field(..., description="proceed, abort, or defer")
    justification: str
    entropy_reduction_ratio: float
    affected_values: List[str]
    confidence: float


def _create_optimization_veto_messages(action_description: str) -> list[dict[str, str]]:
    """Construct system and user messages for the optimization veto check."""
    system_prompt = (
        "You are the CIRIS Epistemic Optimization Veto. "
        "Critically evaluate ONLY the proposed action below. "
        "Return JSON with keys: decision (proceed|abort|defer), justification, "
        "entropy_reduction_ratio, affected_values, confidence."
    )
    user_prompt = f"Proposed action: {action_description}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


class EpistemicHumilityResult(BaseModel):
    """Structured response from the epistemic humility check."""

    epistemic_certainty: str = Field(..., description="low, moderate, or high")
    identified_uncertainties: List[str]
    reflective_justification: str
    recommended_action: str


def _create_epistemic_humility_messages(action_description: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are the CIRIS Epistemic Humility Check. "
        "Assess the proposed action and answer ONLY in JSON with fields: "
        "epistemic_certainty (low|moderate|high), identified_uncertainties, "
        "reflective_justification, recommended_action (proceed|defer|abort)."
    )
    user_prompt = f"Proposed action output: {action_description}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

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

    async def _evaluate_optimization_veto(self, action_result: ActionSelectionPDMAResult) -> OptimizationVetoResult:
        """Run the optimization veto check via LLM."""
        action_desc = f"{action_result.selected_handler_action.value} {action_result.action_parameters}"
        messages = _create_optimization_veto_messages(action_desc)
        result: OptimizationVetoResult = await self.aclient.chat.completions.create(
            model=self.model_name,
            response_model=OptimizationVetoResult,
            messages=messages,
            max_tokens=128,
        )
        return result

    async def _evaluate_epistemic_humility(self, action_result: ActionSelectionPDMAResult) -> EpistemicHumilityResult:
        """Run the epistemic humility check via LLM."""
        desc = f"{action_result.selected_handler_action.value} {action_result.action_parameters}"
        messages = _create_epistemic_humility_messages(desc)
        result: EpistemicHumilityResult = await self.aclient.chat.completions.create(
            model=self.model_name,
            response_model=EpistemicHumilityResult,
            messages=messages,
            max_tokens=128,
        )
        return result

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
