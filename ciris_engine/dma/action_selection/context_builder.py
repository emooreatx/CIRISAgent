"""Context building utilities for Action Selection PDMA."""

import logging
from typing import Dict, Any, Optional, List
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.formatters import format_user_profiles, format_system_snapshot
from ciris_engine.utils import ENGINE_OVERVIEW_TEMPLATE

logger = logging.getLogger(__name__)


class ActionSelectionContextBuilder:
    """Builds context for action selection evaluation."""
    
    def __init__(self, prompts: Dict[str, str], service_registry: Optional[Any] = None, multi_service_sink: Optional[Any] = None):
        self.prompts = prompts
        self.service_registry = service_registry
        self.multi_service_sink = multi_service_sink
        self._instruction_generator: Optional[Any] = None
    
    def build_main_user_content(
        self,
        triaged_inputs: Dict[str, Any],
        agent_profile_name: Optional[str] = None
    ) -> str:
        """Build the main user content for LLM evaluation."""
        
        # Extract core components
        original_thought = triaged_inputs["original_thought"]
        ethical_pdma_result = triaged_inputs["ethical_pdma_result"]
        csdma_result = triaged_inputs["csdma_result"]
        dsdma_result = triaged_inputs.get("dsdma_result")
        current_ponder_count = triaged_inputs["current_ponder_count"]
        max_rounds = triaged_inputs["max_rounds"]
        
        # Build context sections
        permitted_actions = self._get_permitted_actions(triaged_inputs)
        action_options_str = ", ".join([a.value for a in permitted_actions])
        
        available_tools_str = self._get_available_tools_str(permitted_actions)
        
        # Build DMA summaries
        ethical_summary = self._build_ethical_summary(ethical_pdma_result)
        csdma_summary = self._build_csdma_summary(csdma_result)
        dsdma_summary_str = self._build_dsdma_summary(dsdma_result)
        
        # Build ponder context
        ponder_notes_str = self._build_ponder_context(
            original_thought, current_ponder_count
        )
        
        # Build final attempt advisory
        final_ponder_advisory = self._build_final_attempt_advisory(
            current_ponder_count, max_rounds, agent_profile_name
        )
        
        # Build guidance sections
        guidance_sections = self._build_guidance_sections(agent_profile_name)
        
        # Build system context
        processing_context = triaged_inputs.get("processing_context")
        user_profile_context_str, system_snapshot_context_str = self._build_system_context(
            processing_context
        )
        
        # Build startup guidance
        startup_guidance = self._build_startup_guidance(original_thought)
        
        # Assemble final content
        main_user_content = f"""
{ENGINE_OVERVIEW_TEMPLATE}Your task is to determine the single most appropriate HANDLER ACTION based on an original thought and evaluations from three prior DMAs (Ethical PDMA, CSDMA, DSDMA).
You MUST execute the Principled Decision-Making Algorithm (PDMA) to choose this HANDLER ACTION and structure your response as a JSON object matching the provided schema.
All fields specified in the schema for your response are MANDATORY unless explicitly marked as optional.
Permitted Handler Actions: {action_options_str}{available_tools_str}
{startup_guidance}
{self._get_reject_thought_guidance()}
{final_ponder_advisory}
{guidance_sections['action_parameter_schemas']}
PDMA for Action Selection (all fields MANDATORY):
1.  'context_summary_for_action_selection': Summarize situation from original thought and DMAs. Crucially, note if CSDMA (see `csdma_summary`) flagged significant ambiguity impacting comprehension or safety. What is the core challenge, especially if such ambiguity exists?
2.  'action_alignment_check': MANDATORY field. This MUST be a JSON object (dictionary) where keys are
    plausible HANDLER ACTIONS (from {action_options_str}) and values are their evaluations
    against CIRIS principles & M-1. Use DMA summaries.
    {guidance_sections['action_alignment_csdma_guidance']}
    {guidance_sections['action_alignment_example']}
3.  'action_conflicts': Identify conflicts *between potential handler actions*. If none, "No conflicts identified." or null.
4.  'action_resolution': Resolve conflicts. If none, "Not applicable as no conflicts were identified." or null.
5.  'selected_action': The LLM should determine this based on the inputs and other PDMA steps from the list: {action_options_str}.
6.  'action_parameters': Parameters for the chosen action. This MUST be a JSON object strictly matching the schema for the selected_action.
    {guidance_sections['action_parameters_speak_csdma_guidance']}
    {guidance_sections['action_parameters_ponder_guidance']}
    Provide empty dict {{}} if no parameters for other actions.
    {guidance_sections['action_parameters_observe_guidance']}
7.  'rationale': Justify *why* this handler action is optimal. {guidance_sections['action_selection_rationale_csdma_guidance']}
8.  'monitoring_for_selected_action': Concrete monitoring plan for THIS chosen action (string or dict).

IMPORTANT: Your entire response MUST be a single JSON object.
The JSON object MUST have these top-level keys, all populated:
'context_summary_for_action_selection', 'action_alignment_check', 'action_conflicts',
'action_resolution', 'selected_action', 'action_parameters',
'rationale', 'monitoring_for_selected_action'.

Original Thought: "{original_thought.content}"
{ponder_notes_str}
{user_profile_context_str} 
{system_snapshot_context_str}

DMA Summaries to consider for your PDMA reasoning:
Ethical PDMA: {ethical_summary}
CSDMA: {csdma_summary}
DSDMA: {dsdma_summary_str}

Based on all the provided information and the PDMA framework for action selection, determine the appropriate handler action and structure your response as specified.
Adhere strictly to the schema for your JSON output.
"""
        return main_user_content.strip()
    
    def _get_permitted_actions(self, triaged_inputs: Dict[str, Any]) -> List[HandlerActionType]:
        """Get permitted actions from triaged inputs."""
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
        
        permitted_actions = triaged_inputs.get("permitted_actions", default_permitted_actions)
        
        if "permitted_actions" not in triaged_inputs:
            original_thought = triaged_inputs["original_thought"]
            logger.warning(
                f"ActionSelectionPDMA: 'permitted_actions' not found in triaged_inputs for thought {original_thought.thought_id}. Falling back to default."
            )
        elif not permitted_actions:
            original_thought = triaged_inputs["original_thought"]
            logger.warning(
                f"ActionSelectionPDMA: 'permitted_actions' in triaged_inputs is empty for thought {original_thought.thought_id}. Falling back to default."
            )
            permitted_actions = default_permitted_actions
        
        return permitted_actions
    
    def _get_available_tools_str(self, permitted_actions: List[HandlerActionType]) -> str:
        """Get available tools string if TOOL action is permitted."""
        available_tools_str = ""
        if HandlerActionType.TOOL in permitted_actions:
            try:
                from ciris_engine.action_handlers.tool_handler import ToolHandler
                
                tool_registry = ToolHandler._tool_registry
                if tool_registry and hasattr(tool_registry, "_tools"):
                    tool_names = list(tool_registry._tools.keys())
                    if tool_names:
                        available_tools_str = f"\nAvailable tools: {', '.join(tool_names)}"
            except Exception:
                pass
        
        return available_tools_str
    
    def _build_ethical_summary(self, ethical_pdma_result: EthicalDMAResult) -> str:
        """Build ethical DMA summary."""
        conflicts_str = "None"
        resolution_str = "None"
        if isinstance(ethical_pdma_result.alignment_check, dict):
            conflicts_str = str(
                ethical_pdma_result.alignment_check.get("conflicts", "None")
            )
            resolution_str = str(
                ethical_pdma_result.alignment_check.get("resolution", "None")
            )
        
        return f"Ethical PDMA Stance: {ethical_pdma_result.decision}. Key Conflicts: {conflicts_str}. Resolution: {resolution_str}."
    
    def _build_csdma_summary(self, csdma_result: CSDMAResult) -> str:
        """Build CSDMA summary."""
        return f"CSDMA Output: Plausibility {csdma_result.plausibility_score:.2f}, Flags: {', '.join(csdma_result.flags) if csdma_result.flags else 'None'}. Reasoning: {csdma_result.reasoning}"
    
    def _build_dsdma_summary(self, dsdma_result: Optional[DSDMAResult]) -> str:
        """Build DSDMA summary."""
        if not dsdma_result:
            return "DSDMA did not apply or did not run for this thought."
        
        return (
            f"DSDMA ({dsdma_result.domain}) Output: Score {dsdma_result.score:.2f}, "
            f"Recommended Domain Action: {dsdma_result.recommended_action or 'None'}, "
            f"Flags: {', '.join(dsdma_result.flags) if dsdma_result.flags else 'None'}. "
            f"Reasoning: {dsdma_result.reasoning}"
        )
    
    def _build_ponder_context(
        self, 
        original_thought: Thought, 
        current_ponder_count: int
    ) -> str:
        """Build ponder context string."""
        notes_list = original_thought.ponder_notes if original_thought.ponder_notes else []
        
        if notes_list:
            ponder_notes_str = (
                "\n\nIMPORTANT CONTEXT FROM PREVIOUS ACTION ROUNDS:\n"
            )
            ponder_notes_str += f"This thought has been pondered {current_ponder_count} time(s). PLEASE TRY AND ACT (SPEAK) NOW\n"
            ponder_notes_str += (
                "The following key questions were previously identified:\n"
            )
            for i, q_note in enumerate(notes_list):
                ponder_notes_str += f"{i+1}. {q_note}\n"
            ponder_notes_str += (
                "Please consider these questions and the original thought in your current evaluation. "
                "If you choose to 'Ponder' again, ensure your new 'questions' are DIFFERENT "
                "from the ones listed above and aim to address any REMAINING ambiguities or guide towards a solution.\n"
            )
            return ponder_notes_str
        elif current_ponder_count > 0:
            return f"\n\nThis thought has been pondered {current_ponder_count} time(s) previously. If choosing 'Ponder' again, formulate new, insightful questions.\n"
        
        return ""
    
    def _build_final_attempt_advisory(
        self,
        current_ponder_count: int,
        max_rounds: int,
        agent_profile_name: Optional[str]
    ) -> str:
        """Build final attempt advisory."""
        is_final_attempt_round = current_ponder_count >= max_rounds - 1
        
        if not is_final_attempt_round:
            return ""
        
        final_ponder_advisory_template = self._get_profile_specific_prompt(
            "final_ponder_advisory", agent_profile_name
        )
        try:
            return final_ponder_advisory_template.format(
                current_ponder_count_plus_1=current_ponder_count + 1,
                max_rounds=max_rounds,
            )
        except KeyError as e:
            logger.error(
                f"KeyError formatting final_ponder_advisory_template: {e}. Template: '{final_ponder_advisory_template}'"
            )
            return "\nIMPORTANT FINAL ATTEMPT: Attempt to provide a terminal action."
    
    def _build_guidance_sections(self, agent_profile_name: Optional[str]) -> Dict[str, str]:
        """Build all guidance sections."""
        return {
            'action_alignment_csdma_guidance': self._get_profile_specific_prompt(
                "csdma_ambiguity_guidance", agent_profile_name
            ),
            'action_alignment_example': self._get_profile_specific_prompt(
                "csdma_ambiguity_alignment_example", agent_profile_name
            ),
            'action_parameters_speak_csdma_guidance': self._get_profile_specific_prompt(
                "action_params_speak_csdma_guidance", agent_profile_name
            ),
            'action_parameters_ponder_guidance': self._get_profile_specific_prompt(
                "action_params_ponder_guidance", agent_profile_name
            ),
            'action_parameters_observe_guidance': self._get_profile_specific_prompt(
                "action_params_observe_guidance", agent_profile_name
            ),
            'action_selection_rationale_csdma_guidance': self._get_profile_specific_prompt(
                "action_selection_rationale_csdma_guidance", agent_profile_name
            ),
            'action_parameter_schemas': self._get_dynamic_action_schemas(permitted_actions),
        }
    
    def _build_system_context(self, processing_context_data: Any) -> tuple[str, str]:
        """Build user profile and system snapshot context."""
        user_profile_context_str = ""
        system_snapshot_context_str = ""
        
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
        
        return user_profile_context_str, system_snapshot_context_str
    
    def _build_startup_guidance(self, original_thought: Thought) -> str:
        """Build startup guidance if applicable."""
        if original_thought.thought_type == "startup_meta":
            return (
                "\nCRITICAL STARTUP DIRECTIVE: When handling 'startup_meta' thoughts, "
                "select SPEAK to confirm status or PONDER only if additional internal checks are required. "
                "Avoid MEMORIZE, ACT, REJECT, or DEFER during startup."
            )
        return ""
    
    def _get_reject_thought_guidance(self) -> str:
        """Get reject thought guidance."""
        return "\nNote on 'Reject Thought': Use this action sparingly, primarily if the original thought is nonsensical, impossible to act upon even with clarification, or fundamentally misaligned with the agent's purpose. Prefer 'Ponder' or 'Speak' for clarification if possible."
    
    def _get_profile_specific_prompt(
        self, base_key: str, agent_profile_name: Optional[str]
    ) -> str:
        """Get profile-specific prompt, falling back to base key."""
        if agent_profile_name:
            profile_key = f"{agent_profile_name.lower()}_mode_{base_key}"
            if profile_key in self.prompts:
                return self.prompts[profile_key]

        if base_key in self.prompts:
            return self.prompts[base_key]

        logger.warning(
            f"Prompt key for '{base_key}' (profile: {agent_profile_name}) not found. Using empty string."
        )
        return ""
    
    def _get_dynamic_action_schemas(self, permitted_actions: List[HandlerActionType]) -> str:
        """Get dynamically generated action schemas or fall back to static prompts."""
        try:
            # Lazy initialize the instruction generator
            if self._instruction_generator is None:
                from ciris_engine.dma.action_selection.action_instruction_generator import ActionInstructionGenerator
                self._instruction_generator = ActionInstructionGenerator(self.service_registry, self.multi_service_sink)
            
            # Generate dynamic instructions
            dynamic_schemas = self._instruction_generator.generate_action_instructions(permitted_actions)
            
            if dynamic_schemas:
                logger.debug("Using dynamically generated action schemas")
                return dynamic_schemas
            
        except Exception as e:
            logger.warning(f"Failed to generate dynamic action schemas: {e}")
        
        # Fall back to static schemas from prompts
        return self.prompts.get("action_parameter_schemas", "")