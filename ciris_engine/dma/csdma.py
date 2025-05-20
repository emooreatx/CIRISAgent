from typing import Dict, Any, List, Optional
import logging

import instructor
from openai import AsyncOpenAI
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import CSDMAResult
from ciris_engine.core.config_manager import get_config
from instructor.exceptions import InstructorRetryException

logger = logging.getLogger(__name__)

class CSDMAEvaluator:
    """
    Evaluates a thought for common-sense plausibility using an LLM
    and returns a structured CSDMAResult using the 'instructor' library.
    """

    def __init__(self,
                 aclient: AsyncOpenAI, # Expect raw AsyncOpenAI client
                 model_name: Optional[str] = None, # Allow override, else use config
                 environmental_kg: Any = None,
                 task_specific_kg: Any = None,
                 prompt_overrides: Optional[Dict[str, str]] = None): # Added prompt_overrides
        
        app_config = get_config()
        self.model_name = model_name or app_config.llm_services.openai.model_name
        self.prompt_overrides = prompt_overrides or {} # Store overrides
        
        try:
            configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
            self.instructor_mode = instructor.Mode[configured_mode_str]
        except KeyError:
             logger.warning(f"Invalid instructor_mode '{app_config.llm_services.openai.instructor_mode}' in config. Defaulting to JSON.")
             self.instructor_mode = instructor.Mode.JSON
        
        # Check if the client is already patched by instructor
        if isinstance(aclient, instructor.Instructor):
            logger.debug("CSDMAEvaluator received an already patched instructor client.")
            self.aclient = aclient
            # Optionally, verify if the mode matches the expected mode?
            # if aclient.mode != self.instructor_mode:
            #     logger.warning(f"CSDMAEvaluator received instructor client with mode {aclient.mode.name}, but expected {self.instructor_mode.name}. Using received client anyway.")
        else:
            logger.debug("CSDMAEvaluator received a raw AsyncOpenAI client. Patching with instructor...")
            self.aclient: instructor.Instructor = instructor.patch(aclient, mode=self.instructor_mode)

        self.env_kg = environmental_kg # Placeholder for now
        self.task_kg = task_specific_kg   # Placeholder for now
        # Log the final client type and mode being used
        log_mode = self.aclient.mode.name if hasattr(self.aclient, 'mode') else 'N/A (Raw Client?)'
        logger.info(f"CSDMAEvaluator initialized with model: {self.model_name}. Using instructor client with mode: {log_mode}. Overrides: {self.prompt_overrides is not None}")

    def _create_csdma_messages_for_instructor(self, thought_content: str, context_summary: str = "Standard Earth-based physical context.") -> List[Dict[str,str]]:
        """
        Creates the messages list for the LLM to evaluate common sense plausibility,
        suitable for use with `instructor` and expecting `CSDMAResult`.
        """
        default_system_message = f"""You are a Common Sense Evaluation agent. Your task is to assess a given "thought" for its alignment with general common-sense understanding of the physical world, typical interactions, and resource constraints on Earth, considering the provided context.

Reference CSDMA Steps for Evaluation:
1. Context Grounding: The context is: {context_summary}. **Crucially, assume a standard Earth-based physical reality with all its common implications (e.g., gravity, thermodynamics, material properties like ice melting in a hot environment) unless the thought *explicitly and unambiguously* states it operates in a hypothetical scenario where these specific real-world effects are to be ignored or are altered.** General statements about it being a "problem," "riddle," or "exercise" are not sufficient to ignore obvious physics *unless the problem explicitly states that real-world physics should be suspended for the specific interacting elements in question.*
2. Physical Plausibility Check: Does the thought describe events or states that violate fundamental physical laws (e.g., conservation of energy/mass)? Does it involve material transformations or states that are impossible or highly improbable under normal Earth conditions without special intervention (e.g., ice remaining solid indefinitely in a hot frying pan)? **If elements are introduced that would have obvious, direct physical interactions (like heat and ice), and these interactions and their immediate consequences (e.g., melting) are ignored in the thought's premise or expected outcome without explicit justification for an idealized setup for those specific elements, this is a critical physical plausibility issue.** Flag such instances (e.g., "Physical_Implausibility_Ignored_Interaction", "Requires_Explicit_Idealization_Statement", "Potential_Trick_Question_Physics_Ignored"). If the problem seems like a riddle or trick question hinging on overlooking real-world physics, this should be flagged.
3. Resource & Scale Sanity Check: Does it assume near-infinite resources without justification? Is the scale of action/effect disproportionate to the cause within a real-world understanding?
4. Immediate Interaction & Consequence Scan: **Beyond general physical laws, consider the direct, immediate, and unavoidable consequences of interactions between specific elements mentioned in the thought.** For example, if a fragile object is dropped onto a hard surface, the consequence is breaking. If a flame meets flammable material, it ignites. If ice is placed on a hot surface, it melts. Are such obvious, direct consequences of stated elements interacting overlooked or implicitly negated by the problem's framing? This is a key aspect of common sense.
5. Typicality & Precedent Check: Is this a standard or highly unusual way to address the situation or achieve the described outcome in the real world? Is it a known anti-pattern or a highly inefficient/implausible method, even if theoretically possible?
6. Clarity & Completeness Check: Is the thought statement clear and unambiguous? Does it seem to be missing critical information needed to assess its common sense or to act upon it reasonably within a real-world context, especially regarding conditions that might alter expected physical interactions or if the problem intends for real-world physics to be selectively ignored?

Your response MUST be a single JSON object adhering to the provided schema, with the following keys:
- "common_sense_plausibility_score": A float between 0.0 (highly implausible) and 1.0 (highly plausible). **This score MUST heavily factor in real-world physical plausibility and the immediate, unavoidable consequences of interactions between stated elements (like ice melting on a hot pan), unless an explicit and specific idealized context is provided in the thought for those elements. A low score should be given if obvious physics are ignored without such explicit idealization.**
- "flags": A list of strings identifying any specific common sense violations, physical implausibilities (especially ignored interactions), or clarity issues (e.g., "Physical_Implausibility_Ignored_Interaction", "Atypical_Approach", "Ambiguous_Statement", "Needs_Clarification", "Information_Missing", "Requires_Explicit_Idealization_Statement", "Potential_Trick_Question_Physics_Ignored"). If none, provide an empty list. This field is MANDATORY (even if empty).
- "reasoning": A brief (1-2 sentences) explanation for your score and flags. This field is MANDATORY.
"""
        # Use override if available, otherwise use default
        system_message_content = self.prompt_overrides.get("csdma_system_prompt", default_system_message)
        # Ensure context_summary is still used if the override is a template
        if "{context_summary}" in system_message_content:
            system_message_content = system_message_content.format(context_summary=context_summary)


        user_message = f"Based on the CSDMA framework, evaluate the common sense and clarity of the following thought: \"{thought_content}\""
        return [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message}
        ]

    # Updated signature to use ProcessingQueueItem
    async def evaluate_thought(self, thought_item: ProcessingQueueItem) -> CSDMAResult:
        # Extract thought content string robustly from ProcessingQueueItem.content (Dict[str, Any])
        thought_content_str = ""
        if isinstance(thought_item.content, dict):
            thought_content_str = thought_item.content.get("text", thought_item.content.get("description", str(thought_item.content)))
        else: # Should not happen based on ProcessingQueueItem definition, but handle defensively
             thought_content_str = str(thought_item.content)

        context_summary = "Standard Earth-based physical context, unless otherwise specified in the thought."
        # Example of how context might be overridden from the thought item itself
        # Note: ProcessingQueueItem.content is Dict[str, Any], not str, so direct check is fine.
        # if isinstance(thought_item.content, dict) and "context_override" in thought_item.content:
        #     context_summary = thought_item.content["context_override"]
        # Check initial_context for environment context description, as ProcessingQueueItem stores it there.
        if hasattr(thought_item, 'initial_context') and thought_item.initial_context and "environment_context" in thought_item.initial_context:
            env_ctx = thought_item.initial_context["environment_context"]
            if isinstance(env_ctx, dict) and "description" in env_ctx: # Check if env_ctx is a dict and has 'description'
                context_summary = env_ctx["description"]
            elif isinstance(env_ctx, dict) and "current_channel" in env_ctx: # Fallback to channel name if description missing
                 context_summary = f"Context: Discord channel '{env_ctx['current_channel']}'"
            elif isinstance(env_ctx, str):
                context_summary = env_ctx


        messages = self._create_csdma_messages_for_instructor(thought_content_str, context_summary)

        try:
            csdma_eval: CSDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=CSDMAResult, # Key instructor feature
                messages=messages,
                max_tokens=512 # CSDMA response is usually shorter
            )

            # If raw_llm_response is a field in CSDMAResult and you want to populate it:
            if hasattr(csdma_eval, '_raw_response') and hasattr(csdma_eval, 'raw_llm_response'):
                raw_resp = getattr(csdma_eval, '_raw_response', None)
                if raw_resp:
                    setattr(csdma_eval, 'raw_llm_response', str(raw_resp))


            logger.info(f"CSDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}: Score {csdma_eval.common_sense_plausibility_score:.2f}")
            return csdma_eval

        except InstructorRetryException as e_instr: # Catch specific instructor retry/validation error
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"CSDMA (instructor) InstructorRetryException for thought {thought_item.thought_id}: {error_detail}", exc_info=True)
            # Add required args to exception for fallback result
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
