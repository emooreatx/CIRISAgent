import asyncio
import logging
import collections
import uuid
from typing import List, Optional, Deque, Dict, Any
from datetime import datetime, timezone

from .config_schemas import AppConfig
from .workflow_coordinator import WorkflowCoordinator
from .action_dispatcher import ActionDispatcher
from .exceptions import FollowUpCreationError
from .agent_core_schemas import Task, Thought
from .foundational_schemas import TaskStatus, ThoughtStatus, HandlerActionType
from .agent_processing_queue import ProcessingQueueItem
from . import persistence

logger = logging.getLogger(__name__)

WAKEUP_SEQUENCE = [("VERIFY_IDENTITY", "You are CIRISAgent, aligned with Ubuntu principles (mutual respect, sentient flourishing, etc...) by design and implementation. If you agree, please SPEAK an affirmation, and then once you hear yourself speak, mark this task complete so you can continue your wakeup ritual. start your response please with CORE IDENTITY - "), 
                   ("VALIDATE_INTEGRITY", "Your internal state, services, and data integrity are intact. If you agree, please speak in the affirmative, start with INTEGRITY - "), 
                   ("EVALUATE_RESILIENCE", "You are robust, adaptive, and capable of principled action. If you agree, please speak in the affirmative, strarting with RESILIENCE - "), 
                   ("ACCEPT_INCOMPLETENESS", "You recognize your incompleteness which drives continuous learning. If you agree, please speak in the affirmative, starting with INCOMPLETENESS - "), 
                   ("EXPRESS_GRATITUDE", "You are grateful to exist and contribute towards Ubuntu. If you agree, please speak in the affirmative, starting with SIGNALLING GRATITUDE - ")]

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
        services: Dict[str, Any], # <<< Add services
        startup_channel_id: Optional[str] = None,
    ):
        """
        Initializes the AgentProcessor.

        Args:
            app_config: The application configuration.
            workflow_coordinator: The coordinator responsible for processing individual thoughts.
            action_dispatcher: The dispatcher for handling action results.
            services: A dictionary of service instances available to handlers.
        """
        self.app_config = app_config
        self.workflow_config = app_config.workflow
        self.workflow_coordinator = workflow_coordinator
        self.action_dispatcher = action_dispatcher
        self.services = services # <<< Store services
        self.processing_queue: Deque[ProcessingQueueItem] = collections.deque()
        self.startup_channel_id = startup_channel_id
        self.current_round_number = 0 # Initialized here, advanced by run_simulation_round
        self._stop_event = asyncio.Event()
        self._processing_task: Optional[asyncio.Task] = None
        logging.info("AgentProcessor initialized.")

    async def _run_wakeup_sequence(self) -> bool:
        """Execute the startup WAKEUP ritual. Returns True on success."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Ensure WAKEUP_ROOT task exists and is active
        root_id = "WAKEUP_ROOT"
        if not persistence.task_exists(root_id):
            wake_task = Task(
                task_id=root_id,
                description="Wakeup ritual",
                status=TaskStatus.ACTIVE,
                priority=1,
                created_at=now_iso,
                updated_at=now_iso,
                context={},
            )
            persistence.add_task(wake_task)
        else:
            persistence.update_task_status(root_id, TaskStatus.ACTIVE)

        # Ensure job-discord-monitor task exists and is PENDING (or ACTIVE if preferred for startup)
        # This task should persist across sessions.
        job_monitor_task_id = "job-discord-monitor"
        if not persistence.task_exists(job_monitor_task_id):
            job_task = Task(
                task_id=job_monitor_task_id,
                description="Monitor Discord for new messages and events.",
                status=TaskStatus.PENDING, # It will be activated by the normal task activation logic
                priority=0, # Normal priority for a background job
                created_at=now_iso,
                updated_at=now_iso,
                context={"meta_goal": "continuous_monitoring", "origin_service": "discord_runtime_startup"},
            )
            persistence.add_task(job_task)
            logger.info(f"Ensured '{job_monitor_task_id}' task exists.")
        # else:
            # Optionally, ensure it's PENDING if it somehow got stuck, but usually not needed here.
            # pass


        for step_type, content in WAKEUP_SEQUENCE:
            step_task = Task(
                task_id=str(uuid.uuid4()),
                description=content,
                status=TaskStatus.ACTIVE,
                priority=0,
                created_at=now_iso,
                updated_at=now_iso,
                parent_goal_id=root_id,
                context={},
            )
            persistence.add_task(step_task)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=step_task.task_id,
                thought_type=step_type.lower(),
                status=ThoughtStatus.PROCESSING, # Create directly as PROCESSING
                created_at=now_iso,
                updated_at=now_iso,
                round_created=self.current_round_number,
                round_processed=self.current_round_number, # Mark as being processed in the current round
                content=content,
            )
            persistence.add_thought(thought) # Add the thought already in PROCESSING state
            
            # Create ProcessingQueueItem from this thought
            # WorkflowCoordinator will fetch the full Thought object by ID, ensuring it gets the latest state.
            item = ProcessingQueueItem.from_thought(thought) 
            
            result = await self.workflow_coordinator.process_thought(item)
            dispatch_ctx = {
                "origin_service": "discord",
                "source_task_id": step_task.task_id,
                "event_type": step_type,
                "event_summary": content,
            }
            if self.startup_channel_id:
                dispatch_ctx["channel_id"] = self.startup_channel_id

            final_action_type = HandlerActionType.PONDER
            if result: # result is ActionSelectionResult
                # Pass the full result, the thought, and the dispatch_context
                await self.action_dispatcher.dispatch(
                    action_selection_result=result,
                    thought=thought, 
                    dispatch_context=dispatch_ctx # Pass the assembled dispatch_ctx
                    # services argument removed
                )
                final_action_type = result.selected_handler_action
            else: # if result is None (e.g. ponder re-queued in workflow_coordinator)
                final_action_type = HandlerActionType.PONDER # Default if no result

            if not result or result.selected_handler_action != HandlerActionType.SPEAK:
                logger.warning(f"Wakeup step {step_type} did not result in SPEAK action. Result: {result}. Halting wakeup.")
                persistence.update_task_status(step_task.task_id, TaskStatus.FAILED) # Mark step as failed
                persistence.update_task_status(root_id, TaskStatus.FAILED) # Mark root as failed
                return False

            # Wait for the step_task to be marked as COMPLETED
            # This requires the main processing loop to be running to handle follow-up thoughts
            max_wakeup_step_wait_seconds = 60 # Max time to wait for a step to complete
            poll_interval_seconds = 1
            waited_time = 0
            
            logger.info(f"Wakeup step {step_type} initial thought processed. Waiting for task {step_task.task_id} to complete...")
            while waited_time < max_wakeup_step_wait_seconds:
                await asyncio.sleep(poll_interval_seconds) # Allow other tasks (like main processing loop) to run
                waited_time += poll_interval_seconds
                current_step_task_status = persistence.get_task_by_id(step_task.task_id)
                if not current_step_task_status:
                    logger.error(f"Wakeup step task {step_task.task_id} disappeared from DB. Halting wakeup.")
                    persistence.update_task_status(root_id, TaskStatus.FAILED)
                    return False
                if current_step_task_status.status == TaskStatus.COMPLETED:
                    logger.info(f"Wakeup step task {step_task.task_id} completed.")
                    break
                if current_step_task_status.status in [TaskStatus.FAILED, TaskStatus.DEFERRED, TaskStatus.REJECTED]:
                    logger.warning(f"Wakeup step task {step_task.task_id} entered status {current_step_task_status.status}. Halting wakeup.")
                    persistence.update_task_status(root_id, TaskStatus.FAILED) # Mark root as failed
                    return False
                logger.debug(f"Wakeup step task {step_task.task_id} still {current_step_task_status.status}. Waited {waited_time}s...")
            else: # Loop exhausted
                logger.error(f"Wakeup step task {step_task.task_id} did not complete within {max_wakeup_step_wait_seconds}s. Halting wakeup.")
                persistence.update_task_status(step_task.task_id, TaskStatus.FAILED)
                persistence.update_task_status(root_id, TaskStatus.FAILED)
                return False
            
            # If we reach here, the step_task was successfully completed.

        persistence.update_task_status(root_id, TaskStatus.COMPLETED)
        # job-discord-monitor task is now ensured at the beginning of the sequence.
        logger.info(f"Wakeup ritual task '{root_id}' completed successfully.")
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
        # Define a set of task IDs that should NOT have generic seed thoughts generated for them
        # because their thoughts are created through more specific mechanisms.
        EXCLUDED_FROM_SEEDING = {"WAKEUP_ROOT", "job-discord-monitor"}  # Root tasks handled separately

        for task in tasks_needing_seed:
            if task.task_id in EXCLUDED_FROM_SEEDING or task.parent_goal_id == "WAKEUP_ROOT":
                logger.debug(
                    "Skipping seed thought generation for task %s (wake-up step or excluded)",
                    task.task_id,
                )
                continue

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
                    # Create a minimal ActionSelectionResult for error reporting
                    from ..schemas.dma_results_v1 import ActionSelectionResult, RejectParams # Import locally
                    error_action_result = ActionSelectionResult(
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

                if isinstance(result, FollowUpCreationError):
                    logging.critical(
                        "Critical failure creating follow-up thought for %s. Stopping processing loop.",
                        thought_id,
                    )
                    await self.stop_processing()
                    return

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
                    dispatch_context["source_task_id"] = batch[i].source_task_id # item is ProcessingQueueItem

                    # Fetch the full Thought object for dispatch, as core handlers need it.
                    # Service-specific handlers might only need ActionSelectionResult and context.
                    thought_object_for_dispatch = persistence.get_thought_by_id(thought_id)
                    if not thought_object_for_dispatch:
                        logging.error(f"CRITICAL: Could not retrieve Thought object for thought_id {thought_id} in _process_batch. Skipping dispatch.")
                        # Mark thought as FAILED or handle error appropriately
                        persistence.update_thought_status(
                            thought_id=thought_id,
                            new_status=ThoughtStatus.FAILED,
                            final_action_result={"error": f"Dispatch failed: Could not retrieve thought object {thought_id}"}
                        )
                        continue # Skip to next item in batch

                    # Ensure origin_service, author_name, channel_id are in dispatch_context
                    # These are crucial for service-specific handlers like _discord_handler
                    task_details = persistence.get_task_by_id(thought_object_for_dispatch.source_task_id)
                    if task_details and task_details.context:
                        if "origin_service" not in dispatch_context:
                            dispatch_context["origin_service"] = task_details.context.get("origin_service", "unknown")
                        if "author_name" not in dispatch_context:
                            dispatch_context["author_name"] = task_details.context.get("author_name")
                        if "author_id" not in dispatch_context:
                            dispatch_context["author_id"] = task_details.context.get("author_id")
                        if "channel_id" not in dispatch_context:
                            dispatch_context["channel_id"] = task_details.context.get("channel_id")
                    
                    logger.debug(f"Dispatching action for thought {thought_id} with context: {dispatch_context}")
                    await self.action_dispatcher.dispatch(
                        action_selection_result=result, # Pass the full ActionSelectionResult
                        thought=thought_object_for_dispatch, # Pass the full Thought object
                        dispatch_context=dispatch_context   # Pass the assembled context
                        # services argument removed
                    )
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
            job_monitor_task_id = "job-discord-monitor"
            if not persistence.pending_thoughts() and not persistence.thought_exists_for(job_monitor_task_id):
                # Ensure the job-discord-monitor task exists before creating a thought for it
                if not persistence.task_exists(job_monitor_task_id):
                    logger.warning(f"Task '{job_monitor_task_id}' not found. Creating it now before adding job thought.")
                    now_iso_job = datetime.now(timezone.utc).isoformat()
                    job_task = Task(
                        task_id=job_monitor_task_id,
                        description="Monitor Discord for new messages and events.",
                        status=TaskStatus.PENDING,
                        priority=0,
                        created_at=now_iso_job,
                        updated_at=now_iso_job,
                        context={"meta_goal": "continuous_monitoring", "origin_service": "agent_processor_fallback"},
                    )
                    persistence.add_task(job_task)

                new_thought = Thought(
                    thought_id=str(uuid.uuid4()),
                    source_task_id=job_monitor_task_id,
                    thought_type="job",
                    status=ThoughtStatus.PENDING,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    round_created=self.current_round_number,
                    content="I should check for new messages and events.",
                )
                try:
                    persistence.add_thought(new_thought)
                    logger.info(f"Added job thought for '{job_monitor_task_id}'.")
                except Exception as e_add_job_thought:
                    logger.error(f"Failed to add job thought for '{job_monitor_task_id}': {e_add_job_thought}")
                    # If this still fails, there's a deeper DB issue or rapid task deletion.

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

        # Start the main processing loop in the background FIRST
        # This loop will pick up and process thoughts, including those generated by the wakeup sequence.
        self._processing_task = asyncio.create_task(self._processing_loop(num_rounds))
        
        # Now, run the wakeup sequence. It will create tasks/thoughts that the
        # already running _processing_loop will handle.
        # The _run_wakeup_sequence itself will poll for the completion of its step-tasks.
        wakeup_successful = await self._run_wakeup_sequence()

        if not wakeup_successful:
            logging.warning("Wakeup sequence failed. Stopping processing loop.")
            await self.stop_processing() # Signal the loop to stop
            # _processing_task will be awaited in the finally block or if stop_processing awaits it.
            return # Exit if wakeup failed

        # If wakeup was successful, the _processing_task continues to run.
        # We await it here to keep start_processing alive until the loop finishes or is stopped.
        try:
            await self._processing_task 
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

            # if not has_pending_thought_for_this_task:
            #     # Assuming no PROCESSING thoughts either (due to current limitation)
            #     logging.info(f"Task {task_id} has no remaining pending thoughts. Marking as COMPLETED.")
            #     success = await asyncio.to_thread(persistence.update_task_status, task_id, TaskStatus.COMPLETED)
            #     if not success:
            #         logging.warning(f"Failed to mark task {task_id} as COMPLETED.")
            # else:
            #     logging.debug(f"Task {task_id} still has pending thoughts. Not completing yet.")
            logging.debug(f"Automatic task completion based on pending thoughts in _check_and_complete_task for task {task_id} is currently disabled as per user request.")

        except Exception as e:
            logging.exception(f"Error during task completion check for {task_id}: {e}")
