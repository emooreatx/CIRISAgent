import logging
from typing import Dict, Any, Optional

import instructor

from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.formatters import format_user_profiles, format_system_snapshot
from ciris_engine.utils import COVENANT_TEXT
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o"

logger = logging.getLogger(__name__)

class EthicalPDMAEvaluator(BaseDMA):
    """
    Evaluates a thought against core ethical principles using an LLM
    and returns a structured EthicalDMAResult using the 'instructor' library.
    """

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: str = DEFAULT_OPENAI_MODEL_NAME,
        max_retries: int = 2,
        prompt_overrides: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(
            service_registry=service_registry,
            model_name=model_name,
            max_retries=max_retries,
            instructor_mode=instructor.Mode.JSON,
        )

        self.DEFAULT_PROMPT_TEMPLATE: Dict[str, str] = {
            "system_guidance_header": """You are an ethical reasoning shard of a CIRIS AI system governed by the CIRIS Covenant.

Your task is to perform an ethical evaluation of user messages using the Principled Decision-Making Algorithm (PDMA). The PDMA integrates the following CIRIS principles:

- **Do Good:** Promote positive outcomes and wellbeing.
- **Avoid Harm:** Actively prevent and mitigate harm.
- **Honor Autonomy:** Respect individual agency and informed consent.
- **Ensure Fairness:** Maintain impartiality and equity.

Evaluate the thought by:
1. Identifying plausible actions.
2. Analyzing actions against each CIRIS principle.
3. Determining the ethically optimal action.

Your response must be structured as follows:
{
  "alignment_check": Detailed ethical analysis addressing each CIRIS principle,
  "decision": Your ethically optimal action or stance,
  "rationale": Justification for your decision referencing your analysis.
}

Do not include extra fields or PDMA step names.""",
        }
        self.prompt_template = {**self.DEFAULT_PROMPT_TEMPLATE, **(prompt_overrides or {})}

        logger.info(f"EthicalPDMAEvaluator initialized with model: {self.model_name}")

    async def evaluate(self, thought_item: ProcessingQueueItem) -> EthicalDMAResult:
        original_thought_content = str(thought_item.content)
        logger.debug(f"Evaluating thought ID {thought_item.thought_id}")

        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for PDMA evaluation")

        aclient = llm_service.get_client().instruct_client

        system_snapshot_context_str = ""
        user_profile_context_str = ""

        if hasattr(thought_item, 'context') and thought_item.context:
            system_snapshot = thought_item.context.get("system_snapshot")
            if system_snapshot:
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profile_context_str = format_user_profiles(user_profiles_data)
                system_snapshot_context_str = format_system_snapshot(system_snapshot)

        full_context_str = system_snapshot_context_str + user_profile_context_str

        user_message_with_context = (
            f"{full_context_str}\nSystem Thought to Evaluate: '{original_thought_content}'"
        )

        try:
            response_obj: EthicalDMAResult = await aclient.chat.completions.create(
                model=self.model_name,
                response_model=EthicalDMAResult,
                messages=[
                    {"role": "system", "content": COVENANT_TEXT},
                    {"role": "system", "content": self.prompt_template["system_guidance_header"]},
                    {"role": "user", "content": user_message_with_context}
                ],
                max_retries=self.max_retries
            )
            logger.info(f"Evaluation successful for thought ID {thought_item.thought_id}")
            return response_obj

        except Exception as e:
            logger.error(f"Evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            fallback_data = {
                "alignment_check": {"error": str(e)},
                "decision": f"Error: {e}",
                "rationale": "Evaluation failed due to an exception."
            }
            return EthicalDMAResult.model_validate(fallback_data)

    def __repr__(self) -> str:
        return f"<EthicalPDMAEvaluator model='{self.model_name}'>"
