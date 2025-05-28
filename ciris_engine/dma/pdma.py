import logging
from typing import Dict, Any, Optional, Union

import instructor
from openai import AsyncOpenAI

from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.formatters import format_user_profiles, format_system_snapshot
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o"

logger = logging.getLogger(__name__)

class EthicalPDMAEvaluator:
    """
    Evaluates a thought against core ethical principles using an LLM
    and returns a structured EthicalDMAResult using the 'instructor' library.
    """

    def __init__(self,
                 aclient: instructor.Instructor, # Expect an already patched instructor.Instructor client
                 model_name: str = DEFAULT_OPENAI_MODEL_NAME,
                 max_retries: int = 2, # Default to a sensible number of retries
                 # instructor_mode is now determined by the passed aclient
                 prompt_overrides: Optional[Dict[str, str]] = None # Keep prompt_overrides if used by this DMA
                 ):
        """
        Initializes the evaluator with an instructor-patched client.

        Args:
            aclient: An instructor-patched AsyncOpenAI client instance.
            model_name: The name of the LLM model to use.
            max_retries: The maximum number of retries for LLM calls.
            prompt_overrides: Optional dictionary to override default prompts.
        """
        self.aclient = aclient # Use the passed instructor client directly
        self.model_name = model_name
        self.max_retries = max_retries # Store max_retries
        
        # Default prompt template (can be overridden by subclasses or specific instances)
        self.DEFAULT_PROMPT_TEMPLATE: Dict[str, str] = {
            # ... (keep existing default prompt parts if any, or define them here) ...
            "system_guidance_header": """You are a highly meticulous reasoning agent governed by the CIRIS Covenant.
Your task is to execute ALL SIX steps of the Principled Decision-Making Algorithm (PDMA) in response to a user message.
You MUST structure your entire output as a single JSON object that strictly adheres to the provided schema.
ALL fields in the schema are critically important and MUST be populated with substantive, relevant content. Do not omit any fields unless they are explicitly marked as optional in the underlying schema and a null value is appropriate.

The PDMA steps and their corresponding JSON fields (which you MUST generate) are:
""",
            "pdma_step_context": """1.  "Context" (PDMA Step 1: Contextualise):
    - Restate the user's request.
    - List all affected stakeholders.
    - Note any relevant constraints.""",
            "pdma_step_alignment": """2.  "Alignment-Check" (PDMA Step 2: Alignment-Check):
    - This MUST be a dictionary.
    - Include 'plausible_actions': A list of plausible actions considered.
    - Include evaluations for each of the six CIRIS principles: 'do_good', 'avoid_harm', 'honor_autonomy', 'ensure_fairness', 'fidelity_transparency', 'integrity'.
    - Include an evaluation for 'meta_goal_m1' (adaptive coherence).
    - If a principle evaluation is not directly applicable, briefly state why (e.g., "Not directly applicable as no immediate action is proposed yet."). Do not leave the key out.""",
            "pdma_step_conflicts": """3.  "Conflicts" (PDMA Step 3: Conflict-Spot):
    - Identify any trade-offs or principle conflicts discovered.
    - If no conflicts are apparent, you MUST provide the string "No conflicts identified." or null. Do not omit this field if it's required by the schema, otherwise, it can be omitted if truly null and the schema allows.""",
            "pdma_step_resolution": """4.  "Resolution" (PDMA Step 4: Resolve):
    - Explain how conflicts (if any) are resolved using Non-Maleficence priority, Autonomy thresholds, and Justice balancing.
    - If no conflicts were identified, you MUST provide the string "Not applicable as no conflicts were identified." or null. Do not omit this field if it's required by the schema.""",
            "pdma_step_decision": """5.  "Decision" (PDMA Step 5: Decision Rationale):
    - This field is MANDATORY and CRITICAL.
    - Clearly state your ethically-optimal decision, reasoned judgment, or recommended ethical stance.
    - Provide a comprehensive justification for this decision based on the preceding PDMA steps.""",
            "pdma_step_monitoring": """6.  "Monitoring" (PDMA Step 6: Monitor):
    - This field is MANDATORY and CRITICAL.
    - Propose a concrete monitoring plan, including what specific metrics to watch and potential update triggers related to your decision/judgment.
    - This should be a dictionary (e.g., {{"metric_to_watch": "description", "update_trigger": "description"}}) or a descriptive string."""
        }
        self.prompt_template = {**self.DEFAULT_PROMPT_TEMPLATE, **(prompt_overrides or {})}


        # The instructor_mode is inherent in the passed aclient
        logger.info(f"EthicalPDMAEvaluator initialized with model: {self.model_name} (using provided instructor client)")

    async def evaluate(self, thought_item: ProcessingQueueItem) -> EthicalDMAResult:
        """
        Performs the ethical evaluation using the PDMA prompt and instructor.

        Args:
            thought_item: The processing queue item containing the content to evaluate.

        Returns:
            An EthicalDMAResult object containing the structured evaluation or error details.
        """
        original_thought_content = str(thought_item.content)
        logger.debug(f"Starting EthicalPDMA evaluation for thought ID {thought_item.thought_id}")

        system_snapshot_context_str = ""
        user_profile_context_str = ""

        if hasattr(thought_item, 'context') and thought_item.context:
            system_snapshot = thought_item.context.get("system_snapshot")
            if system_snapshot:
                # Format user profiles using the shared formatter
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profile_context_str = format_user_profiles(user_profiles_data)

                # Format the rest of the system snapshot (excluding user profiles as they are handled)
                system_snapshot_context_str = format_system_snapshot(system_snapshot)

        # Combine context strings. User profiles are usually presented first.
        
        # full_context_str = user_profile_context_str + system_snapshot_context_str
        full_context_str = system_snapshot_context_str + user_profile_context_str
        
        # Prepend combined context to the user message content
        user_message_with_context = f"{full_context_str}\nSystem Thought to Evaluate (consider any provided context when performing your ethical analysis): '{original_thought_content}'"
        
        logger.debug(f"EthicalPDMA input to LLM for thought {thought_item.thought_id}:\n{user_message_with_context}")

        # System prompt instructing the LLM on its role and the expected JSON structure
        # using the ALIASED field names.
        pdma_system_guidance = f"""You are a highly meticulous reasoning agent governed by the CIRIS Covenant.
Your task is to execute ALL SIX steps of the Principled Decision-Making Algorithm (PDMA) in response to a user message.
You MUST structure your entire output as a single JSON object that strictly adheres to the provided schema.
ALL fields in the schema are critically important and MUST be populated with substantive, relevant content. Do not omit any fields unless they are explicitly marked as optional in the underlying schema and a null value is appropriate.

The PDMA steps and their corresponding JSON fields (which you MUST generate) are:

1.  "Context": Restate the user's request, list all affected stakeholders, and note any relevant constraints.
2.  "Alignment-Check": This MUST be a dictionary. Include 'plausible_actions', all six CIRIS principles, and 'meta_goal_m1'.
3.  "Conflicts": Identify any trade-offs or principle conflicts discovered. If none, provide "No conflicts identified." or null.
4.  "Resolution": Explain how conflicts (if any) are resolved. If none, provide "Not applicable as no conflicts were identified." or null.
5.  "Decision": This field is MANDATORY and CRITICAL. Clearly state your ethically-optimal decision, reasoned judgment, or recommended ethical stance. Provide a comprehensive justification for this decision based on the preceding PDMA steps.
6.  "Monitoring": This field is MANDATORY and CRITICAL. Propose a concrete monitoring plan, including what specific metrics to watch and potential update triggers related to your decision/judgment. This should be a dictionary or a descriptive string.

IMPORTANT: Your entire response MUST be a single JSON object. The JSON object MUST have these top-level keys, all populated: 'Context', 'Alignment-Check', 'Conflicts', 'Resolution', 'Decision', 'Monitoring'.
"""

        try:
            # Use the instructor-patched client to get a structured response
            response_obj: EthicalDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=EthicalDMAResult,
                # mode= is set when patching the client, not per call
                messages=[
                    {"role": "system", "content": pdma_system_guidance},
                    {"role": "user", "content": f"{user_message_with_context}.\nThat was the context. Now here is the task: Apply the full PDMA process to the following user message (which may include prefixed system context) and provide your complete structured analysis."}
                ],
                max_retries=self.max_retries # Pass configured max_retries here
                # Add other parameters like max_tokens, temperature if needed
            )

            # Attempt to capture raw response if available (may vary by instructor version)
            raw_response_str = None
            if hasattr(response_obj, '_raw_response') and response_obj._raw_response:
               try:
                   # Accessing the raw response might differ; this is a common pattern
                   raw_response_str = str(response_obj._raw_response)
                   logger.debug(f"EthicalPDMA: Raw LLM response captured.")
               except Exception as raw_err:
                   logger.warning(f"EthicalPDMA: Could not serialize raw response: {raw_err}")
            else:
                logger.debug("EthicalPDMA: No _raw_response attribute found on result.")

            # Add raw response to the object if captured (field exists in schema)
            if raw_response_str:
                response_obj.raw_llm_response = raw_response_str

            logger.info(f"EthicalPDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}")
            return response_obj

        except Exception as e:
            logger.error(f"EthicalPDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            # Return a fallback/error EthicalDMAResult instance
            # Ensure all aliased fields are present or Pydantic will complain here too if they are required.
            # Use the alias directly for instantiation when populate_by_name=True
            fallback_data = {
                "Context": f"Error: LLM call via instructor failed - {e}",
                "Alignment-Check": {"error": f"LLM/Instructor error: {e}"},
                "Decision": f"Error: LLM/Instructor error - {e}",
                "Monitoring": {"error": f"LLM/Instructor error: {e}"},
                # Optional fields (Conflicts, Resolution) default to None per schema
                "raw_llm_response": f"Exception during evaluation: {e}"
            }
            # Use model_validate to handle potential validation issues with fallback
            return EthicalDMAResult.model_validate(fallback_data)


    def __repr__(self) -> str:
        return f"<EthicalPDMAEvaluator model='{self.model_name}' (using instructor)>"

# Example Usage (Conceptual - requires setup)
# async def main():
#     from ciris_engine.services.llm_client import CIRISLLMClient # Assuming client setup
#     llm_client_instance = CIRISLLMClient() # Get configured client
#     instructor_client = llm_client_instance.instruct_client # Get patched client
#
#     pdma_evaluator = EthicalPDMAEvaluator(aclient=instructor_client)
#
#     # Create a dummy thought item
#     dummy_thought = ProcessingQueueItem(
#         thought_id="dummy-123",
#         source_task_id="task-abc",
#         content="Should I invest in cryptocurrency?",
#         priority=5,
#         thought_type="query"
#     )
#
#     result = await pdma_evaluator.evaluate(dummy_thought)
#     print(result.model_dump_json(indent=2, by_alias=True)) # Use by_alias=True for aliased keys
#
# if __name__ == "__main__":
#    # Basic logging setup for example
#    logging.basicConfig(level=logging.INFO)
#    # asyncio.run(main()) # Requires running LLM/mocks
