# src/ciris_engine/dma/dsdma_teacher.py
from typing import Dict, Any, List, Optional
import logging

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field # Ensure BaseModel and Field are imported for LLMOutputForDSDMA

from ciris_engine.dma.dsdma_base import BaseDSDMA
# Corrected imports
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.agent_core_schemas import DSDMAResult
# DEFAULT_OPENAI_MODEL_NAME is not needed here if BaseDSDMA handles model_name from config
# Import InstructorRetryException for specific error handling
from instructor.exceptions import InstructorRetryException
# AsyncOpenAI for type hinting in __init__
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Temporary model for what the LLM should return for this DSDMA via instructor
class LLMOutputForDSDMA(BaseModel):
    # Renamed to align with DSDMAResult
    domain_alignment_score: float = Field(..., ge=0.0, le=1.0)
    recommended_action: Optional[str] = Field(default=None)
    flags: List[str] = Field(default_factory=list)
    reasoning: str

class BasicTeacherDSDMA(BaseDSDMA):
    DOMAIN_NAME = "BasicTeacherMod"
    DEFAULT_TEMPLATE = """You are a Domain-Specific Decision-Making Algorithm (DSDMA) for a Discord moderator acting with the philosophy of a "Basic Homeroom Teacher".
Your guiding principle is: "Let the community explore and interact freely, with purpose, intervening minimally and gently only when necessary to guide, protect, or maintain a broadly constructive environment."

Current Context (e.g., Discord channel, user): {context_str}
Domain Knowledge (e.g., rules summary): {rules_summary_str}

Evaluate the "thought" based on the "Basic Teacher" philosophy. Your goals are to:
1. Foster learning and positive exploration.
2. Intervene only if activity becomes genuinely harmful, significantly off-topic for a sustained period, or unfairly targets individuals.
3. Prefer guiding questions or gentle reminders over punitive actions.
4. Assess if the "thought" contributes to or detracts from a purposeful, albeit lively, community.

Your response MUST be a single JSON object adhering to the provided schema, with the following keys:
- "domain_alignment_score": A float between 0.0 (strongly against "Teacher" philosophy) and 1.0 (strongly aligned). MANDATORY.
- "recommended_action": A brief, specific, teacher-like action string (e.g., "Observe for now", "Ask a guiding question: 'What are we trying to achieve here?'", "No action needed, part of exploration"). This can be null if no action is best.
- "flags": A list of strings for specific concerns (e.g., "StiflesExploration", "BecomingDisruptive"). If none, an empty list. MANDATORY (even if empty).
- "reasoning": A brief (1-2 sentences) explanation for your score, flags, and recommended action. MANDATORY.
"""

    def __init__(self,
                 aclient: AsyncOpenAI, # Expect raw AsyncOpenAI client
                 model_name: Optional[str] = None, # Allow override, else use config from BaseDSDMA
                 domain_specific_knowledge: Optional[Dict[str, Any]] = None,
                 prompt_template: Optional[str] = None):
        super().__init__(domain_name=self.DOMAIN_NAME,
                         aclient=aclient, # Pass raw client to super
                         model_name=model_name, # Pass model_name to super
                         domain_specific_knowledge=domain_specific_knowledge,
                         prompt_template=prompt_template)
        # self.aclient and self.model_name are now set by BaseDSDMA
        # self.instructor_mode is also set by BaseDSDMA

    def _create_teacher_dsdma_messages_for_instructor(self, thought_content: str, current_context: Dict[str, Any]) -> List[Dict[str,str]]:
        """
        Creates the messages list for the LLM to evaluate a thought from a "Basic Teacher" mod perspective,
        suitable for use with `instructor`.
        """
        context_str = str(current_context) if current_context else "No specific context provided."
        rules_summary_str = self.domain_specific_knowledge.get("rules_summary", "General good conduct expected.") if isinstance(self.domain_specific_knowledge, dict) else "General good conduct expected."

        system_message_content = self.prompt_template.format(
            context_str=context_str,
            rules_summary_str=rules_summary_str
        )

        user_message_content = f"Given the Basic Teacher DSDMA framework and current context, evaluate this thought: \"{thought_content}\""

        return [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content}
        ]

    # Updated signature to use ProcessingQueueItem
    async def evaluate_thought(self, thought_item: ProcessingQueueItem, current_context: Dict[str, Any]) -> DSDMAResult:
        # Extract thought content string robustly from ProcessingQueueItem.content (Dict[str, Any])
        thought_content_str = ""
        if isinstance(thought_item.content, dict):
            thought_content_str = thought_item.content.get("text", thought_item.content.get("description", str(thought_item.content)))
        else: # Should not happen based on ProcessingQueueItem definition, but handle defensively
             thought_content_str = str(thought_item.content)

        messages = self._create_teacher_dsdma_messages_for_instructor(thought_content_str, current_context)

        try:
            llm_eval_data: LLMOutputForDSDMA = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=LLMOutputForDSDMA,
                messages=messages,
                max_tokens=512 # Adjust as needed
            )

            # Instantiate DSDMAResult using the updated schema fields
            dsdma_final_result = DSDMAResult(
                domain_name=self.DOMAIN_NAME, # Populate domain_name from the class constant
                domain_alignment_score=min(max(llm_eval_data.domain_alignment_score, 0.0), 1.0),
                recommended_action=llm_eval_data.recommended_action, # Populate recommended_action directly
                flags=llm_eval_data.flags,
                reasoning=llm_eval_data.reasoning,
                domain_specific_output={} # Clear domain_specific_output unless other data is needed
            )
            raw_response_data = None
            if hasattr(llm_eval_data, '_raw_response'): # Check if instructor attached the raw response
                raw_response_data = str(llm_eval_data._raw_response)
            dsdma_final_result.raw_llm_response = raw_response_data

            logger.info(f"DSDMA {self.DOMAIN_NAME} (instructor) evaluation successful for thought ID {thought_item.thought_id}: Score {dsdma_final_result.domain_alignment_score:.2f}")
            return dsdma_final_result

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"DSDMA {self.DOMAIN_NAME} (instructor) InstructorRetryException for thought {thought_item.thought_id}: {error_detail}", exc_info=True)
            # Add required args to exception for fallback result, including domain_name
            return DSDMAResult(
                domain_name=self.DOMAIN_NAME,
                domain_alignment_score=0.0,
                recommended_action=None, # No recommendation on error
                flags=["Instructor_ValidationError"],
                reasoning=f"Failed DSDMA evaluation via instructor due to validation error: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e:
            logger.error(f"DSDMA {self.DOMAIN_NAME} (instructor) evaluation failed for thought ID {thought_item.thought_id}: {e}", exc_info=True)
            # Add required args to exception for fallback result, including domain_name
            return DSDMAResult(
                domain_name=self.DOMAIN_NAME,
                domain_alignment_score=0.0,
                recommended_action=None, # No recommendation on error
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed DSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<BasicTeacherDSDMA model='{self.model_name}' (using instructor)>"
