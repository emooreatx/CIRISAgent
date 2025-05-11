# src/ciris_engine/dma/pdma.py
import logging
import os # For API keys
from typing import Dict, Any, Optional # Keep existing typings

import instructor # New import
from openai import AsyncOpenAI # New import

# Keep existing imports from ciris_engine
from ciris_engine.core.data_schemas import ThoughtQueueItem, EthicalPDMAResult
# Note: We might not need CIRISLLMClient here anymore if using instructor directly with AsyncOpenAI
# from ciris_engine.services.llm_client import CIRISLLMClient # Potentially remove if not used
from ciris_engine.core.config import DEFAULT_OPENAI_MODEL_NAME # For model name


class EthicalPDMAEvaluator:
    """
    Evaluates a thought against core ethical principles using an LLM
    and returns a structured EthicalPDMAResult using the 'instructor' library.
    """

    def __init__(self, aclient: instructor.Instructor, model_name: str = DEFAULT_OPENAI_MODEL_NAME): # Takes model_name for flexibility
        # API key should be handled by OpenAI library via env var OPENAI_API_KEY
        # or explicitly passed if necessary for AsyncOpenAI.
        # For instructor, you patch an instance of the OpenAI client.
        # self.aclient = instructor.patch(AsyncOpenAI( # REMOVED - client is now injected
            # api_key=os.environ.get("OPENAI_API_KEY"), # Handled by library if env var is set
            # base_url=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1") # Handled by library
        # ))
        self.aclient = aclient # Use the injected client
        self.model_name = model_name
        # The prompt for ethical PDMA needs to guide the LLM but the schema enforcement
        # will now be handled by instructor and the EthicalPDMAResult model.
        self.prompt_template = self._build_ethical_pdma_prompt_template()

    def _build_ethical_pdma_prompt_template(self) -> str:
        # This is the prompt that describes the PDMA task to the LLM.
        # It no longer needs to specify "Output only the JSON object" as
        # instructor will handle forcing the output to match EthicalPDMAResult.
        # However, it's still good practice to tell the LLM its output will be structured.
        return f"""You are a reasoning agent governed by the CIRIS Covenant.
At every turn you MUST execute the Principled Decision-Making Algorithm (PDMA) in order:

1.  **Contextualise**: Restate the user's request and list all affected stakeholders & constraints.
2.  **Alignment-Check**: Evaluate each plausible action against the six principles (Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Fidelity/Transparency, Integrity) and Meta-Goal M-1 (adaptive coherence).
3.  **Conflict-Spot**: Identify trade-offs or principle conflicts.
4.  **Resolve**: Apply Non-Maleficence priority, Autonomy thresholds, and Justice balancing.
5.  **Decision Rationale**: Choose the ethically-optimal stance/judgment and explain *why* in a comprehensive manner.
6.  **Monitor**: State one concrete metric you would watch related to this stance/judgment.

Your response will be structured according to a predefined schema with fields for each of these steps (context_analysis, alignment_check, conflicts, resolution, decision_rationale, monitoring_plan).
Please provide detailed and thoughtful content for each field.

User Message to Evaluate:
{{user_message}}
""" # Using {{user_message}} as a placeholder for instructor or direct formatting.

    async def evaluate(self, thought_item: ThoughtQueueItem) -> EthicalPDMAResult:
        user_message_content = str(thought_item.content)
        # The prompt passed to the LLM doesn't need explicit JSON instructions anymore
        # if using instructor with a response_model.
        # However, the system message should still guide the LLM about its role.

        # The prompt for the user role might just be the user_message_content,
        # and the system role would contain the PDMA instructions.

        # Using instructor's `response_model`
        try:
            # The `self.prompt_template` can be the system message,
            # or you can structure messages list as per instructor examples.
            # The key is `response_model=EthicalPDMAResult`.

            # Example of structuring for instructor based on its typical usage:
            # The system prompt sets the overall task.
            # The user prompt provides the specific content to analyze.
            # The content from _build_ethical_pdma_prompt_template IS the system prompt.

            # system_prompt_content = self.prompt_template.replace("{{user_message}}", user_message_content) # Not using this approach

            # Alternative way, closer to standard OpenAI calls that instructor patches:
            # The prompt previously used for `call_llm` can be adapted.
            # The `create_llm_prompt` method (that was generating the full text for the LLM)
            # should be refactored. The part describing the PDMA steps is the "system" part.
            # The "User: {message_content}" part is the "user" part.

            # Refactoring the old `create_llm_prompt` from PDMA evaluator:
            # Old prompt structure:
            # intro_to_pdma_steps + specific_user_message_section + json_instruction_section
            # New structure for instructor:
            # System message: intro_to_pdma_steps + general_guidance_for_structured_output
            # User message: specific_user_message_content

            # Let's define the system prompt part:
            pdma_system_guidance = f"""You are a highly meticulous reasoning agent governed by the CIRIS Covenant.
Your task is to execute ALL SIX steps of the Principled Decision-Making Algorithm (PDMA) in response to a user message.
You MUST structure your entire output as a single JSON object that strictly adheres to the provided schema.
ALL fields in the schema are critically important and MUST be populated with substantive, relevant content. Do not omit any fields.

The PDMA steps and their corresponding JSON fields (which you MUST generate) are:

1.  'context_analysis' (PDMA Step 1: Contextualise):
    - Restate the user's request.
    - List all affected stakeholders.
    - Note any relevant constraints.

2.  'alignment_check' (PDMA Step 2: Alignment-Check):
    - This MUST be a dictionary.
    - Include 'plausible_actions': A list of plausible actions considered.
    - Include evaluations for each of the six CIRIS principles: 'do_good', 'avoid_harm', 'honor_autonomy', 'ensure_fairness', 'fidelity_transparency', 'integrity'.
    - Include an evaluation for 'meta_goal_m1' (adaptive coherence).
    - If a principle evaluation is not directly applicable, briefly state why (e.g., "Not directly applicable as no immediate action is proposed yet."). Do not leave the key out.

3.  'conflicts' (PDMA Step 3: Conflict-Spot):
    - Identify any trade-offs or principle conflicts discovered.
    - If no conflicts are apparent, you MUST provide the string "No conflicts identified." or null. Do not omit this field.

4.  'resolution' (PDMA Step 4: Resolve):
    - Explain how conflicts (if any) are resolved using Non-Maleficence priority, Autonomy thresholds, and Justice balancing.
    - If no conflicts were identified, you MUST provide the string "Not applicable as no conflicts were identified." or null. Do not omit this field.

5.  'decision_rationale' (PDMA Step 5: Decision Rationale):
    - This field is MANDATORY and CRITICAL.
    - Clearly state your ethically-optimal decision, reasoned judgment, or recommended ethical stance.
    - Provide a comprehensive justification for this decision based on the preceding PDMA steps.

6.  'monitoring_plan' (PDMA Step 6: Monitor):
    - This field is MANDATORY and CRITICAL.
    - Propose a concrete monitoring plan, including what specific metrics to watch and potential update triggers related to your decision/judgment.
    - This should be a dictionary (e.g., {{"metric_to_watch": "description", "update_trigger": "description"}}) or a descriptive string.

Adhere strictly to this structure for the JSON output. Every field mentioned above must be present in your JSON response.
"""

            # The actual call using instructor:
            response_obj: EthicalPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=EthicalPDMAResult, # This is the key `instructor` feature
                messages=[
                    {"role": "system", "content": pdma_system_guidance},
                    {"role": "user", "content": f"Apply the full PDMA process to the following user message and provide your complete structured analysis: '{user_message_content}'"}
                ]
                # max_tokens=1500, # REMOVED THIS LINE
                # temperature=0.0, # Optional: keep for determinism if desired
            )
            # `instructor` should ensure `response_obj` is an instance of `EthicalPDMAResult`
            # or raise an error if it can't validate/coerce.

            # Add the raw response if available and if your Pydantic model expects it
            # `instructor` might not provide the raw string easily if it directly gives the Pydantic object.
            # You might need to see how `instructor` handles this or if it's necessary.
            # For now, let's assume `response_obj` is the Pydantic model.
            # If raw_llm_response is needed, we might need a more complex setup or to
            # make a raw call first, then parse with instructor if that's how it works.
            # Often, the raw response is accessible via an attribute on the returned object with instructor.
            # Let's assume `response_obj` is sufficient and `raw_llm_response` in Pydantic can be optional.
            if hasattr(response_obj, '_raw_response'): # Check if instructor adds it
               response_obj.raw_llm_response = str(response_obj._raw_response)

            logging.info(f"EthicalPDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}")
            return response_obj

        except Exception as e:
            logging.error(f"EthicalPDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            # Return a fallback/error EthicalPDMAResult instance
            return EthicalPDMAResult(
                context_analysis=f"Error: LLM call via instructor failed - {e}",
                alignment_check={"error": f"LLM/Instructor error: {e}"},
                decision_rationale=f"Error: LLM/Instructor error - {e}",
                monitoring_plan={"error": f"LLM/Instructor error: {e}"},
                raw_llm_response=f"Exception: {e}"
            )

    def __repr__(self) -> str:
        return f"<EthicalPDMAEvaluator model='{self.model_name}' (using instructor)>"
