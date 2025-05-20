from datetime import datetime, timezone
from typing import Any

from .agent_core_schemas import Thought, HandlerActionType


def track_action(thought: Thought, action: HandlerActionType, parameters: Any) -> None:
    """Record the selected action on the thought history and increment count."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action.value,
        "parameters": parameters.model_dump() if hasattr(parameters, "model_dump") else parameters,
    }
    thought.history.append(entry)
    thought.action_count += 1
