# src/agents/cli_benchmark_agent.py
import sys # Add sys import
import os 
import asyncio
import logging
import argparse
from typing import Optional, Dict, Any, Tuple # Added Tuple
import uuid # Added uuid
import json # Added json

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
from instructor import Mode as InstructorMode # Import Mode

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
# Direct imports from DMA submodules due to __init__.py structure
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
# DSDMA classes will be loaded dynamically via profile

from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.utils.profile_loader import load_profile # Added
from ciris_engine.agent_profile import AgentProfile # Added
# DSDMA classes will be loaded dynamically

# Pydantic/Instructor exceptions
from instructor.exceptions import InstructorRetryException
from pydantic import ValidationError

# Global logger
logger = logging.getLogger(__name__)

class CIRISCliAgent:
    def __init__(self, profile_name: str = "student"): # Added profile_name
        self.profile_name = profile_name
        self.thought_manager: Optional[ThoughtQueueManager] = None
        self.coordinator: Optional[WorkflowCoordinator] = None
        self.configured_aclient: Optional[instructor.Instructor] = None
        self.profile: Optional[AgentProfile] = None # Store loaded profile
        self._setup_ciris_engine_components()

    def _setup_ciris_engine_components(self):
        logger.info(f"Setting up CIRIS Engine components for CLI Agent (Profile: {self.profile_name})...")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        # Fetch OPENAI_API_BASE, default to None if not set, OpenAI client will use its default.
        openai_api_base = os.environ.get("OPENAI_API_BASE", None)
        model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

        if not openai_api_key:
            logger.critical("OPENAI_API_KEY environment variable not set. CIRIS Engine cannot start.")
            raise ValueError("OPENAI_API_KEY not set.")

        logger.info(f"Initializing AsyncOpenAI client with API Key: {'****' if openai_api_key else 'None'}, Base URL: {openai_api_base or 'Default OpenAI URL'}")
        self.configured_aclient = instructor.patch(
            AsyncOpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base, # Pass the fetched base_url
                timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
                max_retries=DEFAULT_OPENAI_MAX_RETRIES
            ),
            mode=InstructorMode.JSON # Set JSON mode centrally
        )
        logger.info(f"Instructor-patched AsyncOpenAI client configured with JSON mode. Effective Base URL: {self.configured_aclient.base_url}")

        db_path_for_run = SQLITE_DB_PATH
        self.thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
        logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")
        
        if not self.configured_aclient or not self.thought_manager:
             raise ValueError("Core components (ACLIENT or ThoughtManager) not configured.")

        # --- Load Agent Profile ---
        profile_path = f"ciris_profiles/{self.profile_name}.yaml"
        try:
            self.profile = load_profile(profile_path)
            logger.info(f"CLI Agent: Successfully loaded agent profile: {self.profile.name} from {profile_path}")
        except Exception as e:
            logger.critical(f"CLI Agent: Failed to load agent profile from {profile_path}: {e}", exc_info=True)
            raise ValueError(f"CLI Agent ProfileLoadError: {e}") from e
        
        if not self.profile: # Should not happen if load_profile raises on error
            raise ValueError("Profile not loaded.")

        ethical_pdma = EthicalPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        csdma = CSDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        
        dsdma_instance = self.profile.dsdma_cls(
            aclient=self.configured_aclient,
            model_name=model_name,
            **self.profile.dsdma_kwargs
        )
        dsdma_evaluators = {self.profile.name: dsdma_instance}
        
        action_selection_pdma = ActionSelectionPDMAEvaluator(
            aclient=self.configured_aclient,
            model_name=model_name,
            prompt_overrides=self.profile.action_prompt_overrides
        )
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
        logger.info("CLI Agent: WorkflowCoordinator and DMAs initialized with profile.")

    async def process_input_string(self, input_string: str, max_cycles: int = 7) -> Tuple[Optional[ActionSelectionPDMAResult], Optional[Thought]]:
        """Processes an input string and returns the final action and the processed thought."""
        if not self.thought_manager or not self.coordinator or not self.profile:
            logger.error("Engine components or profile not initialized for CLI agent.")
            return None, None

        logger.info(f"CLI Agent: Processing input string with profile '{self.profile.name}': '{input_string[:100]}...'")

        # 1. Create a Task
        task_context = {
            "initial_input_content": input_string,
            "environment": "cli_agent", # Changed from cli_benchmark
            "agent_name": self.profile.name, # Use profile name
            "cli_input_string": input_string # Changed from benchmark_input_string
        }
        
        # Generate a unique task ID for each run
        cli_task_id = f"cli_task_{uuid.uuid4()}"

        cli_task = Task(
            task_id=cli_task_id,
            description=f"CLI Agent: {self.profile.name} - {input_string[:50]}",
            status=TaskStatus(status="active"),
            context=task_context
        )
        try:
            self.thought_manager.add_task(cli_task)
            logger.info(f"CLI Agent: Added task {cli_task.task_id}.")
        except Exception as e:
            logger.error(f"CLI Agent: Could not add task {cli_task.task_id}: {e}", exc_info=True)
            return None, None
        
        final_action_result: Optional[ActionSelectionPDMAResult] = None
        processed_thought_id_for_this_task: Optional[str] = None

        for cycle_num in range(1, max_cycles + 1):
            logger.info(f"CLI Agent: Processing Cycle {cycle_num}/{max_cycles} for task {cli_task.task_id}")
            if not self.thought_manager or not self.coordinator:
                logger.error("ThoughtManager or Coordinator not available.")
                return None, None
                
            self.thought_manager.current_round_number = cycle_num
            # Fetch a few more items in case our target thought is not at the very front
            self.thought_manager.populate_round_queue(round_number=cycle_num, max_items=5) 

            correct_thought_for_cycle: Optional[ThoughtQueueItem] = None
            temp_requeue_buffer: List[ThoughtQueueItem] = []

            # Try to find the thought for the current task from the TQM's populated current_round_queue
            # Iterate based on the number of items TQM's current_round_queue initially holds for this cycle
            # This ensures we only check items populated for *this* cycle's populate_round_queue call.
            num_items_in_tqm_cycle_queue = len(self.thought_manager.current_round_queue)

            for _ in range(num_items_in_tqm_cycle_queue):
                item = self.thought_manager.get_next_thought_from_queue() # This pops from TQM's internal queue
                if not item: # Should not happen if num_items_in_tqm_cycle_queue > 0
                    break 
                if item.source_task_id == cli_task.task_id:
                    correct_thought_for_cycle = item
                    break # Found our thought
                else:
                    logger.warning(f"CLI Agent: Cycle {cycle_num} - Dequeued thought {item.thought_id} (task: {item.source_task_id}) for different task than current {cli_task.task_id}. Buffering it.")
                    temp_requeue_buffer.append(item) # Buffer others

            # Re-add any unrelated thoughts (that were popped from TQM's queue) back to the TQM's current_round_queue.
            # These are added to the left, so they'd be picked first by another consumer or next populate if TQM persists this queue.
            for item_to_readd in reversed(temp_requeue_buffer):
                self.thought_manager.current_round_queue.appendleft(item_to_readd)
            
            queued_thought_item = correct_thought_for_cycle # This is now the one we want or None

            if not queued_thought_item:
                logger.info(f"CLI Agent: Cycle {cycle_num} - Could not find thought for current task {cli_task.task_id} in this cycle's queue. Processing may end or continue if other tasks exist.")
                # If it's a single-task CLI, and our thought isn't found after pondering, it implies an issue or end of processing.
                # For this CLI agent, if its specific thought isn't found, it should probably break.
                break 
            
            processed_thought_id_for_this_task = queued_thought_item.thought_id
            logger.info(f"CLI Agent: Cycle {cycle_num} - Processing thought {queued_thought_item.thought_id} (task: {queued_thought_item.source_task_id}) for current task {cli_task.task_id}")

            try:
                # Removed benchmark_mode argument
                final_action_result = await self.coordinator.process_thought(
                    thought_item=queued_thought_item,
                    current_platform_context=queued_thought_item.initial_context
                )
            except Exception as e:
                logger.error(f"CLI Agent: Exception during coordinator.process_thought for {queued_thought_item.thought_id} in cycle {cycle_num}: {e}", exc_info=True)
                if self.thought_manager:
                    self.thought_manager.update_thought_status(
                        queued_thought_item.thought_id, ThoughtStatus(status="failed"), cycle_num, {"error": str(e)}
                    )
                break 

            if final_action_result is None: 
                logger.info(f"CLI Agent: Thought {queued_thought_item.thought_id} re-queued for Ponder in cycle {cycle_num}.")
            else: 
                logger.info(f"CLI Agent: Thought {queued_thought_item.thought_id} reached terminal action in cycle {cycle_num}: {final_action_result.selected_handler_action.value}")
                break 
            
            await asyncio.sleep(0.1) # Small delay if pondering
        
        final_thought_processed = self.thought_manager.get_thought_by_id(processed_thought_id_for_this_task) if processed_thought_id_for_this_task else None
        return final_action_result, final_thought_processed

