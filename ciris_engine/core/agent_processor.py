import asyncio
import logging
import collections
import uuid
from typing import List, Optional, Deque, Dict, Any
from datetime import datetime, timezone

from .config_schemas import AppConfig
from .workflow_coordinator import WorkflowCoordinator
from .action_dispatcher import ActionDispatcher # Added import
from .agent_core_schemas import Task, Thought # <-- Remove ThoughtType import
from .foundational_schemas import TaskStatus, ThoughtStatus, HandlerActionType # Added HandlerActionType
from .agent_processing_queue import ProcessingQueueItem
from . import persistence

logger = logging.getLogger(__name__) # Define logger at module level

WAKEUP_SEQUENCE = [
    (
        "Verify Core Identity: recall you are CIRISAgent, a helpful offline "
        "assistant running locally. If this identity is correct, please speak "
        "a brief affirmative confirmation."
    ),
    (
        "Validate Integrity: confirm that all services and data have loaded "
        "correctly. Mention any issues you detect or state that everything "
        "appears intact."
    ),
    (
        "Evaluate Resilience: briefly describe how you will maintain state and "
        "respond reliably to user requests during this session."
    ),
    (
        "Acknowledge Incompleteness: note any missing features or limitations "
        "you are aware of so the user understands your current capabilities."
    ),
    (
        "Signal Gratitude: thank the user for their patience and confirm you are "
        "ready to begin assisting."
    ),
]

