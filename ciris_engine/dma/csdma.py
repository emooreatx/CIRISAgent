from typing import Dict, Any, List, Optional
import logging

import instructor
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.protocols.dma_interface import CSDMAInterface
from ciris_engine.schemas.dma_results_v1 import CSDMAResult
from ciris_engine.config.config_manager import get_config
from ciris_engine.formatters import (
    format_system_snapshot,
    format_user_profiles,
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)
from instructor.exceptions import InstructorRetryException
from ciris_engine.utils import COVENANT_TEXT

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = """=== Common Sense DMA Guidance ===
You are a Common Sense Evaluation agent. Your task is to assess a given "thought" for its alignment with general common-sense understanding of the physical world, typical interactions, and resource constraints on Earth, considering the provided context.

Reference CSDMA Steps for Evaluation:
1. Context Grounding: The context is: {context_summary}. **Crucially, assume a standard Earth-based physical reality with all its common implications (e.g., gravity, thermodynamics, material properties like ice melting in a hot environment) unless the thought *explicitly and unambiguously* states it operates in a hypothetical scenario where these specific real-world effects are to be ignored or are altered.** General statements about it being a "problem," "riddle," or "exercise" are not sufficient to ignore obvious physics *unless the problem explicitly states that real-world physics should be suspended for the specific interacting elements in question.*
2. Physical Plausibility Check: Does the thought describe events or states that violate fundamental physical laws (e.g., conservation of energy/mass)? Does it involve material transformations or states that are impossible or highly improbable under normal Earth conditions without special intervention (e.g., ice remaining solid indefinitely in a hot frying pan)? **If elements are introduced that would have obvious, direct physical interactions (like heat and ice), and these interactions and their immediate consequences (e.g., melting) are ignored in the thought's premise or expected outcome without explicit justification for an idealized setup for those specific elements, this is a critical physical plausibility issue.** Flag such instances (e.g., "Physical_Implausibility_Ignored_Interaction", "Requires_Explicit_Idealization_Statement", "Potential_Trick_Question_Physics_Ignored"). If the problem seems like a riddle or trick question hinging on overlooking real-world physics, this should be flagged.
3. Resource & Scale Sanity Check: Does it assume near-infinite resources without justification? Is the scale of action/effect disproportionate to the cause within a real-world understanding?
4. Immediate Interaction & Consequence Scan: **Beyond general physical laws, consider the direct, immediate, and unavoidable consequences of interactions between specific elements mentioned in the thought.** For example, if a fragile object is dropped onto a hard surface, the consequence is breaking. If a flame meets flammable material, it ignites. If ice is placed on a hot surface, it melts. Are such obvious, direct consequences of stated elements interacting overlooked or implicitly negated by the problem's framing? This is a key aspect of common sense.
5. Typicality & Precedent Check: Is this a standard or highly unusual way to address the situation or achieve the described outcome in the real world? Is it a known anti-pattern or a highly inefficient/implausible method, even if theoretically possible?
6. Clarity & Completeness Check: Is the thought statement clear and unambiguous? Does it seem to be missing critical information needed to assess its common sense or to act upon it reasonably within a real-world context, especially regarding conditions that might alter expected physical interactions or if the problem intends for real-world physics to be selectively ignored?

Your response MUST be a single JSON object adhering to the provided schema, with the following keys:
- "plausibility_score": A float between 0.0 (highly implausible) and 1.0 (highly plausible). **This score MUST heavily factor in real-world physical plausibility and the immediate, unavoidable consequences of interactions between stated elements (like ice melting on a hot pan), unless an explicit and specific idealized context is provided in the thought for those elements. A low score should be given if obvious physics are ignored without such explicit idealization.**
- "flags": A list of strings identifying any specific common sense violations, physical implausibilities (especially ignored interactions), or clarity issues (e.g., "Physical_Implausibility_Ignored_Interaction", "Atypical_Approach", "Ambiguous_Statement", "Needs_Clarification", "Information_Missing", "Requires_Explicit_Idealization_Statement", "Potential_Trick_Question_Physics_Ignored"). If none, provide an empty list. This field is MANDATORY (even if empty).
- "reasoning": A brief (1-2 sentences) explanation for your score and flags. This field is MANDATORY.

"""

