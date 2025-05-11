# src/agents/cli_benchmark_agent.py
import sys # Add sys import
import os # os is already imported, ensure it's used for path manipulation
import asyncio
import logging
import argparse
from typing import Optional, Dict, Any

# --- Add src directory to sys.path ---
# This allows the script to find modules in the 'src' directory (e.g., ciris_engine)
# when run from the project root or as an absolute path.
current_script_path = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_script_path, '..', '..')) # This should point to CIRISAgent/
# If ciris_engine is directly under src, and agents is also under src, then src_path should be CIRISAgent/src
project_src_path = os.path.join(src_path, 'src') # Path to CIRISAgent/src

# Let's adjust to correctly point to the 'src' directory that contains 'ciris_engine'
# If script is in /home/emoore/CIRISAgent/src/agents/cli_benchmark_agent.py
# __file__ is /home/emoore/CIRISAgent/src/agents/cli_benchmark_agent.py
# os.path.dirname(__file__) is /home/emoore/CIRISAgent/src/agents
# os.path.join(os.path.dirname(__file__), '..') is /home/emoore/CIRISAgent/src
path_to_src_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if path_to_src_directory not in sys.path:
    sys.path.insert(0, path_to_src_directory)
# --- End sys.path modification ---

from openai import AsyncOpenAI
import instructor

# CIRIS Engine imports
from ciris_engine.core.data_schemas import (
    Task, Thought, ThoughtQueueItem, TaskStatus, ThoughtStatus, ThoughtType,
    HandlerActionType, ActionSelectionPDMAResult
)
from ciris_engine.core.config import (
    SQLITE_DB_PATH,
    DEFAULT_OPENAI_MODEL_NAME,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MAX_RETRIES
)
from ciris_engine.core.thought_queue_manager import ThoughtQueueManager
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.dma import (
    EthicalPDMAEvaluator,
    CSDMAEvaluator,
    BasicTeacherDSDMA,
    ActionSelectionPDMAEvaluator
)
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging

# Pydantic/Instructor exceptions
from instructor.exceptions import InstructorRetryException
from pydantic import ValidationError

# Global logger
logger = logging.getLogger(__name__)

