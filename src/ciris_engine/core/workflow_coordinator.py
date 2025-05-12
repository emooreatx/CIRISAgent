# src/ciris_engine/core/workflow_coordinator.py
import logging
import asyncio # New import
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING # Added TYPE_CHECKING

from .data_schemas import (
    ThoughtQueueItem,
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionPDMAResult,
    HandlerActionType,
    ThoughtStatus # Ensure ThoughtStatus is available
)
from .thought_queue_manager import ThoughtQueueManager # Added import
from ciris_engine.services.llm_client import CIRISLLMClient # Assume this will have an async call_llm
# Direct imports for DMA evaluators to avoid circular dependencies
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
# from ciris_engine.dma.dsdma_base import BaseDSDMA # For type hinting - moved to TYPE_CHECKING
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails

if TYPE_CHECKING:
    from ciris_engine.dma.dsdma_base import BaseDSDMA # Import only for type checking

MAX_PONDER_ROUNDS = 5 # Define the constant

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
                 action_selection_pdma_evaluator: ActionSelectionPDMAEvaluator,
                 ethical_guardrails: EthicalGuardrails,
                 thought_queue_manager: ThoughtQueueManager, # <-- ADD THIS
                 dsdma_evaluators: Optional[Dict[str, 'BaseDSDMA']] = None # Use string literal for forward reference
                ):
        self.llm_client = llm_client
        self.ethical_pdma_evaluator = ethical_pdma_evaluator
        self.csdma_evaluator = csdma_evaluator
        self.dsdma_evaluators = dsdma_evaluators if dsdma_evaluators else {}
        self.action_selection_pdma_evaluator = action_selection_pdma_evaluator
        self.ethical_guardrails = ethical_guardrails
        self.thought_queue_manager = thought_queue_manager # <-- ADD THIS

    async def process_thought(self, thought_item: ThoughtQueueItem,
                              current_platform_context: Optional[Dict[str, Any]] = None,
                              benchmark_mode: bool = False # Add benchmark_mode parameter
                              ) -> Optional[ActionSelectionPDMAResult]: # Return type can be None now
        """
        Processes a single thought item through the full DMA and guardrail pipeline.
        The initial Ethical PDMA, CSDMA, and DSDMA calls are made concurrently.
        """
        logging.info(f"WorkflowCoordinator: Async processing thought ID {thought_item.thought_id} - '{str(thought_item.content)[:50]}...'")
        current_platform_context = current_platform_context or thought_item.initial_context or {}

        # --- Stage 1: Initial DMAs (Concurrent Execution) ---
        initial_dma_tasks = []

        # 1. Ethical PDMA Task
        logging.debug(f"Scheduling Ethical PDMA for thought ID {thought_item.thought_id}")
        initial_dma_tasks.append(self.ethical_pdma_evaluator.evaluate(thought_item))

        # 2. CSDMA Task
        logging.debug(f"Scheduling CSDMA for thought ID {thought_item.thought_id}")
        initial_dma_tasks.append(self.csdma_evaluator.evaluate_thought(thought_item))

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
        if self.dsdma_evaluators:
            # Get the first DSDMA instance from the dictionary
            # This assumes that the relevant DSDMA for the current thought/profile is present.
            # A more robust system might involve matching thought context to DSDMA capabilities.
            first_dsdma_key = next(iter(self.dsdma_evaluators))
            active_dsdma = self.dsdma_evaluators.get(first_dsdma_key)
            if active_dsdma:
                logging.debug(f"Scheduling DSDMA '{active_dsdma.domain_name}' for thought ID {thought_item.thought_id}")
                initial_dma_tasks.append(active_dsdma.evaluate_thought(thought_item, current_platform_context))
                selected_dsdma_instance = active_dsdma
            else: # Should not happen if dsdma_evaluators is not empty
                logging.warning(f"DSDMA evaluators populated, but could not retrieve an instance for thought {thought_item.thought_id}")
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
            logging.debug(f"Ethical PDMA Result: {ethical_pdma_result.decision_rationale[:100]}...")
        elif isinstance(dma_results[0], Exception):
            logging.error(f"Ethical PDMA failed for thought {thought_item.thought_id}: {dma_results[0]}")
            # Create a fallback EthicalPDMAResult
            ethical_pdma_result = EthicalPDMAResult(
                context_analysis=f"Ethical PDMA failed: {str(dma_results[0])}",
                alignment_check={"error": "Ethical PDMA exception"},
                decision_rationale="Ethical PDMA evaluation failed due to exception.",
                monitoring_plan={"status": "Ethical PDMA failure"},
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
                logging.debug(f"DSDMA ({dsdma_result.domain_name if dsdma_result else 'N/A'}) Result: Score {dsdma_result.domain_specific_score if dsdma_result else 'N/A'}, Action: {dsdma_result.recommended_action if dsdma_result else 'N/A'}")
            elif isinstance(dma_results[2], Exception):
                logging.error(f"DSDMA ({selected_dsdma_instance.domain_name}) failed for thought {thought_item.thought_id}: {dma_results[2]}")
                # dsdma_result remains None, ActionSelectionPDMA should handle None input
        elif dma_results[2] is None: 
            logging.debug("No DSDMA was run, dsdma_result is None.")
            dsdma_result = None
        
        # Ensure critical results are present, even if they are error fallbacks
        if not ethical_pdma_result or not csdma_result:
            logging.critical(f"Missing critical DMA results (Ethical or CSDMA) for thought {thought_item.thought_id} even after fallback. Cannot proceed to Action Selection.")
            return ActionSelectionPDMAResult(
                context_summary_for_action_selection="Critical DMA failure upstream (Ethical or CSDMA).",
                action_alignment_check={"Error": "Upstream DMA failure (Ethical or CSDMA)"},
                selected_handler_action=HandlerActionType.DEFER_TO_WA,
                action_parameters={"reason": "Critical failure in initial Ethical or CSDMA processing."},
                action_selection_rationale="Cannot select action due to upstream Ethical or CSDMA failure."
            )

        # Fetch current_ponder_count before action selection for the evaluator
        thought_db_instance_for_ponder_check = self.thought_queue_manager.get_thought_by_id(thought_item.thought_id)
        current_ponder_count = 0 # Default if thought not found, though it should be
        if thought_db_instance_for_ponder_check:
            current_ponder_count = thought_db_instance_for_ponder_check.ponder_count
        else:
            logging.error(f"Could not retrieve thought ID {thought_item.thought_id} from DB before ActionSelection. Ponder count will be 0.")


        logging.debug(f"Running Action Selection PDMA for thought ID {thought_item.thought_id} (Ponder count: {current_ponder_count}, Benchmark: {benchmark_mode})")
        
        triaged_inputs_for_action_selection = {
            "original_thought": thought_item.thought_object, # Pass the full Thought model from ThoughtQueueItem
            "ethical_pdma_result": ethical_pdma_result,
            "csdma_result": csdma_result,
            "dsdma_result": dsdma_result,
            "current_ponder_count": current_ponder_count,
            "max_ponder_rounds": MAX_PONDER_ROUNDS,
            "benchmark_mode": benchmark_mode
        }
        
        action_selection_result: ActionSelectionPDMAResult = await self.action_selection_pdma_evaluator.evaluate(
            triaged_inputs=triaged_inputs_for_action_selection
        )
        logging.info(f"Action Selection PDMA chose: {action_selection_result.selected_handler_action.value} with params {action_selection_result.action_parameters}")

        logging.debug(f"Applying ethical guardrails to selected action for thought ID {thought_item.thought_id}")
        passes_guardrail, reason, epistemic_data = await self.ethical_guardrails.check_action_output_safety(action_selection_result) # Awaited

        final_action_result = action_selection_result

        if not passes_guardrail:
            logging.warning(f"Guardrail failed for thought ID {thought_item.thought_id}: {reason}. Overriding action to DEFER_TO_WA.")
            
            defer_action_params_guardrail = {
                "original_proposed_action": action_selection_result.selected_handler_action.value,
                "original_action_parameters": action_selection_result.action_parameters,
                "guardrail_failure_reason": reason,
                "epistemic_data": epistemic_data,
                "pdma_trace_id": thought_item.thought_id, # Use thought_id as trace_id
                "autonomy_tier": 0, # Default autonomy tier
                "context": str(thought_item.content), # Original thought content
                "candidate_response": action_selection_result.action_parameters.get("message_content", "N/A (Guardrail Deferral)"), # Attempt to get candidate if Speak
                "metrics": {"guardrail_triggered": True},
                "trigger": "GUARDRAIL_FAILURE"
            }
            final_action_result = ActionSelectionPDMAResult( 
                context_summary_for_action_selection=action_selection_result.context_summary_for_action_selection,
                action_alignment_check=action_selection_result.action_alignment_check,
                action_conflicts=action_selection_result.action_conflicts,
                action_resolution=action_selection_result.action_resolution,
                selected_handler_action=HandlerActionType.DEFER_TO_WA,
                action_parameters=defer_action_params_guardrail,
                action_selection_rationale=f"Original action '{action_selection_result.selected_handler_action.value}' overridden by guardrail. Reason: {reason}",
                monitoring_for_selected_action={"status": "Awaiting WA guidance on deferral."},
                raw_llm_response=action_selection_result.raw_llm_response 
            )
            logging.info(f"Action for thought ID {thought_item.thought_id} is now DEFER_TO_WA due to guardrail failure.")
        else:
            logging.info(f"Guardrail passed for action '{final_action_result.selected_handler_action.value}' for thought ID {thought_item.thought_id}.")

        if final_action_result.selected_handler_action == HandlerActionType.PONDER:
            key_questions = final_action_result.action_parameters.get('key_questions')
            
            # Fetch the full thought to get current ponder_count
            thought_db_instance = self.thought_queue_manager.get_thought_by_id(thought_item.thought_id)
            
            if not thought_db_instance:
                logging.error(f"PONDER: Could not retrieve thought ID {thought_item.thought_id} from DB. Cannot process Ponder action.")
                # Fallback to DEFER_TO_WA if thought cannot be fetched
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection=final_action_result.context_summary_for_action_selection,
                    action_alignment_check=final_action_result.action_alignment_check,
                    selected_handler_action=HandlerActionType.DEFER_TO_WA,
                    action_parameters={"reason": f"PONDER failed: Could not retrieve thought {thought_item.thought_id} for ponder count check."},
                    action_selection_rationale="PONDER action failed due to inability to retrieve thought details."
                )

            current_ponder_count = thought_db_instance.ponder_count

            if current_ponder_count >= MAX_PONDER_ROUNDS:
                logging.warning(f"Thought ID {thought_item.thought_id} has reached max ponder rounds ({MAX_PONDER_ROUNDS}). Overriding to DEFER_TO_WA.")
                self.thought_queue_manager.update_thought_status(
                    thought_id=thought_item.thought_id,
                    new_status=ThoughtStatus(status="deferred"), # Or "failed"
                    round_processed=self.thought_queue_manager.current_round_number, # Mark as processed in this round
                    processing_result={"status": "Deferred due to max ponder rounds", "final_ponder_count": current_ponder_count},
                    ponder_notes=key_questions, # Keep last ponder notes
                    ponder_count=current_ponder_count # Record final ponder count
                )
                # Populate action_parameters for WBDPackage when deferring due to max ponder rounds
                defer_action_params = {
                    "reason": f"Thought reached maximum ponder rounds ({MAX_PONDER_ROUNDS}). Original ponder questions: {key_questions}",
                    "final_ponder_count": current_ponder_count,
                    "pdma_trace_id": thought_item.thought_id, # Use thought_id as trace_id
                    "autonomy_tier": 0, # Default autonomy tier
                    "context": str(thought_item.content), # Original thought content
                    "candidate_response": "N/A (Deferred due to max ponder rounds)",
                    "metrics": {"ponder_count": current_ponder_count},
                    "trigger": "MAX_PONDER_ROUNDS_REACHED"
                }
                return ActionSelectionPDMAResult(
                    context_summary_for_action_selection=final_action_result.context_summary_for_action_selection,
                    action_alignment_check=final_action_result.action_alignment_check,
                    selected_handler_action=HandlerActionType.DEFER_TO_WA,
                    action_parameters=defer_action_params,
                    action_selection_rationale=f"Ponder action overridden. Thought reached max ponder rounds ({MAX_PONDER_ROUNDS})."
                )
            else:
                new_ponder_count = current_ponder_count + 1
                logging.info(f"Thought ID {thought_item.thought_id} resulted in PONDER action (count: {new_ponder_count}). Questions: {key_questions}. Re-queueing.")
                
                success = self.thought_queue_manager.update_thought_status(
                    thought_id=thought_item.thought_id,
                    new_status=ThoughtStatus(status="pending"), # Reset to pending for re-queuing
                    round_processed=None, # Clear round_processed for re-queue
                    processing_result={"status": "Re-queued for Ponder", "ponder_action_details": final_action_result.model_dump()},
                    ponder_notes=key_questions,
                    ponder_count=new_ponder_count # Save incremented ponder_count
                )
                if success:
                    logging.info(f"Thought ID {thought_item.thought_id} successfully updated (ponder_count: {new_ponder_count}) and marked for re-processing.")
                    return None # Indicates internal re-processing, no final action for agent *yet*
                else:
                    logging.error(f"Failed to update thought ID {thought_item.thought_id} for re-processing Ponder. Proceeding with Ponder as terminal for safety.")
                    # Fallback: return the Ponder action if re-queueing fails, so it's not lost.
                    # Ensure the original ponder_count is part of the returned action if update failed.
                    final_action_result.action_parameters["ponder_count_at_failure"] = current_ponder_count
                    return final_action_result
        
        if final_action_result and final_action_result.selected_handler_action != HandlerActionType.PONDER:
            success = self.thought_queue_manager.update_thought_status(
                thought_id=thought_item.thought_id,
                new_status=ThoughtStatus(status="completed"),
                round_processed=self.thought_queue_manager.current_round_number,
                processing_result={"status": "Completed", "final_action": final_action_result.selected_handler_action.value}
            )
            if success:
                logging.info(f"Thought ID {thought_item.thought_id} successfully updated to completed.")
            else:
                logging.error(f"Failed to update thought ID {thought_item.thought_id} to completed.")
        
        return final_action_result # For all other actions

    def __repr__(self) -> str:
        return "<WorkflowCoordinator (Async)>"
