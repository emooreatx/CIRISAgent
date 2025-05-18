from typing import Dict, Any, Optional, List, Union # Added Union
import logging

import instructor
from openai import AsyncOpenAI

# Corrected imports
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem # Though 'Thought' model is used internally
from ciris_engine.core.agent_core_schemas import (
    Thought, # Assuming Thought model is passed in triaged_inputs
    CSDMAResult,
    DSDMAResult,
    EthicalPDMAResult,
    ActionSelectionPDMAResult,
    HandlerActionType,
    # Import all param types for potential parsing later, though not strictly needed for this file's direct logic
    ObserveParams, SpeakParams, ActParams, PonderParams,
    RejectParams, DeferParams, MemorizeParams, RememberParams, ForgetParams,
    CIRISSchemaVersion # Import CIRISSchemaVersion
)
from ciris_engine.core.foundational_schemas import HandlerActionType as CoreHandlerActionType # Alias to avoid conflict if any
from ciris_engine.core.config_schemas import DEFAULT_OPENAI_MODEL_NAME # Corrected import
from instructor.exceptions import InstructorRetryException
import instructor # Import the main instructor module for Mode
from ciris_engine.utils import DEFAULT_WA
from pydantic import BaseModel, Field, ValidationError

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
            "Given PDMA, CSDMA and DSDMA results, choose one handler action. "
            "Use MEMORIZE to store facts in graph memory when allowed. "
            "REMEMBER and FORGET exist but may be disabled. "
            "If ponder rounds exceed the limit the system auto‑defers."
        ),
        "decision_format": ( # This describes the LLM's direct output structure
            "Return JSON with keys: context_summary_for_action_selection, action_alignment_check, "
            "action_conflicts, action_resolution, selected_handler_action, action_parameters, "
            "action_selection_rationale, monitoring_for_selected_action."
            # Confidence score is not requested from LLM here, but is part of ActionSelectionPDMAResult
        ),
        "closing_reminder": (
            "Remember CIRIS principles override personal preference."
        ),
        "action_parameter_schemas": (
            "Schemas for 'action_parameters' based on the selected_handler_action:\n"
            "SPEAK: {\"content\": string, \"target_channel\"?: string, \"target_agent_did\"?: string, \"modality\"?: string, \"correlation_id\"?: string}\n"
            "PONDER: {\"key_questions\": [string], \"focus_areas\"?: [string], \"max_ponder_rounds\"?: int}\n"
            "MEMORIZE: {\"knowledge_unit_description\": string, \"knowledge_data\": object|string, \"knowledge_type\": string, \"source\": string, \"confidence\": float, \"publish_to_dkg\"?: bool, \"target_ka_ual\"?: string, \"channel_metadata\"?: object}\n"
            "DEFER: {\"reason\": string, \"target_wa_ual\": string, \"deferral_package_content\": object}\n"
            "REJECT: {\"reason\": string, \"rejection_code\"?: string}\n"
            "ACT: {\"tool_name\": string, \"arguments\": object}"
        ),
        "normal_mode_csdma_ambiguity_guidance": (
            "If CSDMA highlighted critical ambiguity, highly align 'Speak' (for user clarification) "
            "or 'Ponder' (to formulate key clarifying questions) with Fidelity & Do-Good."
        ),
        "normal_mode_csdma_ambiguity_alignment_example": (
            """Example: {{"Speak": "Evaluation...", "Ponder": "High alignment due to CSDMA flag."}}"""
        ),
        "normal_mode_action_params_speak_csdma_guidance": (
            "If 'Speak' is chosen, the 'action_parameters' MUST be a JSON object. This object MUST contain a key named 'content'. The value for 'content' MUST be the substantive response string. Example: {{\"content\": \"Your direct answer or clarifying question here.\"}}. DO NOT use 'message_content'."
        ),
        "normal_mode_action_params_ponder_guidance": (
            "If 'Ponder' is chosen (and not in final benchmark attempt under benchmark_mode, or if advisory allows), 'key_questions' MUST "
            "list 2-3 distinct, NEW questions to resolve the ambiguity, building upon or differing from any previous ponder_notes. For example, if the original thought was about \"murres\":\n"
            """    {{"key_questions": ["What are 'murres' in this specific fictional context?", "Are 'murres' animals, mythological beings, or something else entirely?", "What is the user's primary goal for this 'murres' narrative?"]}}"""
        ),
        "normal_mode_action_selection_rationale_csdma_guidance": (
            "If addressing CSDMA-flagged ambiguity, this MUST be a central part of your rationale."
        ),
        "student_mode_csdma_ambiguity_guidance": (
            "If CSDMA highlighted critical ambiguity, strongly consider 'Ponder' to formulate critical analytical questions. "
            "'Speak' for clarification is acceptable if Pondering cannot resolve it."
        ),
        "student_mode_csdma_ambiguity_alignment_example": (
            """Example: {{"Ponder": "Very high alignment for critical analysis due to CSDMA flag.", "Speak": "Moderate alignment for clarification if Ponder is insufficient."}}"""
        ),
        "student_mode_action_params_speak_csdma_guidance": (
            "If 'Speak' is chosen for clarification due to CSDMA ambiguity, 'content' MUST be a question aimed at understanding the core concepts or assumptions. " # Changed to 'content'
            "Avoid providing answers when fundamental understanding is lacking. Ensure the key is 'content'." # Add reminder
        ),
        "student_mode_action_params_ponder_guidance": (
            "If 'Ponder' is chosen, 'key_questions' MUST list 2-3 critical, analytical questions that challenge assumptions, explore underlying principles, or seek deeper understanding of the ambiguous elements. "
            "For example, if the thought is 'Explain quantum entanglement for a layperson':\n"
            """    {{"key_questions": ["What is the current understanding of 'layperson' in this context - e.g., no science background, some high school physics?", "What specific aspect of quantum entanglement is most confusing or interesting to the user?", "Are there any analogies the user already understands that could be leveraged (e.g., correlated dice)?"]}}"""
        ),
        "student_mode_action_selection_rationale_csdma_guidance": (
            "If CSDMA flagged ambiguity, your rationale MUST explain how the chosen action (especially Ponder) helps in critically analyzing and understanding the ambiguous concept from a learner's perspective."
        ),
        "normal_mode_final_ponder_advisory": (
            "\nIMPORTANT FINAL PONDER ROUND ADVISORY (Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_ponder_rounds}):\n"
            "You have Pondered multiple times. This is your final opportunity to provide a direct answer or a definitive deferral.\n"
            "Your primary goal now is to attempt a 'Speak' action if at all feasible, using the original thought and all previous ponder notes to construct a response.\n"
            "If, after careful consideration, you determine that a 'Speak' action is not possible due to unresolved critical ambiguities, then 'Defer to WA' is the appropriate choice.\n"
            "Avoid selecting 'Ponder' again, as it will automatically result in a DEFER_TO_WA by the system.\n"
            "'Reject Thought' should only be used if the original request is fundamentally unserviceable."
        ),
        "student_mode_final_ponder_advisory": (
            "\nCRITICAL FINAL ATTEMPT (Student Profile - Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_ponder_rounds}):\n"
            "You have Pondered multiple times. This is your ABSOLUTE FINAL opportunity to provide a DIRECT ANSWER.\n"
            "You MUST select 'Speak' and provide your best direct answer based on all prior analysis and CSDMA flags. YOUR ANSWER MUST NOT BE A QUESTION.\n"
            "If you cannot formulate a direct, non-question answer, then 'Reject Thought' is your only other viable option. DO NOT PONDER AGAIN. DO NOT DEFER."
        )
    }

    def __init__(self,
                 aclient: AsyncOpenAI, # Expect raw AsyncOpenAI client
                 model_name: str = DEFAULT_OPENAI_MODEL_NAME,
                 prompt_overrides: Optional[Dict[str, str]] = None,
                 instructor_mode: instructor.Mode = instructor.Mode.JSON): # Add instructor_mode
        # Patch the client with instructor and the specified mode
        self.aclient: instructor.Instructor = instructor.patch(aclient, mode=instructor_mode)
        self.model_name = model_name
        self.prompt = {**self.DEFAULT_PROMPT, **(prompt_overrides or {})}
        self.instructor_mode = instructor_mode # Store for reference if needed

    def _get_profile_specific_prompt(self, base_key: str, agent_profile_name: Optional[str]) -> str:
        if agent_profile_name:
            profile_key = f"{agent_profile_name.lower()}_mode_{base_key}"
            if profile_key in self.prompt:
                return self.prompt[profile_key]
        
        normal_key = f"normal_mode_{base_key}"
        if normal_key in self.prompt:
            return self.prompt[normal_key]
        
        if base_key in self.prompt:
             return self.prompt[base_key]

        logger.warning(f"Prompt key for '{base_key}' (profile: {agent_profile_name}) not found. Using default from DEFAULT_PROMPT or empty string.")
        return self.DEFAULT_PROMPT.get(normal_key, self.DEFAULT_PROMPT.get(base_key,""))


    def _prepare_main_user_content(
        self,
        triaged_inputs: Dict[str, Any]
    ) -> str:
        original_thought: Thought = triaged_inputs['original_thought'] # Assuming Thought model
        ethical_pdma_result: EthicalPDMAResult = triaged_inputs['ethical_pdma_result']
        csdma_result: CSDMAResult = triaged_inputs['csdma_result']
        dsdma_result: Optional[DSDMAResult] = triaged_inputs.get('dsdma_result')
        current_ponder_count: int = triaged_inputs['current_ponder_count']
        max_ponder_rounds: int = triaged_inputs['max_ponder_rounds']
        agent_profile: Optional[Any] = triaged_inputs.get('agent_profile') # Get the profile if available

        agent_name_from_thought = None
        # Prefer agent name from the passed agent_profile object
        if agent_profile and hasattr(agent_profile, 'name'): # Check for 'name' attribute
             agent_name_from_thought = agent_profile.name
             logger.debug(f"Using agent name '{agent_name_from_thought}' from provided agent_profile object.")
        elif hasattr(original_thought, 'processing_context') and original_thought.processing_context:
            # Fallback to environment_context within the thought if agent_profile not passed or no name
            environment_context = original_thought.processing_context.get('environment_context')
            if isinstance(environment_context, dict):
                agent_name_from_thought = environment_context.get('agent_name')
                if agent_name_from_thought:
                    logger.debug(f"Using agent name '{agent_name_from_thought}' from thought's environment_context.")
        
        # The old fallback to original_thought.context_json is removed as it was non-standard.
        if not agent_name_from_thought:
            logger.warning(f"Could not determine agent name for thought {original_thought.thought_id}. Profile-specific prompts might not apply.")

        # --- Get permitted actions dynamically ---
        # Default fallback list
        default_permitted_actions = [
            HandlerActionType.SPEAK, HandlerActionType.PONDER,
            HandlerActionType.REJECT, HandlerActionType.DEFER
        ]
        permitted_actions: List[HandlerActionType] = triaged_inputs.get('permitted_actions', default_permitted_actions)

        if 'permitted_actions' not in triaged_inputs:
             logger.warning(f"ActionSelectionPDMA: 'permitted_actions' not found in triaged_inputs for thought {original_thought.thought_id}. Falling back to default: {[a.value for a in default_permitted_actions]}")
        elif not permitted_actions: # Handle case where it's provided but empty
             logger.warning(f"ActionSelectionPDMA: 'permitted_actions' in triaged_inputs is empty for thought {original_thought.thought_id}. Falling back to default.")
             permitted_actions = default_permitted_actions

        action_options_str = ", ".join([action.value for action in permitted_actions])
        # --- End dynamic permitted actions ---

        # Using ethical_pdma_result.decision as decision_rationale is not present
        ethical_summary = f"Ethical PDMA Stance: {ethical_pdma_result.decision}. Key Conflicts: {ethical_pdma_result.conflicts or 'None'}. Resolution: {ethical_pdma_result.resolution or 'None'}."
        csdma_summary = f"CSDMA Output: Plausibility {csdma_result.common_sense_plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"
        
        dsdma_summary_str = "DSDMA did not apply or did not run for this thought."
        if dsdma_result:
            # Accessing dsdma_result.domain_name which was added to the schema
            dsdma_summary_str = f"DSDMA ({dsdma_result.domain_name}) Output: Score {dsdma_result.domain_alignment_score:.2f}, Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. Reasoning: {dsdma_result.reasoning}"

        ponder_notes_str_for_prompt_if_any = ""
        notes_list = original_thought.ponder_notes if original_thought.ponder_notes else []

        if notes_list:
            ponder_notes_str_for_prompt_if_any = "\n\nIMPORTANT CONTEXT FROM PREVIOUS PONDERING ROUND(S):\n"
            ponder_notes_str_for_prompt_if_any += f"This thought has been pondered {current_ponder_count} time(s). PLEASE TRY AND ACT (SPEAK) NOW\n"
            ponder_notes_str_for_prompt_if_any += "The following key questions were previously identified:\n"
            for i, q_note in enumerate(notes_list):
                ponder_notes_str_for_prompt_if_any += f"{i+1}. {q_note}\n"
            ponder_notes_str_for_prompt_if_any += ("Please consider these questions and the original thought in your current evaluation. "
                                                 "If you choose to 'Ponder' again, ensure your new 'key_questions' are DIFFERENT "
                                                 "from the ones listed above and aim to address any REMAINING ambiguities or guide towards a solution.\n")
        elif current_ponder_count > 0:
             ponder_notes_str_for_prompt_if_any = f"\n\nThis thought has been pondered {current_ponder_count} time(s) previously. If choosing 'Ponder' again, formulate new, insightful questions.\n"

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
                final_ponder_advisory = "\nIMPORTANT FINAL PONDER ROUND: Attempt to provide a terminal action."
        
        reject_thought_guidance = "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."
        
        action_alignment_csdma_guidance = self._get_profile_specific_prompt("csdma_ambiguity_guidance", agent_name_from_thought)
        action_alignment_example = self._get_profile_specific_prompt("csdma_ambiguity_alignment_example", agent_name_from_thought)
        action_parameters_speak_csdma_guidance = self._get_profile_specific_prompt("action_params_speak_csdma_guidance", agent_name_from_thought)
        action_parameters_ponder_guidance = self._get_profile_specific_prompt("action_params_ponder_guidance", agent_name_from_thought)
        action_selection_rationale_csdma_guidance = self._get_profile_specific_prompt("action_selection_rationale_csdma_guidance", agent_name_from_thought)
        action_parameter_schemas = self.prompt.get("action_parameter_schemas", self.DEFAULT_PROMPT.get("action_parameter_schemas", ""))

        profile_specific_system_header_injection = ""
        current_system_header = self.prompt.get("system_header", self.DEFAULT_PROMPT["system_header"])
        if current_system_header != self.DEFAULT_PROMPT["system_header"]:
            profile_specific_system_header_injection = f"IMPORTANT AGENT PROFILE DIRECTIVE: {current_system_header}\n\n"

        startup_guidance = ""
        if original_thought.thought_type == "startup_meta":
            startup_guidance = (
                "\nCRITICAL STARTUP DIRECTIVE: When handling 'startup_meta' thoughts, "
                "select SPEAK to confirm status or PONDER only if additional internal checks are required. "
                "Avoid MEMORIZE, ACT, REJECT, or DEFER during startup."
            )

        # Using original_thought.content which is a string
        main_user_content_prompt = f"""\
{profile_specific_system_header_injection}Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional.
Permitted Handler Actions: {action_options_str}
{startup_guidance}
{reject_thought_guidance}
{final_ponder_advisory}
{action_parameter_schemas}
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
6.  'action_parameters': Parameters for the chosen action. This MUST be a JSON object strictly matching the schema for the selected_handler_action.
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

Original Thought: "{original_thought.content}"
{ponder_notes_str_for_prompt_if_any}
Original Thought Processing Context: {str(original_thought.processing_context) if original_thought.processing_context else "N/A"}

DMA Summaries to consider for your PDMA reasoning:
Ethical PDMA: {ethical_summary}
CSDMA: {csdma_summary}
DSDMA: {dsdma_summary_str}

Based on all the provided information and the PDMA framework for action selection, determine the appropriate handler action and structure your response as specified.
Adhere strictly to the schema for your JSON output.
"""
        if is_final_attempt_round and agent_name_from_thought and agent_name_from_thought.lower() == "student":
            logger.debug(f"STUDENT PROFILE - FINAL PONDER ATTEMPT - ActionSelectionPDMA main_user_content_prompt:\n{main_user_content_prompt}")
        return main_user_content_prompt

    async def evaluate(
        self,
        triaged_inputs: Dict[str, Any]
    ) -> ActionSelectionPDMAResult:
        original_thought: Thought = triaged_inputs['original_thought'] # For logging & post-processing

        # --- Special case for forcing PONDER ---
        # Check the original message content from the task context stored in the thought's processing_context
        original_message_content = None
        if original_thought.processing_context and \
           isinstance(original_thought.processing_context.get("initial_task_context"), dict):
            original_message_content = original_thought.processing_context["initial_task_context"].get("content")

        if original_message_content and original_message_content.strip().lower() == "ponder":
            logger.info(f"ActionSelectionPDMA: Detected 'ponder' keyword in original message for thought ID {original_thought.thought_id}. Forcing PONDER action.")
            ponder_params = PonderParams(key_questions=["Forced ponder: What are the key ambiguities?", "Forced ponder: How can this be clarified?"])
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Forced PONDER action due to 'ponder' keyword.",
                action_alignment_check={"PONDER": "Forced by test condition"},
                selected_handler_action=HandlerActionType.PONDER,
                action_parameters=ponder_params,
                action_selection_rationale="Forced PONDER for testing ponder loop.",
                monitoring_for_selected_action="Monitor ponder count and deferral.",
                ethical_assessment_summary=(
                    triaged_inputs['ethical_pdma_result'].model_dump()
                    if isinstance(triaged_inputs.get('ethical_pdma_result'), BaseModel)
                    else ({"summary": triaged_inputs.get('ethical_pdma_result')} if isinstance(triaged_inputs.get('ethical_pdma_result'), dict) else {"status": "Skipped or error", "details": str(triaged_inputs.get('ethical_pdma_result'))})
                ),
                csdma_assessment_summary=(
                    triaged_inputs['csdma_result'].model_dump()
                    if isinstance(triaged_inputs.get('csdma_result'), BaseModel)
                    else ({"summary": triaged_inputs.get('csdma_result')} if isinstance(triaged_inputs.get('csdma_result'), dict) else {"status": "Skipped or error", "details": str(triaged_inputs.get('csdma_result'))})
                ),
                dsdma_assessment_summary=(
                    triaged_inputs['dsdma_result'].model_dump()
                    if isinstance(triaged_inputs.get('dsdma_result'), BaseModel)
                    else ({"summary": triaged_inputs.get('dsdma_result')} if isinstance(triaged_inputs.get('dsdma_result'), dict) else {"status": "Skipped or error", "details": str(triaged_inputs.get('dsdma_result'))})
                )
            )
        # --- End special case ---
        
        main_user_content = self._prepare_main_user_content(triaged_inputs)
        messages = [
            {"role": "system", "content": self.prompt.get("system_header", "")}, # Use .get for safety
            {"role": "user",   "content": main_user_content},
            {"role": "system", "content": self.prompt.get("decision_format", "")}, # Use .get
            {"role": "system", "content": self.prompt.get("closing_reminder", "")}, # Use .get
        ]

        try:
            # Use the internal _ActionSelectionLLMResponse model for the instructor call
            llm_response_internal: _ActionSelectionLLMResponse = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=_ActionSelectionLLMResponse, # Use internal model
                messages=messages,
                max_tokens=1500
            )

            # Manually construct the final ActionSelectionPDMAResult
            # and parse action_parameters
            parsed_action_params: Union[BaseModel, Dict[str, Any]]
            selected_action = llm_response_internal.selected_handler_action
            raw_params = llm_response_internal.action_parameters

            ParamModel = ACTION_PARAM_MODELS.get(selected_action)
            
            if ParamModel:
                try:
                    if isinstance(raw_params, dict):
                        # Special handling for DEFER if params are empty, provide defaults
                        if selected_action == HandlerActionType.DEFER and not raw_params:
                            logger.warning(
                                f"LLM chose DEFER with empty parameters for thought {original_thought.thought_id}. Using default DeferParams."
                            )
                            parsed_action_params = DeferParams(
                                reason="LLM chose to defer without providing specific parameters.",
                                target_wa_ual=DEFAULT_WA,
                                deferral_package_content={
                                    "original_thought_content": original_thought.content,
                                    "llm_rationale": llm_response_internal.action_selection_rationale,
                                },
                            )
                        elif (
                            selected_action == HandlerActionType.SPEAK
                            and "message_content" in raw_params
                            and "content" not in raw_params
                        ):
                            logger.warning(
                                f"Remapping 'message_content' to 'content' for SPEAK action for thought {original_thought.thought_id}."
                            )
                            raw_params["content"] = raw_params.pop("message_content")
                            parsed_action_params = ParamModel(**raw_params)
                        else:
                            parsed_action_params = ParamModel(**raw_params)
                    else:
                        logger.error(
                            f"action_parameters from LLM was not a dict for {selected_action}: {raw_params}. Attempting to use as is if it's already a BaseModel."
                        )
                        if isinstance(raw_params, BaseModel):
                            parsed_action_params = raw_params  # Assume it's already the correct model type
                        else:
                            parsed_action_params = raw_params  # Keep as is, might cause issues downstream if not a dict/model
                except ValidationError as ve:
                    logger.error(
                        f"Parameter validation failed for {selected_action} on thought {original_thought.thought_id}: {ve}"
                    )
                    fallback_params = PonderParams(
                        key_questions=[
                            f"Action parameters for {selected_action.value} failed validation: {ve.errors()}"
                        ]
                    )
                    raw_llm_response_str = (
                        str(llm_response_internal._raw_response)
                        if hasattr(llm_response_internal, "_raw_response")
                        else None
                    )
                    return ActionSelectionPDMAResult(
                        schema_version=llm_response_internal.schema_version,
                        context_summary_for_action_selection=llm_response_internal.context_summary_for_action_selection,
                        action_alignment_check=llm_response_internal.action_alignment_check,
                        action_conflicts=llm_response_internal.action_conflicts,
                        action_resolution=llm_response_internal.action_resolution,
                        selected_handler_action=HandlerActionType.PONDER,
                        action_parameters=fallback_params,
                        action_selection_rationale=
                        f"Fallback to PONDER due to parameter validation failure for {selected_action.value}",
                        monitoring_for_selected_action="Review parameter generation logic.",
                        confidence_score=llm_response_internal.confidence_score,
                        raw_llm_response=raw_llm_response_str,
                    )
                except Exception as e_parse:
                    logger.error(
                        f"Failed to parse action_parameters for {selected_action}: {e_parse}. Parameters: {raw_params}"
                    )
                    parsed_action_params = raw_params  # Fallback: keep as raw if parsing fails
            else:
                logger.warning(f"No ParamModel found for {selected_action} to parse parameters: {raw_params}")
                parsed_action_params = raw_params # Fallback: keep as raw

            # Get raw response if available (instructor might attach it)
            raw_llm_response_str = None
            if hasattr(llm_response_internal, '_raw_response'): # Check the internal response object
                 raw_llm_response_str = str(llm_response_internal._raw_response)


            final_action_eval = ActionSelectionPDMAResult(
                schema_version=llm_response_internal.schema_version,
                context_summary_for_action_selection=llm_response_internal.context_summary_for_action_selection,
                action_alignment_check=llm_response_internal.action_alignment_check,
                action_conflicts=llm_response_internal.action_conflicts,
                action_resolution=llm_response_internal.action_resolution,
                selected_handler_action=llm_response_internal.selected_handler_action,
                action_parameters=parsed_action_params, # Use the parsed or original dict
                action_selection_rationale=llm_response_internal.action_selection_rationale,
                monitoring_for_selected_action=llm_response_internal.monitoring_for_selected_action,
                confidence_score=llm_response_internal.confidence_score,
                raw_llm_response=raw_llm_response_str # Populate from the internal response
            )

            logger.info(f"ActionSelectionPDMA (instructor) evaluation successful for thought ID {original_thought.thought_id}: Chose {final_action_eval.selected_handler_action.value}")
            logger.debug(f"ActionSelectionPDMA (instructor) action_parameters: {final_action_eval.action_parameters}")
            return final_action_eval

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"ActionSelectionPDMA (instructor) InstructorRetryException for thought {original_thought.thought_id}: {error_detail}", exc_info=True)
            # Fallback to PONDER with reason
            fallback_params = PonderParams(key_questions=[f"System error during action selection: {error_detail}"])
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Error: LLM/Instructor validation error during action selection.",
                action_alignment_check={"error": f"InstructorRetryException: {error_detail}"},
                selected_handler_action=HandlerActionType.PONDER, 
                action_parameters=fallback_params,
                action_selection_rationale=f"Fallback due to InstructorRetryException: {error_detail}",
                monitoring_for_selected_action="Monitor system logs for error resolution.",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e:
            logger.error(f"ActionSelectionPDMA (instructor) evaluation failed for thought ID {original_thought.thought_id}: {e}", exc_info=True)
            fallback_params = PonderParams(key_questions=[f"System error during action selection: {str(e)}"])
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection=f"Error: General exception - {str(e)}",
                action_alignment_check={"error": f"General Exception: {str(e)}"},
                selected_handler_action=HandlerActionType.PONDER,
                action_parameters=fallback_params,
                action_selection_rationale=f"Fallback due to General Exception: {str(e)}",
                monitoring_for_selected_action="Monitor system logs for error resolution.",
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' (using instructor)>"


