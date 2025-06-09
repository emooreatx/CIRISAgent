import logging
from abc import ABC
from typing import Dict, Any, Optional, List

import instructor

from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.dma_results_v1 import DSDMAResult
from ciris_engine.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.protocols.dma_interface import DSDMAInterface
from ciris_engine.formatters import (
    format_user_profiles,
    format_system_snapshot,
    format_system_prompt_blocks,
    get_escalation_guidance
)
from ciris_engine.utils import COVENANT_TEXT
from pydantic import BaseModel, Field
from instructor.exceptions import InstructorRetryException
from ciris_engine.config.config_manager import get_config

logger = logging.getLogger(__name__)

class BaseDSDMA(BaseDMA, DSDMAInterface):
    """
    Abstract Base Class for Domain-Specific Decision-Making Algorithms.
    Handles instructor client patching based on global config.
    """
    DEFAULT_TEMPLATE: Optional[str] = (
        "You are a domain-specific evaluator for the '{domain_name}' domain. "
        "Your primary goal is to assess how well a given 'thought' aligns with the specific rules, "
        "objectives, and knowledge pertinent to this domain. "
        "Consider the provided domain rules: '{rules_summary_str}' and the general platform context: '{context_str}'. "
        "Additionally, user profile information and system snapshot details will be provided with the thought for background awareness. "
        "When evaluating thoughts that might lead to TOOL actions, consider whether the tools available "
        "are appropriate for the domain and whether their use aligns with domain-specific best practices. "
        "Focus your evaluation on domain alignment."
    )

    def __init__(self,
                 domain_name: str,
                 service_registry: ServiceRegistry,
                 model_name: Optional[str] = None,
                 domain_specific_knowledge: Optional[Dict[str, Any]] = None,
                 prompt_template: Optional[str] = None,
                 **kwargs: Any) -> None:
        
        app_config = get_config()
        resolved_model = model_name or app_config.llm_services.openai.model_name

        try:
            configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
            instructor_mode = instructor.Mode[configured_mode_str]
        except KeyError:
            logger.warning(
                f"Invalid instructor_mode '{app_config.llm_services.openai.instructor_mode}' in config for DSDMA {domain_name}. Defaulting to JSON."
            )
            instructor_mode = instructor.Mode.JSON

        super().__init__(
            service_registry=service_registry,
            model_name=resolved_model,
            max_retries=2,
            instructor_mode=instructor_mode,
            **kwargs
        )

        self.domain_name = domain_name
        self.domain_specific_knowledge = domain_specific_knowledge if domain_specific_knowledge else {}
        self.prompt_template = prompt_template if prompt_template is not None else (self.DEFAULT_TEMPLATE if self.DEFAULT_TEMPLATE is not None else "")

        logger.info(
            f"BaseDSDMA '{self.domain_name}' initialized with model: {self.model_name}, instructor_mode: {self.instructor_mode.name}"
        )

    class LLMOutputForDSDMA(BaseModel):
        score: float = Field(..., ge=0.0, le=1.0)
        recommended_action: Optional[str] = Field(default=None)
        flags: List[str] = Field(default_factory=list)
        reasoning: str

    async def evaluate_thought(self, thought_item: ProcessingQueueItem, current_context: Dict[str, Any]) -> DSDMAResult:
        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for DSDMA evaluation")

        aclient = instructor.patch(llm_service.get_client().client, mode=self.instructor_mode)

        thought_content_str = str(thought_item.content)

        context_str = str(current_context) if current_context else "No specific platform context provided."
        rules_summary_str = self.domain_specific_knowledge.get("rules_summary", "General domain guidance") if isinstance(self.domain_specific_knowledge, dict) else "General domain guidance"

        system_snapshot_block = ""
        user_profiles_block = ""
        identity_block = ""
        
        if hasattr(thought_item, 'context') and thought_item.context:
            system_snapshot = thought_item.context.get("system_snapshot")
            if system_snapshot:
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profiles_block = format_user_profiles(user_profiles_data)
                system_snapshot_block = format_system_snapshot(system_snapshot)
            
            identity_block = thought_item.context.get("identity_context", "")

        escalation_guidance_block = get_escalation_guidance(0)
        
        task_history_block = ""
        
        template_has_blocks = any(placeholder in self.prompt_template for placeholder in [
            "{task_history_block}", "{escalation_guidance_block}", 
            "{system_snapshot_block}", "{user_profiles_block}"
        ])
        
        if template_has_blocks:
            try:
                system_message_content = self.prompt_template.format(
                    task_history_block=task_history_block,
                    escalation_guidance_block=escalation_guidance_block,
                    system_snapshot_block=system_snapshot_block,
                    user_profiles_block=user_profiles_block,
                    domain_name=self.domain_name,
                    rules_summary_str=rules_summary_str,
                    context_str=context_str
                )
            except KeyError as e:
                logger.error(f"Missing template variable in DSDMA template: {e}")
                system_message_content = format_system_prompt_blocks(
                    identity_block,
                    task_history_block,
                    system_snapshot_block,
                    user_profiles_block,
                    escalation_guidance_block,
                    f"You are a domain-specific evaluator for the '{self.domain_name}' domain. "
                    f"Consider the domain rules: '{rules_summary_str}' and context: '{context_str}'."
                )
        else:
            system_message_template = self.prompt_template
            if not system_message_template:
                system_message_template = (
                    "You are a domain-specific evaluator for the '{domain_name}' domain. "
                    "Your primary goal is to assess how well a given 'thought' aligns with the specific rules, "
                    "objectives, and knowledge pertinent to this domain. "
                    "Consider the provided domain rules: '{rules_summary_str}' and the general platform context: '{context_str}'. "
                    "Additionally, user profile information and system snapshot details will be provided with the thought for background awareness. "
                    "Focus your evaluation on domain alignment."
                )

            system_message_content = system_message_template.format(
                domain_name=self.domain_name,
                rules_summary_str=rules_summary_str,
                context_str=context_str
            )

        full_snapshot_and_profile_context_str = system_snapshot_block + user_profiles_block
        user_message_content = f"{full_snapshot_and_profile_context_str}\nEvaluate this thought for the '{self.domain_name}' domain: \"{thought_content_str}\""
        
        logger.debug(f"DSDMA '{self.domain_name}' input to LLM for thought {thought_item.thought_id}:\nSystem: {system_message_content}\nUser: {user_message_content}")

        messages = [
            {"role": "system", "content": COVENANT_TEXT},
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content}
        ]

        try:
            llm_eval_data: BaseDSDMA.LLMOutputForDSDMA = await aclient.chat.completions.create(
                model=self.model_name,
                response_model=BaseDSDMA.LLMOutputForDSDMA,
                messages=messages,
                max_tokens=512,
            )

            result = DSDMAResult(
                domain=self.domain_name,
                score=min(max(llm_eval_data.score, 0.0), 1.0),
                recommended_action=llm_eval_data.recommended_action,
                flags=llm_eval_data.flags,
                reasoning=llm_eval_data.reasoning
            )
            logger.info(
                f"DSDMA '{self.domain_name}' (instructor) evaluation successful for thought ID {thought_item.thought_id}: "
                f"Score {result.score}, Recommended Action: {result.recommended_action}"
            )
            if hasattr(llm_eval_data, "_raw_response"):
                result.raw_llm_response = str(llm_eval_data._raw_response)
            return result
        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, "errors") else str(e_instr)
            logger.error(
                f"DSDMA {self.domain_name} InstructorRetryException for thought {thought_item.thought_id}: {error_detail}",
                exc_info=True,
            )
            return DSDMAResult(
                domain=self.domain_name,
                score=0.0,
                recommended_action=None,
                flags=["Instructor_ValidationError"],
                reasoning=f"Failed DSDMA evaluation via instructor due to validation error: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}",
            )
        except Exception as e:
            logger.error(
                f"DSDMA {self.domain_name} evaluation failed for thought ID {thought_item.thought_id}: {e}",
                exc_info=True,
            )
            return DSDMAResult(
                domain=self.domain_name,
                score=0.0,
                recommended_action=None,
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed DSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}",
            )

    async def evaluate(
        self, thought_item: ProcessingQueueItem, current_context: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> DSDMAResult:
        """Alias for evaluate_thought to satisfy BaseDMA."""
        context = current_context or {}
        return await self.evaluate_thought(thought_item, context)

    def __repr__(self) -> str:
        return f"<BaseDSDMA domain='{self.domain_name}'>"
        # No legacy field names present; v1 field names are already used throughout.