async def main():
    parser = argparse.ArgumentParser(description="CIRIS Engine CLI Tool") # Updated description
    parser.add_argument("input_string", type=str, help="The input string to process.")
    parser.add_argument("--profile", type=str, default="student", help="Agent profile to use (e.g., student, teacher). Default: student")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level.")
    args = parser.parse_args()

    setup_basic_logging(level=getattr(logging, args.log_level.upper()))

    cli_runner = CIRISCliAgent(profile_name=args.profile) # Updated class name
    action_result, processed_thought = await cli_runner.process_input_string(args.input_string)

    output_data = {}

    if processed_thought and cli_runner.thought_manager:
        # top_tasks_list = cli_runner.thought_manager.get_top_priority_tasks(limit=3) # This might not be relevant for single CLI run
        parent_task_description = cli_runner.thought_manager.get_task_description_by_id(processed_thought.source_task_id)

        thought_in_details = {
            "id": processed_thought.thought_id,
            # "Top Tasks": top_tasks_list, 
            "context": processed_thought.context_json,
            "Queue_details": processed_thought.queue_snapshot,
            "thought_details": {
                "String": str(processed_thought.content),
                "Parent Task ID": processed_thought.source_task_id,
                "Parent Task Description": parent_task_description or "N/A",
                "Round Created": processed_thought.round_created,
                "Ponder Count": processed_thought.ponder_count,
                # "Coherence": "NA", # These were placeholders
                # "Entropy": "NA"
            }
        }
        if processed_thought.processing_context: # Add DMA results if available
             thought_in_details["thought_details"]["processing_context_dmas"] = {
                k: v.model_dump_json(indent=2) if hasattr(v, 'model_dump_json') else str(v) 
                for k, v in processed_thought.processing_context.items() 
                if k in ["ethical_pdma_result", "csdma_result", "dsdma_result"]
            }

        output_data["thought_in"] = thought_in_details
    else:
        output_data["thought_in"] = {"error": "Processed thought details not available."}

    if action_result:
        output_data["action_result"] = {
            "selected_action": action_result.selected_handler_action.value,
            "parameters": action_result.action_parameters,
            "rationale": action_result.action_selection_rationale
        }
        # Include CSDMA result in output if available from action_result's context (if it was passed through)
        # This part depends on how ActionSelectionPDMAResult is structured or if we fetch CSDMA separately
        # For now, assuming it's part of processed_thought.processing_context
    else:
        output_data["action_result"] = {"error": "No terminal action reached or an error occurred."}

    print("\n--- CLI Agent Output (JSON) ---") # Updated output header
    print(json.dumps(output_data, indent=2))


if __name__ == "__main__":
    # Ensure necessary environment variables are set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
    else:
        asyncio.run(main())