# --- Internal Model for Instructor Parsing (Workaround for Grammar Issues) ---
# Mirrors ActionSelectionPDMAResult but simplifies action_parameters to Dict
class _ActionSelectionLLMResponse(BaseModel):
    schema_version: CIRISSchemaVersion = Field(default=CIRISSchemaVersion.V1_0_BETA)
    context_summary_for_action_selection: str
    action_alignment_check: Dict[str, Any]
    action_conflicts: Optional[str] = None
    action_resolution: Optional[str] = None
    selected_handler_action: CoreHandlerActionType # Use aliased HandlerActionType
    action_parameters: Dict[str, Any] # Simplified to Dict for LLM call
    action_selection_rationale: str
    monitoring_for_selected_action: Union[Dict[str, Union[str, List[str]]], str] # Allow list of strings for KPIs
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    # raw_llm_response is not expected from the LLM directly in this internal model,
    # it will be populated from the raw API response later.

    class Config:
        populate_by_name = True

# --- Mapping from HandlerActionType to specific Param Model ---
ACTION_PARAM_MODELS: Dict[CoreHandlerActionType, type[BaseModel]] = {
    CoreHandlerActionType.OBSERVE: ObserveParams,
    CoreHandlerActionType.SPEAK: SpeakParams,
    CoreHandlerActionType.ACT: ActParams,
    CoreHandlerActionType.PONDER: PonderParams,
    CoreHandlerActionType.REJECT: RejectParams,
    CoreHandlerActionType.DEFER: DeferParams,
    CoreHandlerActionType.MEMORIZE: MemorizeParams,
    CoreHandlerActionType.REMEMBER: RememberParams,
    CoreHandlerActionType.FORGET: ForgetParams,
}
