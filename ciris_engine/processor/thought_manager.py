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
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, ThoughtType, TaskStatus
from ciris_engine import persistence
from ciris_engine.processor.processing_queue import ProcessingQueueItem

logger = logging.getLogger(__name__)


class ThoughtManager:
    """Manages thought generation, queueing, and processing."""

    def __init__(self, max_active_thoughts: int = 50, default_channel_id: Optional[str] = None) -> None:
        self.max_active_thoughts = max_active_thoughts
        self.default_channel_id = default_channel_id
        self.processing_queue: Deque[ProcessingQueueItem] = collections.deque()
        
    def generate_seed_thought(
        self,
        task: Task,
        round_number: int = 0
    ) -> Optional[Thought]:
        """Generate a seed thought for a task - elegantly copy the context."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Simply copy the task's context to the thought
        # The schemas handle the nested structure elegantly
        context = task.context.model_copy() if task.context else None
        
        # Log for debugging but don't modify the context
        if context:
            logger.info(f"SEED_THOUGHT: Copying context for task {task.task_id}")
            # Check if we have channel context in the proper location
            if context.initial_task_context and context.initial_task_context.channel_context:
                channel_id = context.initial_task_context.channel_context.channel_id
                logger.info(f"SEED_THOUGHT: Found channel_id='{channel_id}' in initial_task_context.channel_context")
            elif context.system_snapshot and context.system_snapshot.channel_context:
                channel_id = context.system_snapshot.channel_context.channel_id
                logger.info(f"SEED_THOUGHT: Found channel_id='{channel_id}' in system_snapshot.channel_context")
            else:
                logger.warning(f"SEED_THOUGHT: No channel context found for task {task.task_id}")
        else:
            logger.critical(f"SEED_THOUGHT: Task {task.task_id} has NO context - POTENTIAL SECURITY BREACH")
            # Delete the malicious task immediately
            try:
                persistence.update_task_status(task.task_id, TaskStatus.FAILED)
                logger.critical(f"SEED_THOUGHT: Marked malicious task {task.task_id} as FAILED")
            except Exception as e:
                logger.critical(f"SEED_THOUGHT: Failed to mark malicious task {task.task_id} as FAILED: {e}")
            return None
        
        thought = Thought(
            thought_id=f"th_seed_{task.task_id}_{str(uuid.uuid4())[:4]}",
            source_task_id=task.task_id,
            thought_type=ThoughtType.STANDARD,
            status=ThoughtStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            round_number=round_number,
            content=f"Initial seed thought for task: {task.description}",
            context=context,
            thought_depth=0,
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

    
    def populate_queue(self, round_number: int) -> int:
        """
        Populate the processing queue for the current round.
        Returns the number of thoughts added to queue.
        """
        self.processing_queue.clear()
        
        if self.max_active_thoughts <= 0:
            logger.warning("max_active_thoughts is zero or negative")
            return 0
        
        pending_thoughts = persistence.get_pending_thoughts_for_active_tasks(
            limit=self.max_active_thoughts
        )
        
        memory_meta = [t for t in pending_thoughts if t.thought_type == ThoughtType.MEMORY]
        if memory_meta:
            pending_thoughts = memory_meta
            logger.info("Memory meta-thoughts detected; processing them exclusively")
        
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
        updated_items: List[Any] = []
        
        for item in batch:
            try:
                success = persistence.update_thought_status(
                    thought_id=item.thought_id,
                    status=ThoughtStatus.PROCESSING,
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
        thought_type: ThoughtType = ThoughtType.FOLLOW_UP,
        round_number: int = 0
    ) -> Optional[Thought]:
        """Create a follow-up thought from a parent thought."""
        now_iso = datetime.now(timezone.utc).isoformat()
        context = parent_thought.context.model_copy() if parent_thought.context else ThoughtContext()
        thought = Thought(
            thought_id=f"th_followup_{parent_thought.thought_id[:8]}_{str(uuid.uuid4())[:4]}",
            source_task_id=parent_thought.source_task_id,
            thought_type=thought_type,
            status=ThoughtStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            round_number=round_number,
            content=content,
            parent_thought_id=parent_thought.thought_id,
            context=context,
            thought_depth=parent_thought.thought_depth + 1,
            ponder_notes=None,
            final_action={},
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
        DISABLED: Idle mode is disabled.
        Returns False (no job thoughts created).
        """
        # Idle mode disabled - no automatic job creation
        logger.debug(
            "ThoughtManager.handle_idle_state called but idle mode is disabled for round %s", 
            round_number
        )
        return False
    
    def get_pending_thought_count(self) -> int:
        """Get count of pending thoughts for active tasks (strict gating)."""
        return persistence.count_pending_thoughts_for_active_tasks()
    
    def get_processing_thought_count(self) -> int:
        """Get count of thoughts currently processing."""
        return persistence.count_thoughts_by_status(ThoughtStatus.PROCESSING)