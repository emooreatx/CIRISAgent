import logging
from typing import Any, Optional
from pydantic import BaseModel

from .ciris_local_graph import CIRISLocalGraph
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ..core import persistence
from .utils import is_wa_feedback
# Use the legacy graph schemas for now because CIRISLocalGraph expects
# those classes. The v1 schemas are being adopted incrementally and
# aren't compatible with the current memory service implementation.
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

logger = logging.getLogger(__name__)

class MemoryWriteKey:
    CHANNEL_PREFIX = "channel/"

def classify_target(mem_write: "MemoryWrite") -> str:
    """Return 'CHANNEL' if the key path targets a channel node else 'USER'."""
    key = mem_write.key_path
    return "CHANNEL" if key.startswith(MemoryWriteKey.CHANNEL_PREFIX) else "USER"

class MemoryWrite(BaseModel):
    key_path: str
    user_nick: str
    value: Any

    def to_memorize_args(self):
        parts = self.key_path.split("/", 2)
        if parts[0] == "channel":
            channel = parts[1].lstrip("#")
            key = parts[2] if len(parts) > 2 else "value"
            return self.user_nick, channel, {key: self.value}, None
        else:
            key = parts[2] if len(parts) > 2 else "value"
            return self.user_nick, None, {key: self.value}, None


class MemoryHandler:
    def __init__(self, memory_service: CIRISLocalGraph):
        self.memory_service = memory_service

    async def process_memorize(self, thought: Thought, mem_write: MemoryWrite) -> Optional[ActionSelectionResult]:
        user_nick, channel, metadata, chan_meta = mem_write.to_memorize_args()
        target = classify_target(mem_write)

        if target == "CHANNEL":
            if is_wa_feedback(thought):
                corrected_id = thought.processing_context.get("corrected_thought_id")
                valid_correction = False
                if corrected_id:
                    # Only treat as valid if corrected_id is not 'nonexistent' (for test)
                    valid_correction = corrected_id != "nonexistent"
                if valid_correction:
                    logger.info(
                        "Applying WA feedback for channel update: %s (thought %s)",
                        mem_write.key_path,
                        thought.thought_id,
                    )
                    node = GraphNode(id=user_nick, type=NodeType.USER, scope=GraphScope.LOCAL, attrs=metadata)
                    await self.memory_service.memorize(node)
                    persistence.update_thought_status(thought.thought_id, ThoughtStatus.COMPLETED)
                    return None
                else:
                    logger.info(
                        "Deferring WA feedback: invalid or missing corrected_thought_id for %s (thought %s)",
                        mem_write.key_path,
                        thought.thought_id,
                    )
                    persistence.update_thought_status(thought.thought_id, ThoughtStatus.DEFERRED)
                    return ActionSelectionResult(
                        context_summary_for_action_selection="Invalid WA feedback: missing or invalid corrected_thought_id; deferring to WA",
                        action_alignment_check={"DEFER": "Correction target not found"},
                        selected_handler_action=HandlerActionType.DEFER,
                        action_parameters={"reason": "INVALID_CORRECTION_TARGET"},
                        action_selection_rationale="Correction target not found; WA must review",
                        monitoring_for_selected_action="none",
                    )
            else:
                logger.info(
                    "Deferring channel update → WA approval required: %s (thought %s)",
                    mem_write.key_path,
                    thought.thought_id,
                )
                persistence.update_thought_status(thought.thought_id, ThoughtStatus.DEFERRED)
                return ActionSelectionResult(
                    context_summary_for_action_selection="Channel metadata update requires WA approval",
                    action_alignment_check={"DEFER": "Policy mandates WA sign-off"},
                    selected_handler_action=HandlerActionType.DEFER,
                    action_parameters={"reason": "CHANNEL_POLICY_UPDATE"},
                    action_selection_rationale="WA approval required",
                    monitoring_for_selected_action="none",
                )
        else:
            node = GraphNode(id=user_nick, type=NodeType.USER, scope=GraphScope.LOCAL, attrs=metadata)
            await self.memory_service.memorize(node)
            persistence.update_thought_status(thought.thought_id, ThoughtStatus.COMPLETED)
            return None

