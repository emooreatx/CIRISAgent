"""Refactored Action Selection PDMA - Modular and Clean."""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

import instructor

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.config_schemas_v1 import DEFAULT_OPENAI_MODEL_NAME
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.dma_interface import ActionSelectionDMAInterface
from ciris_engine.protocols.faculties import EpistemicFaculty
from ciris_engine.utils import COVENANT_TEXT
from ciris_engine.formatters import format_system_prompt_blocks, format_user_profiles, format_system_snapshot

from .base_dma import BaseDMA
from .action_selection import (
    ActionSelectionContextBuilder,
    ActionSelectionSpecialCases,
    ActionParameterProcessor,
    FacultyIntegration,
)

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = """{system_header}

{decision_format}

{closing_reminder}"""


class ActionSelectionPDMAEvaluator(BaseDMA, ActionSelectionDMAInterface):
    """
    Modular Action Selection PDMA Evaluator.
    
    Takes outputs from Ethical PDMA, CSDMA, and DSDMA and selects a concrete
    handler action using the Principled Decision-Making Algorithm.
    
    Features:
    - Modular component architecture
    - Faculty integration for enhanced evaluation
    - Recursive evaluation on guardrail failures
    - Special case handling (wakeup tasks, forced ponder, etc.)
    """

    PROMPT_FILE = Path(__file__).parent / "prompts" / "action_selection_pdma.yml"
    
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
        """Initialize ActionSelectionPDMAEvaluator."""
        super().__init__(
            service_registry=service_registry,
            model_name=model_name,
            max_retries=max_retries,
            prompt_overrides=prompt_overrides,
            faculties=faculties,
            instructor_mode=instructor_mode,
            **kwargs
        )
        
        # Initialize components
        self.context_builder = ActionSelectionContextBuilder(self.prompts)
        self.parameter_processor = ActionParameterProcessor()
        self.faculty_integration = FacultyIntegration(faculties) if faculties else None

    async def evaluate(
        self, 
        triaged_inputs: Dict[str, Any],
        enable_recursive_evaluation: bool = False,
        **kwargs: Any
    ) -> ActionSelectionResult:
        """Evaluate triaged inputs and select optimal action."""
        
        original_thought: Thought = triaged_inputs["original_thought"]
        logger.debug(f"Evaluating action selection for thought ID {original_thought.thought_id}")

        # Handle special cases first
        special_result = await self._handle_special_cases(triaged_inputs)
        if special_result:
            return special_result

        # Perform main evaluation
        try:
            result = await self._perform_main_evaluation(triaged_inputs, enable_recursive_evaluation)
            
            # Add faculty metadata if applicable
            if self.faculty_integration and triaged_inputs.get("faculty_enhanced"):
                result = self.faculty_integration.add_faculty_metadata_to_result(
                    result, 
                    faculty_enhanced=True,
                    recursive_evaluation=triaged_inputs.get("recursive_evaluation", False)
                )
            
            logger.info(f"Action selection successful for thought {original_thought.thought_id}: {result.selected_action.value}")
            return result
            
        except Exception as e:
            logger.error(f"Action selection failed for thought {original_thought.thought_id}: {e}", exc_info=True)
            return self._create_fallback_result(str(e))

    async def recursive_evaluate_with_faculties(
        self,
        triaged_inputs: Dict[str, Any],
        guardrail_failure_context: Dict[str, Any]
    ) -> ActionSelectionResult:
        """Perform recursive evaluation using epistemic faculties."""
        
        if not self.faculty_integration:
            logger.warning("Recursive evaluation requested but no faculties available. Falling back to regular evaluation.")
            return await self.evaluate(triaged_inputs, enable_recursive_evaluation=False)
        
        original_thought: Thought = triaged_inputs["original_thought"]
        logger.info(f"Starting recursive evaluation with faculties for thought {original_thought.thought_id}")
        
        # Enhance inputs with faculty evaluations
        enhanced_inputs = await self.faculty_integration.enhance_evaluation_with_faculties(
            original_thought=original_thought,
            triaged_inputs=triaged_inputs,
            guardrail_failure_context=guardrail_failure_context
        )
        enhanced_inputs["recursive_evaluation"] = True
        
        # Perform evaluation with enhanced inputs
        return await self.evaluate(enhanced_inputs, enable_recursive_evaluation=False)

    async def _handle_special_cases(self, triaged_inputs: Dict[str, Any]) -> Optional[ActionSelectionResult]:
        """Handle special cases that override normal evaluation."""
        
        # Check for forced ponder
        ponder_result = await ActionSelectionSpecialCases.handle_ponder_force(triaged_inputs)
        if ponder_result:
            return ponder_result
        
        # Check wakeup task SPEAK requirement
        wakeup_result = await ActionSelectionSpecialCases.handle_wakeup_task_speak_requirement(triaged_inputs)
        if wakeup_result:
            return wakeup_result
        
        return None

    async def _perform_main_evaluation(
        self, 
        triaged_inputs: Dict[str, Any],
        enable_recursive_evaluation: bool
    ) -> ActionSelectionResult:
        """Perform the main LLM-based evaluation."""
        
        # Get LLM service
        llm_service = await self.get_llm_service()
        if not llm_service:
            raise RuntimeError("LLM service unavailable for ActionSelectionPDMA")

        # Build evaluation context
        agent_profile = triaged_inputs.get("agent_profile")
        agent_name = getattr(agent_profile, "name", None) if agent_profile else None
        
        main_user_content = self.context_builder.build_main_user_content(
            triaged_inputs, agent_name
        )
        
        # Add faculty insights if available
        if triaged_inputs.get("faculty_evaluations") and self.faculty_integration:
            faculty_insights = self.faculty_integration.build_faculty_insights_string(
                triaged_inputs["faculty_evaluations"]
            )
            main_user_content += faculty_insights

        # Build system message
        system_message = self._build_system_message(triaged_inputs)
        
        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": COVENANT_TEXT},
            {"role": "system", "content": system_message},
            {"role": "user", "content": main_user_content},
        ]

        # Call LLM with instructor
        aclient = instructor.patch(
            llm_service.get_client().client, mode=self.instructor_mode
        )
        
        llm_response: ActionSelectionResult = await aclient.chat.completions.create(
            model=self.model_name,
            response_model=ActionSelectionResult,
            messages=messages,
            max_tokens=1500,
            max_retries=self.max_retries,
        )

        # Process and validate parameters
        final_result = self.parameter_processor.process_action_parameters(
            llm_response, triaged_inputs
        )

        # Log OBSERVE actions for debugging
        if final_result.selected_action == HandlerActionType.OBSERVE:
            logger.warning(f"OBSERVE ACTION: Successfully created for thought {triaged_inputs['original_thought'].thought_id}")
            logger.warning(f"OBSERVE PARAMS: {final_result.action_parameters}")
            logger.warning(f"OBSERVE RATIONALE: {final_result.rationale}")

        return final_result

    def _build_system_message(self, triaged_inputs: Dict[str, Any]) -> str:
        """Build the system message for LLM evaluation."""
        
        processing_context = triaged_inputs.get("processing_context")
        
        system_snapshot_block = ""
        user_profiles_block = ""
        identity_block = ""
        
        if processing_context:
            if isinstance(processing_context, dict):
                system_snapshot = processing_context.get("system_snapshot")
                if system_snapshot:
                    user_profiles_block = format_user_profiles(
                        system_snapshot.get("user_profiles")
                    )
                    system_snapshot_block = format_system_snapshot(system_snapshot)
                identity_block = processing_context.get("identity_context", "")
            else:
                # Handle ThoughtContext objects
                if hasattr(processing_context, "system_snapshot") and processing_context.system_snapshot:
                    user_profiles_block = format_user_profiles(
                        getattr(processing_context.system_snapshot, "user_profiles", None)
                    )
                    system_snapshot_block = format_system_snapshot(processing_context.system_snapshot)
                if hasattr(processing_context, "identity_context"):
                    identity_block = processing_context.identity_context or ""

        system_guidance = DEFAULT_TEMPLATE.format(
            system_header=self.prompts.get("system_header", ""),
            decision_format=self.prompts.get("decision_format", ""),
            closing_reminder=self.prompts.get("closing_reminder", ""),
        )

        return format_system_prompt_blocks(
            identity_block,
            "",
            system_snapshot_block,
            user_profiles_block,
            None,
            system_guidance,
        )

    def _create_fallback_result(self, error_message: str) -> ActionSelectionResult:
        """Create a fallback result for error cases."""
        
        fallback_params = PonderParams(
            questions=[f"System error during action selection: {error_message}"]
        )
        
        return ActionSelectionResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters=fallback_params,
            rationale=f"Fallback due to error: {error_message}",
            raw_llm_response=f"Error: {error_message}",
        )

    def __repr__(self) -> str:
        faculty_count = len(self.faculties) if self.faculties else 0
        return f"<ActionSelectionPDMAEvaluator model='{self.model_name}' faculties={faculty_count}>"