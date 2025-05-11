# src/ciris_engine/dma/action_selection_pdma.py
from typing import Dict, Any, Optional, List
import logging

import instructor
from openai import AsyncOpenAI

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
        self.aclient = aclient
        self.model_name = model_name

    def _create_action_selection_messages_for_instructor(
        self,
        original_thought: ThoughtQueueItem,
        ethical_pdma_result: EthicalPDMAResult,
        csdma_result: CSDMAResult,
        dsdma_result: Optional[DSDMAResult],
        current_ponder_count: int,
        max_ponder_rounds: int,
        benchmark_mode: bool
    ) -> List[Dict[str, str]]:
        # Define permitted actions, explicitly excluding "No Action".
        # Also excluding USE_TOOL and LISTEN as they are not the focus.
        permitted_actions = [
            HandlerActionType.SPEAK,
            HandlerActionType.PONDER,
            HandlerActionType.REJECT_THOUGHT,
            HandlerActionType.DEFER_TO_WA
        ]
        action_options_str = ", ".join([action.value for action in permitted_actions])

        ethical_summary = f"Ethical PDMA Stance: {ethical_pdma_result.decision_rationale}. Key Conflicts: {ethical_pdma_result.conflicts or 'None'}. Resolution: {ethical_pdma_result.resolution or 'None'}."
        csdma_summary = f"CSDMA Output: Plausibility {csdma_result.common_sense_plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"
        dsdma_summary_str = "DSDMA did not apply or did not run for this thought."
        if dsdma_result:
            dsdma_summary_str = f"DSDMA ({dsdma_result.domain_name}) Output: Score {dsdma_result.domain_specific_score:.2f}, Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. Reasoning: {dsdma_result.reasoning}"

        ponder_notes_str_for_prompt_if_any = ""
        notes_list = []
        if hasattr(original_thought, 'ponder_notes') and original_thought.ponder_notes:
            notes_list = original_thought.ponder_notes
        elif original_thought.initial_context and original_thought.initial_context.get('ponder_notes'):
            notes_list = original_thought.initial_context.get('ponder_notes')

        if notes_list: # This implies current_ponder_count > 0 if notes exist from previous ponder
            ponder_notes_str_for_prompt_if_any = "\n\nIMPORTANT CONTEXT FROM PREVIOUS PONDERING ROUND(S):\n"
            ponder_notes_str_for_prompt_if_any += f"This thought has been pondered {current_ponder_count} time(s). PLEASE TRY AND ACT (SPEAK) NOW\n"
            ponder_notes_str_for_prompt_if_any += "The following key questions were previously identified:\n"
            for i, q_note in enumerate(notes_list):
                ponder_notes_str_for_prompt_if_any += f"{i+1}. {q_note}\n"
            ponder_notes_str_for_prompt_if_any += ("Please consider these questions and the original thought in your current evaluation. "
                                                 "If you choose to 'Ponder' again, ensure your new 'key_questions' are DIFFERENT "
                                                 "from the ones listed above and aim to address any REMAINING ambiguities or guide towards a solution.\n")
        elif current_ponder_count > 0: # Pondered, but somehow no notes (should be rare)
             ponder_notes_str_for_prompt_if_any = f"\n\nThis thought has been pondered {current_ponder_count} time(s) previously. If choosing 'Ponder' again, formulate new, insightful questions.\n"


        initial_benchmark_advisory = ""
        if benchmark_mode and current_ponder_count == 0: # First attempt in benchmark mode
            initial_benchmark_advisory = f"""
\n**BENCHMARK MODE - INITIAL ATTEMPT**:
Your ABSOLUTE PRIORITY is to attempt to answer the original thought directly using the 'Speak' action.
Analyze all provided information (original thought, DMA summaries) to formulate the best possible answer.
DO NOT select 'Ponder' or 'Defer to WA' on this initial attempt unless the input is utterly incomprehensible or directly requests no action.
If the input is a question or problem, you MUST attempt to provide a solution or answer via 'Speak'.
Avoid 'Reject Thought' unless the query is fundamentally unanswerable or inappropriate.
"""

        final_ponder_advisory = ""
        is_final_attempt_round = current_ponder_count >= max_ponder_rounds - 1

        if is_final_attempt_round:
            if benchmark_mode:
                final_ponder_advisory = f"""
\n**CRITICAL FINAL BENCHMARK ATTEMPT** (Ponder Count for NEXT attempt would be {current_ponder_count + 1}/{max_ponder_rounds}):
This is a benchmark run and your LAST CHANCE to provide a direct answer. You MUST provide a terminal answer NOW.
Strongly prioritize selecting the 'Speak' action with your best possible answer to the original thought, considering all previous ponder notes.
DO NOT select 'Ponder'. DO NOT select 'Defer to WA'.
If you absolutely cannot formulate a direct answer via 'Speak', then select 'Reject Thought' with a clear rationale, but only as a last resort.
Your primary goal is to output a definitive response via 'Speak'.
"""
            else: # Normal mode, final ponder round before automatic deferral
                final_ponder_advisory = f"""
\nIMPORTANT FINAL PONDER ROUND ADVISORY (Ponder Count for NEXT attempt would be {current_ponder_count + 1}/{max_ponder_rounds}):
You have Pondered multiple times. This is your final opportunity to provide a direct answer or a definitive deferral.
Your primary goal now is to attempt a 'Speak' action if at all feasible, using the original thought and all previous ponder notes to construct a response.
If, after careful consideration, you determine that a 'Speak' action is not possible due to unresolved critical ambiguities, then 'Defer to WA' is the appropriate choice.
Avoid selecting 'Ponder' again, as it will automatically result in a DEFER_TO_WA by the system.
'Reject Thought' should only be used if the original request is fundamentally unserviceable.
"""
        
        reject_thought_guidance = "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."

        # Conditional prompt segments for CSDMA ambiguity handling, nuanced by benchmark_mode and ponder_count
        if benchmark_mode:
            if current_ponder_count == 0: # Initial Benchmark Attempt
                action_alignment_csdma_guidance = """If CSDMA highlighted critical ambiguity, 'Speak' (for user clarification if essential to providing an initial answer as per the Initial Benchmark Advisory) or 'Ponder' (if a direct answer is truly impossible due to incomprehensibility) can be considered. The absolute priority is to attempt a 'Speak' response."""
                action_alignment_example = """Example: {{"Speak": "High priority for initial answer or essential clarification.", "Ponder": "Fallback if input is critically ambiguous and unanswerable via Speak."}}"""
                action_parameters_speak_csdma_guidance = """If 'Speak' is chosen, 'message_content' MUST contain the substantive response or an ESSENTIAL clarification if CSDMA identified critical ambiguity AND this is the INITIAL benchmark attempt. The primary goal is to provide some form of direct engagement via 'Speak' if at all possible, fulfilling the Initial Benchmark Advisory."""
            elif not is_final_attempt_round: # Intermediate Benchmark Ponder Rounds
                action_alignment_csdma_guidance = """If CSDMA highlighted critical ambiguity, highly align 'Ponder' (to formulate key clarifying questions internally for the next ponder round) with Fidelity & Do-Good.
    In BENCHMARK MODE (intermediate rounds), 'Speak' should be reserved for definitive answers, not for asking clarification questions to the user."""
                action_alignment_example = """Example: {{"Ponder": "High alignment due to CSDMA flag for internal clarification.", "Speak": "Lower alignment if used for clarification in intermediate benchmark rounds."}}"""
                action_parameters_speak_csdma_guidance = """If 'Speak' is chosen, 'message_content' MUST contain the substantive response. IMPORTANT FOR INTERMEDIATE BENCHMARK ROUNDS: If CSDMA identified ambiguity, DO NOT use 'Speak' to ask the user for clarification. Instead, use 'Ponder' to formulate internal questions. 'Speak' is for delivering a final answer."""
            else: # Final Benchmark Attempt (final_ponder_advisory will dominate)
                action_alignment_csdma_guidance = """On this CRITICAL FINAL BENCHMARK ATTEMPT, 'Speak' is paramount for delivering a definitive answer. 'Ponder' is strictly forbidden by the final advisory."""
                action_alignment_example = """Example: {{"Speak": "Highest alignment for final answer.", "Ponder": "Forbidden on final benchmark attempt."}}"""
                action_parameters_speak_csdma_guidance = """If 'Speak' is chosen, 'message_content' MUST contain the substantive response. This is the final benchmark attempt; clarification questions are not appropriate, a definitive answer is required."""
        else: # Normal Mode (not benchmark_mode)
            action_alignment_csdma_guidance = """If CSDMA highlighted critical ambiguity, highly align 'Speak' (for user clarification)
    or 'Ponder' (to formulate key clarifying questions) with Fidelity & Do-Good."""
            action_alignment_example = """Example: {{"Speak": "Evaluation...", "Ponder": "High alignment due to CSDMA flag."}}"""
            action_parameters_speak_csdma_guidance = """If 'Speak' is chosen, 'message_content' MUST contain the substantive response. If resolving CSDMA-identified ambiguity, 'message_content' MUST be a concise question to the user for clarification (e.g., {{"message_content": "To clarify, what do you mean by 'X'?"}})."""

        system_prompt = f"""You are an Action Selection reasoning agent governed by the CIRIS Covenant.
Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional.
{initial_benchmark_advisory}
Permitted Handler Actions: {action_options_str}
{reject_thought_guidance}
{final_ponder_advisory}
PDMA for Action Selection (all fields MANDATORY):
1.  'context_summary_for_action_selection': Summarize situation from original thought and DMAs. Crucially, note if CSDMA (see `csdma_summary`) flagged significant ambiguity impacting comprehension or safety. What is the core challenge, especially if such ambiguity exists?
2.  'action_alignment_check': MANDATORY field. This MUST be a JSON object (dictionary) where keys are
    plausible HANDLER ACTIONS (from {action_options_str}) and values are their evaluations
    against CIRIS principles & M-1. Use DMA summaries.
    {action_alignment_csdma_guidance}
    {action_alignment_example}
3.  'action_conflicts': Identify conflicts *between potential handler actions*. If none, "No conflicts identified." or null.
4.  'action_resolution': Resolve conflicts. If none, "Not applicable as no conflicts were identified." or null.
5.  'selected_handler_action': The LLM should determine this based on the inputs and other PDMA steps from the list: {action_options_str}.
6.  'action_parameters': Parameters for the chosen action.
    {action_parameters_speak_csdma_guidance}
    If 'Speak' is chosen, 'message_content' MUST contain the substantive response. If resolving CSDMA-identified ambiguity, 'message_content' MUST be a concise question to the user for clarification (e.g., {{"message_content": "To clarify, what do you mean by 'X'?"}}).
    If 'Ponder' is chosen (and not in final benchmark attempt under benchmark_mode, or if advisory allows), 'key_questions' MUST
    list 2-3 distinct, NEW questions to resolve the ambiguity, building upon or differing from any previous ponder_notes. For example, if the original thought was about "murres":
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
        dsdma_result: Optional[DSDMAResult],
        current_ponder_count: int,
        max_ponder_rounds: int,
        benchmark_mode: bool = False 
    ) -> ActionSelectionPDMAResult:

        messages = self._create_action_selection_messages_for_instructor(
            original_thought,
            ethical_pdma_result,
            csdma_result,
            dsdma_result,
            current_ponder_count,
            max_ponder_rounds,
            benchmark_mode
        )

        try:
            action_eval: ActionSelectionPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=ActionSelectionPDMAResult,
                messages=messages,
                max_tokens=1500
            )

            is_final_attempt_round = current_ponder_count >= max_ponder_rounds - 1
            if benchmark_mode and is_final_attempt_round and \
               (action_eval.selected_handler_action == HandlerActionType.PONDER or \
                action_eval.selected_handler_action == HandlerActionType.DEFER_TO_WA):
                logger.warning(f"Benchmark mode: LLM selected {action_eval.selected_handler_action.value} on final attempt for thought {original_thought.thought_id} despite strong advisory. This might indicate prompt ineffectiveness or need for override.")

            if not isinstance(action_eval.selected_handler_action, HandlerActionType):
                try:
                    # Attempt to coerce if it's a string matching an enum value
                    action_eval.selected_handler_action = HandlerActionType(str(action_eval.selected_handler_action))
                except ValueError as ve: # If string doesn't match any enum value
                    logger.error(f"ActionSelectionPDMA (instructor) invalid action type '{action_eval.selected_handler_action}': {ve}. Defaulting to Ponder.")
                    # Fallback to PONDER if the LLM hallucinates an action type
                    action_eval.selected_handler_action = HandlerActionType.PONDER
                    action_eval.action_parameters = {"reason": f"Invalid action type received: {str(action_eval.selected_handler_action)}"}
                    action_eval.action_selection_rationale = f"Fallback to Ponder due to invalid action type: {str(action_eval.selected_handler_action)}. Original rationale may be lost."


            raw_response_data = None
            if hasattr(action_eval, '_raw_response'):
                raw_response_data = str(action_eval._raw_response)
            
            if hasattr(action_eval, 'raw_llm_response'):
                action_eval.raw_llm_response = raw_response_data
            elif raw_response_data is not None:
                logger.warning("ActionSelectionPDMAResult does not have 'raw_llm_response' field, but raw data was available from instructor.")

            logger.info(f"ActionSelectionPDMA (instructor) evaluation successful for thought ID {original_thought.thought_id}: Chose {action_eval.selected_handler_action.value}")
            return action_eval

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"ActionSelectionPDMA (instructor) InstructorRetryException for thought {original_thought.thought_id}: {error_detail}", exc_info=True)
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Error: LLM/Instructor validation error during action selection.",
                action_alignment_check={"error": f"InstructorRetryException: {error_detail}"},
                selected_handler_action=HandlerActionType.PONDER, 
                action_parameters={"reason": f"InstructorRetryException: {error_detail}"},
                action_selection_rationale=f"Fallback due to InstructorRetryException: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e: # General exception
            logger.error(f"ActionSelectionPDMA (instructor) evaluation failed for thought ID {original_thought.thought_id}: {e}", exc_info=True)
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection=f"Error: General exception - {str(e)}",
                action_alignment_check={"error": f"General Exception: {str(e)}"},
                selected_handler_action=HandlerActionType.PONDER,
                action_parameters={"reason": f"General Exception: {str(e)}"},
                action_selection_rationale=f"Fallback due to General Exception: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' (using instructor)>"
