import logging
from typing import Dict, Any, Optional, Union

import instructor
from openai import AsyncOpenAI

from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import EthicalPDMAResult
from ciris_engine.formatters.prompt_blocks import (
    format_task_context,
    format_system_snapshot,
    format_user_profiles,
    format_parent_task_chain,
    format_thoughts_chain,
    format_user_prompt_blocks,
    format_system_prompt_blocks,
)
from ciris_engine.formatters.escalation import get_escalation_guidance
from ciris_engine.formatters.schema_guidance import format_schema_guidance
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o"

logger = logging.getLogger(__name__)

class EthicalPDMAEvaluator:
    """
    Evaluates a thought against core ethical principles using an LLM
    and returns a structured EthicalPDMAResult using the 'instructor' library.
    """

    # ----------------------------------------------------------------
    # Canonical PDMA Prompt Template
    # ----------------------------------------------------------------
    DEFAULT_TEMPLATE = """
=== Task History ===
{task_history_block}

=== System Guidance ===
You are a CIRIS-aligned Progressive Decision-Making Agent. Follow CIRIS principles—coherence, integrity, and ethical rigor—in every analysis.

=== Escalation Guidance ===
{escalation_guidance_block}

=== System Snapshot ===
{system_snapshot_block}

=== User Profiles ===
{user_profiles_block}
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

    async def evaluate(
        self,
        thought_item: ProcessingQueueItem,
        context: Dict[str, Any],
        schema: Optional[str] = None,
        **kwargs: Any,
    ) -> EthicalPDMAResult:
        """Perform the ethical evaluation using canonical prompt blocks."""

        logger.debug(
            f"Starting EthicalPDMA evaluation for thought ID {thought_item.thought_id}"
        )

        current_task = context["current_task"]
        recent_actions = context["recent_actions"]
        completed_tasks = context.get("completed_tasks", [])
        system_snapshot = context["system_snapshot"]
        user_profiles_list = context.get("user_profiles", {})
        parent_tasks = context.get("parent_tasks", [])
        thoughts_chain = context.get("thoughts_chain", [])
        actions_taken = context.get("actions_taken", 0)
        max_actions = context.get("max_actions", 7)

        task_history_block = format_task_context(
            current_task, recent_actions, completed_tasks
        )
        escalation_block = get_escalation_guidance(actions_taken, max_actions)
        system_snapshot_block = format_system_snapshot(system_snapshot)
        user_profiles_block = format_user_profiles(user_profiles_list)
        parent_tasks_block = format_parent_task_chain(parent_tasks)
        thoughts_chain_block = format_thoughts_chain(thoughts_chain)
        schema_block = format_schema_guidance(schema) if schema else None

        system_message = self.DEFAULT_TEMPLATE.format(
            task_history_block=task_history_block,
            escalation_guidance_block=escalation_block,
            system_snapshot_block=system_snapshot_block,
            user_profiles_block=user_profiles_block,
        )

        user_message = format_user_prompt_blocks(
            parent_tasks_block, thoughts_chain_block, schema_block
        )

        logger.debug(
            f"EthicalPDMA system prompt for thought {thought_item.thought_id}:\n{system_message}"
        )
        logger.debug(
            f"EthicalPDMA user prompt for thought {thought_item.thought_id}:\n{user_message}"
        )

        try:
            response_obj: EthicalPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=EthicalPDMAResult,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                max_retries=self.max_retries,
                **kwargs,
            )

            raw_response_str = None
            if hasattr(response_obj, "_raw_response") and response_obj._raw_response:
                try:
                    raw_response_str = str(response_obj._raw_response)
                    logger.debug("EthicalPDMA: Raw LLM response captured.")
                except Exception as raw_err:  # noqa: BLE001
                    logger.warning(
                        f"EthicalPDMA: Could not serialize raw response: {raw_err}"
                    )
            else:
                logger.debug("EthicalPDMA: No _raw_response attribute found on result.")

            if raw_response_str:
                response_obj.raw_llm_response = raw_response_str

            logger.info(
                f"EthicalPDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}"
            )
            return response_obj

        except Exception as e:  # noqa: BLE001
            logger.error(
                f"EthicalPDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}",
                exc_info=True,
            )
            fallback_data = {
                "Context": f"Error: LLM call via instructor failed - {e}",
                "Alignment-Check": {"error": f"LLM/Instructor error: {e}"},
                "Decision": f"Error: LLM/Instructor error - {e}",
                "Monitoring": {"error": f"LLM/Instructor error: {e}"},
                "raw_llm_response": f"Exception during evaluation: {e}",
            }
            return EthicalPDMAResult.model_validate(fallback_data)


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
