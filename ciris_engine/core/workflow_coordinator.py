import sys # Import sys for maxsize
import logging
import asyncio # New import
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING # Added TYPE_CHECKING
from pydantic import BaseModel # Added import

from .foundational_schemas import TaskStatus, ThoughtStatus, HandlerActionType
from .agent_core_schemas import EthicalPDMAResult, CSDMAResult, DSDMAResult, ActionSelectionPDMAResult, Thought, Task
from .agent_processing_queue import ProcessingQueueItem
from .config_schemas import AppConfig, WorkflowConfig # Import AppConfig and WorkflowConfig
from . import persistence # Import persistence module
from ciris_engine.services.llm_client import CIRISLLMClient # Assume this will have an async call_llm
# Direct imports for DMA evaluators to avoid circular dependencies
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
# from ciris_engine.dma.dsdma_base import BaseDSDMA # For type hinting - moved to TYPE_CHECKING
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils import DEFAULT_WA
from ciris_engine.utils import GraphQLContextProvider

if TYPE_CHECKING:
    from ciris_engine.dma.dsdma_base import BaseDSDMA # Import only for type checking
    from ciris_engine.services.discord_graph_memory import DiscordGraphMemory
    from ciris_engine.utils import GraphQLContextProvider

# MAX_PONDER_ROUNDS = 5 # REMOVED Constant - will use config

