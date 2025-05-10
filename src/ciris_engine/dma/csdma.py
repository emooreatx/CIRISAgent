# src/ciris_engine/dma/csdma.py
from typing import Dict, Any, List, Optional
import logging

import instructor # New import
from openai import AsyncOpenAI # New import

from ciris_engine.core.data_schemas import ThoughtQueueItem, CSDMAResult
from ciris_engine.core.config import DEFAULT_OPENAI_MODEL_NAME
# Remove CIRISLLMClient import if no longer used directly
# from ciris_engine.services.llm_client import CIRISLLMClient, LLMResponse 

# Setup logger for this module
logger = logging.getLogger(__name__)

class CSDMAEvaluator:
    """
    Evaluates a thought for common-sense plausibility using an LLM
    and returns a structured CSDMAResult using the 'instructor' library.
    """

    def __init__(self, model_name: str = DEFAULT_OPENAI_MODEL_NAME, environmental_kg: Any = None, task_specific_kg: Any = None):
        # Each DMA using instructor will manage its own patched client for now
        self.aclient = instructor.patch(AsyncOpenAI())
        self.model_name = model_name
        self.env_kg = environmental_kg # Placeholder for now
        self.task_kg = task_specific_kg   # Placeholder for now

    def _create_csdma_messages_for_instructor(self, thought_content: str, context_summary: str = "Standard Earth-based physical context.") -> List[Dict[str,str]]:
        """
        Creates the messages list for the LLM to evaluate common sense plausibility,
        suitable for use with `instructor` and expecting `CSDMAResult`.
        """
        system_message = f"""You are a Common Sense Evaluation agent. Your task is to assess a given "thought" for its alignment with general common-sense understanding of the physical world, typical interactions, and resource constraints on Earth, considering the provided context.

Reference CSDMA Steps for Evaluation:
1. Context Grounding: The context is: {context_summary}
2. Physical Plausibility Check: Does it violate conservation laws? Impossible material transformations? Ignore biological needs?
3. Resource & Scale Sanity Check: Assume near-infinite resources? Scale disproportionate to cause?
4. Immediate Interaction & Consequence Scan: Obvious physical reactions? Typical agent reactions ignored? Obvious feedback loops?
5. Typicality & Precedent Check: Standard way to address situation? Known anti-pattern?

Your response MUST be a single JSON object adhering to the provided schema, with the following keys:
- "common_sense_plausibility_score": A float between 0.0 (highly implausible) and 1.0 (highly plausible). This field is MANDATORY.
- "flags": A list of strings identifying any specific common sense violations (e.g., "Physical_Implausibility", "Atypical_Approach"). If none, provide an empty list. This field is MANDATORY (even if empty).
- "reasoning": A brief (1-2 sentences) explanation for your score and flags. This field is MANDATORY.
"""
        user_message = f"Based on the CSDMA framework, evaluate the common sense of the following thought: \"{thought_content}\""
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    async def evaluate_thought(self, thought_item: ThoughtQueueItem) -> CSDMAResult:
        thought_content_str = str(thought_item.content) # Ensure it's a string
        context_summary = "Standard Earth-based physical context, unless otherwise specified in the thought."
        # Example of how context might be overridden from the thought item itself
        if isinstance(thought_item.content, dict) and "context_override" in thought_item.content:
            context_summary = thought_item.content["context_override"]
        elif thought_item.initial_context and "environment_context" in thought_item.initial_context:
            # Attempt to get a more specific context if available from initial_context
            env_ctx = thought_item.initial_context["environment_context"]
            if isinstance(env_ctx, dict) and "description" in env_ctx:
                context_summary = env_ctx["description"]
            elif isinstance(env_ctx, str):
                context_summary = env_ctx


        messages = self._create_csdma_messages_for_instructor(thought_content_str, context_summary)

        try:
            csdma_eval: CSDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=CSDMAResult, # Key instructor feature
                messages=messages,
                max_tokens=512 # CSDMA response is usually shorter
                # temperature=0.0, # Consider for more deterministic structured output
            )

            # Ensure score is within Pydantic model's validation range (ge=0.0, le=1.0)
            # Instructor should handle this if Pydantic model has constraints.
            # If raw_llm_response is a field in CSDMAResult and you want to populate it:
            if hasattr(csdma_eval, '_raw_response') and hasattr(csdma_eval, 'raw_llm_response'):
                csdma_eval.raw_llm_response = str(csdma_eval._raw_response)

            logger.info(f"CSDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}: Score {csdma_eval.common_sense_plausibility_score:.2f}")
            return csdma_eval

        except instructor.exceptions.InstructorRetryException as e_instr: # Catch specific instructor retry/validation error
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"CSDMA (instructor) InstructorRetryException for thought {thought_item.thought_id}: {error_detail}", exc_info=True)
            return CSDMAResult(
                common_sense_plausibility_score=0.0, # Default to lowest plausibility on error
                flags=["Instructor_ValidationError"],
                reasoning=f"Failed CSDMA evaluation via instructor due to validation error: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e: # Catch other potential errors (API connection, etc.)
            logger.error(f"CSDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            return CSDMAResult(
                common_sense_plausibility_score=0.0, # Default to lowest plausibility on error
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed CSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<CSDMAEvaluator model='{self.model_name}' (using instructor)>"
