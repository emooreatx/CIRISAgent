"""
CLI-specific observation handler for routing CLI input into Tasks and initial Thoughts.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus, HandlerActionType
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine import persistence

logger = logging.getLogger(__name__)

async def handle_cli_observe_event(
    payload: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> ActionSelectionResult:
    """
    Handles CLI observation events.
    Creates a Task and an initial PONDER Thought from the given payload.
    """
    message_id = payload.get("message_id")
    content = payload.get("content")
    context_data = payload.get("context", {})
    description = payload.get("task_description", content)

    # Ensure cli_mode is in context_data if provided in the broader context
    if context and "cli_mode" in context:
        context_data["cli_mode"] = context.get("cli_mode")
    if context and "agent_mode" in context:
        context_data["agent_mode"] = context.get("agent_mode")


    if not message_id or not content:
        logger.error(
            "CLIObserveHandler: Missing message_id or content in payload. Cannot create task. Payload: %s",
            payload,
        )
        # Return a non-action or a specific error action if desired
        return ActionSelectionResult(
            selected_action=HandlerActionType.NO_ACTION,
            action_parameters={},
            rationale="Missing message_id or content in CLI payload.",
        )

    # Use message_id as task_id for idempotency if desired, or generate a new one
    # For CLI, each input line is often a new intent, so a unique task_id might be better
    # However, the original code used message_id, so we'll stick to it for now.
    task_id = message_id 

    if persistence.task_exists(task_id):
        logger.debug("CLIObserveHandler: Task %s already exists. Skipping creation.", task_id)
        # Optionally, we could create a new thought for an existing task if it's active
        # For now, just return an observe action pointing to the existing task.
        return ActionSelectionResult(
            selected_action=HandlerActionType.OBSERVE, # Or NO_ACTION if we don't want to re-trigger
            action_parameters={"task_id": task_id},
            rationale="Task already exists. Skipping creation.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Create the Task
    new_task = Task(
        task_id=task_id,
        description=description,
        status=TaskStatus.ACTIVE, # Start as ACTIVE since we're creating a PONDER thought
        priority=1,
        created_at=now_iso,
        updated_at=now_iso,
        context=context_data,
    )


    try:
        persistence.add_task(new_task)
        logger.info("CLIObserveHandler: Created task %s from CLI observation.", new_task.task_id)

    except Exception as e:
        logger.exception("CLIObserveHandler: Failed to add task error: %s", e)

