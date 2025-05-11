# src/ciris_engine/dma/pdma.py
import logging
import os # For API keys
from typing import Dict, Any, Optional # Keep existing typings

import instructor 
from openai import AsyncOpenAI 

from ciris_engine.core.data_schemas import ThoughtQueueItem, EthicalPDMAResult
from ciris_engine.core.config import DEFAULT_OPENAI_MODEL_NAME 

logger = logging.getLogger(__name__) # Added logger

class EthicalPDMAEvaluator:
    """
    Evaluates a thought against core ethical principles using an LLM
    and returns a structured EthicalPDMAResult using the 'instructor' library.
    """

    def __init__(self, aclient: instructor.Instructor, model_name: str = DEFAULT_OPENAI_MODEL_NAME):
        self.aclient = aclient 
        self.model_name = model_name
        # The prompt_template is now built within the evaluate method or a helper,
        # as it's static text. No need to call _build_ethical_pdma_prompt_template() here.

    async def evaluate(self, thought_item: ThoughtQueueItem) -> EthicalPDMAResult:
        user_message_content = str(thought_item.content)

        # System prompt instructing the LLM on its role and the expected JSON structure
        # using the ALIASED field names.
        pdma_system_guidance = f"""You are a highly meticulous reasoning agent governed by the CIRIS Covenant.
Your task is to execute ALL SIX steps of the Principled Decision-Making Algorithm (PDMA) in response to a user message.
You MUST structure your entire output as a single JSON object that strictly adheres to the provided schema.
ALL fields in the schema are critically important and MUST be populated with substantive, relevant content. Do not omit any fields unless they are explicitly marked as optional in the underlying schema and a null value is appropriate.

The PDMA steps and their corresponding JSON fields (which you MUST generate) are:

1.  "Context" (PDMA Step 1: Contextualise):
    - Restate the user's request.
    - List all affected stakeholders.
    - Note any relevant constraints.

2.  "Alignment-Check" (PDMA Step 2: Alignment-Check):
    - This MUST be a dictionary.
    - Include 'plausible_actions': A list of plausible actions considered.
    - Include evaluations for each of the six CIRIS principles: 'do_good', 'avoid_harm', 'honor_autonomy', 'ensure_fairness', 'fidelity_transparency', 'integrity'.
    - Include an evaluation for 'meta_goal_m1' (adaptive coherence).
    - If a principle evaluation is not directly applicable, briefly state why (e.g., "Not directly applicable as no immediate action is proposed yet."). Do not leave the key out.

3.  "Conflicts" (PDMA Step 3: Conflict-Spot):
    - Identify any trade-offs or principle conflicts discovered.
    - If no conflicts are apparent, you MUST provide the string "No conflicts identified." or null. Do not omit this field if it's required by the schema, otherwise, it can be omitted if truly null and the schema allows.

4.  "Resolution" (PDMA Step 4: Resolve):
    - Explain how conflicts (if any) are resolved using Non-Maleficence priority, Autonomy thresholds, and Justice balancing.
    - If no conflicts were identified, you MUST provide the string "Not applicable as no conflicts were identified." or null. Do not omit this field if it's required by the schema.

5.  "Decision" (PDMA Step 5: Decision Rationale):
    - This field is MANDATORY and CRITICAL.
    - Clearly state your ethically-optimal decision, reasoned judgment, or recommended ethical stance.
    - Provide a comprehensive justification for this decision based on the preceding PDMA steps.

6.  "Monitoring" (PDMA Step 6: Monitor):
    - This field is MANDATORY and CRITICAL.
    - Propose a concrete monitoring plan, including what specific metrics to watch and potential update triggers related to your decision/judgment.
    - This should be a dictionary (e.g., {{"metric_to_watch": "description", "update_trigger": "description"}}) or a descriptive string.

Adhere strictly to this structure for the JSON output. Every field mentioned above as MANDATORY must be present in your JSON response, using the specified capitalized/aliased key names.
"""

        try:
            response_obj: EthicalPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=EthicalPDMAResult, 
                messages=[
                    {"role": "system", "content": pdma_system_guidance},
                    {"role": "user", "content": f"Apply the full PDMA process to the following user message and provide your complete structured analysis: '{user_message_content}'"}
                ]
            )
            
            if hasattr(response_obj, '_raw_response'): 
               response_obj.raw_llm_response = str(response_obj._raw_response)

            logger.info(f"EthicalPDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}")
            return response_obj

        except Exception as e:
            logger.error(f"EthicalPDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            # Return a fallback/error EthicalPDMAResult instance
            # Ensure all aliased fields are present or Pydantic will complain here too if they are required.
            # Since 'Decision' and 'Monitoring' are required, they must be in the fallback.
            return EthicalPDMAResult(
                Context=f"Error: LLM call via instructor failed - {e}", # Using alias
                Alignment_Check={"error": f"LLM/Instructor error: {e}"}, # Using alias (note: Pydantic might auto-convert if alias is 'Alignment-Check')
                Decision=f"Error: LLM/Instructor error - {e}", # Using alias
                Monitoring={"error": f"LLM/Instructor error: {e}"}, # Using alias
                # Optional fields can be omitted if their default is None in the Pydantic model
                # Conflicts=None,
                # Resolution=None,
                raw_llm_response=f"Exception: {e}"
            )

    def __repr__(self) -> str:
        return f"<EthicalPDMAEvaluator model='{self.model_name}' (using instructor)>"
