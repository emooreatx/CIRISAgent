"""
Discord-specific observation handler for routing observation events into Tasks.
Handles both passive (from payload) and active (fetch from Discord channel) modes.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ciris_engine import persistence

logger = logging.getLogger(__name__)

async def handle_discord_observe_event(
    payload: Dict[str, Any],
    mode: str = "passive",
    context: Optional[Dict[str, Any]] = None
) -> None:
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
            return

        if persistence.task_exists(message_id):
            logger.debug("DiscordObserveHandler: Task %s already exists. Skipping creation.", message_id)
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        task = persistence.Task(
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
        except Exception as e:
            logger.exception("DiscordObserveHandler: Failed to add task %s: %s", message_id, e)
        return

    elif mode == "active":
        if context is None:
            logger.error("Active observation mode requires a context with services.")
            return
        discord_service = context.get("discord_service")
        if discord_service is None:
            logger.error("Active observation mode requires 'discord_service' in context.")
            return
        channel_id = payload.get("channel_id") or context.get("default_channel_id")
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
            return

        for msg in messages:
            message_id = msg.get("id")
            content = msg.get("content")
            author_id = msg.get("author_id")
            context_data = {"author_id": author_id, "channel_id": channel_id}
            description = msg.get("task_description", content)
            if not message_id or not content:
                continue
            if persistence.task_exists(message_id):
                continue
            now_iso = datetime.now(timezone.utc).isoformat()
            task = persistence.Task(
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
                logger.info(f"DiscordObserveHandler: Created task {message_id} from active observation.")
            except Exception as e:
                logger.exception(f"DiscordObserveHandler: Failed to add task {message_id}: {e}")
        return
    else:
        logger.error(f"Unknown Discord observation event mode: {mode}")
        return
