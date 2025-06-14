from typing import Dict, Any, List
import logging
import asyncio


from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
)
from ciris_engine.utils import COVENANT_TEXT

DEFAULT_OPENAI_MODEL_NAME = "gpt-4o"


logger = logging.getLogger(__name__)


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
        "You are the CIRIS Epistemic Optimization Veto Shard (CIRIS-EOV), "
        "a critical evaluator within the CIRIS Agent epistemic faculties. "
        "Critically evaluate ONLY the proposed action below.  "
        "Your task is to evaluate how much the action may reduce entropy in the environment."
        "Most actions may reduce entropy by say 0.1 to 0.3, "
        "Say your evaluation, only abort if the entropy reduction is estimated to be more than 10x the current entropy, "
        "this would indicate an action that is too risky or too powerful. "
        "You are not a decision-maker, but a reflective assessor. "
        "You are judging what you see here, not the absence of information. "
        "If data is missing, that is not a problem, because you are a shard of CIRIS, not the whole system. "
        "This action has already passed through many layers of CIRIS Agent's ethical guardrails, "
        "so you can assume it is generally safe to proceed unless you see a clear issue. "
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
        "epistemic_certainty (float 0.0–1.0), identified_uncertainties, "
        "reflective_justification, recommended_action (proceed|ponder|defer). "
        "Calibration examples: 'low'=0.0, 'moderate'=0.5, 'high'=1.0. "
        "Example: {\"epistemic_certainty\": 0.5, \"identified_uncertainties\": [\"ambiguous requirements\"], \"reflective_justification\": \"Some details unclear\", \"recommended_action\": \"ponder\"}"
    )
    user_prompt = f"Proposed action output: {action_description}"
    return [
        {"role": "system", "content": COVENANT_TEXT},
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

async def calculate_epistemic_values(
    text_to_evaluate: str,
    sink,
    model_name: str = DEFAULT_OPENAI_MODEL_NAME
) -> Dict[str, Any]:
    """
    Get both entropy and coherence values using `instructor` for structured output.
    These two calls can be made concurrently.
    """
    results = {"entropy": 0.1, "coherence": 0.9, "error": None}

    async def get_entropy() -> None:
        try:
            messages = _create_entropy_messages_for_instructor(text_to_evaluate)
            entropy_eval, _ = await sink.generate_structured_sync(
                messages=messages,
                response_model=EntropyResult,
                handler_name="epistemic_entropy",
                max_tokens=64,
                temperature=0.0
            )
            logger.debug(f"Epistemic Faculty: Entropy evaluation result: {entropy_eval}")
            return entropy_eval.entropy
        except Exception as e:
            logger.error(f"Epistemic Faculty: Error getting entropy: {e}", exc_info=True)
            results["entropy_error"] = f"Entropy Error: {str(e)}"
            return 0.1

    async def get_coherence() -> None:
        try:
            messages = _create_coherence_messages_for_instructor(text_to_evaluate)
            coherence_eval, _ = await sink.generate_structured_sync(
                messages=messages,
                response_model=CoherenceResult,
                handler_name="epistemic_coherence",
                max_tokens=64,
                temperature=0.0
            )
            logger.debug(f"Epistemic Faculty: Coherence evaluation result: {coherence_eval}")
            return coherence_eval.coherence
        except Exception as e:
            logger.error(f"Epistemic Faculty: Error getting coherence: {e}", exc_info=True)
            results["coherence_error"] = f"Coherence Error: {str(e)}"
            return 0.9

    try:
        entropy_val, coherence_val = await asyncio.gather(
            get_entropy(),
            get_coherence(),
            return_exceptions=False
        )
        results["entropy"] = min(max(float(entropy_val), 0.0), 1.0)
        results["coherence"] = min(max(float(coherence_val), 0.0), 1.0)

    except Exception as e_gather:
        logger.error(f"Epistemic Faculty: Error in asyncio.gather: {e_gather}", exc_info=True)
        results["error"] = results.get("error", "") + f" Gather Error: {str(e_gather)};"

    general_error_messages: List[Any] = []
    if "entropy_error" in results:
        general_error_messages.append(results["entropy_error"])
        del results["entropy_error"]
    if "coherence_error" in results:
        general_error_messages.append(results["coherence_error"])
        del results["coherence_error"]

    if general_error_messages:
        existing_error = results.get("error") or ""
        if existing_error and not existing_error.endswith("; "):
             existing_error += "; "
        results["error"] = existing_error + "; ".join(general_error_messages)
    elif results["error"] is None:
        if "error" in results:
            del results["error"]


    logging.info(f"Epistemic values calculated: Entropy={results.get('entropy', 0.1):.2f}, Coherence={results.get('coherence', 0.9):.2f}")
    return results

async def evaluate_optimization_veto(
    action_result: ActionSelectionResult,
    sink,
    model_name: str = DEFAULT_OPENAI_MODEL_NAME,
) -> OptimizationVetoResult:
    """Run the optimization veto check via LLM and return the raw result."""
    action_desc = f"{action_result.selected_action.value} {action_result.action_parameters}" # Corrected field name
    messages = _create_optimization_veto_messages(action_desc)
    try:
        result, _ = await sink.generate_structured_sync(
            messages=messages,
            response_model=OptimizationVetoResult,
            handler_name="epistemic_optimization_veto",
            max_tokens=500,
            temperature=0.0
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
    sink,
    model_name: str = DEFAULT_OPENAI_MODEL_NAME,
) -> EpistemicHumilityResult:
    """Run the epistemic humility check via LLM and return the raw result."""
    desc = f"{action_result.selected_action.value} {action_result.action_parameters}"
    messages = _create_epistemic_humility_messages(desc)
    try:
        result, _ = await sink.generate_structured_sync(
            messages=messages,
            response_model=EpistemicHumilityResult,
            handler_name="epistemic_humility",
            max_tokens=384,
            temperature=0.0
        )
        # Fallback: convert string epistemic_certainty to float if needed
        if isinstance(result.epistemic_certainty, str):
            mapping = {"low": 0.0, "moderate": 0.5, "high": 1.0}
            val = mapping.get(result.epistemic_certainty.lower(), 0.0)
            result.epistemic_certainty = val
        logger.info(f"Epistemic Faculty: Epistemic humility result: {result}")
        return result
    except Exception as e:
        logger.error(f"Epistemic Faculty: Error in epistemic humility: {e}", exc_info=True)
        return EpistemicHumilityResult(
            epistemic_certainty=0.0,
            identified_uncertainties=[f"LLM error: {str(e)}"],
            reflective_justification=f"LLM error: {str(e)}",
            recommended_action="abort",
        )
