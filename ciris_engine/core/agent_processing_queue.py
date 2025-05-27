import collections
from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Import the NEW Thought model from agent_core_schemas
from ..schemas.agent_core_schemas_v1 import Thought

class ProcessingQueueItem(BaseModel):
    """
    Represents an item loaded into an in-memory processing queue (e.g., collections.deque).
    This is a lightweight representation derived from a Thought, optimized for queue processing.
    """
    thought_id: str
    source_task_id: str
    thought_type: str # Corresponds to Thought.thought_type (string)
    # Content for the queue item can be richer than Thought.content if needed,
    # e.g., holding initial structured data before it's summarized into Thought.content (str).
    content: Union[str, Dict[str, Any]]
    priority: int # Derived from the associated Thought
    raw_input_string: Optional[str] = Field(default=None, description="The original input string that generated this thought, if applicable.")
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial context when the thought was first received/generated for processing.")
    ponder_notes: Optional[List[str]] = Field(default=None, description="Key questions from a previous Ponder action if this item is being re-queued.")
    
    # Note: Storing the full Thought object directly in a queue item can make it heavy.
    # If the full Thought object is needed during queue processing,
    # it can be fetched by its thought_id from persistent storage.
    # This keeps the queue item itself lean.

    @classmethod
    def from_thought(
        cls,
        thought_instance: Thought,
        raw_input: Optional[str] = None,
        initial_ctx: Optional[Dict[str, Any]] = None,
        # Allow overriding content for the queue item if it differs from thought.content
        queue_item_content: Optional[Union[str, Dict[str, Any]]] = None
    ) -> "ProcessingQueueItem":
        """
        Creates a ProcessingQueueItem from a Thought instance.
        """
        final_initial_ctx = initial_ctx if initial_ctx is not None else thought_instance.context

        # Use provided queue_item_content if available, otherwise default to thought_instance.content
        resolved_content = queue_item_content if queue_item_content is not None else thought_instance.content

        return cls(
            thought_id=thought_instance.thought_id,
            source_task_id=thought_instance.source_task_id,
            thought_type=thought_instance.thought_type,
            content=resolved_content,
            priority=thought_instance.priority, # Now available on Thought model
            raw_input_string=raw_input if raw_input is not None else str(thought_instance.content), # Default raw_input to stringified content
            initial_context=final_initial_ctx if final_initial_ctx is not None else {},
            ponder_notes=thought_instance.ponder_notes
        )

# Type alias for the queue itself
ProcessingQueue = collections.deque[ProcessingQueueItem]

# Regarding "ThoughtQueueContext":
# The `initial_context` field in `ProcessingQueueItem` can hold context specific to that item.
# If a broader context for the entire queue's processing round or a batch of thoughts
# is needed, a separate model could be defined here. For example:
#
# class AgentProcessingBatchContext(BaseModel):
#     current_processing_round: int
#     overall_agent_status: Optional[str] = None # e.g., "normal", "degraded", "high_alert"
#     active_system_directives: Optional[List[str]] = None
#     # ... other relevant contextual information for a batch of processing
#
# This `AgentProcessingBatchContext` could then be passed alongside the `ProcessingQueue`
# to the parts of the system that manage and consume the queue.
# For now, such a model is not created unless further specified.