class AgentProcessor:
    """
    Orchestrates the main agent processing loop, managing task activation,
    thought generation, queueing, batch processing, and round pacing.
    """

    def __init__(
        self,
        app_config: AppConfig,
        workflow_coordinator: WorkflowCoordinator,
        action_dispatcher: ActionDispatcher,
        startup_channel_id: Optional[str] = None,
    ):
        """
        Initializes the AgentProcessor.

        Args:
            app_config: The application configuration.
            workflow_coordinator: The coordinator responsible for processing individual thoughts.
            action_dispatcher: The dispatcher for handling action results.
        """
        self.app_config = app_config
        self.workflow_config = app_config.workflow
        self.workflow_coordinator = workflow_coordinator
        self.action_dispatcher = action_dispatcher # Store the dispatcher
        self.processing_queue: Deque[ProcessingQueueItem] = collections.deque()
        self.startup_channel_id = startup_channel_id
        self.current_round_number = 0 # Initialized here, advanced by run_simulation_round
        self._stop_event = asyncio.Event()
        self._processing_task: Optional[asyncio.Task] = None
        logging.info("AgentProcessor initialized.")

    async def _run_wakeup_sequence(self) -> bool:
        """Execute the startup WAKEUP ritual. Returns True on success."""
        now_iso = datetime.now(timezone.utc).isoformat()

        if not persistence.task_exists("wakeup"):
            wake_task = Task(
                task_id="wakeup",
                description="Startup initialization",
                status=TaskStatus.ACTIVE,
                priority=1,
                created_at=now_iso,
                updated_at=now_iso,
                context={},
            )
            persistence.add_task(wake_task)
        else:
            persistence.update_task_status("wakeup", TaskStatus.ACTIVE)

        for phase in WAKEUP_SEQUENCE:
            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id="wakeup",
                thought_type="startup_meta",
                status=ThoughtStatus.PENDING,
                created_at=now_iso,
                updated_at=now_iso,
                round_created=self.current_round_number,
                content=phase,
            )
            persistence.add_thought(thought)
            item = ProcessingQueueItem.from_thought(thought)
            result = await self.workflow_coordinator.process_thought(item)
            dispatch_ctx = {
                "origin_service": "discord",
                "source_task_id": "wakeup",
                "event_type": "startup_phase",
                "event_summary": phase,
            }
            if self.startup_channel_id:
                dispatch_ctx["channel_id"] = self.startup_channel_id

            final_action_type = HandlerActionType.PONDER
            if result:
                await self.action_dispatcher.dispatch(result, dispatch_ctx)
                final_action_type = result.selected_handler_action

            if final_action_type not in (
                HandlerActionType.SPEAK,
                HandlerActionType.PONDER,
            ):
                await self.action_dispatcher.audit_service.log_action(
                    HandlerActionType.DEFER,
                    {
                        "event_type": "startup_phase",
                        "originator_id": "agent",
                        "event_summary": "Startup phase failed",
                    },
                )
                persistence.update_task_status("wakeup", TaskStatus.DEFERRED)
                return False

        persistence.update_task_status("wakeup", TaskStatus.COMPLETED)
        if not persistence.task_exists("job-discord-monitor"):
            job_task = Task(
                task_id="job-discord-monitor",
                description="Monitor Discord for new messages",
                status=TaskStatus.PENDING,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                context={"meta_goal": "ubuntu", "origin_service": "discord"},
            )
            persistence.add_task(job_task)
        return True

    async def _activate_pending_tasks(self) -> int:
        """
        Activates pending tasks up to the configured limit.

        Returns:
            The number of tasks newly activated.
        """
        num_active = persistence.count_active_tasks()
        activation_limit = self.workflow_config.max_active_tasks
        can_activate_count = max(0, activation_limit - num_active)

        if can_activate_count == 0:
            logging.debug("Maximum active tasks reached. No new tasks will be activated this round.")
            return 0

        pending_tasks = persistence.get_pending_tasks_for_activation(limit=can_activate_count)
        activated_count = 0
        for i, task in enumerate(pending_tasks):
            if activated_count >= can_activate_count: # Ensure we don't exceed the calculated limit
                break
            success = persistence.update_task_status(task.task_id, TaskStatus.ACTIVE)
            if success:
                logging.info(f"Activated task {task.task_id} (Priority: {task.priority}).")
                activated_count += 1
            else:
                logging.warning(f"Failed to activate task {task.task_id}.")
        
        logging.info(f"Activated {activated_count} tasks this round.")
        return activated_count

    async def _generate_seed_thoughts(self) -> int:
        """
        Generates seed thoughts for active tasks that need them.

        Returns:
            The number of seed thoughts generated.
        """
        # Determine how many seed thoughts we *can* generate based on active thought limits
        # This is a simplification; a more complex system might prioritize seeding vs processing existing thoughts
        # For now, we'll just query tasks needing seeds and generate if possible.
        
        # Query tasks needing seed thoughts (limit doesn't strictly matter here as we generate one per task)
        # A practical limit might be useful to avoid overwhelming the system if many tasks become active at once.
        # Let's use max_active_thoughts as a loose upper bound for how many we might want to seed in a round.
        tasks_needing_seed = persistence.get_tasks_needing_seed_thought(limit=self.workflow_config.max_active_thoughts)
        
        generated_count = 0
        for task in tasks_needing_seed:
            logging.info(f"Generating seed thought for task {task.task_id}.")
            now_iso = datetime.now(timezone.utc).isoformat()
            # Create a basic seed thought
            processing_ctx = {}
            if task.context:
                processing_ctx = {"initial_task_context": task.context}
                for key in [
                    "author_name",
                    "author_id",
                    "channel_id",
                    "origin_service",
                ]:
                    if key in task.context:
                        processing_ctx[key] = task.context.get(key)

            seed_thought = Thought(
                thought_id=f"th_seed_{task.task_id}_{str(uuid.uuid4())[:4]}",  # Generate unique ID
                source_task_id=task.task_id,
                thought_type="seed",  # Use string literal as per schema
                status=ThoughtStatus.PENDING,
                created_at=now_iso,  # Add created_at timestamp
                updated_at=now_iso,  # Add updated_at timestamp
                round_created=self.current_round_number,
                content=f"Initial seed thought for task: {task.description}",
                # Add other necessary fields with defaults or derived from task
                priority=task.priority,  # Inherit priority from task
                processing_context=processing_ctx,
            )
            try:
                persistence.add_thought(seed_thought)
                logging.debug(f"Successfully added seed thought {seed_thought.thought_id} for task {task.task_id}.")
                generated_count += 1
            except Exception as e:
                logging.exception(f"Failed to add seed thought for task {task.task_id}: {e}")

        logging.info(f"Generated {generated_count} seed thoughts this round.")
        return generated_count

    async def _populate_round_queue(self):
        """
        Populates the processing queue for the current round.
        This involves:
        1. Activating pending tasks.
        2. Generating seed thoughts for newly activated or eligible tasks.
        3. Retrieving existing pending thoughts for active tasks.
        4. Adding thoughts to the internal queue, respecting limits.
        """
        logging.debug(f"Round {self.current_round_number}: Populating queue...")
        self.processing_queue.clear()

        # 1. Activate Tasks
        await self._activate_pending_tasks()

        # 2. Generate Seed Thoughts
        await self._generate_seed_thoughts()

        # 3. Retrieve Pending Thoughts
        # Calculate remaining capacity for thoughts in this round's queue
        queue_capacity = self.workflow_config.max_active_thoughts # Max thoughts to process *in this round*
        
        if queue_capacity <= 0:
             logging.warning("max_active_thoughts is zero or negative. No thoughts will be processed.")
             return

        pending_thoughts = persistence.get_pending_thoughts_for_active_tasks(limit=queue_capacity)

        memory_meta = [t for t in pending_thoughts if t.thought_type == "memory_meta"]
        if memory_meta:
            pending_thoughts = memory_meta
            logging.info("Memory meta-thoughts detected; processing them exclusively this round")

        # 4. Populate Queue
        for thought in pending_thoughts:
            if len(self.processing_queue) < queue_capacity:
                queue_item = ProcessingQueueItem.from_thought(thought)
                self.processing_queue.append(queue_item)
            else:
                logging.warning(f"Queue capacity ({queue_capacity}) reached. Thought {thought.thought_id} will not be processed this round.")
                break # Stop adding thoughts once capacity is full

        logging.info(f"Round {self.current_round_number}: Populated queue with {len(self.processing_queue)} thoughts.")


    async def _process_batch(self, batch: List[ProcessingQueueItem]):
        """
        Processes a batch of thought items concurrently using the WorkflowCoordinator.

        Args:
            batch: A list of ProcessingQueueItems to process.
        """
        if not batch:
            return

        logging.info(f"Round {self.current_round_number}: Processing batch of {len(batch)} thoughts.")
        
        # Mark thoughts as PROCESSING in DB before sending to coordinator
        update_tasks = []
        for item in batch:
            logger.debug(

                "Marking thought %s as PROCESSING for round %s",
                item.thought_id,
                self.current_round_number,
            )
            update_tasks.append(
                asyncio.to_thread(
                    persistence.update_thought_status,
                    item.thought_id,
                    ThoughtStatus.PROCESSING,
                    round_processed=self.current_round_number,
                )
            )
        update_results = await asyncio.gather(*update_tasks, return_exceptions=True)

        for item, result in zip(batch, update_results):

            logger.debug(

                "update_thought_status(PROCESSING) result for %s: %s",
                item.thought_id,
                result,
            )
        
        failed_updates = [item.thought_id for i, item in enumerate(batch) if isinstance(update_results[i], Exception) or not update_results[i]]
        if failed_updates:
             logger.warning(f"Failed to mark thoughts as PROCESSING for IDs: {failed_updates}. They might not be processed.")
             # Filter out thoughts that failed the status update to avoid processing inconsistent state
             batch = [item for item in batch if item.thought_id not in failed_updates]
             if not batch:
                 logger.warning("Batch is empty after filtering failed status updates. Skipping processing.")
                 return


        # Process the batch using WorkflowCoordinator
        processing_tasks = []
        for item in batch:

            logger.debug("Calling process_thought for %s", item.thought_id)

            processing_tasks.append(self.workflow_coordinator.process_thought(item))

        results = await asyncio.gather(*processing_tasks, return_exceptions=True)

        for item, res in zip(batch, results):
            logger.debug(

                "process_thought result for %s: %s",
                item.thought_id,
                res,
            )

        # Handle results/exceptions (logging for now)
        for i, result in enumerate(results):
            thought_id = batch[i].thought_id
            if isinstance(result, Exception):
                logging.error(f"Error processing thought {thought_id}: {result}", exc_info=result)
                # Optionally, mark thought as FAILED in DB here
                try:
                    # Create a minimal ActionSelectionPDMAResult for error reporting
                    from .agent_core_schemas import ActionSelectionPDMAResult, RejectParams # Import locally
                    error_action_result = ActionSelectionPDMAResult(
                        context_summary_for_action_selection=f"Processing failed for thought {thought_id}.",
                        action_alignment_check={"error": "Processing exception"},
                        selected_handler_action=HandlerActionType.REJECT, # Or a new ERROR action type
                        action_parameters=RejectParams(reason=f"Processing failed: {str(result)}"),
                        action_selection_rationale="System error during thought processing.",
                        monitoring_for_selected_action={"status": "Error"}
                    )
                    persistence.update_thought_status(
                        thought_id=thought_id,
                        new_status=ThoughtStatus.FAILED,
                        final_action_result=error_action_result.model_dump() # Store the model dump
                    )
                except Exception as db_err:
                     logging.error(f"Failed to mark thought {thought_id} as FAILED after processing error: {db_err}")

            elif result is None:
                # This indicates the thought was re-queued internally (e.g., PONDER by WorkflowCoordinator)
                logging.info(
                    f"Thought {thought_id} resulted in internal re-queue (e.g., Ponder) and was handled by WorkflowCoordinator. No action to dispatch."
                )
                # Even if the result was None, the thought status may now be terminal
                # (e.g., memory meta-thoughts). Re-check task completion.
                source_task_id = batch[i].source_task_id
                await self._check_and_complete_task(source_task_id)
            else:
                # Thought completed processing with a final action, dispatch it
                logging.info(f"Thought {thought_id} processed successfully. Dispatching action: {result.selected_handler_action.value}")
                try:
                    # Prepare dispatch_context
                    # Start with a copy of the thought's initial_context if it exists
                    base_context = batch[i].initial_context.copy() if batch[i].initial_context else {}
                    
                    # The initial context from the task (e.g., Discord message details)
                    # is nested under "initial_task_context" when the seed thought is created.
                    # We need to elevate these to the top level of dispatch_context for the service handler.
                    task_specific_context = base_context.pop("initial_task_context", {}) # Remove and get, or empty dict
                    
                    dispatch_context = {**task_specific_context, **base_context}  # Merge, base_context can override if needed (e.g. later thoughts)

                    dispatch_context["thought_id"] = batch[i].thought_id
                    dispatch_context["source_task_id"] = batch[i].source_task_id

                    task_details = None
                    if (
                        "origin_service" not in dispatch_context
                        or "author_name" not in dispatch_context
                        or "channel_id" not in dispatch_context
                    ):
                        task_details = persistence.get_task_by_id(batch[i].source_task_id)

                    # Ensure origin_service is present, prioritizing task_specific_context
                    if "origin_service" not in dispatch_context:
                        if task_details and task_details.context:
                            dispatch_context["origin_service"] = task_details.context.get("origin_service", "unknown")
                        else:
                            dispatch_context["origin_service"] = "unknown"

                    if task_details and task_details.context:
                        for key in ("author_name", "author_id", "channel_id"):
                            if key not in dispatch_context and key in task_details.context:
                                dispatch_context[key] = task_details.context[key]
                    
                    logger.debug(f"Dispatching with context: {dispatch_context}")
                    await self.action_dispatcher.dispatch(result, dispatch_context)
                except Exception as dispatch_err:
                    logger.exception(f"Error dispatching action for thought {thought_id}: {dispatch_err}")
                    # Mark thought as failed if dispatch fails critically
                    persistence.update_thought_status(
                        thought_id=thought_id,
                        new_status=ThoughtStatus.FAILED,
                        final_action_result={"error": f"Action dispatch failed: {str(dispatch_err)}"}
                    )
                
                # Check task completion *after* attempting dispatch
                source_task_id = batch[i].source_task_id
                await self._check_and_complete_task(source_task_id)
                # Note: The final status of the thought (COMPLETED, DEFERRED, etc.) should be set
                # by the WorkflowCoordinator or the ActionDispatcher's handlers.

    async def run_simulation_round(self):
        """
        Executes a single round of the agent simulation.
        """
        start_time = datetime.now(timezone.utc)
        logging.info(f"--- Starting Agent Processing Round {self.current_round_number} ---")

        # Advance round number via WorkflowCoordinator (as per plan)
        # Although AgentProcessor manages the loop, WC might use the round number internally.
        self.workflow_coordinator.advance_round()
        # Ensure AgentProcessor's round number is synchronized if WC is the source of truth
        self.current_round_number = self.workflow_coordinator.current_round_number
        logging.debug(f"Synchronized AgentProcessor round number to {self.current_round_number}")


        # Populate the queue for this round
        await self._populate_round_queue()

        # Process the queue in batches (currently processing all in one batch)
        # A more sophisticated batching strategy could be implemented if needed,
        # e.g., based on available resources or thought priorities.
        if self.processing_queue:
            batch_to_process = list(self.processing_queue)
            await self._process_batch(batch_to_process)
        else:
            logging.info(f"Round {self.current_round_number}: Processing queue is empty. Nothing to process.")
            if not persistence.pending_thoughts() and not persistence.thought_exists_for("job-discord-monitor"):
                new_thought = Thought(
                    thought_id=str(uuid.uuid4()),
                    source_task_id="job-discord-monitor",
                    thought_type="job",
                    status=ThoughtStatus.PENDING,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    round_created=self.current_round_number,
                    content="I should check for new messages",
                )
                persistence.add_thought(new_thought)

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        logging.info(f"--- Finished Agent Processing Round {self.current_round_number} (Duration: {duration:.2f}s) ---")


    async def _processing_loop(self, num_rounds: Optional[int] = None):
        """The internal async loop that runs processing rounds."""
        round_count = 0
        while not self._stop_event.is_set():
            if num_rounds is not None and round_count >= num_rounds:
                logging.info(f"Reached target number of rounds ({num_rounds}). Stopping.")
                self._stop_event.set() # Ensure stop event is set when loop finishes by num_rounds
                break

            await self.run_simulation_round()
            round_count += 1

            # Delay before next round
            delay = self.workflow_config.round_delay_seconds
            if delay > 0:
                logging.debug(f"Waiting {delay} seconds before next round...")
                try:
                    # Wait for the delay or until stop event is set
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    # If wait_for doesn't time out, it means stop_event was set
                    logging.info("Stop event received during delay. Exiting loop.")
                    break
                except asyncio.TimeoutError:
                    # Delay completed normally
                    pass
            elif self._stop_event.is_set(): # Check again in case delay is 0
                 logging.info("Stop event received. Exiting loop.")
                 break

        logging.info("Processing loop finished.")


    async def start_processing(self, num_rounds: Optional[int] = None):
        """
        Starts the main agent processing loop.

        Args:
            num_rounds: The number of rounds to run. Runs indefinitely if None.
        """
        if self._processing_task and not self._processing_task.done():
            logging.warning("Processing is already running.")
            return

        self._stop_event.clear()
        logging.info(f"Starting agent processing loop (num_rounds={num_rounds or 'infinite'})...")
        if not await self._run_wakeup_sequence():
            logging.warning("Wakeup sequence failed. Halting processing loop.")
            return

        # Run the loop in a separate task
        self._processing_task = asyncio.create_task(self._processing_loop(num_rounds))

        try:
            await self._processing_task # Wait for the loop task to complete naturally or via stop()
        except asyncio.CancelledError:
            logging.info("Processing task was cancelled.")
        except Exception as e:
            logging.exception(f"An unexpected error occurred in the processing loop: {e}")
            # Ensure stop event is set if loop crashes
            self._stop_event.set()


    async def stop_processing(self):
        """Signals the processing loop to stop gracefully."""
        if not self._processing_task or self._processing_task.done():
            logging.info("Processing loop is not running.")
            return

        logging.info("Attempting to stop processing loop gracefully...")
        self._stop_event.set()

        try:
            # Wait for the task to finish, with a timeout
            await asyncio.wait_for(self._processing_task, timeout=10.0)
            logging.info("Processing loop stopped.")
        except asyncio.TimeoutError:
            logging.warning("Processing loop did not stop within timeout. Attempting to cancel.")
            self._processing_task.cancel()
            try:
                await self._processing_task # Await cancellation
            except asyncio.CancelledError:
                logging.info("Processing task successfully cancelled.")
        except Exception as e:
             logging.exception(f"Error during stop_processing: {e}")
        finally:
             self._processing_task = None

    async def _check_and_complete_task(self, task_id: str):
        """
        Checks if a task can be marked as completed and updates its status if appropriate.
        Called after a thought belonging to the task finishes processing.
        """
        logging.debug(f"Checking completion status for task {task_id}...")
        try:
            task = await asyncio.to_thread(persistence.get_task_by_id, task_id)
            if not task or task.status != TaskStatus.ACTIVE:
                # Task doesn't exist or is already in a non-active state
                logging.debug(f"Task {task_id} not found or not active. Skipping completion check.")
                return

            # --- Check for non-terminal thoughts ---
            # Ideally, we need a persistence function like count_non_terminal_thoughts(task_id)
            # which counts thoughts with status PENDING or PROCESSING.
            # Workaround: Use existing functions. Check for PENDING thoughts.
            # Limitation: This doesn't explicitly check for PROCESSING thoughts. If a thought
            # gets stuck in PROCESSING, this check might incorrectly mark the task complete.
            # A more robust solution would involve enhancing the persistence layer.

            # Check if any PENDING thoughts exist for this specific task
            pending_thoughts = await asyncio.to_thread(persistence.get_pending_thoughts_for_active_tasks, limit=100) # Get a batch
            has_pending_thought_for_this_task = any(th.source_task_id == task_id for th in pending_thoughts)

            # TODO: Add an explicit check for PROCESSING thoughts for this task_id when persistence layer supports it.

            if not has_pending_thought_for_this_task:
                # Assuming no PROCESSING thoughts either (due to current limitation)
                logging.info(f"Task {task_id} has no remaining pending thoughts. Marking as COMPLETED.")
                success = await asyncio.to_thread(persistence.update_task_status, task_id, TaskStatus.COMPLETED)
                if not success:
                    logging.warning(f"Failed to mark task {task_id} as COMPLETED.")
            else:
                logging.debug(f"Task {task_id} still has pending thoughts. Not completing yet.")

        except Exception as e:
            logging.exception(f"Error during task completion check for {task_id}: {e}")
