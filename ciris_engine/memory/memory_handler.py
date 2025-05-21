import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel

from ..services.discord_graph_memory import DiscordGraphMemory
from ..core.graph_schemas import GraphNode, GraphScope, NodeType
from ..core.agent_core_schemas import ActionSelectionPDMAResult
from ..core.agent_core_schemas import Thought
from ..core.foundational_schemas import HandlerActionType, ThoughtStatus
from ..core import persistence
from .utils import classify_target, is_wa_correction

logger = logging.getLogger(__name__)

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
    def __init__(self, memory_service: DiscordGraphMemory):
        self.memory_service = memory_service

    async def process_memorize(self, thought: Thought, mem_write: MemoryWrite) -> Optional[ActionSelectionPDMAResult]:
        user_nick, channel, metadata, chan_meta = mem_write.to_memorize_args()
        target = classify_target(mem_write)

        if target == "CHANNEL":
            if is_wa_correction(thought):
                logger.info(
                    "Applying WA correction for channel update: %s (thought %s)",
                    mem_write.key_path,
                    thought.thought_id,
                )
                node = GraphNode(id=user_nick, type=NodeType.USER, scope=GraphScope.LOCAL, attrs=metadata)
                await self.memory_service.memorize(node)
                persistence.update_thought_status(thought.thought_id, ThoughtStatus.COMPLETED)
                return None
            else:
                logger.info(
                    "Deferring channel update → WA approval required: %s (thought %s)",
                    mem_write.key_path,
                    thought.thought_id,
                )
                persistence.update_thought_status(thought.thought_id, ThoughtStatus.DEFERRED)
                return ActionSelectionPDMAResult(
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
