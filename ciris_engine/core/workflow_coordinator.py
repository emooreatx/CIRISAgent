import sys # Import sys for maxsize
import logging

logger = logging.getLogger(__name__)
import asyncio # New import
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING # Added TYPE_CHECKING
from pydantic import BaseModel # Added import

from .foundational_schemas import TaskStatus, ThoughtStatus, HandlerActionType
from .agent_core_schemas import EthicalPDMAResult, CSDMAResult, DSDMAResult, ActionSelectionPDMAResult, Thought, Task
from .agent_processing_queue import ProcessingQueueItem
from .config_schemas import AppConfig, WorkflowConfig # Import AppConfig and WorkflowConfig
from . import persistence # Import persistence module
from ciris_engine.services.llm_client import CIRISLLMClient # Assume this will have an async call_llm
from ciris_engine.core.dma_executor import (
    run_pdma,
    run_csdma,
    run_dsdma,
    run_action_selection_pdma,
)
from ciris_engine.core.config_schemas import DMA_RETRY_LIMIT
from ciris_engine.core.action_tracker import track_action
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils import DEFAULT_WA
from ciris_engine.utils import GraphQLContextProvider
from ciris_engine.utils.deferral_package_builder import build_deferral_package
from .thought_escalation import escalate_due_to_guardrail

if TYPE_CHECKING:
    from ciris_engine.dma.dsdma_base import BaseDSDMA # Import only for type checking
    from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
    from ciris_engine.utils import GraphQLContextProvider
    from ciris_engine.dma.pdma import EthicalPDMAEvaluator
    from ciris_engine.dma.csdma import CSDMAEvaluator
    from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator


