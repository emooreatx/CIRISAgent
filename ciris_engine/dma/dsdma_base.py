import logging # Add logging
from abc import ABC
from typing import Dict, Any, Optional, List

import instructor # For instructor.Mode
from openai import AsyncOpenAI # For type hinting raw client

# Corrected imports based on project structure
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.agent_core_schemas import DSDMAResult
from ciris_engine.utils.context_formatters import format_user_profiles_for_prompt, format_system_snapshot_for_prompt # New import
from pydantic import BaseModel, Field
from instructor.exceptions import InstructorRetryException
from ciris_engine.core.config_manager import get_config # To access global config

logger = logging.getLogger(__name__) # Add logger

class BaseDSDMA(ABC):
    """
    Abstract Base Class for Domain-Specific Decision-Making Algorithms.
    Handles instructor client patching based on global config.
    """
    DEFAULT_TEMPLATE: Optional[str] = "" # Subclasses should override this

    def __init__(self,
                 domain_name: str,
                 aclient: AsyncOpenAI, # Expect raw AsyncOpenAI client
                 model_name: Optional[str] = None, # Allow override, else use config
                 domain_specific_knowledge: Optional[Dict[str, Any]] = None,
                 prompt_template: Optional[str] = None):
        
        app_config = get_config()
        self.model_name = model_name or app_config.llm_services.openai.model_name
        
        try:
            configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
            self.instructor_mode = instructor.Mode[configured_mode_str]
        except KeyError:
            logger.warning(f"Invalid instructor_mode '{app_config.llm_services.openai.instructor_mode}' in config for DSDMA {domain_name}. Defaulting to JSON.")
            self.instructor_mode = instructor.Mode.JSON

        self.aclient: instructor.Instructor = instructor.patch(aclient, mode=self.instructor_mode)
        
        self.domain_name = domain_name
        self.domain_specific_knowledge = domain_specific_knowledge if domain_specific_knowledge else {}
        # Use provided template, fallback to class default, then empty string
        self.prompt_template = prompt_template if prompt_template is not None else (self.DEFAULT_TEMPLATE if self.DEFAULT_TEMPLATE is not None else "")
        
        logger.info(f"BaseDSDMA '{self.domain_name}' initialized with model: {self.model_name}, instructor_mode: {self.instructor_mode.name}")
        super().__init__()

    class LLMOutputForDSDMA(BaseModel):
        domain_alignment_score: float = Field(..., ge=0.0, le=1.0)
        recommended_action: Optional[str] = Field(default=None)
        flags: List[str] = Field(default_factory=list)
        reasoning: str

    async def evaluate_thought(self, thought_item: ProcessingQueueItem, current_context: Dict[str, Any]) -> DSDMAResult:
        thought_content_str = ""
        if isinstance(thought_item.content, dict):
            thought_content_str = thought_item.content.get("text", thought_item.content.get("description", str(thought_item.content)))
        else:
            thought_content_str = str(thought_item.content)

        context_str = str(current_context) if current_context else "No specific platform context provided."
        rules_summary_str = self.domain_specific_knowledge.get("rules_summary", "General domain guidance") if isinstance(self.domain_specific_knowledge, dict) else "General domain guidance"

        system_snapshot_context_str = ""
        user_profile_context_str = ""

        if hasattr(thought_item, 'processing_context') and thought_item.processing_context:
            system_snapshot = thought_item.processing_context.get("system_snapshot")
            if system_snapshot:
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profile_context_str = format_user_profiles_for_prompt(user_profiles_data)
                
                system_snapshot_context_str = format_system_snapshot_for_prompt(system_snapshot, thought_item.processing_context)

        # Prepare system message content
        # Subclasses might provide a more specific template.
        # The template should ideally allow for {domain_name}, {rules_summary_str}, {platform_context_str}
        # and then the user message would contain the thought and the formatted snapshot context.
        
        system_message_template = self.prompt_template
        if not system_message_template: # Default if subclass doesn't provide one
            system_message_template = (
                "You are a domain-specific evaluator for the '{domain_name}' domain. "
                "Your primary goal is to assess how well a given 'thought' aligns with the specific rules, "
                "objectives, and knowledge pertinent to this domain. "
                "Consider the provided domain rules: '{rules_summary_str}' and the general platform context: '{context_str}'. " # Changed placeholder
                "Additionally, user profile information and system snapshot details will be provided with the thought for background awareness. "
                "Focus your evaluation on domain alignment."
            )

        system_message_content = system_message_template.format(
            domain_name=self.domain_name,
            rules_summary_str=rules_summary_str,
            context_str=context_str # Changed keyword to context_str
        )

        # User message includes the thought and the formatted snapshot context (user profiles + system state)
        full_snapshot_and_profile_context_str = system_snapshot_context_str + user_profile_context_str
        user_message_content = f"{full_snapshot_and_profile_context_str}\nEvaluate this thought for the '{self.domain_name}' domain: \"{thought_content_str}\""
        
        logger.debug(f"DSDMA '{self.domain_name}' input to LLM for thought {thought_item.thought_id}:\nSystem: {system_message_content}\nUser: {user_message_content}")

        messages = [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content}
        ]

        try:
            llm_eval_data: BaseDSDMA.LLMOutputForDSDMA = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=BaseDSDMA.LLMOutputForDSDMA,
                messages=messages,
                max_tokens=512,
            )

            result = DSDMAResult(
                domain_name=self.domain_name,
                domain_alignment_score=min(max(llm_eval_data.domain_alignment_score, 0.0), 1.0),
                recommended_action=llm_eval_data.recommended_action,
                flags=llm_eval_data.flags,
                reasoning=llm_eval_data.reasoning,
                domain_specific_output={},
            )
            logger.info(
                f"DSDMA '{self.domain_name}' (instructor) evaluation successful for thought ID {thought_item.thought_id}: "
                f"Score {result.domain_alignment_score}, Recommended Action: {result.recommended_action}"
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
                domain_name=self.domain_name,
                domain_alignment_score=0.0,
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
                domain_name=self.domain_name,
                domain_alignment_score=0.0,
                recommended_action=None,
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed DSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}",
            )

    def __repr__(self) -> str:
        return f"<BaseDSDMA domain='{self.domain_name}'>"