class CIRISBenchmarkCLI:
    def __init__(self):
        self.thought_manager: Optional[ThoughtQueueManager] = None
        self.coordinator: Optional[WorkflowCoordinator] = None
        self.configured_aclient: Optional[instructor.Instructor] = None
        self._setup_ciris_engine_components()

    def _setup_ciris_engine_components(self):
        logger.info("Setting up CIRIS Engine components for CLI benchmark...")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

        if not openai_api_key:
            logger.critical("OPENAI_API_KEY environment variable not set. CIRIS Engine cannot start.")
            raise ValueError("OPENAI_API_KEY not set.")

        self.configured_aclient = instructor.patch(AsyncOpenAI(
            timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
            max_retries=DEFAULT_OPENAI_MAX_RETRIES
        ))
        logger.info("Instructor-patched AsyncOpenAI client configured.")

        # Use an in-memory SQLite DB for benchmark runs to keep them isolated
        # or a specific benchmark DB file. For simplicity, using default path but
        # be mindful if running multiple benchmarks concurrently.
        db_path_for_run = SQLITE_DB_PATH # Or ":memory:" for true in-memory
        self.thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
        logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")
        
        if not self.configured_aclient:
             raise ValueError("AsyncOpenAI client not configured.")
        if not self.thought_manager:
            raise ValueError("ThoughtQueueManager not initialized.")

        ethical_pdma = EthicalPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        csdma = CSDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        teacher_dsdma = BasicTeacherDSDMA(aclient=self.configured_aclient, model_name=model_name)
        dsdma_evaluators = {"BasicTeacherMod": teacher_dsdma}
        action_selection_pdma = ActionSelectionPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        guardrails = EthicalGuardrails(aclient=self.configured_aclient, model_name=model_name)

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

    async def process_input_string(self, input_string: str, max_cycles: int = 7) -> Optional[ActionSelectionPDMAResult]:
        if not self.thought_manager or not self.coordinator:
            logger.error("Engine components not initialized.")
            return None

        logger.info(f"Processing input string for benchmark: '{input_string[:100]}...'")

        # 1. Create a Task
        cli_task = Task(
            task_id="cli_benchmark_task_01", # Static ID for simplicity in benchmark
            description=f"CLI Benchmark Task for input: {input_string[:50]}",
            status=TaskStatus(status="active")
        )
        try:
            self.thought_manager.add_task(cli_task)
        except Exception as e: # Catch if task already exists or other DB issues
            logger.warning(f"Could not add task {cli_task.task_id} (may already exist or DB error): {e}")


        # 2. Create a Thought
        initial_context: Dict[str, Any] = {
            "environment": "cli_benchmark_tool",
            "user_input_string": input_string
            # No discord_message_obj here
        }
        cli_thought = Thought(
            source_task_id=cli_task.task_id,
            content=input_string,
            status=ThoughtStatus(status="pending"),
            round_created=1, # Start with round 1
            processing_context=initial_context
        )
        try:
            self.thought_manager.add_thought(cli_thought)
            logger.info(f"Added thought {cli_thought.thought_id} for benchmark.")
        except Exception as e:
            logger.error(f"Failed to add thought for benchmark: {e}")
            return None
        
        # 3. Processing Loop
        # For CLI benchmark, we directly process the created thought and loop if it's Pondered.
        
        current_thought_to_process: Thought = cli_thought
        final_action_result: Optional[ActionSelectionPDMAResult] = None

        for cycle_num in range(1, max_cycles + 1):
            logger.info(f"Benchmark Processing Cycle {cycle_num}/{max_cycles} for thought {current_thought_to_process.thought_id}")
            if not self.thought_manager or not self.coordinator: # Should be initialized
                logger.error("ThoughtManager or Coordinator not available.")
                return None
                
            self.thought_manager.current_round_number = cycle_num

            # Convert the DB Thought object to a ThoughtQueueItem for the coordinator
            # This simulates what populate_round_queue + get_next_thought_from_queue would do for this specific thought
            thought_queue_item = ThoughtQueueItem.from_thought_db(
                current_thought_to_process,
                raw_input=str(current_thought_to_process.content), # Or however raw_input is derived
                initial_ctx=current_thought_to_process.processing_context
            )
            
            # Update status to 'processing' before sending to coordinator (optional, but good practice)
            # self.thought_manager.update_thought_status(current_thought_to_process.thought_id, ThoughtStatus(status="processing"), cycle_num)

            try:
                final_action_result = await self.coordinator.process_thought(
                    thought_item=thought_queue_item,
                    current_platform_context=thought_queue_item.initial_context,
                    benchmark_mode=True # Pass benchmark_mode as True
                )
            except Exception as e:
                logger.error(f"Exception during coordinator.process_thought for {current_thought_to_process.thought_id} in cycle {cycle_num}: {e}", exc_info=True)
                if self.thought_manager:
                    self.thought_manager.update_thought_status(
                        current_thought_to_process.thought_id, ThoughtStatus(status="failed"), cycle_num, {"error": str(e)}
                    )
                break # Stop on error

            if final_action_result is None: # Ponder re-queue by coordinator
                logger.info(f"Thought {current_thought_to_process.thought_id} re-queued for Ponder in cycle {cycle_num}.")
                # Fetch the updated thought from DB to continue the loop with new ponder_count/notes
                updated_thought_from_db = self.thought_manager.get_thought_by_id(current_thought_to_process.thought_id)
                if updated_thought_from_db and updated_thought_from_db.status.status == "pending":
                    current_thought_to_process = updated_thought_from_db
                    logger.info(f"DB state for {current_thought_to_process.thought_id} AFTER Ponder re-queue: "
                                 f"Status='{current_thought_to_process.status.status}', "
                                 f"PonderCount={current_thought_to_process.ponder_count}, "
                                 f"PonderNotes='{current_thought_to_process.ponder_notes}'")
                else:
                    logger.error(f"Thought {current_thought_to_process.thought_id} was expected to be re-queued as 'pending' but found status: "
                                 f"{updated_thought_from_db.status.status if updated_thought_from_db else 'Not Found'}. Ending loop.")
                    break
            else: # Terminal action
                logger.info(f"Thought {current_thought_to_process.thought_id} reached terminal action in cycle {cycle_num}: {final_action_result.selected_handler_action.value}")
                if self.thought_manager:
                    self.thought_manager.update_thought_status(
                        current_thought_to_process.thought_id, 
                        ThoughtStatus(status="processed"), 
                        cycle_num, 
                        final_action_result.model_dump()
                    )
                break # End loop on terminal action
            
            await asyncio.sleep(0.1) # Small delay

        return final_action_result

async def main():
    parser = argparse.ArgumentParser(description="CIRIS Engine CLI Benchmark Tool")
    parser.add_argument("input_string", type=str, help="The input string to process as a thought.")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level.")
    args = parser.parse_args()

    setup_basic_logging(level=getattr(logging, args.log_level.upper()))

    cli_runner = CIRISBenchmarkCLI()
    final_result = await cli_runner.process_input_string(args.input_string)

    if final_result:
        action_type = final_result.selected_handler_action
        action_params = final_result.action_parameters if final_result.action_parameters else {}
        
        print(f"\n--- Benchmark Result ---")
        print(f"Final Action Type: {action_type.value}")

        if action_type == HandlerActionType.SPEAK:
            print(f"Message Content: {action_params.get('message_content', 'N/A')}")
        elif action_type == HandlerActionType.DEFER_TO_WA:
            print(f"Deferral Reason: {action_params.get('reason', 'N/A')}")
            if "final_ponder_count" in action_params:
                 print(f"Final Ponder Count: {action_params['final_ponder_count']}")
        elif action_type == HandlerActionType.PONDER: # Should not happen if loop breaks on terminal
            print(f"Ended on PONDER (unexpected for terminal): {action_params.get('key_questions', 'N/A')}")
        elif action_type == HandlerActionType.REJECT_THOUGHT:
            print(f"Rejection Reason: {action_params.get('reason', 'N/A')}")
        else:
            print(f"Action Parameters: {action_params}")
    else:
        print("\n--- Benchmark Result ---")
        print("No terminal action reached within max cycles or an error occurred.")
        # Optionally, retrieve and print the last known state of the thought from DB
        if cli_runner.thought_manager: # Check if thought_manager was initialized
            # Attempt to get the thought ID used. This is a bit indirect.
            # A better way would be to store the created thought_id in the class instance.
            # For now, this is a placeholder.
            logger.info("To see the final state of the thought, you might need to query the database manually if its ID is not readily available here.")


if __name__ == "__main__":
    # Ensure necessary environment variables are set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        # logger.error (already handled by setup)
    else:
        asyncio.run(main())
