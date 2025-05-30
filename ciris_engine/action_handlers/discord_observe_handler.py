"""
Discord-specific observation handler for routing observation events into Tasks.
Handles both passive (from payload) and active (fetch from Discord channel) modes.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

from ciris_engine import persistence

logger = logging.getLogger(__name__)

async def handle_discord_observe_event(
    payload: Dict[str, Any],
    mode: str = "passive",
    context: Optional[Dict[str, Any]] = None
) -> ActionSelectionResult:
    """
    Handles Discord observation events in two modes:
    - Passive: Creates a Task from the given payload if it does not already exist.
    - Active: Fetches messages from a Discord channel and creates tasks for each message.
    Args:
        payload: The observation payload (for passive mode) or parameters for active mode.
        mode: 'passive' (default) or 'active'.
        context: Optional context dict, should include services for active mode.
    """
    if mode == "passive":
        message_id = payload.get("message_id")
        content = payload.get("content")
        context_data = payload.get("context", {})
        description = payload.get("task_description", content)

        if not message_id or not content:
            logger.error(
                "DiscordObserveHandler: Missing message_id or content in payload. Cannot create task. Payload: %s",
                payload,
            )
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={},
                rationale="Missing message_id or content in payload.",
            )

        if persistence.task_exists(message_id):
            logger.debug("DiscordObserveHandler: Task %s already exists. Skipping creation.", message_id)
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={"task_id": message_id},
                rationale="Task already exists. Skipping creation.",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        task = Task(
            task_id=message_id,
            description=description,
            status=persistence.TaskStatus.PENDING,
            priority=1,
            created_at=now_iso,
            updated_at=now_iso,
            context=context_data,
        )
        try:
            persistence.add_task(task)
            logger.info("DiscordObserveHandler: Created task %s from observation.", message_id)
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={"task_id": message_id},
                rationale=f"Task {message_id} created from Discord observation.",
            )
        except Exception as e:
            logger.exception("DiscordObserveHandler: Failed to add task %s: %s", message_id, e)
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={"task_id": message_id},
                rationale=f"Failed to add task: {e}",
            )

    elif mode == "active":
        if context is None:
            logger.error("Active observation mode requires a context with services.")
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={},
                rationale="Active observation mode requires a context with services.",
            )
        discord_service = context.get("discord_service")
        if discord_service is None:
            logger.error("Active observation mode requires 'discord_service' in context.")
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={},
                rationale="Active observation mode requires 'discord_service' in context.",
            )
        channel_id = payload.get("channel_id") or context.get("default_channel_id")
        if not channel_id:
            logger.error("Active observation mode requires a channel_id")
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={},
                rationale="Active observation mode requires a channel_id.",
            )
        offset = payload.get("offset", 0)
        limit = payload.get("limit", 20)
        include_agent = payload.get("include_agent", True)
        agent_id = context.get("agent_id")

        try:
            messages = await discord_service.fetch_messages(
                channel_id=channel_id,
                offset=offset,
                limit=limit,
                include_agent=include_agent,
                agent_id=agent_id
            )
        except Exception as e:
            logger.error(f"Failed to fetch messages from channel {channel_id}: {e}")
            return ActionSelectionResult(
                selected_action=HandlerActionType.OBSERVE,
                action_parameters={},
                rationale=f"Failed to fetch messages: {e}",
            )

        # Process messages into a summary for follow-up thought
        message_summaries = []
        for msg in messages:
            message_id = msg.get("id")
            content = msg.get("content")
            author_id = msg.get("author_id")
            timestamp = msg.get("timestamp", "unknown time")
            
            if not message_id or not content:
                continue
                
            # Format message for inclusion in follow-up
            summary = f"[{timestamp}] {author_id}: {content[:200]}{'...' if len(content) > 200 else ''}"
            message_summaries.append(summary)
        
        # Create summary of observed messages
        if message_summaries:
            messages_text = "\n".join(message_summaries)
            observation_summary = f"Active Discord observation of channel {channel_id} (limit: {limit}, offset: {offset}):\n\n{messages_text}"
        else:
            observation_summary = f"Active Discord observation of channel {channel_id} found no messages (limit: {limit}, offset: {offset})"
        
        return ActionSelectionResult(
            selected_action=HandlerActionType.OBSERVE,
            action_parameters={
                "channel_id": channel_id,
                "message_count": len(message_summaries),
                "observation_summary": observation_summary
            },
            rationale=f"Active observation completed. Observed {len(message_summaries)} messages from channel {channel_id}.",
        )
    else:
        logger.error(f"Unknown Discord observation event mode: {mode}")
        return ActionSelectionResult(
            selected_action=HandlerActionType.OBSERVE,
            action_parameters={},
            rationale=f"Unknown Discord observation event mode: {mode}",
        )
