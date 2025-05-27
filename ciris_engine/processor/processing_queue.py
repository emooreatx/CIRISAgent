import collections
from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from ciris_engine.schemas.agent_core_schemas_v1 import Thought

class ProcessingQueueItem(BaseModel):
    """
    Represents an item loaded into an in-memory processing queue (e.g., collections.deque).
    This is a lightweight representation derived from a Thought, optimized for queue processing.
    """
    thought_id: str
    source_task_id: str
    thought_type: str # Corresponds to Thought.thought_type (string)
    content: Union[str, Dict[str, Any]]
    raw_input_string: Optional[str] = Field(default=None, description="The original input string that generated this thought, if applicable.")
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial context when the thought was first received/generated for processing.")
    ponder_notes: Optional[List[str]] = Field(default=None, description="Key questions from a previous Ponder action if this item is being re-queued.")

    @classmethod
    def from_thought(
        cls,
        thought_instance: Thought,
        raw_input: Optional[str] = None,
        initial_ctx: Optional[Dict[str, Any]] = None,
        queue_item_content: Optional[Union[str, Dict[str, Any]]] = None
    ) -> "ProcessingQueueItem":
        """
        Creates a ProcessingQueueItem from a Thought instance.
        """
        final_initial_ctx = initial_ctx if initial_ctx is not None else thought_instance.context
        resolved_content = queue_item_content if queue_item_content is not None else thought_instance.content
        return cls(
            thought_id=thought_instance.thought_id,
            source_task_id=thought_instance.source_task_id,
            thought_type=thought_instance.thought_type,
            content=resolved_content,
            raw_input_string=raw_input if raw_input is not None else str(thought_instance.content),
            initial_context=final_initial_ctx if final_initial_ctx is not None else {},
            ponder_notes=thought_instance.ponder_notes
        )

ProcessingQueue = collections.deque[ProcessingQueueItem]

# See original file for AgentProcessingBatchContext example and notes.
