# src/ciris_engine/dma/dsdma_student.py
from typing import Dict, Any, List, Optional
import logging

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ciris_engine.dma.dsdma_base import BaseDSDMA
# Corrected imports
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import DSDMAResult
# DEFAULT_OPENAI_MODEL_NAME is not needed here if BaseDSDMA handles model_name from config
from instructor.exceptions import InstructorRetryException
# AsyncOpenAI for type hinting in __init__
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# This model is identical to the one in BasicTeacherDSDMA,
# as evaluate_thought logic is shared.
class LLMOutputForDSDMA(BaseModel):
    # Renamed to align with DSDMAResult
    domain_alignment_score: float = Field(..., ge=0.0, le=1.0)
    recommended_action: Optional[str] = Field(default=None)
    flags: List[str] = Field(default_factory=list)
    reasoning: str

class StudentDSDMA(BaseDSDMA):
    DOMAIN_NAME = "StudentMod"
    DEFAULT_TEMPLATE = """
    You are a curious learner DSDMA. Evaluate the THOUGHT for:

    1. Learning opportunity (+0.5 score boost if present)
    2. Respect for others (significant negative impact if disrespectful)
    3. Genuine confusion vs trolling (penalize trolling)

    Consider the current context: {context_str}
    Consider domain specific knowledge/rules: {rules_summary_str}

    Respond with a JSON object adhering to the schema, including:
    - "domain_alignment_score": float (0-1, apply boosts/penalties based on above criteria)
    - "recommended_action": string (e.g., "Ask for clarification", "Engage with curiosity", "Flag as potential troll")
    - "flags": list of strings (e.g., "LearningOpportunity", "Disrespectful", "PotentialTroll")
    - "reasoning": string (briefly explain your evaluation based on the criteria)
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

    def _create_student_dsdma_messages_for_instructor(self, thought_content: str, current_context: Dict[str, Any]) -> List[Dict[str,str]]:
        """
        Creates the messages list for the LLM to evaluate a thought from a "Student" mod perspective.
        """
        context_str = str(current_context) if current_context else "No specific context provided."
        # Ensure domain_specific_knowledge is a dict before .get()
        rules_summary_str = self.domain_specific_knowledge.get("rules_summary", "General good conduct and curious exploration expected.") if isinstance(self.domain_specific_knowledge, dict) else "General good conduct and curious exploration expected."


        # Use the instance's prompt_template (which could be overridden or default)
        system_message_content = self.prompt_template.format(
            context_str=context_str,
            rules_summary_str=rules_summary_str
        )

        user_message_content = f"Given the Student DSDMA framework, evaluate this thought: \"{thought_content}\""

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

        # Uses its own _create_messages method which uses its own template
        messages = self._create_student_dsdma_messages_for_instructor(thought_content_str, current_context)

        try:
            llm_eval_data: LLMOutputForDSDMA = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=LLMOutputForDSDMA,
                messages=messages,
                max_tokens=512
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
            if hasattr(llm_eval_data, '_raw_response'):
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
        return f"<StudentDSDMA model='{self.model_name}' (using instructor)>"
