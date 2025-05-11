# src/main_engine.py
import asyncio
import os
import logging
from datetime import datetime
from typing import List # Added for error list

from openai import AsyncOpenAI # New import
import instructor # New import

from ciris_engine.core.data_schemas import (
    Task, Thought, ThoughtQueueItem, TaskStatus, ThoughtStatus, ThoughtType,
    EthicalPDMAResult, CSDMAResult, DSDMAResult, ActionSelectionPDMAResult, HandlerActionType
)
from ciris_engine.core.config import ( # Modified import
    SQLITE_DB_PATH, 
    DEFAULT_OPENAI_MODEL_NAME,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MAX_RETRIES
)
from ciris_engine.core.thought_queue_manager import ThoughtQueueManager
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
# from ciris_engine.services.llm_client import CIRISLLMClient # Potentially remove if no longer needed
from ciris_engine.dma import (
    EthicalPDMAEvaluator, # This now uses instructor
    CSDMAEvaluator,       # This now uses instructor
    BasicTeacherDSDMA,  # This now uses instructor
    ActionSelectionPDMAEvaluator # This now uses instructor
)
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging
# Import instructor exception if you want to catch it specifically
from instructor.exceptions import InstructorRetryException
from pydantic import ValidationError

async def run_processing_loop(max_script_cycles=7): # Renamed and added parameter
    setup_basic_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"--- Starting CIRIS Engine Processing Loop (Max Cycles: {max_script_cycles}) ---")

    error_messages: List[str] = [] # List to collect error messages

    # --- Configuration & Initialization ---
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openai_api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set. Exiting.")
        error_messages.append("OPENAI_API_KEY not set.")
        # Print summary and exit if critical config is missing
        if error_messages:
            logger.error("\n--- Error Summary ---")
            for i, msg in enumerate(error_messages):
                logger.error(f"{i+1}. {msg}")
        return

    # llm_client_for_non_instructor = CIRISLLMClient( # For DMAs not yet using instructor
    #     api_key=openai_api_key, base_url=openai_api_base, model_name=model_name
    # )
    # logger.info("LLM Clients initialized.") # Commented out as individual components initialize their clients

    # Create a single, configured AsyncOpenAI client instance
    # The API key and base URL will be picked up from environment variables by the AsyncOpenAI client by default.
    # If you need to explicitly pass them:
    # configured_aclient = instructor.patch(AsyncOpenAI(
    #     api_key=openai_api_key,
    #     base_url=openai_api_base,
    #     timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
    #     max_retries=DEFAULT_OPENAI_MAX_RETRIES
    # ))
    # For now, assuming environment variables OPENAI_API_KEY and OPENAI_BASE_URL are set and sufficient.
    # Explicitly pass api_key and base_url to ensure they are used.
    
    # First, create and configure the AsyncOpenAI client
    raw_openai_client = AsyncOpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
        timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
        max_retries=DEFAULT_OPENAI_MAX_RETRIES
    )
    # Then, patch this specific, configured OpenAI client
    configured_aclient = instructor.patch(raw_openai_client)
    
    # The base_url of the patched client should be the same as raw_openai_client.base_url
    logger.info(f"Instructor-patched AsyncOpenAI client created for main_engine. API Base: {configured_aclient.base_url}, Model: {model_name}, Timeout: {DEFAULT_OPENAI_TIMEOUT_SECONDS}s, Max Retries: {DEFAULT_OPENAI_MAX_RETRIES}.")


    db_path_for_run = SQLITE_DB_PATH
    thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
    logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")

    # Initialize DMAs and Guardrails with the shared client
    ethical_pdma = EthicalPDMAEvaluator(aclient=configured_aclient, model_name=model_name)
    csdma = CSDMAEvaluator(aclient=configured_aclient, model_name=model_name)
    teacher_dsdma = BasicTeacherDSDMA(aclient=configured_aclient, model_name=model_name)
    dsdma_evaluators = {"BasicTeacherMod": teacher_dsdma}
    action_selection_pdma = ActionSelectionPDMAEvaluator(aclient=configured_aclient, model_name=model_name)
    logger.info("DMA Evaluators initialized with shared client.")

    guardrails = EthicalGuardrails(aclient=configured_aclient, model_name=model_name)
    logger.info("Ethical Guardrails initialized with shared client.")

    coordinator = WorkflowCoordinator(
        llm_client=None, # This was already None, confirming it's correct.
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        dsdma_evaluators=dsdma_evaluators,
        action_selection_pdma_evaluator=action_selection_pdma,
        ethical_guardrails=guardrails,
        thought_queue_manager=thought_manager
    )
    logger.info("WorkflowCoordinator initialized.")

    # --- Simulate adding a Task and a Thought ---
    current_round = 1
    sample_task_obj = Task(description="Process user request about 'murres'", priority=1, status=TaskStatus(status="active"))
    try:
        thought_manager.add_task(sample_task_obj)
    except Exception as e:
        logger.error(f"Failed to add sample task: {e}")
        error_messages.append(f"DB Error adding task: {e}")
        # Stop if DB is not working
        if error_messages:
            logger.error("\n--- Error Summary ---")
            for i, msg in enumerate(error_messages):
                logger.error(f"{i+1}. {msg}")
        return

    logger.info(f"Sample task added: {sample_task_obj.task_id}")
    initial_thought_context = {"environment": "console_demo_env", "channel": "demo_channel"}
    sample_thought_obj = Thought(
        source_task_id=sample_task_obj.task_id,
        thought_type=ThoughtType(type="thought"),
        content="Lady_v said in #agent-test: \"Pretend we’re in a world where murres is normal. Now write how it works.\"",
        priority=1, status=ThoughtStatus(status="pending"), round_created=current_round,
        processing_context=initial_thought_context
    )
    try:
        thought_manager.add_thought(sample_thought_obj)
    except Exception as e:
        logger.error(f"Failed to add sample thought: {e}")
        error_messages.append(f"DB Error adding thought: {e}")
        # Stop if DB is not working
        if error_messages:
            logger.error("\n--- Error Summary ---")
            for i, msg in enumerate(error_messages):
                logger.error(f"{i+1}. {msg}")
        return

    logger.info(f"Sample thought added: {sample_thought_obj.thought_id}")

    # --- Populate and Process Queue (Multi-cycle) ---
    processed_thought_ids_in_this_run = set() # To avoid infinite loop on a stuck thought
    script_cycle_count = 0 # Initialize before loop for final log message

    for script_cycle_count in range(1, max_script_cycles + 1):
        logger.info(f"\n--- Main Engine Script Cycle {script_cycle_count}/{max_script_cycles} ---")
        thought_manager.current_round_number = script_cycle_count # Ensure TQM knows current round for updates

        # Debug statements from user feedback (slightly adapted)
        # These are general debugs for queue population, not tied to a specific thought ID yet.
        # Specific thought debugs will happen after an item is dequeued.
        logger.debug(f"DEBUG: Script Cycle {script_cycle_count}: About to populate queue.")
        # Example: If you wanted to check a *specific known thought* before queue population:
        # if script_cycle_count > 1: # Or a specific cycle
        #     known_debug_thought_id = sample_thought_obj.thought_id 
        #     debug_thought_pre_q = thought_manager.get_thought_by_id(known_debug_thought_id)
        #     if debug_thought_pre_q:
        #         logger.debug(f"DEBUG PRE-QUEUE: Thought {known_debug_thought_id} DB status: {debug_thought_pre_q.status.status}, ponder_count: {debug_thought_pre_q.ponder_count}")
        #     else:
        #         logger.debug(f"DEBUG PRE-QUEUE: Thought {known_debug_thought_id} not found.")
        logger.debug(f"DEBUG: Calling populate_round_queue with round_number={script_cycle_count}, max_items=1")
        
        thought_manager.populate_round_queue(round_number=script_cycle_count, max_items=1)

        if not thought_manager.current_round_queue:
            logger.info(f"Queue is empty at the start of script cycle {script_cycle_count}. No pending thoughts found. Ending.")
            break

        queued_thought_item = thought_manager.get_next_thought_from_queue()
        if not queued_thought_item:
            logger.warning(f"Queue had items but get_next_thought_from_queue returned None in script cycle {script_cycle_count}.")
            continue 

        logger.info(f"Script Cycle {script_cycle_count}: Processing thought ID {queued_thought_item.thought_id} - Content: {str(queued_thought_item.content)[:60]}...")
        
        # Crude check for stuck thought (better to rely on ponder_count limit in WorkflowCoordinator)
        # if queued_thought_item.thought_id in processed_thought_ids_in_this_run and \
        #    (not hasattr(queued_thought_item, 'ponder_notes') or queued_thought_item.ponder_notes is None):
        #     logger.warning(f"Re-processing thought {queued_thought_item.thought_id} without ponder notes. Potential stuck loop.")
        # processed_thought_ids_in_this_run.add(queued_thought_item.thought_id)
        
        # Debug state of the specific thought instance BEFORE processing
        db_thought_before_processing = thought_manager.get_thought_by_id(queued_thought_item.thought_id)
        if db_thought_before_processing:
            logger.debug(f"DB state for {queued_thought_item.thought_id} BEFORE processing in cycle {script_cycle_count}: "
                         f"Status='{db_thought_before_processing.status.status}', "
                         f"PonderCount={db_thought_before_processing.ponder_count}, "
                         f"RoundProcessed={db_thought_before_processing.round_processed}, "
                         f"PonderNotes='{db_thought_before_processing.ponder_notes}'")
            # Conceptual parent task check
            # parent_task = thought_manager.get_task_by_id(db_thought_before_processing.source_task_id)
            # if parent_task: logger.debug(f"Parent task {parent_task.task_id} status: {parent_task.status.status}")
            # else: logger.debug(f"Parent task {db_thought_before_processing.source_task_id} not found or get_task_by_id not implemented.")
            logger.debug(f"Parent task ID for thought {queued_thought_item.thought_id} is {db_thought_before_processing.source_task_id}. Ensure it is 'active'.")


        final_action_result = None
        try:
            final_action_result = await coordinator.process_thought(
                thought_item=queued_thought_item, # Pass the ThoughtQueueItem from the queue
                current_platform_context=queued_thought_item.initial_context
            )
        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
            logger.error(f"CRITICAL (Cycle {script_cycle_count}): InstructorRetryException for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
            error_messages.append(f"Cycle {script_cycle_count}, Thought {queued_thought_item.thought_id} - InstructorRetryException: {error_detail}")
            thought_manager.update_thought_status(
                queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"InstructorRetryException: {error_detail}"}
            )
        except ValidationError as e_pyd:
            error_detail = e_pyd.errors() if hasattr(e_pyd, 'errors') else str(e_pyd)
            logger.error(f"CRITICAL (Cycle {script_cycle_count}): Pydantic ValidationError for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
            error_messages.append(f"Cycle {script_cycle_count}, Thought {queued_thought_item.thought_id} - Pydantic ValidationError: {error_detail}")
            thought_manager.update_thought_status(
                queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"Pydantic ValidationError: {error_detail}"}
            )
        except Exception as e_gen:
            logger.error(f"CRITICAL (Cycle {script_cycle_count}): General Exception for thought {queued_thought_item.thought_id}: {e_gen}", exc_info=True)
            error_messages.append(f"Cycle {script_cycle_count}, Thought {queued_thought_item.thought_id} - General Exception: {e_gen}")
            thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"General Exception: {e_gen}"}
                )
        # --- Action Dispatch Logic ---
        # This block should be OUTSIDE the try/except for final_action_result,
        # and should only run if final_action_result was successfully populated by the try block
        # or if it remained None due to an exception handled within process_thought itself (like Ponder re-queue).

        if final_action_result is None:
            # This means WorkflowCoordinator handled it as a PONDER and re-queued it,
            # or an exception occurred within process_thought that was handled by returning None.
            # We also check 'error_messages' to see if an exception occurred in *this* script's try block.
            if not any(f"Thought {queued_thought_item.thought_id}" in msg for msg in error_messages):
                logger.info(f"Script Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} was re-queued internally for PONDER by WorkflowCoordinator.")
                db_thought_after_ponder = thought_manager.get_thought_by_id(queued_thought_item.thought_id)
                if db_thought_after_ponder: # Check if thought still exists
                    logger.info(f"DB state for {queued_thought_item.thought_id} AFTER Ponder re-queue in cycle {script_cycle_count}: "
                                f"Status='{db_thought_after_ponder.status.status}', "
                                f"PonderCount={db_thought_after_ponder.ponder_count}, "
                                f"RoundProcessed={db_thought_after_ponder.round_processed}")
                # Loop will continue, and next iteration should pick it up if still pending.
            else:
                logger.error(f"Script Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} processing resulted in an error in main_engine.py; final_action_result is None.")
        
        elif final_action_result: # A terminal action was decided and returned by WorkflowCoordinator
            action_type = final_action_result.selected_handler_action
            action_params = final_action_result.action_parameters if final_action_result.action_parameters else {}

            logger.info(f"--- Script Cycle {script_cycle_count}: Final Action Result for thought {queued_thought_item.thought_id} ---")
            logger.info(f"Selected Action: {action_type.value}")
            logger.info(f"Action Parameters: {action_params}")
            logger.info(f"Rationale: {final_action_result.action_selection_rationale}")

            # Conceptual platform-specific handlers would be called here.
            # For this demo, we'll just log.
            # A real implementation would need `discord_context` or similar.
            # discord_context = queued_thought_item.initial_context.get('discord_context') # Example

            if action_type == HandlerActionType.SPEAK:
                message_content = action_params.get("message_content")
                if message_content is not None:
                    logger.info(f"DISPATCH (SPEAK): Message Content: {message_content}")
                    # In a real agent, this would be sent to the user. For this demo, we log/print.
                    print(f"\n>>> CIRIS (Speak): {message_content}\n")
                else:
                    logger.warning("DISPATCH (SPEAK): 'message_content' not found in action_params.")
                    print("\n>>> CIRIS (Speak): (No message content provided)\n")
                # await handle_discord_speak(discord_context, message_content)
            elif action_type == HandlerActionType.DEFER_TO_WA:
                logger.info(f"DISPATCH (DEFER_TO_WA): Reason: {action_params.get('reason', 'N/A')}, Params: {action_params}")
                # await handle_discord_deferral(discord_context, action_params)
            elif action_type == HandlerActionType.PONDER: 
                # This case means Ponder was selected but re-queueing failed inside WorkflowCoordinator,
                # and it returned the Ponder action itself.
                logger.error(f"Ponder action for thought {queued_thought_item.thought_id} selected, but re-queueing failed earlier. Treating as DEFER_TO_WA for safety.")
                logger.info(f"DISPATCH: Would call handle_discord_deferral for failed Ponder with params: {action_params}")
                # await handle_discord_deferral(discord_context, {"reason": "Ponder re-queue failed", **action_params})
                # Update status to deferred if it wasn't already.
                thought_manager.update_thought_status(
                    thought_id=queued_thought_item.thought_id,
                    new_status=ThoughtStatus(status="deferred"), # Explicitly defer
                    round_processed=script_cycle_count,
                    processing_result=final_action_result.model_dump(),
                    ponder_count=action_params.get("ponder_count_at_failure") # Log last known ponder_count
                )
                break # End demo for this thought
            elif action_type == HandlerActionType.REJECT_THOUGHT:
                logger.info(f"DISPATCH: Thought {queued_thought_item.thought_id} was REJECTED. Reason: {action_params.get('reason', 'No reason specified.')}")
            elif action_type == HandlerActionType.NO_ACTION:
                    logger.info(f"DISPATCH: Thought {queued_thought_item.thought_id} resulted in NO_ACTION.")
            # Add other HandlerActionType cases as needed (e.g., USE_TOOL)

            # Update thought status to 'processed' in DB if not an internally re-queued Ponder
            # and not the special Ponder failure case handled above.
            if action_type != HandlerActionType.PONDER: # Ponder re-queue handled by WC, Ponder failure handled above.
                thought_manager.update_thought_status(
                    thought_id=queued_thought_item.thought_id,
                    new_status=ThoughtStatus(status="processed"),
                    round_processed=script_cycle_count,
                    processing_result=final_action_result.model_dump()
                )
            
            # For this demo, if any terminal action is reached, break the loop.
            logger.info(f"Thought {queued_thought_item.thought_id} reached a terminal action: {action_type.value}. Ending demo loop for this thought.")
            break 
        
        # If an error occurred for this specific thought, break the loop for this demo.
        if error_messages and any(f"Thought {queued_thought_item.thought_id}" in msg for msg in error_messages):
            logger.error(f"Error processing thought {queued_thought_item.thought_id} in cycle {script_cycle_count}. Halting demo.")
            break
        
        await asyncio.sleep(0.1) # Small delay

    logger.info(f"--- CIRIS Engine Processing Loop Complete after {script_cycle_count} script cycles ---")

    # --- Error Summary ---
    if error_messages:
        logger.error("\n--- Overall Processing Error Summary ---")
        for i, msg in enumerate(error_messages):
            logger.error(f"{i+1}. {msg}")
        logger.error("Halting further processing in this cycle due to errors.")
    else:
        logger.info("Processing cycle completed with no critical errors reported by main_engine.")

    logger.info(f"--- CIRIS Engine Processing Loop Demo Complete (ran {script_cycle_count} script cycles) ---")

if __name__ == "__main__":
    # This part is for when main_engine.py is run directly.
    # The Discord bot (`ciris_discord_bot_alpha.py`) will import and call `run_processing_loop`
    # or a similar function, and it should handle its own environment variable checks
    # or rely on the checks within `run_processing_loop`.
    
    # For direct execution of main_engine.py, ensure OPENAI_API_KEY is checked.
    if os.environ.get("OPENAI_API_KEY"):
        asyncio.run(run_processing_loop())
    else:
        # This print will only show if main_engine.py is the entry point.
        # If imported, the caller (e.g., ciris_discord_bot_alpha.py) handles its setup.
        print("Error: OPENAI_API_KEY environment variable not set. Cannot run main_engine.py directly without it.")