class WorkflowCoordinator:
    """
    Orchestrates the flow of a thought through the various DMAs (with initial
    DMAs running concurrently), faculties (via guardrails), and guardrails
    to produce a final, vetted action.
    """

    def __init__(self,
                 llm_client: CIRISLLMClient, # This LLM client MUST support async operations
                 ethical_pdma_evaluator: EthicalPDMAEvaluator,
                 csdma_evaluator: CSDMAEvaluator,
                 action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator, # Corrected type
                 ethical_guardrails: EthicalGuardrails,
                 app_config: AppConfig, # Corrected type hint to AppConfig
                 # thought_queue_manager: ThoughtQueueManager, # <-- REMOVE THIS
                 dsdma_evaluators: Optional[Dict[str, 'BaseDSDMA']] = None, # Use string literal for forward reference
                 memory_service: Optional['DiscordGraphMemory'] = None,
                 graphql_context_provider: Optional['GraphQLContextProvider'] = None,
                 # current_round_number: int = 0 # REMOVED from parameters
                ):
        self.llm_client = llm_client
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma_evaluators = dsdma_evaluators if dsdma_evaluators else {}
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.memory_service = memory_service
        self.graphql_context_provider = graphql_context_provider or GraphQLContextProvider()
        self.ethical_guardrails = ethical_guardrails
        self.app_config = app_config # Store full AppConfig
        self.workflow_config = app_config.workflow # Store workflow_config part
        self.max_ponder_rounds = self.workflow_config.max_ponder_rounds # Store specific value
        # self.thought_queue_manager = thought_queue_manager # <-- REMOVE THIS
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
            defer_params = DeferParams(
                reason=defer_reason,
                target_wa_ual=DEFAULT_WA,
                deferral_package_content={"error_details": defer_reason}
            )
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Critical error: Thought object not found.",
                action_alignment_check={"Error": "Thought object retrieval failed"},
                selected_handler_action=HandlerActionType.DEFER,
                action_parameters=defer_params,
                action_selection_rationale="System error: Cannot process thought without its core object.",
                monitoring_for_selected_action={"status": "Error: Thought object not found"},
            )

        if thought_object.thought_type == "memory_meta" and self.memory_service:
            await self.memory_service.memorize(
                thought_object.processing_context.get("user_nick", "unknown"),
                thought_object.processing_context.get("channel", "unknown"),
                thought_object.processing_context.get("metadata", {}),
            )
            persistence.update_thought_status(
                thought_object.thought_id,
                ThoughtStatus.COMPLETED,
                round_processed=self.current_round_number,
            )
            return None

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
        initial_dma_tasks.append(self.ethical_pdma_evaluator.evaluate(thought_object)) # Pass thought_object

        # 2. CSDMA Task
        logging.debug(f"Scheduling CSDMA for thought ID {thought_object.thought_id}") # Use thought_object
        initial_dma_tasks.append(self.csdma_evaluator.evaluate_thought(thought_object)) # Pass thought_object

        # 3. DSDMA Task (select and run if applicable)
        selected_dsdma_instance: Optional['BaseDSDMA'] = None # Use string literal
        # Using the "BasicTeacherMod" key as per previous logic.
        # The actual type of dsdma_evaluators values will be concrete DSDMA subclasses.
        # For this example, we assume a profile might specify a DSDMA under a key like "teacher_profile_dsdma"
        # or the profile name itself if only one DSDMA is expected per profile.
        # For now, let's assume the dsdma_evaluators dict keys are profile names or specific DSDMA role names.
        # The current logic in CIRISDiscordEngineBot uses profile.name as the key.
        # We need a more generic way to pick the DSDMA or iterate if multiple could apply.
        # For simplicity, if there's only one DSDMA in dsdma_evaluators, use it.
        # This part needs to align with how profiles define which DSDMA to use.
        
        # Let's assume for now that if dsdma_evaluators is populated, we pick the first one.
        # This is a simplification and might need refinement based on profile structure.
        active_profile_name_for_dsdma: Optional[str] = None
        if self.dsdma_evaluators:
            # Get the first DSDMA instance from the dictionary
            # This assumes that the relevant DSDMA for the current thought/profile is present.
            # A more robust system might involve matching thought context to DSDMA capabilities.
            active_profile_name_for_dsdma = next(iter(self.dsdma_evaluators)) # Key is assumed to be profile name
            active_dsdma = self.dsdma_evaluators.get(active_profile_name_for_dsdma)
            if active_dsdma:
                logging.debug(f"Scheduling DSDMA '{active_dsdma.domain_name}' (Profile: {active_profile_name_for_dsdma}) for thought ID {thought_object.thought_id}")
                initial_dma_tasks.append(active_dsdma.evaluate_thought(thought_object, current_platform_context)) # Pass thought_object
                selected_dsdma_instance = active_dsdma
            else: # Should not happen if dsdma_evaluators is not empty
                logging.warning(f"DSDMA evaluators populated, but could not retrieve an instance for profile key {active_profile_name_for_dsdma} for thought {thought_object.thought_id}")
                async def no_dsdma_result(): return None
                initial_dma_tasks.append(no_dsdma_result())
        else:
            logging.debug(f"No DSDMA evaluators configured or applicable for thought ID {thought_item.thought_id}, will pass None to ActionSelection.")
            async def no_dsdma_result(): return None
            initial_dma_tasks.append(no_dsdma_result())

        logging.debug(f"Awaiting {len(initial_dma_tasks)} initial DMA tasks for thought ID {thought_item.thought_id}")
        dma_results: List[Any] = await asyncio.gather(*initial_dma_tasks, return_exceptions=True)
        logging.debug(f"Initial DMA tasks completed for thought ID {thought_item.thought_id}")

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
                # Corrected field name from domain_specific_score to domain_alignment_score
                logging.debug(f"DSDMA ({dsdma_result.domain_name if dsdma_result else 'N/A'}) Result: Score {dsdma_result.domain_alignment_score if dsdma_result else 'N/A'}, Action: {dsdma_result.recommended_action if dsdma_result else 'N/A'}")
            elif isinstance(dma_results[2], Exception):
                logging.error(f"DSDMA ({selected_dsdma_instance.domain_name}) failed for thought {thought_item.thought_id}: {dma_results[2]}")
                # dsdma_result remains None, ActionSelectionPDMA should handle None input
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
            # Fallback: use the first profile defined in config if no DSDMA context
            profile_key_for_as = next(iter(self.app_config.agent_profiles), None)
            if profile_key_for_as:
                 logging.warning(f"No DSDMA profile context for ActionSelection, falling back to first profile: {profile_key_for_as}")


        if profile_key_for_as:
            # Ensure consistent key lookup (e.g., lowercase if keys in app_config.agent_profiles are from filenames)
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

        action_selection_result: ActionSelectionPDMAResult = await self.action_selection_pdma_evaluator.evaluate(
            triaged_inputs=triaged_inputs_for_action_selection
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
            deferral_package_for_guardrail = {
                "original_proposed_action": action_selection_result.selected_handler_action.value,
                "original_action_parameters": original_params_as_dict,
                "guardrail_failure_reason": reason,
                "epistemic_data": epistemic_data,
                "pdma_trace_id": thought_object.thought_id,
                "autonomy_tier": 0, 
                "context": str(thought_object.content),
                "candidate_response": candidate_response_content,
                "metrics": {"guardrail_triggered": True},
                "trigger": "GUARDRAIL_FAILURE"
            }
            
            # Now create the DeferParams model
            # Assuming DeferParams has 'reason' and 'deferral_package_content' and 'target_wa_ual'
            # We need a default target_wa_ual or get it from config
            # For now, using a placeholder. This should be configured.)
            guardrail_defer_params = DeferParams(
                reason=f"Guardrail failure: {reason}",
                target_wa_ual=DEFAULT_WA,
                deferral_package_content=deferral_package_for_guardrail
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
                raw_llm_response=action_selection_result.raw_llm_response
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
                persistence.update_thought_status(
                    thought_id=thought_object.thought_id,
                    new_status=ThoughtStatus.DEFERRED,
                    round_processed=self.current_round_number,
                    final_action_result={"status": "Deferred due to max ponder rounds", "final_ponder_count": current_ponder_count},
                    ponder_notes=key_questions_list, 
                    ponder_count=current_ponder_count
                )
                
                deferral_package_max_ponder = {
                    "original_ponder_questions": key_questions_list,
                    "final_ponder_count": current_ponder_count,
                    "pdma_trace_id": thought_object.thought_id,
                    "autonomy_tier": 0,
                    "context": str(thought_object.content),
                    "candidate_response": "N/A (Deferred due to max ponder rounds)",
                    "metrics": {"ponder_count": current_ponder_count},
                    "trigger": "MAX_PONDER_ROUNDS_REACHED"
                }
                max_ponder_defer_params = DeferParams(
                    reason=f"Thought reached maximum ponder rounds ({self.max_ponder_rounds}).",
                    target_wa_ual=DEFAULT_WA,
                    deferral_package_content=deferral_package_max_ponder
                )
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection=final_action_result.context_summary_for_action_selection,
                    action_alignment_check=final_action_result.action_alignment_check,
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters=max_ponder_defer_params, # Use DeferParams model
                    action_selection_rationale=f"Ponder action overridden. Thought reached max ponder rounds ({self.max_ponder_rounds}).",
                    monitoring_for_selected_action={"status": "Max ponder rounds reached, deferred"}
                )
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

    async def build_context(self, task: Task, thought: Thought) -> Dict[str, Any]:
        """Builds the execution context for a thought."""
        context = {
            "task": task,
            "thought": thought,
            "counts": {
                "total_tasks": persistence.count_tasks(),
                "total_thoughts": persistence.count_thoughts(),
                "pending_tasks": persistence.count_tasks(TaskStatus.PENDING),
                "pending_thoughts": persistence.count_thoughts(ThoughtStatus.PENDING),
            },
            "top_tasks": [t.task_id for t in persistence.get_top_tasks(3)],
        }
        graphql_extra = await self.graphql_context_provider.enrich_context(task, thought)
        context.update(graphql_extra)
        return context

    def __repr__(self) -> str:
        return "<WorkflowCoordinator (Async)>"
