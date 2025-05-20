import logging # Add logging
from abc import ABC
from typing import Dict, Any, Optional, List

import instructor # For instructor.Mode
from openai import AsyncOpenAI # For type hinting raw client

# Corrected imports based on project structure
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.agent_core_schemas import DSDMAResult
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

        system_snapshot_info_str = ""
        if hasattr(thought_item, 'processing_context') and thought_item.processing_context:
            system_snapshot = thought_item.processing_context.get("system_snapshot")
            if system_snapshot:
                formatted_parts = ["--- System Snapshot Context (for background awareness) ---"]
                if system_snapshot.get("task") and hasattr(system_snapshot["task"], 'description'):
                    formatted_parts.append(f"Current Task: {system_snapshot['task'].description}")
                
                recent_tasks = system_snapshot.get("recently_completed_tasks", [])
                if recent_tasks:
                    formatted_parts.append("Recently Completed Tasks:")
                    for i, task_info in enumerate(recent_tasks[:2]): # Limit for brevity
                        desc = task_info.get('description', 'N/A')
                        outcome = task_info.get('outcome', 'N/A')
                        formatted_parts.append(f"  - Prev. Task {i+1}: {desc[:70]}... (Outcome: {str(outcome)[:70]}...)")

                user_profiles = system_snapshot.get("user_profiles")
                if user_profiles and isinstance(user_profiles, dict):
                    formatted_parts.append("Known User Profiles (for awareness):")
                    for user_key, profile_data in user_profiles.items():
                        if isinstance(profile_data, dict):
                            nick = profile_data.get('nick', user_key)
                            profile_summary = f"User '{user_key}': Nickname/Name: '{nick}'"
                            # Example: if 'interest' was in profile_data
                            # interest = profile_data.get('interest')
                            # if interest: profile_summary += f", Interest: '{str(interest)[:50]}...'"
                            formatted_parts.append(f"  - {profile_summary}")
                
                formatted_parts.append("--- End System Snapshot Context ---")
                system_snapshot_info_str = "\n".join(formatted_parts) + "\n\n"

        # Assuming self.prompt_template is a system message template
        # It should ideally have placeholders for context_str, rules_summary_str, and now system_snapshot_info_str
        # For now, we'll format what we can into system_message and prepend snapshot to user message.
        
        system_message_content = self.prompt_template # If it's a simple string
        if self.prompt_template and "{context_str}" in self.prompt_template and "{rules_summary_str}" in self.prompt_template:
             system_message_content = self.prompt_template.format(
                context_str=context_str,
                rules_summary_str=rules_summary_str,
            )
        elif not self.prompt_template: # If template is empty, provide a generic system message
            system_message_content = f"You are a domain-specific evaluator for the '{self.domain_name}' domain. Evaluate the thought based on the provided domain rules: '{rules_summary_str}' and platform context: '{context_str}'."

        user_message_content = f"{system_snapshot_info_str}Evaluate this thought for the '{self.domain_name}' domain: \"{thought_content_str}\""
        
        logger.debug(f"DSDMA '{self.domain_name}' input to LLM for thought {thought_item.thought_id}:\nSystem: {system_message_content}\nUser: {user_message_content}")

        messages = [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content},
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
