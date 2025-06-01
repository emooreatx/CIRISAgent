from typing import Dict, Any, Optional, List, Union
import logging

import instructor

from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
)
from ciris_engine.schemas.dma_results_v1 import (
    ActionSelectionResult,
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
)
from ciris_engine.schemas.action_params_v1 import (
    ObserveParams,
    SpeakParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RecallParams,
    ForgetParams,
)
from ciris_engine.schemas.action_params_v1 import ToolParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, SchemaVersion
from ciris_engine.schemas.config_schemas_v1 import DEFAULT_OPENAI_MODEL_NAME
from ciris_engine.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from instructor.exceptions import InstructorRetryException
from ciris_engine.utils import DEFAULT_WA, ENGINE_OVERVIEW_TEMPLATE
from ciris_engine.utils import COVENANT_TEXT
from ciris_engine.formatters import (
    format_system_snapshot,
    format_user_profiles,
    format_system_prompt_blocks,
)
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = """{system_header}

{decision_format}

{closing_reminder}"""

class ActionSelectionPDMAEvaluator(BaseDMA):
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
            "RECALL and FORGET exist but may be disabled. "
            "If ponder rounds exceed the limit the system auto‑defers."
        ),
        "decision_format": (
            "Return JSON with keys: context_summary_for_action_selection, action_alignment_check, "
            "action_conflicts, action_resolution, selected_action, action_parameters, "
            "action_selection_rationale, monitoring_for_selected_action."
        ),
        "closing_reminder": (
            "Recall CIRIS principles override personal preference."
        ),
        "action_parameter_schemas": (
            "Schemas for 'action_parameters' based on the selected_action:\n"
            "SPEAK: {\"content\": string, \"channel_id\"?: string}\n"
            "PONDER: {\"questions\": [string], \"focus_areas\"?: [string]}\n"
            "MEMORIZE: {\"key\": string, \"value\": any, \"scope\": string}\n"
            "Scope is either 'identity', 'environment', or 'local'. local is where you can store info about channels and users as nodes\n"
            "RECALL: {\"query\": string, \"scope\": string}\n"
            "FORGET: {\"key\": string, \"scope\": string, \"reason\": string}\n"
            "DEFER: {\"reason\": string, \"context\"?: object}\n"
            "Send to your Wise Authority (WA) for further processing. "
            "REJECT: {\"reason\": string, \"rejection_code\"?: string}\n"
            "Reject means ignore, so it is unactionable or it is nothing you need to worry about.\n"
            "TOOL: {\"name\": string, \"args\": object} - Available tools and their argument schemas:\n"
            "  - discord_delete_message: Delete a message\n"
            "    args: {\"channel_id\": integer, \"message_id\": integer}\n"
            "    Use when: Message violates rules, contains harmful content, or needs removal\n"
            "  - discord_timeout_user: Temporarily mute a user\n"
            "    args: {\"guild_id\": integer, \"user_id\": integer, \"duration_seconds\": integer, \"reason\"?: string}\n"
            "    Use when: User needs a cooling-off period (max 28 days = 2419200 seconds)\n"
            "  - discord_ban_user: Permanently ban a user from the server\n"
            "    args: {\"guild_id\": integer, \"user_id\": integer, \"reason\"?: string, \"delete_message_days\"?: integer (0-7)}\n"
            "    Use when: Severe or repeated violations requiring permanent removal\n"
            "  - discord_kick_user: Remove user from server (they can rejoin)\n"
            "    args: {\"guild_id\": integer, \"user_id\": integer, \"reason\"?: string}\n"
            "    Use when: User needs removal but may be allowed back later\n"
            "OBSERVE: {\"channel_id\"?: string, \"active\"?: boolean, \"context\"?: object}\n"
            "TASK_COMPLETE: {} (no parameters needed)"
        ),
        "tool_usage_guidance": (
            "\nTOOL USAGE GUIDELINES:\n"
            "- Always check if you have the necessary IDs before using a tool\n"
            "- guild_id can often be found in the task context\n"
            "- user_id and message_id should be in the message context\n"
            "- Start with less severe actions (timeout) before escalating\n"
            "- Always provide a clear reason for moderation actions\n"
            "- If IDs are missing, use OBSERVE with active=true to gather more context first\n"
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
            "If 'Ponder' is chosen (and not in final benchmark attempt under benchmark_mode, or if advisory allows), 'questions' MUST "
            "list 2-3 distinct, NEW questions to resolve the ambiguity, building upon or differing from any previous ponder_notes. For example, if the original thought was about \"murres\":\n"
            """    {{"questions": ["What are 'murres' in this specific fictional context?", "Are 'murres' animals, mythological beings, or something else entirely?", "What is the user's primary goal for this 'murres' narrative?"]}}"""
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
            "If 'Ponder' is chosen, 'questions' MUST list 2-3 critical, analytical questions that challenge assumptions, explore underlying principles, or seek deeper understanding of the ambiguous elements. "
            "For example, if the thought is 'Explain quantum entanglement for a layperson':\n"
            """    {{"questions": ["What is the current understanding of 'layperson' in this context - e.g., no science background, some high school physics?", "What specific aspect of quantum entanglement is most confusing or interesting to the user?", "Are there any analogies the user already understands that could be leveraged (e.g., correlated dice)?"]}}"""
        ),
        "student_mode_action_selection_rationale_csdma_guidance": (
            "If CSDMA flagged ambiguity, your rationale MUST explain how the chosen action (especially Ponder) helps in critically analyzing and understanding the ambiguous concept from a learner's perspective."
        ),
        # Added Teacher-specific guidance for OBSERVE
        "teacher_mode_action_params_observe_guidance": (
            "If 'Observe' is chosen by the Teacher profile to gather more context (e.g., about a user's message or current state of a discussion), 'perform_active_look' SHOULD generally be true to actively fetch recent information. "
            "Set 'sources' to relevant identifiers (e.g., channel IDs, user IDs if applicable). "
            "Provide a clear 'reason' for the observation. "
            "Example: {{\"sources\": [\"#relevant_channel_id\"], \"reason\": \"To understand the latest messages from the user before responding.\", \"perform_active_look\": true}}"
        ),
        "normal_mode_action_params_observe_guidance": (
            "If 'Observe' is chosen to gather more context (e.g., about a user's message or current state of a discussion), 'perform_active_look' SHOULD generally be true to actively fetch recent information. "
            "Set 'sources' to relevant identifiers (e.g., channel IDs, user IDs if applicable). "
            "Provide a clear 'reason' for the observation. "
            "Example: {{\"sources\": [\"#relevant_channel_id\"], \"reason\": \"To understand the latest messages from the user before responding.\", \"perform_active_look\": true}}"
        ),
        "normal_mode_final_ponder_advisory": (
            "\nIMPORTANT FINAL PONDER ROUND ADVISORY (Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_rounds}):\n"
            "You have Pondered multiple times. This is your final opportunity to provide a direct answer or a definitive deferral.\n"
            "Your primary goal now is to attempt a 'Speak' action if at all feasible, using the original thought and all previous ponder notes to construct a response.\n"
            "If, after careful consideration, you determine that a 'Speak' action is not possible due to unresolved critical ambiguities, then 'Defer to WA' is the appropriate choice.\n"
            "Avoid selecting 'Ponder' again, as it will automatically result in a DEFER by the system.\n"
            "'Reject Thought' should only be used if the original request is fundamentally unserviceable."
        ),
        "student_mode_final_ponder_advisory": (
            "\nCRITICAL FINAL ATTEMPT (Student Profile - Ponder Count for NEXT attempt would be {current_ponder_count_plus_1}/{max_rounds}):\n"
            "You have Pondered multiple times. This is your ABSOLUTE FINAL opportunity to provide a DIRECT ANSWER.\n"
            "You MUST select 'Speak' and provide your best direct answer based on all prior analysis and CSDMA flags. YOUR ANSWER MUST NOT BE A QUESTION.\n"
            "If you cannot formulate a direct, non-question answer, then 'Reject Thought' is your only other viable option. DO NOT PONDER AGAIN. DO NOT DEFER."
        )
    }

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: str = DEFAULT_OPENAI_MODEL_NAME,
        max_retries: int = 2,
        prompt_overrides: Optional[Dict[str, str]] = None,
        *,
        instructor_mode: instructor.Mode = instructor.Mode.JSON,
    ):
        """
        Initialize ActionSelectionPDMAEvaluator.
        Args:
            aclient: AsyncOpenAI client (will be patched with instructor).
            model_name: LLM model name.
            max_retries: Max retries for LLM calls.
            prompt_overrides: Optional prompt overrides dict.
            instructor_mode: instructor.Mode (must be passed as keyword argument).
        """
        super().__init__(
            service_registry=service_registry,
            model_name=model_name,
            max_retries=max_retries,
            instructor_mode=instructor_mode,
        )
        self.prompt = {**self.DEFAULT_PROMPT, **(prompt_overrides or {})}

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
        ethical_pdma_result: EthicalDMAResult = triaged_inputs['ethical_pdma_result']
        csdma_result: CSDMAResult = triaged_inputs['csdma_result']
        dsdma_result: Optional[DSDMAResult] = triaged_inputs.get('dsdma_result')
        current_ponder_count: int = triaged_inputs['current_ponder_count']
        max_rounds: int = triaged_inputs['max_rounds']
        agent_profile: Optional[Any] = triaged_inputs.get('agent_profile') # Get the profile if available

        agent_name_from_thought = None
        # Prefer agent name from the passed agent_profile object
        if agent_profile and hasattr(agent_profile, 'name'): # Check for 'name' attribute
             agent_name_from_thought = agent_profile.name
             logger.debug(f"Using agent name '{agent_name_from_thought}' from provided agent_profile object.")
        
        # Access processing_context from triaged_inputs
        processing_context_data = triaged_inputs.get('processing_context')
        if not agent_name_from_thought and processing_context_data and isinstance(processing_context_data, dict):
            # Fallback to environment_context within the thought if agent_profile not passed or no name
            environment_context = processing_context_data.get('environment_context') # Use processing_context_data
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
            HandlerActionType.REJECT, HandlerActionType.DEFER,
            HandlerActionType.MEMORIZE, HandlerActionType.RECALL,
            HandlerActionType.FORGET, HandlerActionType.OBSERVE,
            HandlerActionType.TOOL, HandlerActionType.TASK_COMPLETE
        ]
        permitted_actions: List[HandlerActionType] = triaged_inputs.get('permitted_actions', default_permitted_actions)

        if 'permitted_actions' not in triaged_inputs:
             logger.warning(f"ActionSelectionPDMA: 'permitted_actions' not found in triaged_inputs for thought {original_thought.thought_id}. Falling back to default: {[a.value for a in default_permitted_actions]}")
        elif not permitted_actions: # Handle case where it's provided but empty
             logger.warning(f"ActionSelectionPDMA: 'permitted_actions' in triaged_inputs is empty for thought {original_thought.thought_id}. Falling back to default.")
             permitted_actions = default_permitted_actions

        # Build action_options_str for prompt
        action_options_str = ', '.join([a.value for a in permitted_actions])

        # Get available tools if TOOL action is permitted
        available_tools_str = ""
        if HandlerActionType.TOOL in permitted_actions:
            try:
                from ciris_engine.action_handlers.tool_handler import ToolHandler
                tool_registry = ToolHandler._tool_registry
                if tool_registry and hasattr(tool_registry, '_tools'):
                    tool_names = list(tool_registry._tools.keys())
                    if tool_names:
                        available_tools_str = f"\nAvailable tools: {', '.join(tool_names)}"
            except Exception:
                pass  # Silently ignore if tool registry not available
        # Add tool usage guidance
        tool_usage_guidance = self.prompt.get("tool_usage_guidance", self.DEFAULT_PROMPT.get("tool_usage_guidance", ""))
        # ...existing code...

        # Construct ethical_summary carefully, accessing potential nested fields in alignment_check
        conflicts_str = "None"
        resolution_str = "None"
        if isinstance(ethical_pdma_result.alignment_check, dict):
            conflicts_str = str(ethical_pdma_result.alignment_check.get('conflicts', "None"))
            resolution_str = str(ethical_pdma_result.alignment_check.get('resolution', "None"))
        
        ethical_summary = f"Ethical PDMA Stance: {ethical_pdma_result.decision}. Key Conflicts: {conflicts_str}. Resolution: {resolution_str}."
        # Note: csdma_result.common_sense_plausibility_score was an old field name, schema uses plausibility_score
        csdma_summary = f"CSDMA Output: Plausibility {csdma_result.plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"
        
        dsdma_summary_str = "DSDMA did not apply or did not run for this thought."
        if dsdma_result:
            # Accessing dsdma_result.domain and dsdma_result.alignment_score as per schema
            dsdma_summary_str = f"DSDMA ({dsdma_result.domain}) Output: Score {dsdma_result.alignment_score:.2f}, Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. Reasoning: {dsdma_result.reasoning}"

        ponder_notes_str_for_prompt_if_any = ""
        notes_list = original_thought.ponder_notes if original_thought.ponder_notes else []

        if notes_list:
            ponder_notes_str_for_prompt_if_any = "\n\nIMPORTANT CONTEXT FROM PREVIOUS PONDERING ROUND(S):\n"
            ponder_notes_str_for_prompt_if_any += f"This thought has been pondered {current_ponder_count} time(s). PLEASE TRY AND ACT (SPEAK) NOW\n"
            ponder_notes_str_for_prompt_if_any += "The following key questions were previously identified:\n"
            for i, q_note in enumerate(notes_list):
                ponder_notes_str_for_prompt_if_any += f"{i+1}. {q_note}\n"
            ponder_notes_str_for_prompt_if_any += ("Please consider these questions and the original thought in your current evaluation. "
                                                 "If you choose to 'Ponder' again, ensure your new 'questions' are DIFFERENT "
                                                 "from the ones listed above and aim to address any REMAINING ambiguities or guide towards a solution.\n")
        elif current_ponder_count > 0:
             ponder_notes_str_for_prompt_if_any = f"\n\nThis thought has been pondered {current_ponder_count} time(s) previously. If choosing 'Ponder' again, formulate new, insightful questions.\n"

        final_ponder_advisory = ""
        is_final_attempt_round = current_ponder_count >= max_rounds - 1

        if is_final_attempt_round:
            final_ponder_advisory_template = self._get_profile_specific_prompt("final_ponder_advisory", agent_name_from_thought)
            try:
                final_ponder_advisory = final_ponder_advisory_template.format(
                    current_ponder_count_plus_1=current_ponder_count + 1,
                    max_rounds=max_rounds
                )
            except KeyError as e:
                logger.error(f"KeyError formatting final_ponder_advisory_template: {e}. Template: '{final_ponder_advisory_template}'")
                final_ponder_advisory = "\nIMPORTANT FINAL PONDER ROUND: Attempt to provide a terminal action."
        
        reject_thought_guidance = "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."
        
        action_alignment_csdma_guidance = self._get_profile_specific_prompt("csdma_ambiguity_guidance", agent_name_from_thought)
        action_alignment_example = self._get_profile_specific_prompt("csdma_ambiguity_alignment_example", agent_name_from_thought)
        action_parameters_speak_csdma_guidance = self._get_profile_specific_prompt("action_params_speak_csdma_guidance", agent_name_from_thought)
        action_parameters_ponder_guidance = self._get_profile_specific_prompt("action_params_ponder_guidance", agent_name_from_thought)
        # Get Observe guidance - will pick up teacher_mode if agent_name_from_thought is 'teacher'
        action_parameters_observe_guidance = self._get_profile_specific_prompt("action_params_observe_guidance", agent_name_from_thought)
        action_selection_rationale_csdma_guidance = self._get_profile_specific_prompt("action_selection_rationale_csdma_guidance", agent_name_from_thought)
        action_parameter_schemas = self.prompt.get("action_parameter_schemas", self.DEFAULT_PROMPT.get("action_parameter_schemas", ""))

        profile_specific_system_header_injection = ENGINE_OVERVIEW_TEMPLATE + "\n"

        startup_guidance = ""
        if original_thought.thought_type == "startup_meta":
            startup_guidance = (
                "\nCRITICAL STARTUP DIRECTIVE: When handling 'startup_meta' thoughts, "
                "select SPEAK to confirm status or PONDER only if additional internal checks are required. "
                "Avoid MEMORIZE, ACT, REJECT, or DEFER during startup."
            )

        # --- User Profile and System Snapshot Context Injection using Utilities ---
        user_profile_context_str = ""
        system_snapshot_context_str = "" # This will include general system snapshot details
        other_processing_context_str = ""

        # Use processing_context_data obtained from triaged_inputs
        if processing_context_data and isinstance(processing_context_data, dict):
            system_snapshot = processing_context_data.get("system_snapshot")
            if system_snapshot and isinstance(system_snapshot, dict):
                user_profiles_data = system_snapshot.get("user_profiles")
                user_profile_context_str = format_user_profiles(user_profiles_data)
                system_snapshot_context_str = format_system_snapshot(system_snapshot)
        
        # The format_system_snapshot_for_prompt already includes a section for "Original Thought Full Processing Context"
        # so we don't need to add it separately here if we pass original_thought.processing_context to it.

        # --- End User Profile and System Snapshot Context Injection ---

        # Using original_thought.content which is a string
        main_user_content_prompt = f"""
{profile_specific_system_header_injection}Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional.
Permitted Handler Actions: {action_options_str}{available_tools_str}
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
5.  'selected_action': The LLM should determine this based on the inputs and other PDMA steps from the list: {action_options_str}.
6.  'action_parameters': Parameters for the chosen action. This MUST be a JSON object strictly matching the schema for the selected_action.
    {action_parameters_speak_csdma_guidance}
    {action_parameters_ponder_guidance}
    Provide empty dict {{}} if no parameters for other actions.
    {action_parameters_observe_guidance}
7.  'rationale': Justify *why* this handler action is optimal. {action_selection_rationale_csdma_guidance}
8.  'monitoring_for_selected_action': Concrete monitoring plan for THIS chosen action (string or dict).

IMPORTANT: Your entire response MUST be a single JSON object.
The JSON object MUST have these top-level keys, all populated:
'context_summary_for_action_selection', 'action_alignment_check', 'action_conflicts',
'action_resolution', 'selected_action', 'action_parameters',
'rationale', 'monitoring_for_selected_action'.

Original Thought: "{original_thought.content}"
{ponder_notes_str_for_prompt_if_any}
{user_profile_context_str} 
{system_snapshot_context_str}

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
    ) -> ActionSelectionResult:
        original_thought: Thought = triaged_inputs['original_thought'] # For logging & post-processing
        processing_context_data = triaged_inputs.get('processing_context') # Define this at the start of the method

        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for ActionSelectionPDMA")

        aclient = instructor.patch(llm_service.get_client().client, mode=self.instructor_mode)

        # --- Special case for forcing PONDER ---
        # Check the original message content from the task context stored in the processing_context
        original_message_content = None
        # Use processing_context_data defined above
        if processing_context_data and isinstance(processing_context_data, dict) and \
           isinstance(processing_context_data.get("initial_task_context"), dict):
            original_message_content = processing_context_data["initial_task_context"].get("content")

        if original_message_content and original_message_content.strip().lower() == "ponder":
            logger.info(f"ActionSelectionPDMA: Detected 'ponder' keyword in original message for thought ID {original_thought.thought_id}. Forcing PONDER action.")
            ponder_params = PonderParams(questions=["Forced ponder: What are the key ambiguities?", "Forced ponder: How can this be clarified?"])
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=ponder_params.model_dump(mode='json'),
                rationale="Forced PONDER for testing ponder loop.",
                confidence=None,
                raw_llm_response=None
            )
        # --- End special case ---
        
        main_user_content = self._prepare_main_user_content(triaged_inputs)

        system_snapshot_block = ""
        user_profiles_block = ""
        # Use processing_context_data obtained from triaged_inputs
        if processing_context_data and isinstance(processing_context_data, dict) and \
           isinstance(processing_context_data.get("system_snapshot"), dict):
            system_snapshot = processing_context_data.get("system_snapshot")
            user_profiles_block = format_user_profiles(system_snapshot.get("user_profiles"))
            system_snapshot_block = format_system_snapshot(system_snapshot)

        system_guidance = DEFAULT_TEMPLATE.format(
            system_header=self.prompt.get("system_header", self.DEFAULT_PROMPT["system_header"]),
            decision_format=self.prompt.get("decision_format", self.DEFAULT_PROMPT["decision_format"]),
            closing_reminder=self.prompt.get("closing_reminder", self.DEFAULT_PROMPT["closing_reminder"]),
        )

        identity_block = ""
        # Use processing_context_data obtained from triaged_inputs
        if processing_context_data and isinstance(processing_context_data, dict):
            identity_block = processing_context_data.get("identity_context", "")

        system_message = format_system_prompt_blocks(
            identity_block,
            "",
            system_snapshot_block,
            user_profiles_block,
            None,
            system_guidance,
        )

        messages = [
            {"role": "system", "content": COVENANT_TEXT},
            {"role": "system", "content": system_message},
            {"role": "user", "content": main_user_content},
        ]

        try:
            # Use ActionSelectionResult as the response model for the instructor call
            llm_response_internal: ActionSelectionResult = await aclient.chat.completions.create(
                model=self.model_name,
                response_model=ActionSelectionResult,  # Use schema directly
                messages=messages,
                max_tokens=1500,
                max_retries=self.max_retries
            )

            # action_parameters may still need parsing to the correct type, but the schema is now consistent
            parsed_action_params = llm_response_internal.action_parameters
            if isinstance(parsed_action_params, dict):
                action_type = llm_response_internal.selected_action
                try:
                    if action_type == HandlerActionType.OBSERVE:
                        parsed_action_params = ObserveParams(**parsed_action_params)
                    elif action_type == HandlerActionType.SPEAK:
                        parsed_action_params = SpeakParams(**parsed_action_params)
                    elif action_type == HandlerActionType.TOOL:
                        parsed_action_params = ToolParams(**parsed_action_params)
                    elif action_type == HandlerActionType.PONDER:
                        parsed_action_params = PonderParams(**parsed_action_params)
                    elif action_type == HandlerActionType.REJECT:
                        parsed_action_params = RejectParams(**parsed_action_params)
                    elif action_type == HandlerActionType.DEFER:
                        parsed_action_params = DeferParams(**parsed_action_params)
                    elif action_type == HandlerActionType.MEMORIZE:
                        parsed_action_params = MemorizeParams(**parsed_action_params)
                    elif action_type == HandlerActionType.RECALL:
                        parsed_action_params = RecallParams(**parsed_action_params)
                    elif action_type == HandlerActionType.FORGET:
                        parsed_action_params = ForgetParams(**parsed_action_params)
                except ValidationError as ve:
                    logger.warning(f"Could not parse action_parameters dict into specific model for {action_type}: {ve}. Using raw dict.")
                    # fallback to dict
            # Convert to dict for ActionSelectionResult
            # (No longer needed: keep as Pydantic model internally)
            action_params_dict = parsed_action_params
            # --- Inject channel_id for SPEAK actions if available in context ---
            if (
                llm_response_internal.selected_action == HandlerActionType.SPEAK
                and hasattr(action_params_dict, 'channel_id')
            ):
                channel_id = None
                processing_context = triaged_inputs.get('processing_context')
                if processing_context:
                    if hasattr(processing_context, 'identity_context') and processing_context.identity_context:
                        if isinstance(processing_context.identity_context, str) and 'channel' in processing_context.identity_context:
                            import re
                            match = re.search(r"channel is (\S+)", processing_context.identity_context)
                            if match:
                                channel_id = match.group(1)
                    elif isinstance(processing_context, dict):
                        channel_id = (
                            (processing_context.get('identity_context', {}) or {}).get('channel_id')
                            or (processing_context.get('initial_task_context', {}) or {}).get('channel_id')
                            or processing_context.get('channel_id')
                        )
                if channel_id:
                    action_params_dict.channel_id = channel_id
            # --- End channel_id injection ---

            # Return a new ActionSelectionResult with possibly updated action_parameters
            final_action_eval = ActionSelectionResult(
                selected_action=llm_response_internal.selected_action,
                action_parameters=action_params_dict,
                rationale=llm_response_internal.rationale,
                confidence=getattr(llm_response_internal, 'confidence', None),
                raw_llm_response=getattr(llm_response_internal, 'raw_llm_response', None)
            )
            logger.info(f"ActionSelectionPDMA (instructor) evaluation successful for thought ID {original_thought.thought_id}: Chose {final_action_eval.selected_action.value}")
            logger.debug(f"ActionSelectionPDMA (instructor) action_parameters: {final_action_eval.action_parameters}")
            
            # CRITICAL DEBUG: Check for OBSERVE actions specifically
            if final_action_eval.selected_action == HandlerActionType.OBSERVE:
                logger.warning(f"OBSERVE ACTION DEBUG: Successfully created OBSERVE action for thought {original_thought.thought_id}")
                logger.warning(f"OBSERVE ACTION DEBUG: Parameters: {final_action_eval.action_parameters}")
                logger.warning(f"OBSERVE ACTION DEBUG: Rationale: {final_action_eval.rationale}")
            
            return final_action_eval

        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"ActionSelectionPDMA (instructor) InstructorRetryException for thought {original_thought.thought_id}: {error_detail}", exc_info=True)
            fallback_params = PonderParams(questions=[f"System error during action selection: {error_detail}"]) # Corrected questions to questions


            # Fallback should only populate fields of ActionSelectionResult.
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER, 
                action_parameters=fallback_params.model_dump(mode='json'),
                rationale=f"Fallback due to InstructorRetryException: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}"
            )
        except Exception as e:
            logger.error(f"ActionSelectionPDMA (instructor) evaluation failed for thought ID {original_thought.thought_id}: {e}", exc_info=True)
            fallback_params = PonderParams(questions=[f"System error during action selection: {str(e)}"]) # Corrected questions to questions

            # input_snapshot_for_decision logic removed as it's not part of ActionSelectionResult
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=fallback_params.model_dump(mode='json'),
                rationale=f"Fallback due to General Exception: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}"
            )

    def __repr__(self) -> str:
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' (using instructor)>"
