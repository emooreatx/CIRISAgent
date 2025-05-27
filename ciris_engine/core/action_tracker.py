from datetime import datetime, timezone
from typing import Any
import logging

logger = logging.getLogger(__name__)

from ..schemas.agent_core_schemas_v1 import Thought
from ..schemas.foundational_schemas_v1 import HandlerActionType


def track_action(thought: Thought, action: HandlerActionType, parameters: Any) -> None:
    """Record the selected action on the thought history and increment count. Also increment ponder_count for all actions except DEFER."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action.value,
        "parameters": parameters.model_dump() if hasattr(parameters, "model_dump") else parameters,
    }
    thought.history.append(entry)
    thought.action_count += 1
    if action != HandlerActionType.DEFER:
        thought.ponder_count += 1
