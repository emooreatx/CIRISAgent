# src/agents/discord_agent/ciris_discord_bot_alpha.py
import asyncio
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import re
from discord.ext import commands
import discord # type: ignore
from openai import AsyncOpenAI
import instructor
import collections
import sys
# sys.path.append('/home/emoore/CIRISAgent/src/ciris_engine/dma') # Removing this line

# Existing CIRIS Engine imports
from ciris_engine.core.data_schemas import (
    Task, Thought, ThoughtQueueItem, TaskStatus, ThoughtStatus, ThoughtType,
    HandlerActionType, ActionSelectionPDMAResult, ActionRequest
)
from ciris_engine.core.config import (
    SQLITE_DB_PATH,
    DEFAULT_OPENAI_MODEL_NAME,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MAX_RETRIES
)
from ciris_engine.core.thought_queue_manager import ThoughtQueueManager
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
# Direct imports for DMA evaluators
from ciris_engine.dma.pdma import EthicalPDMAEvaluator, EthicalPDMAResult
from ciris_engine.dma.csdma import CSDMAEvaluator, CSDMAResult
from ciris_engine.dma.dsdma_base import DSDMAResult
# from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAResult # Removing this line
# Note: BaseDSDMA and specific DSDMAs like BasicTeacherDSDMA are handled via profile loading,
# so direct imports for them are not strictly needed here for instantiation.
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.utils.profile_loader import load_profile # Added
from ciris_engine.agent_profile import AgentProfile # Added
# DSDMA classes like BasicTeacherDSDMA or StudentDSDMA will be loaded dynamically

# New imports for Discord integration
from .config import DiscordConfig # Relative import assuming it's in the same directory
from .action_handlers import (
    handle_discord_speak,
    handle_discord_deferral,
)

# Pydantic/Instructor exceptions
from instructor.exceptions import InstructorRetryException
from pydantic import ValidationError

# Global logger
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

def serialize_discord_message(message):
    """
    Safely serialize a Discord message to a JSON-compatible dictionary.
    
    Args:
        message: Discord Message object
        
    Returns:
        dict: JSON-serializable representation of the message
    """
    if not message:
        return None
        
    return {
        'id': str(message.id),
        'content': message.content,
        'author': {
            'id': str(message.author.id),
            'name': message.author.name,
            'discriminator': message.author.discriminator if hasattr(message.author, 'discriminator') else None,
        },
        'channel_id': str(message.channel.id),
        'channel_name': getattr(message.channel, 'name', 'DM'),
        'guild_id': str(message.guild.id) if message.guild else None,
        'timestamp': message.created_at.isoformat() if message.created_at else None,
    }

