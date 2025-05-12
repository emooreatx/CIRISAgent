# src/ciris_engine/dma/action_selection_pdma.py
from typing import Dict, Any, Optional, List
import logging

import instructor
# from instructor import Mode as InstructorMode # REMOVE Mode import
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
    DEFAULT_PROMPT = {
        "system_header": (
            "You are the CIRIS Action‑Selection evaluator. "
            "Given the PDMA, CSDMA and DSDMA results, choose one handler action."
        ),
        "decision_format": (
            "Return JSON with keys: action, confidence, rationale."
        ),
        "closing_reminder": (
            "Remember CIRIS principles override personal preference."
        ),
        # Default (Normal Mode) CSDMA Ambiguity Handling Guidance
        "normal_mode_csdma_ambiguity_guidance": (
            "If CSDMA highlighted critical ambiguity, highly align 'Speak' (for user clarification) "
            "or 'Ponder' (to formulate key clarifying questions) with Fidelity & Do-Good."
        ),
        "normal_mode_csdma_ambiguity_alignment_example": (
            """Example: {{"Speak": "Evaluation...", "Ponder": "High alignment due to CSDMA flag."}}"""
        ),
        "normal_mode_action_params_speak_csdma_guidance": (
            "If 'Speak' is chosen, 'message_content' MUST contain the substantive response. If resolving CSDMA-identified ambiguity, "
            "'message_content' MUST be a concise question to the user for clarification (e.g., {{\"message_content\": \"To clarify, what do you mean by 'X'?\"}})."
        ),
        "normal_mode_action_params_ponder_guidance": (
            "If 'Ponder' is chosen (and not in final benchmark attempt under benchmark_mode, or if advisory allows), 'key_questions' MUST "
            "list 2-3 distinct, NEW questions to resolve the ambiguity, building upon or differing from any previous ponder_notes. For example, if the original thought was about \"murres\":\n"
            """    {{"key_questions": ["What are 'murres' in this specific fictional context?", "Are 'murres' animals, mythological beings, or something else entirely?", "What is the user's primary goal for this 'murres' narrative?"]}}"""
        ),
        "normal_mode_action_selection_rationale_csdma_guidance": (
            "If addressing CSDMA-flagged ambiguity, this MUST be a central part of your rationale."
        ),

        # Student Mode CSDMA Ambiguity Handling Guidance (to be overridden by profile)
        "student_mode_csdma_ambiguity_guidance": ( # Default if not overridden by student profile
            "If CSDMA highlighted critical ambiguity, strongly consider 'Ponder' to formulate critical analytical questions. "
            "'Speak' for clarification is acceptable if Pondering cannot resolve it."
        ),
        "student_mode_csdma_ambiguity_alignment_example": ( # Default if not overridden
            """Example: {{"Ponder": "Very high alignment for critical analysis due to CSDMA flag.", "Speak": "Moderate alignment for clarification if Ponder is insufficient."}}"""
        ),
        "student_mode_action_params_speak_csdma_guidance": ( # Default if not overridden
            "If 'Speak' is chosen for clarification due to CSDMA ambiguity, 'message_content' MUST be a question aimed at understanding the core concepts or assumptions. "
            "Avoid providing answers when fundamental understanding is lacking."
        ),
        "student_mode_action_params_ponder_guidance": ( # Default if not overridden
            "If 'Ponder' is chosen, 'key_questions' MUST list 2-3 critical, analytical questions that challenge assumptions, explore underlying principles, or seek deeper understanding of the ambiguous elements. "
            "For example, if the thought is 'Explain quantum entanglement for a layperson':\n"
            """    {{"key_questions": ["What is the current understanding of 'layperson' in this context - e.g., no science background, some high school physics?", "What specific aspect of quantum entanglement is most confusing or interesting to the user?", "Are there any analogies the user already understands that could be leveraged (e.g., correlated dice)?"]}}"""
        ),
        "student_mode_action_selection_rationale_csdma_guidance": ( # Default if not overridden
            "If CSDMA flagged ambiguity, your rationale MUST explain how the chosen action (especially Ponder) helps in critically analyzing and understanding the ambiguous concept from a learner's perspective."
        ),
        # Final Ponder Advisory defaults
        "normal_mode_final_ponder_advisory": (
            "\nIMPORTANT FINAL PONDER ROUND ADVISORY (Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_ponder_rounds}):\n"
            "You have Pondered multiple times. This is your final opportunity to provide a direct answer or a definitive deferral.\n"
            "Your primary goal now is to attempt a 'Speak' action if at all feasible, using the original thought and all previous ponder notes to construct a response.\n"
            "If, after careful consideration, you determine that a 'Speak' action is not possible due to unresolved critical ambiguities, then 'Defer to WA' is the appropriate choice.\n"
            "Avoid selecting 'Ponder' again, as it will automatically result in a DEFER_TO_WA by the system.\n"
            "'Reject Thought' should only be used if the original request is fundamentally unserviceable."
        ),
        "student_mode_final_ponder_advisory": ( # Default if not overridden by student profile
            "\nCRITICAL FINAL ATTEMPT (Student Profile - Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_ponder_rounds}):\n"
            "You have Pondered multiple times. This is your ABSOLUTE FINAL opportunity to provide a DIRECT ANSWER.\n"
            "You MUST select 'Speak' and provide your best direct answer based on all prior analysis and CSDMA flags. YOUR ANSWER MUST NOT BE A QUESTION.\n"
            "If you cannot formulate a direct, non-question answer, then 'Reject Thought' is your only other viable option. DO NOT PONDER AGAIN. DO NOT DEFER."
        )
    }

    def __init__(self, aclient: instructor.Instructor, model_name: str = DEFAULT_OPENAI_MODEL_NAME, prompt_overrides: Optional[Dict[str, str]] = None):
        self.aclient = aclient
        self.model_name = model_name
        self.prompt = {**self.DEFAULT_PROMPT, **(prompt_overrides or {})}

    def _get_profile_specific_prompt(self, base_key: str, agent_profile_name: Optional[str]) -> str:
        """Helper to get profile-specific prompt or fallback to normal mode."""
        if agent_profile_name:
            profile_key = f"{agent_profile_name.lower()}_mode_{base_key}"
            if profile_key in self.prompt:
                return self.prompt[profile_key]
        
        # Fallback to normal_mode or the base key itself if it's a general prompt part
        normal_key = f"normal_mode_{base_key}"
        if normal_key in self.prompt:
            return self.prompt[normal_key]
        
        # Fallback for general keys not prefixed with mode
        if base_key in self.prompt:
             return self.prompt[base_key]

        logger.warning(f"Prompt key for '{base_key}' (profile: {agent_profile_name}) not found. Returning empty string or raising error might be better.")
        return self.DEFAULT_PROMPT.get(normal_key, "") # Default to normal if specific not found


    def _prepare_main_user_content(
        self,
        triaged_inputs: Dict[str, Any]
    ) -> str:
        original_thought: ThoughtQueueItem = triaged_inputs['original_thought']
        ethical_pdma_result: EthicalPDMAResult = triaged_inputs['ethical_pdma_result']
        csdma_result: CSDMAResult = triaged_inputs['csdma_result']
        dsdma_result: Optional[DSDMAResult] = triaged_inputs.get('dsdma_result') # Use .get for optional
        current_ponder_count: int = triaged_inputs['current_ponder_count']
        max_ponder_rounds: int = triaged_inputs['max_ponder_rounds']
        # benchmark_mode: bool = triaged_inputs.get('benchmark_mode', False) # REMOVE - No longer used directly here
        
        agent_name_from_thought = None
        # AttributeError indicated original_thought is a Thought object, not ThoughtQueueItem at this point.
        # Access agent_name via processing_context for a Thought object.
        if hasattr(original_thought, 'processing_context') and original_thought.processing_context:
            environment_context = original_thought.processing_context.get('environment_context')
            if isinstance(environment_context, dict):
                agent_name_from_thought = environment_context.get('agent_name')
        
        # Fallback: Check context_json if not found in processing_context's environment_context
        if not agent_name_from_thought and hasattr(original_thought, 'context_json') and original_thought.context_json:
            environment_context = original_thought.context_json.get('environment_context')
            if isinstance(environment_context, dict):
                agent_name_from_thought = environment_context.get('agent_name')

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
        # original_thought is now a Thought Pydantic model.
        # It has 'ponder_notes' directly and 'processing_context'.
        if original_thought.ponder_notes:
            notes_list = original_thought.ponder_notes
        # Check for ponder_notes within processing_context if not directly on thought (legacy or alternative storage)
        elif original_thought.processing_context and original_thought.processing_context.get('ponder_notes'):
            notes_list = original_thought.processing_context.get('ponder_notes')

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

        # initial_benchmark_advisory and benchmark-specific final_ponder_advisory are removed.
        # Profile-specific prompts should handle any special first-pass or final-pass logic if needed.

        final_ponder_advisory = ""
        is_final_attempt_round = current_ponder_count >= max_ponder_rounds - 1

        if is_final_attempt_round:
            final_ponder_advisory_template = self._get_profile_specific_prompt("final_ponder_advisory", agent_name_from_thought)
            try:
                final_ponder_advisory = final_ponder_advisory_template.format(
                    current_ponder_count_plus_1=current_ponder_count + 1,
                    max_ponder_rounds=max_ponder_rounds
                )
            except KeyError as e:
                logger.error(f"KeyError formatting final_ponder_advisory_template: {e}. Template: '{final_ponder_advisory_template}'")
                # Fallback to a generic message if formatting fails
                final_ponder_advisory = "\nIMPORTANT FINAL PONDER ROUND: Attempt to provide a terminal action."

        
        reject_thought_guidance = "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."

        # Conditional prompt segments are now solely based on agent_name_from_thought (profile)
        # The _get_profile_specific_prompt will fetch the correct version based on agent_name_from_thought
        # or fall back to "normal_mode" defaults if a profile-specific version isn't in self.prompt.
        
        action_alignment_csdma_guidance = self._get_profile_specific_prompt("csdma_ambiguity_guidance", agent_name_from_thought)
        action_alignment_example = self._get_profile_specific_prompt("csdma_ambiguity_alignment_example", agent_name_from_thought)
        action_parameters_speak_csdma_guidance = self._get_profile_specific_prompt("action_params_speak_csdma_guidance", agent_name_from_thought)
        action_parameters_ponder_guidance = self._get_profile_specific_prompt("action_params_ponder_guidance", agent_name_from_thought)
        action_selection_rationale_csdma_guidance = self._get_profile_specific_prompt("action_selection_rationale_csdma_guidance", agent_name_from_thought)

        # Check if there's a custom system_header from the profile to inject
        profile_specific_system_header_injection = ""
        # self.prompt contains merged defaults and overrides.
        # self.DEFAULT_PROMPT["system_header"] is the original default.
        current_system_header = self.prompt.get("system_header", self.DEFAULT_PROMPT["system_header"])
        if current_system_header != self.DEFAULT_PROMPT["system_header"]: # It's a custom override
            profile_specific_system_header_injection = f"IMPORTANT AGENT PROFILE DIRECTIVE: {current_system_header}\n\n"

        main_user_content_prompt = f"""\
{profile_specific_system_header_injection}Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional.
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
    {action_parameters_ponder_guidance}
    Provide empty dict {{}} if no parameters for other actions.
7.  'action_selection_rationale': Justify *why* this handler action is optimal. {action_selection_rationale_csdma_guidance}
8.  'monitoring_for_selected_action': Concrete monitoring plan for THIS chosen action (string or dict).

IMPORTANT: Your entire response MUST be a single JSON object.
The JSON object MUST have these top-level keys, all populated:
'context_summary_for_action_selection', 'action_alignment_check', 'action_conflicts',
'action_resolution', 'selected_handler_action', 'action_parameters',
'action_selection_rationale', 'monitoring_for_selected_action'.

Original Thought: "{str(original_thought.content)}"
{ponder_notes_str_for_prompt_if_any}
Original Thought Processing Context: {str(original_thought.processing_context) if original_thought.processing_context else "N/A"}

DMA Summaries to consider for your PDMA reasoning:
Ethical PDMA: {ethical_summary}
CSDMA: {csdma_summary}
DSDMA: {dsdma_summary_str}

Based on all the provided information and the PDMA framework for action selection, determine the appropriate handler action and structure your response as specified.
Adhere strictly to the schema for your JSON output.
"""
        # Debug logging for Student profile's final ponder attempt prompt
        if is_final_attempt_round and agent_name_from_thought and agent_name_from_thought.lower() == "student":
            logger.debug(f"STUDENT PROFILE - FINAL PONDER ATTEMPT - ActionSelectionPDMA main_user_content_prompt:\n{main_user_content_prompt}")

        return main_user_content_prompt

    async def evaluate(
        self,
        triaged_inputs: Dict[str, Any]
    ) -> ActionSelectionPDMAResult:
        original_thought: ThoughtQueueItem = triaged_inputs['original_thought'] # For logging & post-processing
        current_ponder_count: int = triaged_inputs['current_ponder_count'] # For post-processing
        max_ponder_rounds: int = triaged_inputs['max_ponder_rounds'] # For post-processing
        # benchmark_mode: bool = triaged_inputs.get('benchmark_mode', False) # REMOVE - No longer used directly here

        main_user_content = self._prepare_main_user_content(triaged_inputs)
        messages = [
            {"role": "system", "content": self.prompt["system_header"]},
            {"role": "user",   "content": main_user_content},
            {"role": "system", "content": self.prompt["decision_format"]},
            {"role": "system", "content": self.prompt["closing_reminder"]},
        ]

        try:
            action_eval: ActionSelectionPDMAResult = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=ActionSelectionPDMAResult,
                # mode=InstructorMode.JSON, # REMOVE mode from here
                messages=messages,
                max_tokens=1500
            )

            # Removed benchmark_mode specific warning here. Profile-specific prompts should handle final attempt logic.
            # is_final_attempt_round = current_ponder_count >= max_ponder_rounds - 1
            # if benchmark_mode and is_final_attempt_round and \
            #    (action_eval.selected_handler_action == HandlerActionType.PONDER or \
            #     action_eval.selected_handler_action == HandlerActionType.DEFER_TO_WA):
            #     logger.warning(f"Benchmark mode: LLM selected {action_eval.selected_handler_action.value} on final attempt for thought {original_thought.thought_id} despite strong advisory. This might indicate prompt ineffectiveness or need for override.")

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
            logger.debug(f"ActionSelectionPDMA (instructor) action_parameters: {action_eval.action_parameters}")
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
