"""
Thought management functionality for the CIRISAgent processor.
Handles thought generation, queueing, and processing using v1 schemas.
"""
import logging
import uuid
import collections
from typing import List, Optional, Dict, Any, Deque
from datetime import datetime, timezone

from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
from ciris_engine import persistence
from ciris_engine.processor.processing_queue import ProcessingQueueItem

logger = logging.getLogger(__name__)


class ThoughtManager:
    """Manages thought generation, queueing, and processing."""
    
    def __init__(self, max_active_thoughts: int = 50):
        self.max_active_thoughts = max_active_thoughts
        self.processing_queue: Deque[ProcessingQueueItem] = collections.deque()
        
    def generate_seed_thought(
        self,
        task: Task,
        round_number: int = 0
    ) -> Optional[Thought]:
        """Generate a seed thought for a task using v1 schema."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Build context from task
        context = {}
        if task.context:
            context = {"initial_task_context": task.context.copy()}
            # Copy relevant fields to top level for dispatch
            for key in ["author_name", "author_id", "channel_id", "origin_service"]:
                if key in task.context:
                    context[key] = task.context.get(key)
        
        thought = Thought(
            thought_id=f"th_seed_{task.task_id}_{str(uuid.uuid4())[:4]}",
            source_task_id=task.task_id,
            thought_type="seed",  # v1 uses simpler type
            status=ThoughtStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            round_number=round_number,  # v1 uses single round_number
            content=f"Initial seed thought for task: {task.description}",
            context=context,  # v1 uses 'context' not 'processing_context'
            ponder_count=0,
        )
        
        try:
            persistence.add_thought(thought)
            logger.debug(f"Generated seed thought {thought.thought_id} for task {task.task_id}")
            return thought
        except Exception as e:
            logger.error(f"Failed to add seed thought for task {task.task_id}: {e}")
            return None
    
    def generate_seed_thoughts(self, tasks: List[Task], round_number: int) -> int:
        """Generate seed thoughts for multiple tasks."""
        generated_count = 0
        
        for task in tasks:
            thought = self.generate_seed_thought(task, round_number)
            if thought:
                generated_count += 1
        
        logger.info(f"Generated {generated_count} seed thoughts")
        return generated_count
    
    def create_job_thought(self, round_number: int) -> Optional[Thought]:
        """Create a job thought for Discord monitoring."""
        job_task_id = "job-discord-monitor"
        
        if not persistence.task_exists(job_task_id):
            logger.warning(f"Job task '{job_task_id}' not found")
            return None
        
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            source_task_id=job_task_id,
            thought_type="job",
            status=ThoughtStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            round_number=round_number,
            content="I should check for new messages and events.",
        )
        
        try:
            persistence.add_thought(thought)
            logger.info(f"Created job thought {thought.thought_id}")
            return thought
        except Exception as e:
            logger.error(f"Failed to create job thought: {e}")
            return None
    
    def populate_queue(self, round_number: int) -> int:
        """
        Populate the processing queue for the current round.
        Returns the number of thoughts added to queue.
        """
        self.processing_queue.clear()
        
        if self.max_active_thoughts <= 0:
            logger.warning("max_active_thoughts is zero or negative")
            return 0
        
        # Get pending thoughts
        pending_thoughts = persistence.get_pending_thoughts_for_active_tasks(
            limit=self.max_active_thoughts
        )
        
        # Check for memory meta-thoughts (priority processing)
        memory_meta = [t for t in pending_thoughts if t.thought_type == "memory_meta"]
        if memory_meta:
            pending_thoughts = memory_meta
            logger.info("Memory meta-thoughts detected; processing them exclusively")
        
        # Add to queue
        added_count = 0
        for thought in pending_thoughts:
            if len(self.processing_queue) < self.max_active_thoughts:
                queue_item = ProcessingQueueItem.from_thought(thought)
                self.processing_queue.append(queue_item)
                added_count += 1
            else:
                logger.warning(
                    f"Queue capacity ({self.max_active_thoughts}) reached. "
                    f"Thought {thought.thought_id} will not be processed this round."
                )
                break
        
        logger.info(f"Round {round_number}: Populated queue with {added_count} thoughts")
        return added_count
    
    def get_queue_batch(self) -> List[ProcessingQueueItem]:
        """Get all items from the processing queue as a batch."""
        return list(self.processing_queue)
    
    def mark_thoughts_processing(
        self,
        batch: List[ProcessingQueueItem],
        round_number: int
    ) -> List[ProcessingQueueItem]:
        """
        Mark thoughts as PROCESSING before sending to workflow coordinator.
        Returns the successfully updated items.
        """
        updated_items = []
        
        for item in batch:
            try:
                # v1 schema: update_thought_status doesn't have round_processed param
                # We'll need to update persistence layer or handle differently
                success = persistence.update_thought_status(
                    thought_id=item.thought_id,
                    new_status=ThoughtStatus.PROCESSING,
                    round_processed=round_number,  # This might need adaptation
                )
                if success:
                    updated_items.append(item)
                else:
                    logger.warning(f"Failed to mark thought {item.thought_id} as PROCESSING")
            except Exception as e:
                logger.error(f"Error marking thought {item.thought_id} as PROCESSING: {e}")
        
        return updated_items
    
    def create_follow_up_thought(
        self,
        parent_thought: Thought,
        content: str,
        thought_type: str = "follow_up",
        round_number: int = 0
    ) -> Optional[Thought]:
        """Create a follow-up thought from a parent thought."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Inherit context from parent
        context = parent_thought.context.copy() if parent_thought.context else {}
        
        thought = Thought(
            thought_id=f"th_followup_{parent_thought.thought_id[:8]}_{str(uuid.uuid4())[:4]}",
            source_task_id=parent_thought.source_task_id,
            thought_type=thought_type,
            status=ThoughtStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            round_number=round_number,
            content=content,
            context=context,
            ponder_count=0,
            parent_thought_id=parent_thought.thought_id,  # v1 uses parent_thought_id
        )
        
        try:
            persistence.add_thought(thought)
            logger.info(f"Created follow-up thought {thought.thought_id}")
            return thought
        except Exception as e:
            logger.error(f"Failed to create follow-up thought: {e}")
            return None
    
    def handle_idle_state(self, round_number: int) -> bool:
        """
        Handle idle state when no thoughts are pending.
        Returns True if a job thought was created.
        """
        job_task_id = "job-discord-monitor"
        
        if not persistence.pending_thoughts() and not persistence.thought_exists_for(job_task_id):
            # Ensure job task exists
            if not persistence.task_exists(job_task_id):
                logger.warning(f"Task '{job_task_id}' not found. Creating it.")
                now_iso = datetime.now(timezone.utc).isoformat()
                job_task = Task(
                    task_id=job_task_id,
                    description="Monitor Discord for new messages and events.",
                    status=TaskStatus.PENDING,
                    priority=0,
                    created_at=now_iso,
                    updated_at=now_iso,
                    context={
                        "meta_goal": "continuous_monitoring",
                        "origin_service": "agent_processor_fallback"
                    },
                )
                persistence.add_task(job_task)
            
            # Create job thought
            thought = self.create_job_thought(round_number)
            return thought is not None
        
        return False
    
    def get_pending_thought_count(self) -> int:
        """Get count of pending thoughts."""
        return persistence.count_pending_thoughts()
    
    def get_processing_thought_count(self) -> int:
        """Get count of thoughts currently processing."""
        return persistence.count_thoughts_by_status(ThoughtStatus.PROCESSING)