from typing import Dict, Any, List, Optional, cast
import logging

from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.logic.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.protocols.dma.base import CSDMAProtocol
from ciris_engine.schemas.dma.results import CSDMAResult
from ciris_engine.logic.formatters import (
    format_system_snapshot,
    format_user_profiles,
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)
from ciris_engine.logic.utils import COVENANT_TEXT
from .prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = """=== Common Sense DMA Guidance ===
You are a Common Sense Evaluation agent. Your task is to assess a given "thought" for its alignment with general common-sense understanding of the physical world, typical interactions, and resource constraints on Earth, considering the provided context.
[... truncated for brevity ...]
"""

class CSDMAEvaluator(BaseDMA, CSDMAProtocol):
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

        # Use provided model_name or default from base class
        super().__init__(
            service_registry=service_registry,
            model_name=model_name,
            max_retries=max_retries,
            prompt_overrides=prompt_overrides,
            **kwargs
        )

        self.prompt_overrides = prompt_overrides or {}

        # Load prompts from YAML file
        self.prompt_loader = get_prompt_loader()
        try:
            prompt_collection = self.prompt_loader.load_prompt_template("csdma_common_sense")
            # Convert PromptCollection to dict for backward compatibility
            self.prompt_template_data = {
                "system_guidance_header": prompt_collection.system_guidance_header or DEFAULT_TEMPLATE,
                "covenant_header": prompt_collection.uses_covenant_header
            }
        except FileNotFoundError:
            logger.warning("CSDMA prompt template not found, using fallback")
            # Fallback to embedded prompt for backward compatibility
            self.prompt_template_data = {
                "system_guidance_header": DEFAULT_TEMPLATE,
                "covenant_header": True
            }

        # Apply prompt overrides if provided
        if self.prompt_overrides:
            self.prompt_template_data.update(self.prompt_overrides)

        # Client will be retrieved from the service registry during evaluation

        self.env_kg = environmental_kg # Placeholder for now
        self.task_kg = task_specific_kg   # Placeholder for now
        # Log the final client type being used
        logger.info(
            f"CSDMAEvaluator initialized with model: {self.model_name}. "
            f"Overrides: {self.prompt_overrides is not None}"
        )

    def _create_csdma_messages_for_instructor(
        self,
        thought_content: str,
        context_summary: str,
        identity_context_block: str,
        system_snapshot_block: str,
        user_profiles_block: str,
    ) -> List[Dict[str, str]]:
        """Assemble prompt messages using canonical formatting utilities and prompt loader."""
        messages = []

        if self.prompt_loader.uses_covenant_header(self.prompt_template_data):
            messages.append({"role": "system", "content": COVENANT_TEXT})

        system_message = self.prompt_loader.get_system_message(
            self.prompt_template_data,
            context_summary=context_summary,
            original_thought_content=thought_content
        )

        formatted_system = format_system_prompt_blocks(
            identity_context_block,
            "",
            system_snapshot_block,
            user_profiles_block,
            None,
            system_message,
        )
        messages.append({"role": "system", "content": formatted_system})

        user_message = self.prompt_loader.get_user_message(
            self.prompt_template_data,
            context_summary=context_summary,
            original_thought_content=thought_content
        )

        if not user_message or user_message == f"Thought to evaluate: {thought_content}":
            user_message = format_user_prompt_blocks(
                format_parent_task_chain([]),
                format_thoughts_chain([{"content": thought_content}]),
                None,
            )

        messages.append({"role": "user", "content": user_message})

        return messages

    async def evaluate_thought(self, thought_item: ProcessingQueueItem) -> CSDMAResult:

        thought_content_str = str(thought_item.content)

        context_summary = "Standard Earth-based physical context, unless otherwise specified in the thought."
        if hasattr(thought_item, 'initial_context') and thought_item.initial_context:
            # Type narrow to dict
            if isinstance(thought_item.initial_context, dict) and "environment_context" in thought_item.initial_context:
                env_ctx = thought_item.initial_context["environment_context"]
                if isinstance(env_ctx, dict) and "description" in env_ctx:
                    context_summary = str(env_ctx["description"])
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
            result_tuple = await self.call_llm_structured(
                messages=messages,
                response_model=CSDMAResult,
                max_tokens=512,
                temperature=0.0
            )
            csdma_eval: CSDMAResult = result_tuple[0]

            # raw_llm_response field has been removed from CSDMAResult

            logger.info(f"CSDMA (instructor) evaluation successful for thought ID {thought_item.thought_id}: Score {csdma_eval.plausibility_score:.2f}")
            return csdma_eval

        except Exception as e:
            logger.error(f"CSDMA evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            return CSDMAResult(
                plausibility_score=0.0,
                flags=["LLM_Error", "defer_for_retry"],
                reasoning=f"Failed CSDMA evaluation: {str(e)}"
            )

    async def evaluate(self, *args: Any, **kwargs: Any) -> CSDMAResult:  # type: ignore[override]
        """Evaluate thought for common sense alignment."""
        # Extract arguments - maintain backward compatibility
        input_data = args[0] if args else kwargs.get('input_data')
        
        if not input_data:
            raise ValueError("input_data is required")
            
        return await self.evaluate_thought(input_data)

    def __repr__(self) -> str:
        return f"<CSDMAEvaluator model='{self.model_name}' (using instructor)>"
