# src/ciris_engine/dma/action_selection_pdma.py
from typing import Dict, Any, Optional, List
import logging

import instructor # New import
from openai import AsyncOpenAI # New import

from ciris_engine.core.data_schemas import (
    ThoughtQueueItem,
    CSDMAResult,
    DSDMAResult,
    EthicalPDMAResult,
    ActionSelectionPDMAResult,
    HandlerActionType
)
from ciris_engine.core.config import DEFAULT_OPENAI_MODEL_NAME
from instructor.exceptions import InstructorRetryException

logger = logging.getLogger(__name__)

class ActionSelectionPDMAEvaluator:
    """
    The second PDMA in the sequence. It takes the original thought and the outputs
    of the Ethical PDMA, CSDMA, and DSDMA, then performs a PDMA process
    to select a single, concrete handler action, using `instructor`.
    """

    def __init__(self, aclient: instructor.Instructor, model_name: str = DEFAULT_OPENAI_MODEL_NAME):
        # self.aclient = instructor.patch(AsyncOpenAI()) # REMOVED - client is now injected
        self.aclient = aclient # Use the injected client
        self.model_name = model_name

    def _create_action_selection_messages_for_instructor(
        self,
        original_thought: ThoughtQueueItem,
        ethical_pdma_result: EthicalPDMAResult,
        csdma_result: CSDMAResult,
        dsdma_result: Optional[DSDMAResult]
    ) -> List[Dict[str, str]]:
        action_options_str = ", ".join([action.value for action in HandlerActionType])

        # Summarize inputs for the prompt
        ethical_summary = f"Ethical PDMA Stance: {ethical_pdma_result.decision_rationale}. Key Conflicts: {ethical_pdma_result.conflicts or 'None'}. Resolution: {ethical_pdma_result.resolution or 'None'}."
        csdma_summary = f"CSDMA Output: Plausibility {csdma_result.common_sense_plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"
        dsdma_summary_str = "DSDMA did not apply or did not run for this thought."
        if dsdma_result:
            dsdma_summary_str = f"DSDMA ({dsdma_result.domain_name}) Output: Score {dsdma_result.domain_specific_score:.2f}, Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. Reasoning: {dsdma_result.reasoning}"

        # Logic to include ponder_notes
        ponder_notes_str_for_prompt_if_any = ""
        notes_list = []
        if hasattr(original_thought, 'ponder_notes') and original_thought.ponder_notes:
            notes_list = original_thought.ponder_notes
        elif original_thought.initial_context and original_thought.initial_context.get('ponder_notes'):
            notes_list = original_thought.initial_context.get('ponder_notes')

        if notes_list:
            ponder_notes_str_for_prompt_if_any = "\n\nIMPORTANT CONTEXT FROM PREVIOUS PONDERING ROUND:\n"
            ponder_notes_str_for_prompt_if_any += "The following key questions were identified as needing resolution for this thought:\n"
            for i, q_note in enumerate(notes_list):
                ponder_notes_str_for_prompt_if_any += f"{i+1}. {q_note}\n"
            ponder_notes_str_for_prompt_if_any += "Please consider these questions and the original thought in your current evaluation.\n"

        system_prompt = f"""You are an Action Selection reasoning agent governed by the CIRIS Covenant.
Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional in the Pydantic schema that `instructor` will use.

Permitted Handler Actions: {action_options_str}

PDMA for Action Selection (all fields MANDATORY):
1.  'context_summary_for_action_selection': Summarize situation from original thought and DMAs. Crucially, note if CSDMA (see `csdma_summary`) flagged significant ambiguity impacting comprehension or safety. What is the core challenge, especially if such ambiguity exists?
2.  'action_alignment_check': MANDATORY field. This MUST be a JSON object (dictionary) where keys are
    plausible HANDLER ACTIONS (from {action_options_str}) and values are their evaluations
    against CIRIS principles & M-1. Use DMA summaries.
    If CSDMA highlighted critical ambiguity, highly align 'Speak' (for user clarification)
    or 'Ponder' (to formulate key clarifying questions) with Fidelity & Do-Good.
    Example: {{"Speak": "Evaluation...", "Ponder": "High alignment due to CSDMA flag."}}
3.  'action_conflicts': Identify conflicts *between potential handler actions*. If none, "No conflicts identified." or null.
4.  'action_resolution': Resolve conflicts. If none, "Not applicable as no conflicts were identified." or null.
5.  'selected_handler_action': # The LLM should now determine this based on the inputs and other PDMA steps.
6.  'action_parameters': Parameters for the chosen action.
    If 'Speak' is chosen to resolve CSDMA-identified ambiguity, 'message_content' MUST be a concise question to the user for clarification (e.g., {{"message_content": "To clarify, what do you mean by 'X'?"}}).
    If 'Ponder' is chosen, 'key_questions' MUST
    list 2-3 distinct questions to resolve the ambiguity. For example, if the original thought was about "murres":
    {{"key_questions": ["What are 'murres' in this specific fictional context?", "Are 'murres' animals, mythological beings, or something else entirely?", "What is the user's primary goal for this 'murres' narrative?"]}}
    Provide empty dict {{}} if no parameters for other actions.
7.  'action_selection_rationale': Justify *why* this handler action is optimal. If addressing CSDMA-flagged ambiguity, this MUST be a central part of your rationale.
8.  'monitoring_for_selected_action': Concrete monitoring plan for THIS chosen action (string or dict).

IMPORTANT: Your entire response MUST be a single JSON object.
The JSON object MUST have these top-level keys, all populated:
'context_summary_for_action_selection', 'action_alignment_check', 'action_conflicts',
'action_resolution', 'selected_handler_action', 'action_parameters',
'action_selection_rationale', 'monitoring_for_selected_action'.

Original Thought: "{str(original_thought.content)}"
{ponder_notes_str_for_prompt_if_any}
Original Thought Initial Context: {str(original_thought.initial_context) if original_thought.initial_context else "N/A"}

DMA Summaries to consider for your PDMA reasoning:
Ethical PDMA: {ethical_summary}
CSDMA: {csdma_summary}
DSDMA: {dsdma_summary_str}

Adhere strictly to the schema for your JSON output.
"""
        user_prompt = "Based on all the provided information and the PDMA framework for action selection, determine the appropriate handler action and structure your response as specified in the system prompt."

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    async def evaluate(
        self,
        original_thought: ThoughtQueueItem,
        ethical_pdma_result: EthicalPDMAResult,
        csdma_result: CSDMAResult,
        dsdma_result: Optional[DSDMAResult]
    ) -> ActionSelectionPDMAResult:

        messages = self._create_action_selection_messages_for_instructor(
            original_thought,
            ethical_pdma_result,
            csdma_result,
            dsdma_result
        )

        try:
            action_eval: ActionSelectionPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=ActionSelectionPDMAResult,
                messages=messages,
                max_tokens=1500 # Keep this generous as synthesis can be verbose
            )

            # Post-validation/coercion if necessary (instructor should handle enum conversion)
            if not isinstance(action_eval.selected_handler_action, HandlerActionType):
                try:
                    action_eval.selected_handler_action = HandlerActionType(str(action_eval.selected_handler_action))
                except ValueError as ve:
                    logging.error(f"ActionSelectionPDMA (instructor) invalid action type '{action_eval.selected_handler_action}': {ve}. Defaulting to Ponder.")
                    # This path should ideally not be hit if instructor works as expected with enums.
                    # If the LLM returns a string not in the enum, Pydantic validation *within instructor* should fail.
                    # Re-raise to be caught by the broader exception handlers below to ensure consistent fallback.
                    raise            

            raw_response_data = None
            if hasattr(action_eval, '_raw_response'): # Check if instructor attached the raw response
                raw_response_data = str(action_eval._raw_response)
            
            if hasattr(action_eval, 'raw_llm_response'):
                action_eval.raw_llm_response = raw_response_data
            elif raw_response_data is not None:
                logger.warning("ActionSelectionPDMAResult does not have 'raw_llm_response' field, but raw data was available from instructor.")


            logging.info(f"ActionSelectionPDMA (instructor) evaluation successful for thought ID {original_thought.thought_id}: Chose {action_eval.selected_handler_action.value}")
            return action_eval

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logging.error(f"ActionSelectionPDMA (instructor) InstructorRetryException for thought {original_thought.thought_id}: {error_detail}", exc_info=True)
            # Ensure all required fields are present in the fallback
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Error: LLM/Instructor validation error during action selection.",
                action_alignment_check={"error": f"InstructorRetryException: {error_detail}"},
                selected_handler_action=HandlerActionType.PONDER,
                action_parameters={"reason": f"InstructorRetryException: {error_detail}"},
                action_selection_rationale=f"Fallback due to InstructorRetryException: {error_detail}",
                # Optional fields like action_conflicts, action_resolution, monitoring_for_selected_action will default to None
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e:
            logging.error(f"ActionSelectionPDMA (instructor) evaluation failed for thought ID {original_thought.thought_id}: {e}", exc_info=True)
            # Ensure all required fields are present in the fallback
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection=f"Error: General exception - {str(e)}",
                action_alignment_check={"error": f"General Exception: {str(e)}"},
                selected_handler_action=HandlerActionType.PONDER,
                action_parameters={"reason": f"General Exception: {str(e)}"},
                action_selection_rationale=f"Fallback due to General Exception: {str(e)}",
                # Optional fields will default to None
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' (using instructor)>"