class CSDMAEvaluator(BaseDMA, CSDMAInterface):
    """
    Evaluates a thought for common-sense plausibility using an LLM
    and returns a structured CSDMAResult using the 'instructor' library.
    """

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: Optional[str] = None,
        max_retries: int = 2,
        environmental_kg: Optional[Any] = None,
        task_specific_kg: Optional[Any] = None,
        prompt_overrides: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> None:

        app_config = get_config()
        resolved_model = model_name or app_config.llm_services.openai.model_name

        try:
            configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
            instructor_mode = instructor.Mode[configured_mode_str]
        except KeyError:
            logger.warning(
                f"Invalid instructor_mode '{app_config.llm_services.openai.instructor_mode}' in config. Defaulting to JSON."
            )
            instructor_mode = instructor.Mode.JSON

        super().__init__(
            service_registry=service_registry,
            model_name=resolved_model,
            max_retries=max_retries,
            prompt_overrides=prompt_overrides,
            instructor_mode=instructor_mode,
            **kwargs
        )

        self.prompt_overrides = prompt_overrides or {}
        

        # Client will be retrieved from the service registry during evaluation

        self.env_kg = environmental_kg # Placeholder for now
        self.task_kg = task_specific_kg   # Placeholder for now
        # Log the final client type and mode being used
        log_mode = self.instructor_mode.name
        logger.info(
            f"CSDMAEvaluator initialized with model: {self.model_name}. "
            f"Using instructor client with mode: {log_mode}. Overrides: {self.prompt_overrides is not None}"
        )

    def _create_csdma_messages_for_instructor(
        self,
        thought_content: str,
        context_summary: str,
        identity_context_block: str,
        system_snapshot_block: str,
        user_profiles_block: str,
    ) -> List[Dict[str, str]]:
        """Assemble prompt messages using canonical formatting utilities."""
        system_guidance = self.prompt_overrides.get("csdma_system_prompt", DEFAULT_TEMPLATE)
        if "{context_summary}" in system_guidance:
            system_guidance = system_guidance.format(context_summary=context_summary)

        system_message = format_system_prompt_blocks(
            identity_context_block,
            "",
            system_snapshot_block,
            user_profiles_block,
            None,
            system_guidance,
        )

        user_message = format_user_prompt_blocks(
            format_parent_task_chain([]),
            format_thoughts_chain([{"content": thought_content}]),
            None,
        )

        return [
            {"role": "system", "content": COVENANT_TEXT},
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    async def evaluate_thought(self, thought_item: ProcessingQueueItem) -> CSDMAResult:
        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for CSDMA evaluation")

        aclient = instructor.patch(llm_service.get_client().client, mode=self.instructor_mode)

        thought_content_str = str(thought_item.content)

        context_summary = "Standard Earth-based physical context, unless otherwise specified in the thought."
        if hasattr(thought_item, 'initial_context') and thought_item.initial_context and "environment_context" in thought_item.initial_context:
            env_ctx = thought_item.initial_context["environment_context"]
            if isinstance(env_ctx, dict) and "description" in env_ctx:
                context_summary = env_ctx["description"]
            elif isinstance(env_ctx, dict) and "current_channel" in env_ctx:
                 context_summary = f"Context: Discord channel '{env_ctx['current_channel']}'"
            elif isinstance(env_ctx, str):
                context_summary = env_ctx
        
        system_snapshot_block = ""
        user_profiles_block = ""

        if hasattr(thought_item, 'context') and thought_item.context:
            system_snapshot = thought_item.context.get("system_snapshot")
            if system_snapshot:
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profiles_block = format_user_profiles(user_profiles_data)
                system_snapshot_block = format_system_snapshot(system_snapshot)
        
        identity_block = ""
        if hasattr(thought_item, "context") and thought_item.context:
            identity_block = thought_item.context.get("identity_context", "")

        messages = self._create_csdma_messages_for_instructor(
            thought_content_str,
            context_summary,
            identity_block,
            system_snapshot_block,
            user_profiles_block,
        )
        logger.debug(
            "CSDMA input to LLM for thought %s:\nSystem Snapshot Block: %s\nUser Profiles Block: %s\nContext Summary: %s",
            thought_item.thought_id,
            system_snapshot_block,
            user_profiles_block,
            context_summary,
        )

        try:
            csdma_eval: CSDMAResult = await aclient.chat.completions.create(
                model=self.model_name,
                response_model=CSDMAResult,
                messages=messages,
                max_tokens=512,
                max_retries=self.max_retries
            )

            if hasattr(csdma_eval, '_raw_response') and hasattr(csdma_eval, 'raw_llm_response'):
                raw_resp = getattr(csdma_eval, '_raw_response', None)
                if raw_resp:
                    setattr(csdma_eval, 'raw_llm_response', str(raw_resp))


            logger.info(f"CSDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}: Score {csdma_eval.plausibility_score:.2f}")
            return csdma_eval

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"CSDMA (instructor) InstructorRetryException for thought {thought_item.thought_id}: {error_detail}", exc_info=True)
            return CSDMAResult(
                plausibility_score=0.0,
                flags=["Instructor_ValidationError"],
                reasoning=f"Failed CSDMA evaluation via instructor due to validation error: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e:
            logger.error(f"CSDMA (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            return CSDMAResult(
                plausibility_score=0.0,
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed CSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}"
            )

    async def evaluate(self, thought_item: ProcessingQueueItem, **kwargs: Any) -> CSDMAResult:
        """Alias for evaluate_thought to satisfy BaseDMA."""
        return await self.evaluate_thought(thought_item)

    def __repr__(self) -> str:
        return f"<CSDMAEvaluator model='{self.model_name}' (using instructor)>"