class CIRISDiscordEngineBot:
    """
    Combines CIRIS Engine processing with Discord bot functionality.
    """
    def __init__(self, profile_name: str = "teacher"): # Added profile_name argument
        self.profile_name_to_load = profile_name # Store the profile name
        self.discord_config = DiscordConfig()
        if not self.discord_config.validate(): # type: ignore
            logger.critical("Discord configuration validation failed. Exiting.")
            raise ValueError("Invalid Discord Configuration")

        # Initialize Discord client
        intents = discord.Intents.default() # Using default intents
        intents.messages = True
        intents.message_content = True # Ensure this is enabled in your bot's settings
        intents.guilds = True
        self.client = discord.Client(intents=intents)

        # Initialize CIRIS Engine components
        self.thought_manager: Optional[ThoughtQueueManager] = None
        self.coordinator: Optional[WorkflowCoordinator] = None
        self.configured_aclient: Optional[instructor.Instructor] = None
        self.profile: Optional[AgentProfile] = None # Store the loaded profile
        self.current_round_queue: collections.deque[ThoughtQueueItem] = collections.deque()
        
        self._setup_ciris_engine_components()
        self._register_discord_events()

    def _setup_ciris_engine_components(self):
        """Initializes all CIRIS engine components."""
        logger.info("Setting up CIRIS Engine components...")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        openai_api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1") # Get base_url
        model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

        if not openai_api_key:
            logger.critical("OPENAI_API_KEY environment variable not set. CIRIS Engine cannot start.")
            raise ValueError("OPENAI_API_KEY not set.")

        # First, create and configure the AsyncOpenAI client
        raw_openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
            max_retries=DEFAULT_OPENAI_MAX_RETRIES
        )
        # Then, patch this specific, configured OpenAI client, setting the default mode to JSON
        self.configured_aclient = instructor.patch(raw_openai_client, mode=instructor.Mode.JSON)
        
        # The base_url of the patched client should be the same as raw_openai_client.base_url
        logger.info(f"Instructor-patched AsyncOpenAI client created for Discord bot (Mode: JSON). API Base: {self.configured_aclient.base_url}, Model: {model_name}, Timeout: {DEFAULT_OPENAI_TIMEOUT_SECONDS}s, Max Retries: {DEFAULT_OPENAI_MAX_RETRIES}.")

        db_path_for_run = SQLITE_DB_PATH
        self.thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
        logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")

        if not self.configured_aclient: # Should not happen if OPENAI_API_KEY is set
            logger.critical("AsyncOpenAI client not configured. Cannot initialize DMAs.")
            raise ValueError("AsyncOpenAI client not configured.")

        ethical_pdma = EthicalPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        csdma = CSDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        
        # --- Load Agent Profile for Discord Bot ---
        # Load the profile specified by profile_name_to_load
        profile_path = f"ciris_profiles/{self.profile_name_to_load}.yaml"
        try:
            self.profile = load_profile(profile_path) # Assign to self.profile
            logger.info(f"Discord Bot: Successfully loaded agent profile: {self.profile.name} (from {self.profile_name_to_load}.yaml) from {profile_path}")
        except Exception as e:
            logger.critical(f"Discord Bot: Failed to load agent profile '{self.profile_name_to_load}' from {profile_path}: {e}", exc_info=True)
            raise ValueError(f"Discord Bot ProfileLoadError for '{self.profile_name_to_load}': {e}") from e

        if not self.profile: # Should be caught by above, but as a safeguard
            logger.critical(f"Profile {self.profile_name_to_load} not loaded after load_profile call.")
            raise ValueError("Profile object is None after loading attempt.")

        # Instantiate DSDMA using the profile
        try:
            dsdma_instance = self.profile.dsdma_cls( # Use self.profile
                aclient=self.configured_aclient,
                model_name=model_name, 
                **self.profile.dsdma_kwargs 
            )
            dsdma_evaluators = {self.profile.name: dsdma_instance} # Use self.profile
            logger.info(f"Discord Bot: DSDMA Evaluator '{self.profile.name}' of type {self.profile.dsdma_cls.__name__} initialized using profile.")
        except Exception as e:
            logger.critical(f"Discord Bot: Failed to instantiate DSDMA from profile {self.profile.name}: {e}", exc_info=True)
            raise ValueError(f"Discord Bot DSDMAInstantiationError: {e}") from e

        # Update ActionSelectionPDMAEvaluator instantiation
        try:
            action_selection_pdma = ActionSelectionPDMAEvaluator(
                aclient=self.configured_aclient, 
                model_name=model_name,
                prompt_overrides=self.profile.action_prompt_overrides # Use self.profile
            )
        except Exception as e:
            logger.critical(f"Failed to instantiate ActionSelectionPDMAEvaluator: {e}", exc_info=True)
            raise

        guardrails = EthicalGuardrails(aclient=self.configured_aclient, model_name=model_name)
        logger.info("Discord Bot: DMA Evaluators and Guardrails initialized with profile.")

        self.coordinator = WorkflowCoordinator(
            llm_client=None, 
            ethical_pdma_evaluator=ethical_pdma,
            csdma_evaluator=csdma,
            dsdma_evaluators=dsdma_evaluators,
            action_selection_pdma_evaluator=action_selection_pdma,
            ethical_guardrails=guardrails,
            thought_queue_manager=self.thought_manager
        )
        logger.info("WorkflowCoordinator and all DMAs/Guardrails initialized.")

    def _register_discord_events(self):
        """Registers event handlers for the Discord client."""
        import re
        import os
        import asyncio
        from discord.ext import commands

        DEFERRAL_CH = int(os.getenv("DEFERRAL_CHANNEL", "0"))    # same env var, default to 0 if not set

        @self.client.event
        async def on_ready():
            if not self.client.user:
                logger.error("Discord client user not found on_ready.")
                return
            logger.info(f'Logged in as {self.client.user.name} ({self.client.user.id})')
            if hasattr(self.discord_config, 'log_config') and callable(self.discord_config.log_config):
                self.discord_config.log_config() 
            
            self.client.loop.create_task(self.continuous_thought_processing_loop())

        @self.client.event
        async def on_message(message: discord.Message):
            # ignore ourselves
            if message.author.bot:
                return

            # --- Check if the message should be processed ---
            if not self._should_process_discord_message(message):
                return

            # --- Handle deferral channel messages ---
            if message.channel.id == DEFERRAL_CH:
                # try to locate a PDMA trace‑ID in the root msg this WA reply refers to
                root = (message.reference.resolved
                        if message.reference and message.reference.resolved
                        else message)
                m = re.search(r"`([0-9a-f-]{36})`", root.content)
                if not m:
                    return                  # not a deferral thread

                pdma_id = m.group(1)
                wa_text = message.content.strip()

                # hand it back to the engine
                await self.integrate_wa_response(pdma_id, wa_text)

                # (optional) acknowledge back to WA
                await message.add_reaction("✅")
                return

            # --- Process regular messages ---
            # Serialize the Discord message
            serialized_message = serialize_discord_message(message)

            # Create a Task object
            new_task = Task(
                task_id=str(message.id),  # Use message ID as task ID
                description=message.content,
                priority=2,  # Default priority
                status=TaskStatus(status="active"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                due_date=None,
                context={"discord_message": serialized_message, "environment": f"discord_{self.profile_name_to_load}_bot"},
                parent_goal_id=None
            )
            # Create a Task object
            new_task = Task(
                task_id=str(message.id),  # Use message ID as task ID
                description=message.content,
                priority=2,  # Default priority
                status=TaskStatus(status="active"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                due_date=None,
                context={"discord_message": serialized_message, "environment": f"discord_{self.profile_name_to_load}_bot"},
                parent_goal_id=None
            )
            task_id = self.thought_manager.add_task(new_task)
            logger.info(f"Added task ID {task_id} to database.")

            # Create an ActionRequest object
            action_request = ActionRequest(
                user_id=str(message.author.id),
                user_prompt=message.content,
                channel_id=message.channel.id,
                serialized_context={"discord_message": serialized_message},
                environment=f"discord_{self.profile_name_to_load}_bot"
            )

            # Enqueue the ActionRequest
            # await self.thought_manager.enqueue(action_request) # No longer needed

    async def integrate_wa_response(self, pdma_id: str, wa_text: str):
        """
        Integrates the Wise Authority response back into the engine.
        """
        try:
            from ciris_engine.dma.pdma import PDMAStore # Import here to avoid circular dependencies
            from ciris_engine.core.data_schemas import ActionRequest # Import ActionRequest

            pdma = PDMAStore.load(pdma_id)          # you already persist PDMA json
            orig_req = pdma.original_request        # ActionRequest object

            merged = orig_req.model_copy()
            merged.user_prompt = (
                f"[Wise‑Authority guidance]\n{wa_text}\n\n"
                f"[Original context]\n{orig_req.user_prompt}"
            )

            await self.thought_manager.enqueue(merged)

            ch = await self.client.fetch_channel(orig_req.channel_id)
            await ch.send(
                f"Wise Authority has replied. Incorporating guidance now "
                f"and will respond shortly. (Trace ID {pdma_id})"
            )
        except Exception as e:
            logger.error(f"Error integrating WA response for PDMA ID {pdma_id}: {e}", exc_info=True)

    def _should_process_discord_message(self, message: discord.Message) -> bool:
        logger.debug(f"ENTERING _should_process_discord_message for MSG ID: {message.id}, Author: {message.author.name}, Channel: {message.channel.id}, Guild: {message.guild.id if message.guild else 'N/A'}")
        if not self.client.user: return False # Client not ready
        if message.author == self.client.user:
            return False
        if self.discord_config.server_id_int and message.guild and message.guild.id != self.discord_config.server_id_int:
            logger.debug(f"Message from {message.author.name} ignored: wrong server ID ({message.guild.id}).")
            return False
        is_dm = isinstance(message.channel, discord.DMChannel)
        logger.debug(f"PRE-CHANNEL-CHECK in _should_process_discord_message: is_dm={is_dm}, target_channels_set={self.discord_config.target_channels_set}, message_channel_id={message.channel.id}, mentioned_in_message={self.client.user.mentioned_in(message) if self.client.user else False}")
        if self.discord_config.target_channels_set:
            if is_dm: # This case should ideally not be hit if DMs are broadly ignored or handled by server_id check first.
                logger.debug(f"DM from {message.author.name} ignored: DMs not processed when target channels are set.")
                return False # Explicitly return if it's a DM and target channels are set
            elif message.channel.id not in self.discord_config.target_channels_set:
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} (ID: {message.channel.id}) ignored: not in target_channels_set {self.discord_config.target_channels_set}.")
                return False
            # If channel.id IS in target_channels_set, we proceed (implicitly, by not returning False)
        else: # This block executes if self.discord_config.target_channels_set is None or empty
            # If no specific channels are targeted, only process DMs or mentions in non-DM channels.
            if not is_dm and (not self.client.user or not self.client.user.mentioned_in(message)):
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} (ID: {message.channel.id}) ignored: no specific target channels configured AND bot not mentioned.")
            return False
        return True

    async def continuous_thought_processing_loop(self, max_script_cycles_overall: Optional[int] = None):
        self.current_round_queue: collections.deque[ThoughtQueueItem] = collections.deque()
        await self.client.wait_until_ready()
        logger.info("--- Starting CIRIS Engine Continuous Thought Processing Loop ---")
        
        script_cycle_count = 0
        while not self.client.is_closed():
            script_cycle_count += 1
            if max_script_cycles_overall and script_cycle_count > max_script_cycles_overall:
                logger.info(f"Reached max overall script cycles ({max_script_cycles_overall}). Stopping processing loop.")
                break
            
            if not self.thought_manager or not self.coordinator:
                logger.error("ThoughtManager or Coordinator not initialized. Waiting...")
                await asyncio.sleep(5)
                continue

            current_processing_round = script_cycle_count
            self.thought_manager.current_round_number = current_processing_round
            
            logger.debug(f"Processing Loop Cycle {script_cycle_count}: Populating queue for round {current_processing_round}.")
            self.thought_manager.populate_round_queue(round_number=current_processing_round, max_items=1)

            if not self.thought_manager.current_round_queue:
                await asyncio.sleep(self.discord_config.queue_check_interval_seconds if hasattr(self.discord_config, 'queue_check_interval_seconds') else 5)
                continue

            queued_thought_item = self.thought_manager.get_next_thought_from_queue()
            if not queued_thought_item:
                await asyncio.sleep(1)
                continue

            # queued_thought_item = self.thought_manager.get_next_thought_from_queue()
            # if not queued_thought_item:
            #     await asyncio.sleep(1)
            #     continue

            logger.info(f"Cycle {script_cycle_count}: Processing thought ID {queued_thought_item.thought_id} - Content: {str(queued_thought_item.content)[:60]}...")
            
            # Check if the thought is relevant to this Discord bot instance
            expected_environment = f"discord_{self.profile_name_to_load}_bot"
            thought_environment = None
            if queued_thought_item.initial_context:
                thought_environment = queued_thought_item.initial_context.get("environment")



            try:
                # --- Core Agent Processing ---
                # This is where the main CIRIS Engine processing happens.
                # The coordinator orchestrates the DMAs, Guardrails, and other components.
                # The result is an ActionRequest, which tells the agent what to do.
                action_selection_result: ActionSelectionPDMAResult = await self.coordinator.process_thought(queued_thought_item)

                if not action_selection_result:
                    logger.warning(f"No action request returned for thought {queued_thought_item.thought_id}. Skipping.")

                    continue

                logger.info(f"Action Request for thought {queued_thought_item.thought_id}: {action_selection_result.selected_handler_action}")

                # --- Action Handling ---
                # This section handles the actions requested by the coordinator.
                # It maps ActionTypes to specific handler functions.
                thought_successfully_processed = False
                
                original_message_input = None
                if queued_thought_item.initial_context: # Check if initial_context itself is None
                    original_message_input = queued_thought_item.initial_context.get("discord_message")

                # Check if the action requires original_message_input and if it's missing
                action_is_speak_or_defer = action_selection_result.selected_handler_action in [
                    HandlerActionType.SPEAK, HandlerActionType.DEFER_TO_WA
                ]

                if action_is_speak_or_defer and not original_message_input:
                    logger.error(f"CRITICAL: 'discord_message' not found in initial_context for thought {queued_thought_item.thought_id} (Action: {action_selection_result.selected_handler_action}). Context: {queued_thought_item.initial_context}. Marking thought as failed.")
                    self.thought_manager.update_thought_status(
                        thought_id=queued_thought_item.thought_id,
                        new_status=ThoughtStatus(status="failed", reason="Missing discord_message in initial_context")
                    )
                    thought_successfully_processed = True # Handled by failing
                elif action_selection_result.selected_handler_action == HandlerActionType.SPEAK:
                    # This implies original_message_input is available because the preceding 'if' was false (or action wasn't SPEAK/DEFER).
                    logger.info(f"Action parameters for SPEAK action: {json.dumps(action_selection_result.action_parameters)}")
                    await handle_discord_speak(
                        discord_client=self.client,
                        original_message_input=original_message_input, # Use safe variable
                        action_params=action_selection_result.action_parameters
                    )
                    thought_successfully_processed = True
                elif action_selection_result.selected_handler_action == HandlerActionType.DEFER_TO_WA:
                    # This implies original_message_input is available.
                    await handle_discord_deferral(
                        discord_client=self.client,
                        thought_manager=self.thought_manager, # Pass the thought_manager instance
                        current_thought_id=queued_thought_item.thought_id,
                        current_task_id=queued_thought_item.source_task_id,
                        original_message_input=original_message_input, # Use safe variable
                        action_params=action_selection_result.action_parameters,
                        deferral_channel_id_str=str(self.discord_config.deferral_channel_id)
                    )
                    thought_successfully_processed = True
                else:
                    # This handles:
                    # 1. Actions that are not SPEAK or DEFER.
                    # 2. Cases where SPEAK/DEFER was chosen, but original_message_input was missing (already handled by the first 'if' block).
                    #    In this scenario, thought_successfully_processed is already true, so this 'else' block won't be hit for that specific case.
                    # This correctly marks genuinely unsupported actions.
                    logger.warning(f"Unsupported action type: {action_selection_result.selected_handler_action}. Marking thought as completed.")
                    self.thought_manager.update_thought_status(
                        thought_id=queued_thought_item.thought_id,
                        new_status=ThoughtStatus(status="completed")
                    )
                    thought_successfully_processed = True

            except InstructorRetryException as retry_ex:
                logger.warning(f"Instructor Retry Exception during thought processing (ID {queued_thought_item.thought_id}): {retry_ex}. Marking as failed.")
                self.thought_manager.update_thought_status(
                    thought_id=queued_thought_item.thought_id,
                    new_status=ThoughtStatus(status="failed")
                )

                # Mark the parent task as completed
                if queued_thought_item.source_task_id:
                    try:
                        from ciris_engine.core.data_schemas import TaskStatus
                        self.thought_manager.update_task_status(queued_thought_item.source_task_id, TaskStatus(status="completed"))
                        logger.info(f"Updated task {queued_thought_item.source_task_id} status to COMPLETED.")
                    except Exception as e:
                        logger.error(f"Failed to update task {queued_thought_item.source_task_id} status to COMPLETED: {e}", exc_info=True)

                continue # Skip marking as completed; it's already in the queue.
            except ValidationError as validation_error:
                logger.error(f"Pydantic Validation Error during thought processing (ID {queued_thought_item.thought_id}): {validation_error}", exc_info=True)
                self.thought_manager.update_thought_status(
                    thought_id=queued_thought_item.thought_id,
                    new_status=ThoughtStatus(status="failed")
                )
            except Exception as e:
                logger.error(f"Unexpected error during thought processing (ID {queued_thought_item.thought_id}): {e}", exc_info=True)
                self.thought_manager.update_thought_status(
                    thought_id=queued_thought_item.thought_id,
                    new_status=ThoughtStatus(status="failed")
                )


        logger.info("--- CIRIS Engine Continuous Thought Processing Loop Ended ---")

    def run(self):
        """Starts the Discord bot."""
        discord_token = os.environ.get("DISCORD_BOT_TOKEN")
        if not discord_token:
            logger.critical("DISCORD_BOT_TOKEN environment variable not set. Cannot start Discord bot.")
            raise ValueError("DISCORD_BOT_TOKEN not set.")
        
        logger.info("Starting Discord bot...")
        self.client.run(discord_token)
