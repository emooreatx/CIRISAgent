"""Action handler for routing observation events into Tasks (transport-agnostic)."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from ciris_engine import persistence

logger = logging.getLogger(__name__)

async def handle_observation_event(payload: Dict[str, Any]) -> None:
    """Create a Task from an observation payload if it does not already exist."""
    message_id = payload.get("message_id")
    content = payload.get("content")
    context = payload.get("context", {})
    description = payload.get("task_description", content)

    if not message_id or not content:
        logger.error(
            "EventRouter: Missing message_id or content in payload. Cannot create task. Payload: %s",
            payload,
        )
        return

    if persistence.task_exists(message_id):
        logger.debug("EventRouter: Task %s already exists. Skipping creation.", message_id)
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    task = persistence.Task(
        task_id=message_id,
        description=description,
        status=persistence.TaskStatus.PENDING,
        priority=1,
        created_at=now_iso,
        updated_at=now_iso,
        context=context,
    )
    try:
        persistence.add_task(task)
        logger.info("EventRouter: Created task %s from observation.", message_id)
    except Exception as e:  # pragma: no cover - extreme failure
        logger.exception("EventRouter: Failed to add task %s: %s", message_id, e)
