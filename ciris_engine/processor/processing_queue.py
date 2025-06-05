import collections
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
import logging

logger = logging.getLogger(__name__)

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext


class ThoughtContent(BaseModel):
    """Typed content for a thought."""
    text: Thought
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProcessingQueueItem(BaseModel):
    """
    Represents an item loaded into an in-memory processing queue (e.g., collections.deque).
    This is a lightweight representation derived from a Thought, optimized for queue processing.
    """
    thought_id: Thought
    source_task_id: Thought
    thought_type: Thought # Corresponds to Thought.thought_type (Thoughting)
    content: Thought
    raw_input_string: Optional[str] = Field(default=None, description="The original input string that generated this thought, if applicable.")
    initial_context: Optional[Dict[str, Any] | ThoughtContext] = Field(default=None, description="Initial context when the thought was first received/generated for processing.")
    ponder_notes: Optional[List[str]] = Field(default=None, description="Key questions from a previous Ponder action if this item is being re-queued.")

    @property
    def content_text(self) -> str:
        """Return a best-effort text representation of the content."""
        return self.content.text

    @classmethod
    def from_thought(
        cls,
        thought_instance: Thought,
        raw_input: Optional[str] = None,
        initial_ctx: Optional[Dict[str, Any]] = None,
        queue_item_content: Optional[ThoughtContent | str | Dict[str, Any]] = None
    ) -> "ProcessingQueueItem":
        """
        Creates a ProcessingQueueItem from a Thought instance.
        """
        raw_initial_ctx = initial_ctx if initial_ctx is not None else thought_instance.context
        if hasattr(raw_initial_ctx, 'model_dump') or isinstance(raw_initial_ctx, dict):
            final_initial_ctx = raw_initial_ctx
        else:
            final_initial_ctx = None

        raw_content = queue_item_content if queue_item_content is not None else thought_instance.content
        if isinstance(raw_content, ThoughtContent):
            resolved_content = raw_content
        elif isinstance(raw_content, str):
            resolved_content = ThoughtContent(text=raw_content)
        elif isinstance(raw_content, dict):
            resolved_content = ThoughtContent(**raw_content)
        else:
            resolved_content = ThoughtContent(text=str(raw_content))
        return cls(
            thought_id=thought_instance.thought_id,
            source_task_id=thought_instance.source_task_id,
            thought_type=thought_instance.thought_type,
            content=resolved_content,
            raw_input_string=raw_input if raw_input is not None else str(thought_instance.content),
            initial_context=final_initial_ctx,
            ponder_notes=thought_instance.ponder_notes
        )

ProcessingQueue = collections.deque[ProcessingQueueItem]

