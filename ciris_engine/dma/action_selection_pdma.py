from typing import Dict, Any, Optional, List
import logging

import instructor

from pathlib import Path

import yaml

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
from ciris_engine.schemas.foundational_schemas_v1 import (
    HandlerActionType,
)
from ciris_engine.schemas.config_schemas_v1 import DEFAULT_OPENAI_MODEL_NAME
from ciris_engine.registries.base import ServiceRegistry
from .base_dma import BaseDMA
from ciris_engine.protocols.dma_interface import ActionSelectionDMAInterface
from ciris_engine.protocols.faculties import EpistemicFaculty
from instructor.exceptions import InstructorRetryException
from ciris_engine.utils import ENGINE_OVERVIEW_TEMPLATE
from ciris_engine.utils import COVENANT_TEXT
from ciris_engine.formatters import (
    format_system_snapshot,
    format_user_profiles,
    format_system_prompt_blocks,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = """{system_header}

{decision_format}

{closing_reminder}"""


class ActionSelectionPDMAEvaluator(BaseDMA, ActionSelectionDMAInterface):
    """
    The second PDMA in the sequence. It takes the original thought and the outputs
    of the Ethical PDMA, CSDMA, and DSDMA, then performs a PDMA process
    to select a single, concrete handler action, using `instructor`.
    """

    PROMPT_FILE = (
        Path(__file__).with_name("prompts").joinpath("action_selection_pdma.yml")
    )
    with open(PROMPT_FILE, "r") as f:
        DEFAULT_PROMPT: Dict[str, str] = yaml.safe_load(f) or {}

    def __init__(
        self,
        service_registry: ServiceRegistry,
        model_name: str = DEFAULT_OPENAI_MODEL_NAME,
        max_retries: int = 2,
        prompt_overrides: Optional[Dict[str, str]] = None,
        faculties: Optional[Dict[str, EpistemicFaculty]] = None,
        *,
        instructor_mode: instructor.Mode = instructor.Mode.JSON,
        **kwargs: Any
    ) -> None:
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
            prompt_overrides=prompt_overrides,
            faculties=faculties,
            instructor_mode=instructor_mode,
            **kwargs
        )
        self.prompt = {**self.DEFAULT_PROMPT, **(prompt_overrides or {})}

    def _get_profile_specific_prompt(
        self, base_key: str, agent_profile_name: Optional[str]
    ) -> str:
        if agent_profile_name:
            profile_key = f"{agent_profile_name.lower()}_mode_{base_key}"
            if profile_key in self.prompt:
                return self.prompt[profile_key]

        if base_key in self.prompt:
            return self.prompt[base_key]

        logger.warning(
            f"Prompt key for '{base_key}' (profile: {agent_profile_name}) not found. Using default from DEFAULT_PROMPT or empty string."
        )
        return self.DEFAULT_PROMPT.get(base_key, "")

    def _prepare_main_user_content(self, triaged_inputs: Dict[str, Any]) -> str:
        original_thought: Thought = triaged_inputs["original_thought"]
        ethical_pdma_result: EthicalDMAResult = triaged_inputs["ethical_pdma_result"]
        csdma_result: CSDMAResult = triaged_inputs["csdma_result"]
        dsdma_result: Optional[DSDMAResult] = triaged_inputs.get("dsdma_result")
        current_ponder_count: ThoughtStatus = triaged_inputs["current_ponder_count"]
        max_rounds: ThoughtStatus = triaged_inputs["max_rounds"]
        agent_profile: Optional[Any] = triaged_inputs.get("agent_profile")

        agent_name_from_thought = None
        if agent_profile and hasattr(agent_profile, "name"):
            agent_name_from_thought = agent_profile.name
            logger.debug(
                f"Using agent name '{agent_name_from_thought}' from provided agent_profile object."
            )

        processing_context_data = triaged_inputs.get("processing_context")
        if not agent_name_from_thought and processing_context_data:
            if (
                hasattr(processing_context_data, "environment_context")
                and processing_context_data.environment_context
            ):
                agent_name_from_thought = getattr(
                    processing_context_data.environment_context, "agent_name", None
                )
                if agent_name_from_thought:
                    logger.debug(
                        f"Using agent name '{agent_name_from_thought}' from thought's environment_context."
                    )

        if not agent_name_from_thought:
            logger.warning(
                f"Could not determine agent name for thought {original_thought.thought_id}. Profile-specific prompts might not apply."
            )

        default_permitted_actions = [
            HandlerActionType.SPEAK,
            HandlerActionType.PONDER,
            HandlerActionType.REJECT,
            HandlerActionType.DEFER,
            HandlerActionType.MEMORIZE,
            HandlerActionType.RECALL,
            HandlerActionType.FORGET,
            HandlerActionType.OBSERVE,
            HandlerActionType.TOOL,
            HandlerActionType.TASK_COMPLETE,
        ]
        permitted_actions: List[HandlerActionType] = triaged_inputs.get(
            "permitted_actions", default_permitted_actions
        )

        if "permitted_actions" not in triaged_inputs:
            logger.warning(
                f"ActionSelectionPDMA: 'permitted_actions' not found in triaged_inputs for thought {original_thought.thought_id}. Falling back to default: {[a.value for a in default_permitted_actions]}"
            )
        elif not permitted_actions:
            logger.warning(
                f"ActionSelectionPDMA: 'permitted_actions' in triaged_inputs is empty for thought {original_thought.thought_id}. Falling back to default."
            )
            permitted_actions = default_permitted_actions

        action_options_str = ", ".join([a.value for a in permitted_actions])

        available_tools_str = ""
        if HandlerActionType.TOOL in permitted_actions:
            try:
                from ciris_engine.action_handlers.tool_handler import ToolHandler

                tool_registry = ToolHandler._tool_registry
                if tool_registry and hasattr(tool_registry, "_tools"):
                    tool_names = list(tool_registry._tools.keys())
                    if tool_names:
                        available_tools_str = (
                            f"\nAvailable tools: {', '.join(tool_names)}"
                        )
            except Exception:
                pass

        conflicts_str = "None"
        resolution_str = "None"
        if isinstance(ethical_pdma_result.alignment_check, dict):
            conflicts_str = str(
                ethical_pdma_result.alignment_check.get("conflicts", "None")
            )
            resolution_str = str(
                ethical_pdma_result.alignment_check.get("resolution", "None")
            )

        ethical_summary = f"Ethical PDMA Stance: {ethical_pdma_result.decision}. Key Conflicts: {conflicts_str}. Resolution: {resolution_str}."
        csdma_summary = f"CSDMA Output: Plausibility {csdma_result.plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"

        dsdma_summary_str = "DSDMA did not apply or did not run for this thought."
        if dsdma_result:
            dsdma_summary_str = (
                f"DSDMA ({dsdma_result.domain}) Output: Score {dsdma_result.score:.2f}, "
                f"Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, "
                f"Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. "
                f"Reasoning: {dsdma_result.reasoning}"
            )

        ponder_notes_str_for_prompt_if_any = ""
        notes_list = (
            original_thought.ponder_notes if original_thought.ponder_notes else []
        )

        if notes_list:
            ponder_notes_str_for_prompt_if_any = (
                "\n\nIMPORTANT CONTEXT FROM PREVIOUS ACTION ROUNDS:\n"
            )
            ponder_notes_str_for_prompt_if_any += f"This thought has been pondered {current_ponder_count} time(s). PLEASE TRY AND ACT (SPEAK) NOW\n"
            ponder_notes_str_for_prompt_if_any += (
                "The following key questions were previously identified:\n"
            )
            for i, q_note in enumerate(notes_list):
                ponder_notes_str_for_prompt_if_any += f"{i+1}. {q_note}\n"
            ponder_notes_str_for_prompt_if_any += (
                "Please consider these questions and the original thought in your current evaluation. "
                "If you choose to 'Ponder' again, ensure your new 'questions' are DIFFERENT "
                "from the ones listed above and aim to address any REMAINING ambiguities or guide towards a solution.\n"
            )
        elif current_ponder_count > 0:
            ponder_notes_str_for_prompt_if_any = f"\n\nThis thought has been pondered {current_ponder_count} time(s) previously. If choosing 'Ponder' again, formulate new, insightful questions.\n"

        final_ponder_advisory = ""
        is_final_attempt_round = current_ponder_count >= max_rounds - 1

        if is_final_attempt_round:
            final_ponder_advisory_template = self._get_profile_specific_prompt(
                "final_ponder_advisory", agent_name_from_thought
            )
            try:
                final_ponder_advisory = final_ponder_advisory_template.format(
                    current_ponder_count_plus_1=current_ponder_count + 1,
                    max_rounds=max_rounds,
                )
            except KeyError as e:
                logger.error(
                    f"KeyError formatting final_ponder_advisory_template: {e}. Template: '{final_ponder_advisory_template}'"
                )
                final_ponder_advisory = (
                    "\nIMPORTANT FINAL ATTEMPT: Attempt to provide a terminal action."
                )

        reject_thought_guidance = "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."

        action_alignment_csdma_guidance = self._get_profile_specific_prompt(
            "csdma_ambiguity_guidance", agent_name_from_thought
        )
        action_alignment_example = self._get_profile_specific_prompt(
            "csdma_ambiguity_alignment_example", agent_name_from_thought
        )
        action_parameters_speak_csdma_guidance = self._get_profile_specific_prompt(
            "action_params_speak_csdma_guidance", agent_name_from_thought
        )
        action_parameters_ponder_guidance = self._get_profile_specific_prompt(
            "action_params_ponder_guidance", agent_name_from_thought
        )
        action_parameters_observe_guidance = self._get_profile_specific_prompt(
            "action_params_observe_guidance", agent_name_from_thought
        )
        action_selection_rationale_csdma_guidance = self._get_profile_specific_prompt(
            "action_selection_rationale_csdma_guidance", agent_name_from_thought
        )
        action_parameter_schemas = self.prompt.get(
            "action_parameter_schemas",
            self.DEFAULT_PROMPT.get("action_parameter_schemas", ""),
        )

        profile_specific_system_header_injection = ENGINE_OVERVIEW_TEMPLATE + "\n"

        startup_guidance = ""
        if original_thought.thought_type == "startup_meta":
            startup_guidance = (
                "\nCRITICAL STARTUP DIRECTIVE: When handling 'startup_meta' thoughts, "
                "select SPEAK to confirm status or PONDER only if additional internal checks are required. "
                "Avoid MEMORIZE, ACT, REJECT, or DEFER during startup."
            )

        user_profile_context_str = ""
        system_snapshot_context_str = ""
        other_processing_context_str = ""

        if processing_context_data:
            if (
                hasattr(processing_context_data, "system_snapshot")
                and processing_context_data.system_snapshot
            ):
                user_profiles_data = getattr(
                    processing_context_data.system_snapshot, "user_profiles", None
                )
                user_profile_context_str = format_user_profiles(user_profiles_data)
                system_snapshot_context_str = format_system_snapshot(
                    processing_context_data.system_snapshot
                )

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
        if (
            is_final_attempt_round
            and agent_name_from_thought
            and agent_name_from_thought.lower() == "student"
        ):
            logger.debug(
                f"STUDENT PROFILE - FINAL PONDER ATTEMPT - ActionSelectionPDMA main_user_content_prompt:\n{main_user_content_prompt}"
            )
        return main_user_content_prompt

    async def evaluate(
        self, 
        triaged_inputs: Dict[str, Any],
        enable_recursive_evaluation: bool = False,
        **kwargs: Any
    ) -> ActionSelectionResult:
        original_thought: Thought = triaged_inputs[
            "original_thought"
        ]  # For logging & post-processing
        processing_context_data = triaged_inputs.get(
            "processing_context"
        )  # Define this at the start of the method

        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for ActionSelectionPDMA")

        aclient = instructor.patch(
            llm_service.get_client().client, mode=self.instructor_mode
        )

        # --- Special case for forcing PONDER ---
        # Check the original message content from the task context stored in the processing_context
        original_message_content = None
        # Use processing_context_data defined above
        if (
            processing_context_data
            and hasattr(processing_context_data, "initial_task_context")
            and processing_context_data.initial_task_context
        ):
            original_message_content = getattr(
                processing_context_data.initial_task_context, "content", None
            )

        if (
            original_message_content
            and original_message_content.strip().lower() == "ponder"
        ):
            logger.info(
                f"ActionSelectionPDMA: Detected 'ponder' keyword in original message for thought ID {original_thought.thought_id}. Forcing PONDER action."
            )
            ponder_params = PonderParams(
                questions=[
                    "Forced ponder: What are the key ambiguities?",
                    "Forced ponder: How can this be clarified?",
                ]
            )
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=ponder_params,
                rationale="Forced PONDER for testing ponder loop.",
                confidence=None,
                raw_llm_response=None,
            )
        # --- End special case ---

        # --- Wakeup task SPEAK requirement ---
        # Check if this is a wakeup task and if TASK_COMPLETE is being attempted without prior SPEAK
        task_id = original_thought.source_task_id
        if task_id and self._is_wakeup_task(task_id):
            logger.debug(f"ActionSelectionPDMA: Processing wakeup task {task_id}")

            # If LLM selected TASK_COMPLETE, check if this task has had a successful SPEAK action
            if hasattr(triaged_inputs.get("llm_response_internal"), "selected_action"):
                selected_action = triaged_inputs[
                    "llm_response_internal"
                ].selected_action
                if selected_action == HandlerActionType.TASK_COMPLETE:
                    if not self._task_has_successful_speak(task_id):
                        logger.info(
                            f"ActionSelectionPDMA: Wakeup task {task_id} attempted TASK_COMPLETE without prior SPEAK. Converting to PONDER."
                        )
                        ponder_params = PonderParams(
                            questions=[
                                "This wakeup step requires a SPEAK action before task completion.",
                                "What affirmation should I speak for this wakeup ritual step?",
                            ]
                        )
                        return ActionSelectionResult(
                            selected_action=HandlerActionType.PONDER,
                            action_parameters=ponder_params,
                            rationale="Wakeup task requires SPEAK action before TASK_COMPLETE",
                            confidence=0.95,
                            raw_llm_response="Converted TASK_COMPLETE to PONDER due to missing SPEAK requirement",
                        )
        # --- End wakeup task logic ---

        main_user_content = self._prepare_main_user_content(triaged_inputs)

        system_snapshot_block = ""
        user_profiles_block = ""
        # Use processing_context_data obtained from triaged_inputs
        if (
            processing_context_data
            and isinstance(processing_context_data, dict)
            and isinstance(processing_context_data.get("system_snapshot"), dict)
        ):
            system_snapshot = processing_context_data.get("system_snapshot")
            user_profiles_block = format_user_profiles(
                system_snapshot.get("user_profiles")
            )
            system_snapshot_block = format_system_snapshot(system_snapshot)

        system_guidance = DEFAULT_TEMPLATE.format(
            system_header=self.prompt.get(
                "system_header", self.DEFAULT_PROMPT["system_header"]
            ),
            decision_format=self.prompt.get(
                "decision_format", self.DEFAULT_PROMPT["decision_format"]
            ),
            closing_reminder=self.prompt.get(
                "closing_reminder", self.DEFAULT_PROMPT["closing_reminder"]
            ),
        )
        
        # Add follow-up context for mock LLM when enabled
        original_thought: Thought = triaged_inputs["original_thought"]
        try:
            from ciris_engine.config.config_manager import get_config
            app_config = get_config()
            if getattr(app_config, 'mock_llm', False) and original_thought.parent_thought_id:
                system_guidance += "\n\n[MOCK_LLM_CONTEXT]: This is a follow-up thought (has parent_thought_id)."
        except Exception:
            # Silently continue if config access fails
            pass

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
            llm_response_internal: ActionSelectionResult = (
                await aclient.chat.completions.create(
                    model=self.model_name,
                    response_model=ActionSelectionResult,  # Use schema directly
                    messages=messages,
                    max_tokens=1500,
                    max_retries=self.max_retries,
                )
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
                    logger.warning(
                        f"Could not parse action_parameters dict into specific model for {action_type}: {ve}. Using raw dict."
                    )
                    # fallback to dict
            # Convert to dict for ActionSelectionResult
            # (No longer needed: keep as Pydantic model internally)
            action_params_dict = parsed_action_params
            # --- Inject channel_id for SPEAK actions if available in context ---
            if (
                llm_response_internal.selected_action == HandlerActionType.SPEAK
                and hasattr(action_params_dict, "channel_id")
            ):
                channel_id = None
                processing_context = triaged_inputs.get("processing_context")
                if processing_context:
                    # Handle ThoughtContext schema
                    if (
                        hasattr(processing_context, "identity_context")
                        and processing_context.identity_context
                    ):
                        if (
                            isinstance(processing_context.identity_context, str)
                            and "channel" in processing_context.identity_context
                        ):
                            import re

                            match = re.search(
                                r"channel is (\S+)", processing_context.identity_context
                            )
                            if match:
                                channel_id = match.group(1)

                    # Try initial_task_context field
                    if (
                        not channel_id
                        and hasattr(processing_context, "initial_task_context")
                        and processing_context.initial_task_context
                    ):
                        if isinstance(processing_context.initial_task_context, dict):
                            channel_id = processing_context.initial_task_context.get("channel_id")  # type: ignore[union-attr]

                    # Try system_snapshot.channel_id
                    if (
                        not channel_id
                        and hasattr(processing_context, "system_snapshot")
                        and processing_context.system_snapshot
                    ):
                        channel_id = getattr(
                            processing_context.system_snapshot, "channel_id", None
                        )

                    # Fallback to dict access for backward compatibility
                    elif isinstance(processing_context, dict):
                        channel_id = (
                            (processing_context.get("identity_context", {}) or {}).get(
                                "channel_id"
                            )
                            or (
                                processing_context.get("initial_task_context", {}) or {}
                            ).get("channel_id")
                            or processing_context.get("channel_id")
                        )
                if channel_id:
                    action_params_dict.channel_id = channel_id
            # --- End channel_id injection ---

            # Return a new ActionSelectionResult with possibly updated action_parameters
            final_action_eval = ActionSelectionResult(
                selected_action=llm_response_internal.selected_action,
                action_parameters=action_params_dict,
                rationale=llm_response_internal.rationale,
                confidence=getattr(llm_response_internal, "confidence", None),
                raw_llm_response=getattr(
                    llm_response_internal, "raw_llm_response", None
                ),
            )
            logger.info(
                f"ActionSelectionPDMA (instructor) evaluation successful for thought ID {original_thought.thought_id}: Chose {final_action_eval.selected_action.value}"
            )
            logger.debug(
                f"ActionSelectionPDMA (instructor) action_parameters: {final_action_eval.action_parameters}"
            )

            # CRITICAL DEBUG: Check for OBSERVE actions specifically
            if final_action_eval.selected_action == HandlerActionType.OBSERVE:
                logger.warning(
                    f"OBSERVE ACTION DEBUG: Successfully created OBSERVE action for thought {original_thought.thought_id}"
                )
                logger.warning(
                    f"OBSERVE ACTION DEBUG: Parameters: {final_action_eval.action_parameters}"
                )
                logger.warning(
                    f"OBSERVE ACTION DEBUG: Rationale: {final_action_eval.rationale}"
                )

            return final_action_eval

        except InstructorRetryException as e_instr:
            error_detail = (
                e_instr.errors() if hasattr(e_instr, "errors") else str(e_instr)
            )
            logger.error(
                f"ActionSelectionPDMA (instructor) InstructorRetryException for thought {original_thought.thought_id}: {error_detail}",
                exc_info=True,
            )
            fallback_params = PonderParams(
                questions=[f"System error during action selection: {error_detail}"]
            )  # Corrected questions to questions

            # Fallback should only populate fields of ActionSelectionResult.
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=fallback_params,
                rationale=f"Fallback due to InstructorRetryException: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}",
            )
        except Exception as e:
            logger.error(
                f"ActionSelectionPDMA (instructor) evaluation failed for thought ID {original_thought.thought_id}: {e}",
                exc_info=True,
            )
            fallback_params = PonderParams(
                questions=[f"System error during action selection: {str(e)}"]
            )  # Corrected questions to questions

            # input_snapshot_for_decision logic removed as it's not part of ActionSelectionResult
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=fallback_params,
                rationale=f"Fallback due to General Exception: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}",
            )
    
    async def recursive_evaluate_with_faculties(
        self,
        triaged_inputs: Dict[str, Any],
        guardrail_failure_context: Dict[str, Any]
    ) -> ActionSelectionResult:
        """Perform recursive evaluation using epistemic faculties.
        
        Called when guardrails fail and recursive evaluation is enabled.
        Uses faculties to provide additional insight before action selection.
        
        Args:
            triaged_inputs: Combined inputs from previous DMAs
            guardrail_failure_context: Context about the guardrail failure
            
        Returns:
            ActionSelectionResult with faculty-enhanced reasoning
        """
        original_thought: Thought = triaged_inputs["original_thought"]
        
        logger.info(f"Starting recursive evaluation with faculties for thought {original_thought.thought_id}")
        
        # Apply faculties to the problematic content
        faculty_results = {}
        if self.faculties:
            faculty_results = await self.apply_faculties(
                content=str(original_thought.content),
                context={
                    **guardrail_failure_context,
                    "evaluation_context": "recursive_guardrail_failure"
                }
            )
            logger.debug(f"Faculty evaluation results: {faculty_results}")
        
        # Enhance the user content with faculty insights
        faculty_insights_str = ""
        if faculty_results:
            faculty_insights_str = "\n\nEPISTEMIC FACULTY INSIGHTS:\n"
            for faculty_name, result in faculty_results.items():
                faculty_insights_str += f"- {faculty_name}: {result}\n"
            faculty_insights_str += "\nConsider these faculty evaluations in your decision-making process.\n"
        
        # Add faculty insights to triaged inputs
        enhanced_inputs = {
            **triaged_inputs,
            "faculty_evaluations": faculty_results,
            "guardrail_context": guardrail_failure_context,
            "recursive_evaluation": True
        }
        
        # Override the main user content preparation to include faculty insights
        original_prepare_method = self._prepare_main_user_content
        
        def enhanced_prepare_main_user_content(inputs: Dict[str, Any]) -> str:
            original_content = original_prepare_method(inputs)
            return original_content + faculty_insights_str
        
        # Temporarily replace the method
        self._prepare_main_user_content = enhanced_prepare_main_user_content
        
        try:
            # Perform enhanced evaluation with faculty insights
            result = await self.evaluate(enhanced_inputs, enable_recursive_evaluation=False)
            
            # Add metadata about recursive evaluation
            result.rationale += f"\n\nNote: This decision was made through recursive evaluation with epistemic faculties due to guardrail failure. Faculty insights were incorporated into the reasoning process."
            
            logger.info(f"Recursive evaluation completed for thought {original_thought.thought_id}: {result.selected_action.value}")
            return result
            
        finally:
            # Restore original method
            self._prepare_main_user_content = original_prepare_method

    def _is_wakeup_task(self, task_id: str) -> bool:
        """
        Check if a task is a wakeup task by verifying:
        1. It has a parent task with ID "WAKEUP_ROOT"
        2. It has step_type in context (secure database field)
        """
        try:
            from ciris_engine import persistence

            task = persistence.get_task_by_id(task_id)
            if not task:
                return False

            # Check if parent task is WAKEUP_ROOT (secure check)
            if task.parent_task_id == "WAKEUP_ROOT":
                return True

            # Also check if the task context has step_type (wakeup tasks have this)
            if task.context and task.context.get("step_type"):
                return True

            return False
        except Exception:
            return False

    def _task_has_successful_speak(self, task_id: str) -> bool:
        """
        Check if a task has had a successful SPEAK action by querying:
        1. All thoughts for this task
        2. Check if any thought has a final_action with SPEAK
        3. Verify the thought status is COMPLETED
        """
        try:
            from ciris_engine import persistence
            from ciris_engine.schemas.foundational_schemas_v1 import (
                ThoughtStatus,
                HandlerActionType,
            )

            thoughts = persistence.get_thoughts_by_task_id(task_id)
            if not thoughts:
                return False

            for thought in thoughts:
                # Check if thought is completed and has a SPEAK action
                if (
                    thought.status == ThoughtStatus.COMPLETED
                    and hasattr(thought, "final_action")
                    and thought.final_action
                    and hasattr(thought.final_action, "selected_action")
                    and thought.final_action.selected_action == HandlerActionType.SPEAK
                ):
                    return True

            return False
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' (using instructor)>"
