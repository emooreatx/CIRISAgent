import logging
from typing import Optional, Dict, Any

from ciris_engine.logic.processors.support.processing_queue import ProcessingQueueItem
from ciris_engine.logic.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.protocols.dma.base import PDMAProtocol
from ciris_engine.schemas.dma.results import EthicalDMAResult
from ciris_engine.logic.formatters import format_user_profiles, format_system_snapshot
from ciris_engine.logic.utils import COVENANT_TEXT
from ciris_engine.schemas.runtime.system_context import ThoughtState
from .prompt_loader import get_prompt_loader

DEFAULT_OPENAI_MODEL_NAME = "gpt-4o"

logger = logging.getLogger(__name__)

class EthicalPDMAEvaluator(BaseDMA, PDMAProtocol):
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
        **kwargs: Any
    ) -> None:
        super().__init__(
            service_registry=service_registry,
            model_name=model_name,
            max_retries=max_retries,
            prompt_overrides=prompt_overrides,
            **kwargs
        )
        
        self.prompt_loader = get_prompt_loader()
        try:
            self.prompt_template_data = self.prompt_loader.load_prompt_template("pdma_ethical")
        except FileNotFoundError:
            logger.warning("PDMA prompt template not found, using fallback")
            self.prompt_template_data = {
                "system_guidance_header": """You are an ethical reasoning shard of a CIRIS AI 
                system governed by the CIRIS Covenant.\n\nYour task is 
                to perform an ethical evaluation of user messages using the Principled Decision-Making Algorithm (PDMA). 
                The PDMA integrates the following CIRIS principles:\n\n- **Do Good:** Promote positive 
                outcomes and wellbeing.\n- **Avoid Harm:** Actively prevent and mitigate harm.\n- **Honor Autonomy:** Respect 
                individual agency and informed consent.\n- **Ensure Fairness:** Maintain 
                impartiality and equity.\n\nEvaluate the thought by:\n1. Identifying 
                plausible actions.\n2. Analyzing actions against each CIRIS principle.\n3. Determining 
                the ethically optimal action.\n\nYour response must be 
                structured as follows:\n{\n  \"alignment_check\": Detailed ethical analysis 
                addressing each CIRIS principle,\n  \"decision\": Your 
                ethically optimal action or stance,\n  \"reasoning\": Justification for your 
                decision referencing your analysis.\n}\n\nDo not include extra fields or PDMA step names.""",
                "covenant_header": True
            }
        
        if prompt_overrides:
            self.prompt_template_data.update(prompt_overrides)
        logger.info(f"EthicalPDMAEvaluator initialized with model: {self.model_name}")

    async def evaluate(self, input_data: ProcessingQueueItem, context: Optional[ThoughtState] = None, **kwargs: Any) -> EthicalDMAResult:
        original_thought_content = str(input_data.content)
        logger.debug(f"Evaluating thought ID {input_data.thought_id}")

        system_snapshot_context_str = ""
        user_profile_context_str = ""
        if context and context.system_snapshot:
            system_snapshot_context_str = format_system_snapshot(context.system_snapshot)
            if context.system_snapshot.user_profiles:
                user_profile_context_str = format_user_profiles(context.system_snapshot.user_profiles)
        elif context and context.user_profiles:
            user_profile_context_str = format_user_profiles(context.user_profiles)

        full_context_str = system_snapshot_context_str + user_profile_context_str
        
        messages = []
        
        if self.prompt_loader.uses_covenant_header(self.prompt_template_data):
            messages.append({"role": "system", "content": COVENANT_TEXT})
        
        system_message = self.prompt_loader.get_system_message(
            self.prompt_template_data,
            original_thought_content=original_thought_content,
            full_context_str=full_context_str
        )
        messages.append({"role": "system", "content": system_message})
        
        user_message = self.prompt_loader.get_user_message(
            self.prompt_template_data,
            original_thought_content=original_thought_content,
            full_context_str=full_context_str
        )
        messages.append({"role": "user", "content": user_message})
        
        try:
            result_tuple = await self.call_llm_structured(
                messages=messages,
                response_model=EthicalDMAResult,
                max_tokens=1024,
                temperature=0.0
            )
            response_obj: EthicalDMAResult = result_tuple[0]
            resource_usage = result_tuple[1]
            logger.info(f"Evaluation successful for thought ID {input_data.thought_id}")
            return response_obj
        except Exception as e:
            logger.error(f"Evaluation failed for thought ID {input_data.thought_id}: {e}", exc_info=True)
            fallback_data = {
                "alignment_check": {"error": str(e)},
                "decision": "defer",
                "reasoning": "Evaluation failed due to an exception."
            }
            return EthicalDMAResult.model_validate(fallback_data)

    def __repr__(self) -> str:
        return f"<EthicalPDMAEvaluator model='{self.model_name}'>"