class WorkflowCoordinator:
    """
    Orchestrates the flow of a thought through the various DMAs (with initial
    DMAs running concurrently), faculties (via guardrails), and guardrails
    to produce a final, vetted action.
    """

    def __init__(self,
                 llm_client: CIRISLLMClient, # This LLM client MUST support async operations
                 ethical_pdma_evaluator: 'EthicalPDMAEvaluator',
                 csdma_evaluator: 'CSDMAEvaluator',
                 action_selection_pdma_evaluator: 'ActionSelectionPDMAEvaluator',
                 ethical_guardrails: EthicalGuardrails,
                 app_config: AppConfig,
                 # thought_queue_manager: ThoughtQueueManager,
                 dsdma_evaluators: Optional[Dict[str, 'BaseDSDMA']] = None, # Use string literal for forward reference
                 memory_service: Optional['CIRISLocalGraph'] = None,
                 graphql_context_provider: Optional['GraphQLContextProvider'] = None,
                 # current_round_number: int = 0
                ):
        self.llm_client = llm_client
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma_evaluators = dsdma_evaluators if dsdma_evaluators else {}
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.memory_service = memory_service
        self.graphql_context_provider = graphql_context_provider or GraphQLContextProvider(
            memory_service=memory_service,
            enable_remote_graphql=app_config.enable_remote_graphql,
        )
        self.ethical_guardrails = ethical_guardrails
        self.app_config = app_config
        self.workflow_config = app_config.workflow
        self.max_ponder_rounds = self.workflow_config.max_ponder_rounds
        # self.thought_queue_manager = thought_queue_manager
        self.current_round_number = 0 # Initialize internally

    def advance_round(self):
        """Advances the internal round number, handling potential overflow."""
        if self.current_round_number >= sys.maxsize:
            logging.warning(f"Current round number {self.current_round_number} reached sys.maxsize. Resetting to 0.")
            self.current_round_number = 0
        else:
            self.current_round_number += 1
        logging.debug(f"Advanced to round {self.current_round_number}")

    async def process_thought(self, thought_item: ProcessingQueueItem, # Changed type to ProcessingQueueItem
                              current_platform_context: Optional[Dict[str, Any]] = None,
                              benchmark_mode: bool = False # Add benchmark_mode parameter
                              ) -> Optional[ActionSelectionPDMAResult]: # Return type can be None now
        """
        Processes a single thought item through the full DMA and guardrail pipeline.
        The initial Ethical PDMA, CSDMA, and DSDMA calls are made concurrently.
        """
        logging.info(f"WorkflowCoordinator: Async processing thought ID {thought_item.thought_id} - '{str(thought_item.content)[:50]}...'")
        
        # Fetch the full Thought object using the thought_id from ProcessingQueueItem
        thought_object: Optional[Thought] = persistence.get_thought_by_id(thought_item.thought_id)
        if not thought_object:
            logging.error(f"Critical: Could not retrieve Thought object for thought_id {thought_item.thought_id}. Aborting processing.")
            from .agent_core_schemas import DeferParams
            defer_reason = f"Failed to retrieve thought object for ID {thought_item.thought_id}"
            parent_task_obj = persistence.get_task_by_id(thought_item.source_task_id)
            deferral_package = build_deferral_package(
                thought=None,
                parent_task=parent_task_obj,
                ethical_pdma_result=None,
                csdma_result=None,
                dsdma_result=None,
                trigger_reason="THOUGHT_NOT_FOUND",
                extra={"error_details": defer_reason}
            )
            defer_params = DeferParams(
                reason=defer_reason,
                target_wa_ual=DEFAULT_WA,
                deferral_package_content=deferral_package
            )
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Critical error: Thought object not found.",
                action_alignment_check={"Error": "Thought object retrieval failed"},
                selected_handler_action=HandlerActionType.DEFER,
                action_parameters=defer_params,
                action_selection_rationale="System error: Cannot process thought without its core object.",
                monitoring_for_selected_action={"status": "Error: Thought object not found"},
            )


        # --- Populate System Context into thought_object.processing_context ---
        try:
            parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
            system_context = await self.build_context(parent_task_obj, thought_object)
            if thought_object.processing_context is None:
                thought_object.processing_context = {}
            thought_object.processing_context["system_snapshot"] = system_context
            logging.debug(
                f"Populated system_snapshot for thought {thought_object.thought_id}: {system_context}"
            )

        except Exception as e_ctx:
            logging.error(
                f"Error populating system context for thought {thought_object.thought_id}: {e_ctx}",
                exc_info=True,
            )
            if thought_object.processing_context is None:
                thought_object.processing_context = {}
            thought_object.processing_context["system_snapshot_error"] = str(e_ctx)


        current_platform_context = current_platform_context or thought_item.initial_context or {}

        # --- Stage 1: Initial DMAs (Concurrent Execution) ---
        initial_dma_tasks = []

        # 1. Ethical PDMA Task
        logging.debug(f"Scheduling Ethical PDMA for thought ID {thought_object.thought_id}") # Use thought_object
        initial_dma_tasks.append(
            run_pdma(self.ethical_pdma_evaluator, thought_object, retry_limit=DMA_RETRY_LIMIT)
        )

        # 2. CSDMA Task
        logging.debug(f"Scheduling CSDMA for thought ID {thought_object.thought_id}") # Use thought_object
        initial_dma_tasks.append(
            run_csdma(self.csdma_evaluator, thought_object, retry_limit=DMA_RETRY_LIMIT)
        )

        # 3. DSDMA Task (select and run if applicable)
        selected_dsdma_instance: Optional['BaseDSDMA'] = None
        active_profile_name_for_dsdma: Optional[str] = None
        # --- NEW LOGIC: Always use the active profile as the source of truth ---
        active_profile_for_dsdma = None
        if self.app_config.agent_profiles:
            # Use the profile associated with this WorkflowCoordinator (or default)
            # If the thought or context provides a profile, use it; else fallback to 'default'
            profile_key = None
            if hasattr(thought_object, 'profile_name') and thought_object.profile_name:
                profile_key = thought_object.profile_name.lower()
            elif 'default' in self.app_config.agent_profiles:
                profile_key = 'default'
            else:
                profile_key = next(iter(self.app_config.agent_profiles), None)
            if profile_key:
                active_profile_for_dsdma = self.app_config.agent_profiles.get(profile_key)
                active_profile_name_for_dsdma = profile_key
        # --- END NEW LOGIC ---

        if self.dsdma_evaluators and active_profile_name_for_dsdma:
            # Use the DSDMA instance for the active profile
            active_dsdma = self.dsdma_evaluators.get(active_profile_name_for_dsdma)
            if active_dsdma:
                logging.debug(
                    f"Scheduling DSDMA '{active_dsdma.domain_name}' (Profile: {active_profile_name_for_dsdma}) for thought ID {thought_object.thought_id}"
                )
                initial_dma_tasks.append(
                    run_dsdma(
                        active_dsdma,
                        thought_object,
                        current_platform_context,
                        retry_limit=DMA_RETRY_LIMIT,
                    )
                )
                selected_dsdma_instance = active_dsdma
            else:
                logging.critical(f"DSDMA evaluators present, but no DSDMA instance for active profile '{active_profile_name_for_dsdma}' for thought {thought_object.thought_id}. This is a critical error.")
                from .agent_core_schemas import DeferParams
                parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
                deferral_package = build_deferral_package(
                    thought=thought_object,
                    parent_task=parent_task_obj,
                    ethical_pdma_result=ethical_pdma_result,
                    csdma_result=csdma_result,
                    dsdma_result=None,
                    trigger_reason="NO_DSDMA_INSTANCE",
                    extra={"error": "No DSDMA instance for active profile"}
                )
                defer_params = DeferParams(
                    reason=f"Critical: No DSDMA instance for active profile '{active_profile_name_for_dsdma}' for thought {thought_object.thought_id}",
                    target_wa_ual=DEFAULT_WA,
                    deferral_package_content=deferral_package
                )
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection="Critical error: No DSDMA instance for active profile.",
                    action_alignment_check={"Error": "No DSDMA instance for active profile"},
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=defer_params,
                    action_selection_rationale="System error: No DSDMA instance for active profile.",
                    monitoring_for_selected_action={"status": "Critical: No DSDMA instance for active profile"},
                )
        else:
            logging.debug(f"No DSDMA evaluators configured or applicable for thought ID {thought_item.thought_id}, will pass None to ActionSelection.")
            async def no_dsdma_result(): return None
            initial_dma_tasks.append(no_dsdma_result())

        logging.debug(f"Awaiting {len(initial_dma_tasks)} initial DMA tasks for thought ID {thought_item.thought_id}")
        dma_results: List[Any] = await asyncio.gather(*initial_dma_tasks, return_exceptions=True)
        logging.debug(f"Initial DMA tasks completed for thought ID {thought_item.thought_id}")

        for res in dma_results:
            if isinstance(res, Thought) and any(
                e.get("type") == "dma_failure" for e in res.escalations
            ):
                logging.error(
                    "DMA failure detected for thought %s", res.thought_id
                )
                persistence.update_thought_status(
                    thought_id=res.thought_id,
                    new_status=ThoughtStatus.DEFERRED,
                    round_processed=self.current_round_number,
                    final_action_result={"status": "DMA failure"},
                )
                from .agent_core_schemas import DeferParams

                last_event = res.escalations[-1]
                defer_params = DeferParams(
                    reason=last_event["reason"],
                    target_wa_ual=DEFAULT_WA,
                    deferral_package_content=last_event,
                )
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection="DMA failure",
                    action_alignment_check={"error": "DMA failure"},
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=defer_params,
                    action_selection_rationale="DMA failure prior to ActionSelection",
                    monitoring_for_selected_action={"status": "DMA failure"},
                )

        ethical_pdma_result: Optional[EthicalPDMAResult] = None
        csdma_result: Optional[CSDMAResult] = None
        dsdma_result: Optional[DSDMAResult] = None

        if isinstance(dma_results[0], EthicalPDMAResult):
            ethical_pdma_result = dma_results[0]
            # Use .decision instead of .decision_rationale
            logging.debug(f"Ethical PDMA Result (Decision): {ethical_pdma_result.decision[:100]}...")
        elif isinstance(dma_results[0], Exception):
            logging.error(f"Ethical PDMA failed for thought {thought_item.thought_id}: {dma_results[0]}")
            # Create a fallback EthicalPDMAResult, ensure fields match schema
            ethical_pdma_result = EthicalPDMAResult(
                context=f"Ethical PDMA failed: {str(dma_results[0])}", # Mapped to 'context'
                alignment_check={"error": "Ethical PDMA exception"},
                decision="Ethical PDMA evaluation failed due to exception.", # Mapped to 'decision'
                monitoring={"status": "Ethical PDMA failure"}, # Mapped to 'monitoring'
                raw_llm_response=str(dma_results[0])
            )


        if isinstance(dma_results[1], CSDMAResult):
            csdma_result = dma_results[1]
            logging.debug(f"CSDMA Result: Score {csdma_result.common_sense_plausibility_score}, Flags {csdma_result.flags}")
        elif isinstance(dma_results[1], Exception):
            logging.error(f"CSDMA failed for thought {thought_item.thought_id}: {dma_results[1]}")
            csdma_result = CSDMAResult(
                common_sense_plausibility_score=0.0,
                flags=["CSDMA_Exception"],
                reasoning=f"CSDMA evaluation failed: {str(dma_results[1])}",
                raw_llm_response=str(dma_results[1])
            )

        # The DSDMA task is the third one if it was scheduled
        if selected_dsdma_instance:
            if isinstance(dma_results[2], DSDMAResult):
                dsdma_result = dma_results[2]
                logging.debug(f"DSDMA ({dsdma_result.domain_name if dsdma_result else 'N/A'}) Result: Score {dsdma_result.domain_alignment_score if dsdma_result else 'N/A'}, Action: {dsdma_result.recommended_action if dsdma_result else 'N/A'}")
            else:
                # If DSDMA is required but failed or missing, this is a critical error
                logging.critical(f"DSDMA ({selected_dsdma_instance.domain_name}) failed or did not return a result for thought {thought_item.thought_id}. This is a critical failure.")
                from .agent_core_schemas import DeferParams
                parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
                deferral_package = build_deferral_package(
                    thought=thought_object,
                    parent_task=parent_task_obj,
                    ethical_pdma_result=ethical_pdma_result,
                    csdma_result=csdma_result,
                    dsdma_result=None,
                    trigger_reason="DSDMA_FAILED_OR_MISSING",
                    extra={"error": "DSDMA failed or missing"}
                )
                defer_params = DeferParams(
                    reason=f"Critical: DSDMA failed or missing for thought {thought_item.thought_id}",
                    target_wa_ual=DEFAULT_WA,
                    deferral_package_content=deferral_package
                )
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection="Critical error: DSDMA failed or missing.",
                    action_alignment_check={"Error": "DSDMA failed or missing"},
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=defer_params,
                    action_selection_rationale="System error: DSDMA failed or missing.",
                    monitoring_for_selected_action={"status": "Critical: DSDMA failed or missing"},
                )
        elif dma_results[2] is None:
            logging.debug("No DSDMA was run, dsdma_result is None.")
            dsdma_result = None
        
        # Ensure critical results are present, even if they are error fallbacks
        if not ethical_pdma_result or not csdma_result:
            logging.critical(f"Missing critical DMA results (Ethical or CSDMA) for thought {thought_object.thought_id} even after fallback. Cannot proceed to Action Selection.") # Use thought_object
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Critical DMA failure upstream (Ethical or CSDMA).",
                action_alignment_check={"Error": "Upstream DMA failure (Ethical or CSDMA)"},
                selected_handler_action=HandlerActionType.DEFER,
                action_parameters={"reason": "Critical failure in initial Ethical or CSDMA processing."},
                action_selection_rationale="Cannot select action due to upstream Ethical or CSDMA failure.",
                monitoring_for_selected_action={"status": "Error: Upstream DMA failure"}
            )

        # current_ponder_count is now directly from thought_object fetched earlier
        current_ponder_count = thought_object.ponder_count

        # Determine permitted_actions for ActionSelectionPDMA
        # This assumes a single active profile context for the WorkflowCoordinator instance,
        # or that the profile can be determined (e.g., from thought_object or context).
        # For now, use the profile associated with the DSDMA if available, or a default/first profile.
        permitted_actions_for_thought: List[HandlerActionType] = []
        active_profile_for_as = None
        
        # Attempt to get profile name from DSDMA context if available
        profile_key_for_as = active_profile_name_for_dsdma 
        if not profile_key_for_as and self.app_config.agent_profiles:
            # Always use 'default' as the single source of truth if present
            if "default" in self.app_config.agent_profiles:
                profile_key_for_as = "default"
            else:
                profile_key_for_as = next(iter(self.app_config.agent_profiles), None)
        # CRITICAL: If profile_key_for_as is still None, treat as fatal error
        if not profile_key_for_as:
            logging.critical(f"No agent profile context available for ActionSelection for thought {thought_object.thought_id}. This is a critical error.")
            from .agent_core_schemas import DeferParams
            parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
            deferral_package = build_deferral_package(
                thought=thought_object,
                parent_task=parent_task_obj,
                ethical_pdma_result=ethical_pdma_result,
                csdma_result=csdma_result,
                dsdma_result=dsdma_result,
                trigger_reason="NO_AGENT_PROFILE_CONTEXT",
                extra={"error": "No agent profile context for ActionSelection"}
            )
            defer_params = DeferParams(
                reason=f"Critical: No agent profile context available for ActionSelection for thought {thought_object.thought_id}",
                target_wa_ual=DEFAULT_WA,
                deferral_package_content=deferral_package
            )
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Critical error: No agent profile context for ActionSelection.",
                action_alignment_check={"Error": "No agent profile context for ActionSelection"},
                selected_handler_action=HandlerActionType.DEFER,
                action_parameters=defer_params,
                action_selection_rationale="System error: No agent profile context for ActionSelection.",
                monitoring_for_selected_action={"status": "Critical: No agent profile context for ActionSelection"},
            )

        if profile_key_for_as:
            active_profile_for_as = self.app_config.agent_profiles.get(profile_key_for_as.lower())
            if not active_profile_for_as: # Try original case if lowercase failed
                 active_profile_for_as = self.app_config.agent_profiles.get(profile_key_for_as)

        if active_profile_for_as:
            permitted_actions_for_thought = active_profile_for_as.permitted_actions
            logging.debug(f"Using permitted_actions from profile '{active_profile_for_as.name}' for thought {thought_object.thought_id}")
        else:
            # Fallback if no profile could be determined (should ideally not happen in a configured system)
            logging.warning(f"Could not determine active profile for thought {thought_object.thought_id}. ActionSelectionPDMA might use defaults or fail.")
            # ActionSelectionPDMA has its own default if 'permitted_actions' is missing.

        logging.debug(f"Running Action Selection PDMA for thought ID {thought_object.thought_id} (Ponder count: {current_ponder_count}, Benchmark: {benchmark_mode})")
        
        triaged_inputs_for_action_selection = {
            "original_thought": thought_object,
            "ethical_pdma_result": ethical_pdma_result,
            "csdma_result": csdma_result,
            "dsdma_result": dsdma_result,
            "current_ponder_count": current_ponder_count,
            "max_ponder_rounds": self.max_ponder_rounds,
            "benchmark_mode": benchmark_mode,
            "permitted_actions": permitted_actions_for_thought, # Added permitted_actions
            "agent_profile": active_profile_for_as # Pass the determined agent profile object
        }

        action_selection_result: ActionSelectionPDMAResult = await run_action_selection_pdma(
            self.action_selection_pdma_evaluator,
            triaged_inputs_for_action_selection,
            retry_limit=DMA_RETRY_LIMIT,
        )
        # Log action_parameters carefully, as it can be a Pydantic model
        logging.info(f"Action Selection PDMA chose: {action_selection_result.selected_handler_action.value} with params {str(action_selection_result.action_parameters)}")

        logging.debug(f"Applying ethical guardrails to selected action for thought ID {thought_object.thought_id}") # Use thought_object
        passes_guardrail, reason, epistemic_data = await self.ethical_guardrails.check_action_output_safety(action_selection_result) # Awaited

        final_action_result = action_selection_result
        
        # Import Pydantic models for type checking action_parameters
        from .agent_core_schemas import SpeakParams, PonderParams, DeferParams, RejectParams 

        if not passes_guardrail:
            logging.warning(f"Guardrail failed for thought ID {thought_object.thought_id}: {reason}. Overriding action to DEFER.")
            
            original_params_as_dict = {}
            if isinstance(action_selection_result.action_parameters, BaseModel):
                original_params_as_dict = action_selection_result.action_parameters.model_dump()
            elif isinstance(action_selection_result.action_parameters, dict): # Should ideally be a Pydantic model
                original_params_as_dict = action_selection_result.action_parameters

            candidate_response_content = "N/A (Guardrail Deferral)"
            if isinstance(action_selection_result.action_parameters, SpeakParams):
                candidate_response_content = action_selection_result.action_parameters.content
            elif isinstance(original_params_as_dict, dict): # Fallback if it was a dict
                 candidate_response_content = original_params_as_dict.get("content", candidate_response_content)

            # For DEFER action, action_parameters should be DeferParams or a dict that can initialize it.
            # The ActionSelectionPDMAResult expects a Pydantic model for action_parameters.
            # We will construct a DeferParams model here.
            
            # First, create the deferral package content
            parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
            deferral_package_for_guardrail = build_deferral_package(
                thought=thought_object,
                parent_task=parent_task_obj,
                ethical_pdma_result=ethical_pdma_result,
                csdma_result=csdma_result,
                dsdma_result=dsdma_result,
                trigger_reason="GUARDRAIL_FAILURE",
                extra={
                    "original_proposed_action": action_selection_result.selected_handler_action.value,
                    "original_action_parameters": original_params_as_dict,
                    "guardrail_failure_reason": reason,
                    "epistemic_data": epistemic_data,
                    "metrics": {"guardrail_triggered": True}
                }
            )
            
            # Now create the DeferParams model
            # Assuming DeferParams has 'reason' and 'deferral_package_content' and 'target_wa_ual'
            # We need a default target_wa_ual or get it from config
            # For now, using a placeholder. This should be configured.)
            guardrail_defer_params = DeferParams(
                reason=f"Guardrail failure: {reason}",
                target_wa_ual=DEFAULT_WA,
                deferral_package_content=deferral_package_for_guardrail
            )

            escalate_due_to_guardrail(
                thought_object,
                reason=(
                    f"Guardrail violation detected: {reason}. DMA: ActionSelectionPDMA, "
                    f"Task: {thought_object.source_task_id}. "
                    f"Last action: {thought_object.history[-1]['action']}" if thought_object.history else "Last action: None"
                ),
            )

            final_action_result = ActionSelectionPDMAResult( 
                context_summary_for_action_selection=action_selection_result.context_summary_for_action_selection,
                action_alignment_check=action_selection_result.action_alignment_check,
                action_conflicts=action_selection_result.action_conflicts,
                action_resolution=action_selection_result.action_resolution,
                selected_handler_action=HandlerActionType.DEFER,
                action_parameters=guardrail_defer_params, # Pass the DeferParams model
                action_selection_rationale=f"Original action '{action_selection_result.selected_handler_action.value}' overridden by guardrail. Reason: {reason}",
                monitoring_for_selected_action={"status": "Action overridden by guardrail"},
                raw_llm_response=action_selection_result.raw_llm_response,
                # Ensure the decision_input_context_snapshot is carried over
                decision_input_context_snapshot=action_selection_result.decision_input_context_snapshot
            )
            logging.info(f"Action for thought ID {thought_object.thought_id} is now DEFER due to guardrail failure.")
        else:
            logging.info(f"Guardrail passed for action '{final_action_result.selected_handler_action.value}' for thought ID {thought_object.thought_id}.")

        if final_action_result.selected_handler_action == HandlerActionType.PONDER:
            key_questions_list = []
            if isinstance(final_action_result.action_parameters, PonderParams):
                key_questions_list = final_action_result.action_parameters.key_questions
            elif isinstance(final_action_result.action_parameters, dict): # Fallback if it's a dict
                key_questions_list = final_action_result.action_parameters.get('key_questions', [])
            else:
                logging.error(f"PONDER action for thought {thought_object.thought_id} has invalid action_parameters type: {type(final_action_result.action_parameters)}")

            if epistemic_data and 'optimization_veto' in epistemic_data:
                veto = epistemic_data['optimization_veto']
                note = f"OptVeto: {veto.get('decision')} - {veto.get('justification')}"
                key_questions_list.append(note)
            if epistemic_data and 'epistemic_humility' in epistemic_data:
                hum = epistemic_data['epistemic_humility']
                h_note = f"Humility: {hum.get('recommended_action')} - {hum.get('epistemic_certainty')}"
                key_questions_list.append(h_note)
            
            # current_ponder_count is already from thought_object.ponder_count
            
            if not thought_object: # Should not happen due to early check, but as safeguard
                logging.error(f"PONDER: Critical - thought_object became None for ID {thought_item.thought_id}. Cannot process Ponder action.")
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection=final_action_result.context_summary_for_action_selection,
                    action_alignment_check=final_action_result.action_alignment_check,
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=RejectParams(reason=f"PONDER failed: Critical - thought_object became None for ID {thought_item.thought_id}."), # Use RejectParams
                    action_selection_rationale="PONDER action failed due to internal error retrieving thought details.",
                    monitoring_for_selected_action={"status": "Error: PONDER failed due to missing thought object"}
                )

            if current_ponder_count >= self.max_ponder_rounds:
                logging.warning(f"Thought ID {thought_object.thought_id} has reached max ponder rounds ({self.max_ponder_rounds}). Overriding to DEFER.")
                parent_task_obj = persistence.get_task_by_id(thought_object.source_task_id)
                deferral_package_max_ponder = build_deferral_package(
                    thought=thought_object,
                    parent_task=parent_task_obj,
                    ethical_pdma_result=ethical_pdma_result,
                    csdma_result=csdma_result,
                    dsdma_result=dsdma_result,
                    trigger_reason="MAX_PONDER_ROUNDS_REACHED",
                    extra={
                        "original_ponder_questions": key_questions_list,
                        "final_ponder_count": current_ponder_count,
                        "metrics": {"ponder_count": current_ponder_count}
                    }
                )
                max_ponder_defer_params = DeferParams(
                    reason=f"Thought reached maximum ponder rounds ({self.max_ponder_rounds}).",
                    target_wa_ual=DEFAULT_WA,
                    deferral_package_content=deferral_package_max_ponder
                )
                # Construct the ActionSelectionPDMAResult that represents this deferral
                defer_action_selection_result = ActionSelectionPDMAResult(
                    context_summary_for_action_selection=final_action_result.context_summary_for_action_selection if final_action_result else "Max ponder rounds reached.",
                    action_alignment_check=final_action_result.action_alignment_check if final_action_result else {"DEFER": "Max ponder rounds reached"},
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=max_ponder_defer_params,
                    action_selection_rationale=f"Ponder action overridden. Thought reached max ponder rounds ({self.max_ponder_rounds}).",
                    monitoring_for_selected_action={"status": "Max ponder rounds reached, deferred"}
                )

                persistence.update_thought_status(
                    thought_id=thought_object.thought_id,
                    new_status=ThoughtStatus.DEFERRED,
                    round_processed=self.current_round_number,
                    final_action_result=defer_action_selection_result.model_dump(), # Store the full result
                    ponder_notes=key_questions_list, 
                    ponder_count=current_ponder_count
                )
                # The deferral_package_max_ponder and max_ponder_defer_params were used to build defer_action_selection_result
                return defer_action_selection_result # Return the constructed result
            else: # Re-queue for PONDER
                new_ponder_count = current_ponder_count + 1
                logging.info(f"Thought ID {thought_object.thought_id} resulted in PONDER action (count: {new_ponder_count}). Questions: {key_questions_list}. Re-queueing.")
                
                success = persistence.update_thought_status(
                    thought_id=thought_object.thought_id,
                    new_status=ThoughtStatus.PENDING,
                    round_processed=None, 
                    final_action_result=None, # Set to None when re-queuing for Ponder
                    ponder_notes=key_questions_list,
                    ponder_count=new_ponder_count
                )
                if success:
                    logging.info(f"Thought ID {thought_object.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for re-processing.")
                    return None # Indicates internal re-processing
                else: # Re-queueing failed
                    logging.error(f"Failed to update thought ID {thought_object.thought_id} for re-processing Ponder. Returning Ponder action as terminal.")
                    # If action_parameters was a dict, ensure it's converted to PonderParams or handled
                    if isinstance(final_action_result.action_parameters, dict):
                        # Attempt to create PonderParams if it was a dict, or handle error
                        try:
                            final_action_result.action_parameters = PonderParams(**final_action_result.action_parameters)
                        except Exception: # Catch Pydantic validation error or others
                             logging.error(f"Could not convert action_parameters dict to PonderParams for thought {thought_object.thought_id}")
                             # Fallback to a generic Reject if conversion fails
                             return ActionSelectionPDMAResult(
                                 context_summary_for_action_selection="Ponder re-queue failed, and action_parameters invalid.",
                                 selected_handler_action=HandlerActionType.REJECT,
                                 action_parameters=RejectParams(reason="Ponder re-queue failed and parameters were invalid."),
                                 action_selection_rationale="System error during Ponder re-queue.",
                                 monitoring_for_selected_action={"status": "Error"}
                             )
                    # Add ponder_count_at_failure to the PonderParams if it's the correct type
                    if isinstance(final_action_result.action_parameters, PonderParams):
                        # PonderParams doesn't have a ponder_count_at_failure field.
                        # We might log this or add it to a generic dict in action_parameters if needed,
                        # but ActionSelectionPDMAResult expects a specific Pydantic model for action_parameters.
                        # For now, we just return the Ponder action.
                        pass
                    return final_action_result
        
        # For all other actions OR if PONDER re-queue failed and returned the Ponder action
        if final_action_result: # This means it's a terminal action for this processing cycle
            track_action(
                thought_object,
                final_action_result.selected_handler_action,
                final_action_result.action_parameters,
            )
            success = persistence.update_thought_status(
                thought_id=thought_object.thought_id,
                new_status=ThoughtStatus.COMPLETED, # Or FAILED/DEFERRED if set by dispatcher
                round_processed=self.current_round_number,
                final_action_result=final_action_result.model_dump() # Store the full ActionSelectionPDMAResult
            )
            if success:
                logging.info(f"Thought ID {thought_object.thought_id} successfully updated with final action result.")
            else:
                logging.error(f"Failed to update thought ID {thought_object.thought_id} to completed.") # Use thought_object
        
        return final_action_result # For all other actions

    async def build_context(self, task: Optional[Task], thought: Thought) -> Dict[str, Any]:
        """Builds the execution context for a thought, ensuring JSON serializability for persistence."""
        
        thought_summary = None
        if thought:
            # Handle status: it's an Enum (ThoughtStatus) in the model
            status_val = None
            if thought.status:
                if isinstance(thought.status, ThoughtStatus): # Check if it's an Enum member
                    status_val = thought.status.value
                elif isinstance(thought.status, str): # Fallback if it's already a string
                    status_val = thought.status
            
            # Handle thought_type: it's a str in the model
            thought_type_val = thought.thought_type # Use directly as it's a string

            thought_summary = {
                "thought_id": thought.thought_id,
                "content": thought.content,
                "status": status_val,
                "source_task_id": thought.source_task_id,
                "thought_type": thought_type_val,
                "ponder_count": thought.ponder_count
            }

        recent_tasks_list = []
        db_recent_tasks = persistence.get_recent_completed_tasks(10) 
        for t_obj in db_recent_tasks:
            if isinstance(t_obj, BaseModel):
                recent_tasks_list.append(t_obj.model_dump(mode='json', exclude_none=True))
            else: 
                recent_tasks_list.append(t_obj) # Should not happen if get_recent_completed_tasks returns Task objects

        top_tasks_list = []
        db_top_tasks = persistence.get_top_tasks(10)
        for t_obj in db_top_tasks:
            if isinstance(t_obj, BaseModel): # Assuming get_top_tasks returns Task objects
                 top_tasks_list.append({"task_id": t_obj.task_id, "description": t_obj.description, "priority": t_obj.priority})
            else:
                 top_tasks_list.append(t_obj)


        context = {
            "current_task_details": task.model_dump(mode='json', exclude_none=True) if task and isinstance(task, BaseModel) else None,
            "current_thought_summary": thought_summary,
            "system_counts": {
                "total_tasks": persistence.count_tasks(),
                "total_thoughts": persistence.count_thoughts(),
                "pending_tasks": persistence.count_tasks(TaskStatus.PENDING),
                "pending_thoughts": persistence.count_thoughts(ThoughtStatus.PENDING),
            },
            "top_pending_tasks_summary": top_tasks_list,
            "recently_completed_tasks_summary": recent_tasks_list
        }

        graphql_extra_raw = await self.graphql_context_provider.enrich_context(task, thought)
        
        graphql_extra_processed = {}
        if "user_profiles" in graphql_extra_raw and isinstance(graphql_extra_raw["user_profiles"], dict):
            graphql_extra_processed["user_profiles"] = {}
            for key, profile_obj in graphql_extra_raw["user_profiles"].items():
                if isinstance(profile_obj, BaseModel):
                    graphql_extra_processed["user_profiles"][key] = profile_obj.model_dump(mode='json', exclude_none=True)
                else: 
                    graphql_extra_processed["user_profiles"][key] = profile_obj
        
        # Generic handling for other potential Pydantic models in graphql_extra_raw
        for key, value in graphql_extra_raw.items():
            if key not in graphql_extra_processed: # Avoid reprocessing "user_profiles"
                if isinstance(value, BaseModel):
                    graphql_extra_processed[key] = value.model_dump(mode='json', exclude_none=True)
                elif isinstance(value, list) and all(isinstance(item, BaseModel) for item in value):
                    graphql_extra_processed[key] = [item.model_dump(mode='json', exclude_none=True) for item in value]
                else:
                    graphql_extra_processed[key] = value


        context.update(graphql_extra_processed)
        return context

    def __repr__(self) -> str:
        return "<WorkflowCoordinator (Async)>"
