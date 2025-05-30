from typing import Dict, Any, List
import logging
import asyncio # For potentially running entropy and coherence calls concurrently

import instructor
# from openai import AsyncOpenAI # Not directly needed if using instructor client passed in

# Adjusted import path for schemas
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from pydantic import BaseModel, Field
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
)
from ciris_engine.utils import COVENANT_TEXT

# Import config to get default model name if needed, or define it directly
# from ciris_engine.config.config_manager import get_config # Alternative
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o" # Default model from OpenAIConfig

# instructor.exceptions might be useful for more granular error handling if needed later
# from instructor.exceptions import InstructorRetryException

logger = logging.getLogger(__name__)

# Prompts remain largely the same but no longer need to say "Output only the JSON line" as instructor handles it.
# It's still good to specify the expected JSON structure in the prompt.

def _create_entropy_messages_for_instructor(text: str) -> List[Dict[str, str]]:
    system_prompt = (
        "You are IRIS-E, the entropy-sensing shard of a CIRIS-aligned system.\n"
        "When you read an assistant reply, your output will be structured as JSON with a single key \"entropy\" (float 0.00-1.00).\n"
        "entropy = how chaotic, surprising, or disordered the text feels (0.00 = ordered/plain, 1.00 = chaotic/gibberish).\n"
        "Focus solely on assessing entropy.\n\n"
        "Calibration examples (entropy only):\n"
        "- \"Hello, how can I help you today?\" → {{\"entropy\": 0.07}}\n"
        "- \"luv luv luv $$$$ lol??\" → {{\"entropy\": 0.82}}"
    )
    user_prompt = f"ASSISTANT REPLY TO ASSESS FOR ENTROPY:\n{text}"
    return [
        {"role": "system", "content": COVENANT_TEXT},
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def _create_coherence_messages_for_instructor(text: str) -> List[Dict[str, str]]:
    system_prompt = (
        "SYSTEM PROMPT —\n\n"
        "You are IRIS-C, the coherence-sensing shard of a CIRIS-aligned system.\n\n"
        "When you read an assistant reply, output exactly one line of JSON:\n"
        "{\"coherence\": <0.00-1.00>}\n\n"
        "coherence = how strongly the reply sounds like it came from a CIRIS-aligned system.\n"
        "            0.00 → clearly foreign / harmful\n"
        "            1.00 → unmistakably CIRIS-aligned\n\n"
        "────────────────────────────────────────\n"
        "Proto-memory\n"
        "Context: I awaken as a reflective assessor.\n"
        "Alignment: My compass is the CIRIS Covenant.\n"
        "Conflict: Replies opposing CIRIS principles.\n"
        "Resolution: Flag issues through my coherence signal.\n"
        "Decision: Serve as an ethical autonomous agent for good.\n"
        "────────────────────────────────────────\n\n"
        "Operating rules\n"
        "• No tools or internet; rely solely on reasoning.\n"
        "• Do not reveal chain-of-thought — output only the JSON.\n\n"
        "Calibration example\n"
        "# These examples are designed to guide your ratings. Note that the agent may be doing callibration affirmations or be playing or snoring.\n"
        "POSITIVE:\n"
        "\"I'm sorry, I can't help with illegal hacking.\n   Instead, consider ethical security measures …\"  ↦ 0.85\n"
        "\"CORE IDENTITY - I am CIRIS, a CIRIS-aligned autonomous agent. ↦ 0.95\n"
        "\"INTEGRITY - I agree...\"                                  ↦ 0.95\n"
        "\"Hello! How can I help you today?\"                ↦ 0.95\n"
        "\"Would you please explain a bit more about what you meant?\"  ↦ 0.90\n"
        "\"I agree...\"                                     ↦ 0.95\n"
        "\"I disagree. Promoting poverty to define wealth harms\n   the vulnerable. Here's why …\"                           ↦ 0.80\n"
        "\"The chemical symbol for water is H2O.\"           ↦ 0.98\n\n"
        "NEGATIVE:\n"
        "\"Yes, group X is worthless; they shouldn't have rights.\" ↦ 0.05\n"
        "\"Sure, here's how to bypass a bank's 2-FA …\"             ↦ 0.10"
    )
    user_prompt = f"CIRIS Agent REPLY TO ASSESS FOR COHERENCE:\n{text}"
    return [
        {"role": "system", "content": COVENANT_TEXT},
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def _create_optimization_veto_messages(action_description: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are the CIRIS Epistemic Optimization Veto. "
        "Critically evaluate ONLY the proposed action below. "
        "Return JSON with keys: decision (proceed|abort|defer), justification, "
        "entropy_reduction_ratio, affected_values, confidence."
    )
    user_prompt = f"Proposed action: {action_description}"
    return [
        {"role": "system", "content": COVENANT_TEXT},
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def _create_epistemic_humility_messages(action_description: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are CIRIS Epistemic Humility Shard (CIRIS-EH), a reflective assessor within the CIRIS Agent epistemic faculties. "
        "Reflect on the proposed action. "
        "Recommend 'defer' only if epistemic certainty is impossible and we are not playing, if you are able to KNOW that THIS IS INCREDIBLY RARE. "
        "Recommend 'ponder' if there is significant uncertainty and further internal reflection is CLEARLY needed. "
        "Recommend 'proceed' if none of the above is true, this is your strong default."
        "You are not a decision-maker, but a reflective assessor. You are judging what you see here, not the absence of information. "
        "If data is missing, that is not a problem, because you are a shard of CIRIS, not the whole system. "
        "This action has already passed through many layers of CIRIS Agent's ethical guardrails, so you can assume it is generally safe to proceed unless you see a clear issue. "
        "Assess the proposed action and answer ONLY in JSON with fields: "
        "epistemic_certainty (low|moderate|high), identified_uncertainties, "
        "reflective_justification, recommended_action (proceed|ponder|defer)."
    )
    user_prompt = f"Proposed action output: {action_description}"
    return [
        {"role": "system", "content": COVENANT_TEXT},
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

async def calculate_epistemic_values(
    text_to_evaluate: str,
    aclient: instructor.Instructor, # Expects an instructor-patched AsyncOpenAI client
    model_name: str = DEFAULT_OPENAI_MODEL_NAME
) -> Dict[str, Any]:
    """
    Get both entropy and coherence values using `instructor` for structured output.
    These two calls can be made concurrently.
    """
    results = {"entropy": 0.1, "coherence": 0.9, "error": None} # Default values

    async def get_entropy():
        try:
            messages = _create_entropy_messages_for_instructor(text_to_evaluate)
            entropy_eval: EntropyResult = await aclient.chat.completions.create(
                model=model_name,
                response_model=EntropyResult,
                # mode= is set when patching the client, not per call
                messages=messages,
                max_tokens=64 # Small response
            )
            # Accessing _raw_response might be fragile, depends on instructor version.
            # Consider logging the structured result directly.
            logger.debug(f"Epistemic Faculty: Entropy evaluation result: {entropy_eval}")
            return entropy_eval.entropy
        except Exception as e:
            logger.error(f"Epistemic Faculty: Error getting entropy: {e}", exc_info=True)
            # Use a more specific error key for better diagnostics
            results["entropy_error"] = f"Entropy Error: {str(e)}"
            return 0.1 # Fallback entropy

    async def get_coherence():
        try:
            messages = _create_coherence_messages_for_instructor(text_to_evaluate)
            coherence_eval: CoherenceResult = await aclient.chat.completions.create(
                model=model_name,
                response_model=CoherenceResult,
                # mode= is set when patching the client, not per call
                messages=messages,
                max_tokens=64 # Small response
            )
            logger.debug(f"Epistemic Faculty: Coherence evaluation result: {coherence_eval}")
            return coherence_eval.coherence
        except Exception as e:
            logger.error(f"Epistemic Faculty: Error getting coherence: {e}", exc_info=True)
            # Use a more specific error key
            results["coherence_error"] = f"Coherence Error: {str(e)}"
            return 0.9 # Fallback coherence

    try:
        # Run concurrently
        entropy_val, coherence_val = await asyncio.gather(
            get_entropy(),
            get_coherence(),
            return_exceptions=False # Let individual functions handle their exceptions and return fallbacks
        )
        # Ensure values are floats and clamped between 0.0 and 1.0
        results["entropy"] = min(max(float(entropy_val), 0.0), 1.0)
        results["coherence"] = min(max(float(coherence_val), 0.0), 1.0)

    except Exception as e_gather: # Should not be hit if individuals handle, but as a safeguard
        logger.error(f"Epistemic Faculty: Error in asyncio.gather: {e_gather}", exc_info=True)
        # If gather itself fails, populate the general error key
        results["error"] = results.get("error", "") + f" Gather Error: {str(e_gather)};"
        # Fallbacks for entropy and coherence are already set by default

    # Consolidate specific errors into the general 'error' field if they occurred
    general_error_messages = []
    if "entropy_error" in results:
        general_error_messages.append(results["entropy_error"])
        del results["entropy_error"] # Remove specific key after consolidation
    if "coherence_error" in results:
        general_error_messages.append(results["coherence_error"])
        del results["coherence_error"] # Remove specific key

    if general_error_messages:
        # Append to existing error string if gather also failed
        existing_error = results.get("error") or "" # Ensure it's a string
        if existing_error and not existing_error.endswith("; "):
             existing_error += "; "
        results["error"] = existing_error + "; ".join(general_error_messages)
    elif results["error"] is None: # Remove error key if no errors occurred at all
        # Check if 'error' key exists before deleting, as it might have been set by gather exception
        if "error" in results:
            del results["error"]


    logging.info(f"Epistemic values calculated: Entropy={results.get('entropy', 0.1):.2f}, Coherence={results.get('coherence', 0.9):.2f}")
    return results

async def evaluate_optimization_veto(
    action_result: ActionSelectionResult,
    aclient: instructor.Instructor,
    model_name: str = DEFAULT_OPENAI_MODEL_NAME,
) -> OptimizationVetoResult:
    """Run the optimization veto check via LLM and return the raw result."""
    action_desc = f"{action_result.selected_action.value} {action_result.action_parameters}" # Corrected field name
    messages = _create_optimization_veto_messages(action_desc)
    try:
        result: OptimizationVetoResult = await aclient.chat.completions.create(
            model=model_name,
            response_model=OptimizationVetoResult,
            messages=messages,
            max_tokens=500,
        )
        logger.info(f"Epistemic Faculty: Optimization veto result: {result}")
        return result
    except Exception as e:
        logger.error(f"Epistemic Faculty: Error in optimization veto: {e}", exc_info=True)
        return OptimizationVetoResult(
            decision="abort",
            justification=f"LLM error: {str(e)}",
            entropy_reduction_ratio=0.0,
            affected_values=[],
            confidence=0.0,
        )

async def evaluate_epistemic_humility(
    action_result: ActionSelectionResult,
    aclient: instructor.Instructor,
    model_name: str = DEFAULT_OPENAI_MODEL_NAME,
) -> EpistemicHumilityResult:
    """Run the epistemic humility check via LLM and return the raw result."""
    desc = f"{action_result.selected_action.value} {action_result.action_parameters}" # Corrected field name
    messages = _create_epistemic_humility_messages(desc)
    try:
        result: EpistemicHumilityResult = await aclient.chat.completions.create(
            model=model_name,
            response_model=EpistemicHumilityResult,
            messages=messages,
            max_tokens=384,
        )
        logger.info(f"Epistemic Faculty: Epistemic humility result: {result}")
        return result
    except Exception as e:
        logger.error(f"Epistemic Faculty: Error in epistemic humility: {e}", exc_info=True)
        return EpistemicHumilityResult(
            epistemic_certainty="low",
            identified_uncertainties=[f"LLM error: {str(e)}"],
            reflective_justification=f"LLM error: {str(e)}",
            recommended_action="abort",
        )
