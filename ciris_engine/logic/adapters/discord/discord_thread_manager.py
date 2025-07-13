"""Discord thread management for organized conversations."""
import discord
import logging
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from datetime import timedelta
from enum import Enum

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)


class ThreadType(Enum):
    """Types of threads for different conversations."""
    GUIDANCE = "guidance"
    DEFERRAL = "deferral"
    APPROVAL = "approval"
    TASK = "task"
    ERROR = "error"
    AUDIT = "audit"


class DiscordThreadManager:
    """Manages Discord threads for conversation organization."""

    def __init__(self, client: Optional[discord.Client] = None,
                 time_service: Optional["TimeServiceProtocol"] = None,
                 auto_archive_duration: int = 1440):  # 24 hours
        """Initialize thread manager.

        Args:
            client: Discord client
            time_service: Time service for timestamps
            auto_archive_duration: Thread auto-archive time in minutes
        """
        self.client = client
        self.auto_archive_duration = auto_archive_duration

        # Track active threads
        self._active_threads: Dict[str, discord.Thread] = {}  # key -> thread
        self._thread_metadata: Dict[int, Dict[str, Any]] = {}  # thread_id -> metadata
        self._time_service: TimeServiceProtocol

        # Ensure we have a time service
        if time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()
        else:
            self._time_service = time_service

    def set_client(self, client: discord.Client) -> None:
        """Set Discord client after initialization.

        Args:
            client: Discord client instance
        """
        self.client = client

    async def create_thread(self, channel_id: str, name: str,
                          thread_type: ThreadType,
                          initial_message: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Optional[discord.Thread]:
        """Create a new thread in a channel.

        Args:
            channel_id: Parent channel ID
            name: Thread name
            thread_type: Type of thread
            initial_message: Optional first message in thread
            metadata: Optional metadata to track

        Returns:
            Created thread or None if failed
        """
        if not self.client:
            logger.error("Discord client not initialized")
            return None

        try:
            # Get channel
            channel = self.client.get_channel(int(channel_id))
            if not channel:
                channel = await self.client.fetch_channel(int(channel_id))

            if not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} is not a text channel")
                return None

            # Create thread name with type prefix
            thread_name = f"[{thread_type.value.upper()}] {name}"[:100]  # Discord limit

            # Create thread with or without initial message
            if initial_message:
                # Send message first, then create thread from it
                message = await channel.send(initial_message)
                thread = await message.create_thread(
                    name=thread_name,
                    auto_archive_duration=self.auto_archive_duration  # type: ignore[arg-type]
                )
            else:
                # Create thread directly
                thread = await channel.create_thread(
                    name=thread_name,
                    auto_archive_duration=self.auto_archive_duration,  # type: ignore[arg-type]
                    type=discord.ChannelType.public_thread
                )

            # Track thread
            thread_key = f"{thread_type.value}_{channel_id}_{name}"
            self._active_threads[thread_key] = thread

            # Store metadata
            self._thread_metadata[thread.id] = {
                "type": thread_type.value,
                "created_at": self._time_service.now(),
                "parent_channel_id": channel_id,
                "key": thread_key,
                **(metadata or {})
            }

            logger.info(f"Created thread '{thread_name}' in channel {channel_id}")
            return thread

        except Exception as e:
            logger.exception(f"Failed to create thread: {e}")
            return None

    async def get_or_create_thread(self, channel_id: str, name: str,
                                 thread_type: ThreadType,
                                 metadata: Optional[Dict[str, Any]] = None) -> Optional[discord.Thread]:
        """Get existing thread or create new one.

        Args:
            channel_id: Parent channel ID
            name: Thread name (without type prefix)
            thread_type: Type of thread
            metadata: Optional metadata

        Returns:
            Thread object or None
        """
        thread_key = f"{thread_type.value}_{channel_id}_{name}"

        # Check if thread exists and is still active
        if thread_key in self._active_threads:
            thread = self._active_threads[thread_key]

            # Verify thread is still accessible
            try:
                # Check if archived
                if thread.archived:
                    # Try to unarchive
                    await thread.edit(archived=False)
                    logger.info(f"Unarchived thread {thread.name}")

                return thread

            except discord.NotFound:
                # Thread was deleted
                del self._active_threads[thread_key]
                if thread.id in self._thread_metadata:
                    del self._thread_metadata[thread.id]
                logger.info(f"Thread {thread_key} was deleted, creating new one")
            except Exception as e:
                logger.error(f"Error checking thread {thread_key}: {e}")

        # Create new thread
        return await self.create_thread(channel_id, name, thread_type, metadata=metadata)

    async def send_to_thread(self, thread: discord.Thread, content: Optional[str] = None,
                           embed: Optional[discord.Embed] = None) -> Optional[discord.Message]:
        """Send a message to a thread.

        Args:
            thread: Thread to send to
            content: Message content
            embed: Optional embed

        Returns:
            Sent message or None
        """
        try:
            if embed is not None:
                return await thread.send(content=content, embed=embed)
            else:
                return await thread.send(content=content)
        except Exception as e:
            logger.error(f"Failed to send to thread {thread.id}: {e}")
            return None

    async def create_guidance_thread(self, channel_id: str, context: Dict[str, Any]) -> Optional[discord.Thread]:
        """Create a thread for guidance discussion.

        Args:
            channel_id: Channel to create thread in
            context: Guidance context

        Returns:
            Created thread or None
        """
        # Create thread name from context
        thought_id = context.get("thought_id", "unknown")[:8]
        task_id = context.get("task_id", "unknown")[:8]
        thread_name = f"Guidance-{thought_id}-{task_id}"

        # Initial message
        initial_msg = "**Guidance Request**\n"
        initial_msg += f"Question: {context.get('question', 'N/A')}\n"
        initial_msg += f"Task: `{context.get('task_id', 'N/A')}`\n"
        initial_msg += f"Thought: `{context.get('thought_id', 'N/A')}`"

        return await self.create_thread(
            channel_id=channel_id,
            name=thread_name,
            thread_type=ThreadType.GUIDANCE,
            initial_message=initial_msg,
            metadata=context
        )

    async def create_task_thread(self, channel_id: str, task: Dict[str, Any]) -> Optional[discord.Thread]:
        """Create a thread for task tracking.

        Args:
            channel_id: Channel to create thread in
            task: Task information

        Returns:
            Created thread or None
        """
        task_id = task.get("id", "unknown")[:8]
        task_name = task.get("name", "Task")[:50]
        thread_name = f"Task-{task_id}-{task_name}"

        # Initial message
        initial_msg = "**Task Created**\n"
        initial_msg += f"ID: `{task.get('id', 'N/A')}`\n"
        initial_msg += f"Description: {task.get('description', 'N/A')}\n"
        initial_msg += f"Priority: {task.get('priority', 'normal').upper()}"

        return await self.create_thread(
            channel_id=channel_id,
            name=thread_name,
            thread_type=ThreadType.TASK,
            initial_message=initial_msg,
            metadata=task
        )

    async def archive_old_threads(self, hours: int = 24) -> int:
        """Archive threads older than specified hours.

        Args:
            hours: Age threshold in hours

        Returns:
            Number of threads archived
        """
        if not self.client:
            return 0

        archived_count = 0
        cutoff_time = self._time_service.now() - timedelta(hours=hours)

        # Check all tracked threads
        for thread_key, thread in list(self._active_threads.items()):
            try:
                # Get metadata
                metadata = self._thread_metadata.get(thread.id, {})
                created_at = metadata.get("created_at")

                # Check age
                if created_at and created_at < cutoff_time:
                    # Archive if not already archived
                    if not thread.archived:
                        await thread.edit(archived=True, reason=f"Auto-archive after {hours} hours")
                        archived_count += 1
                        logger.info(f"Archived thread {thread.name}")

                    # Remove from active tracking
                    del self._active_threads[thread_key]
                    if thread.id in self._thread_metadata:
                        del self._thread_metadata[thread.id]

            except discord.NotFound:
                # Thread was deleted
                del self._active_threads[thread_key]
                if thread.id in self._thread_metadata:
                    del self._thread_metadata[thread.id]
            except Exception as e:
                logger.error(f"Error archiving thread {thread_key}: {e}")

        return archived_count

    def get_thread_info(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a thread.

        Args:
            thread_id: Discord thread ID

        Returns:
            Thread information or None
        """
        return self._thread_metadata.get(thread_id)

    def get_active_threads(self, thread_type: Optional[ThreadType] = None) -> List[discord.Thread]:
        """Get list of active threads.

        Args:
            thread_type: Optional filter by type

        Returns:
            List of active threads
        """
        threads = []

        for thread_key, thread in self._active_threads.items():
            if thread_type:
                metadata = self._thread_metadata.get(thread.id, {})
                if metadata.get("type") != thread_type.value:
                    continue
            threads.append(thread)

        return threads

    async def close_thread(self, thread: discord.Thread, reason: Optional[str] = None) -> bool:
        """Close and archive a thread.

        Args:
            thread: Thread to close
            reason: Optional reason for closing

        Returns:
            True if successful
        """
        try:
            # Send closing message if reason provided
            if reason:
                await thread.send(f"**Thread Closed**\nReason: {reason}")

            # Archive the thread
            await thread.edit(archived=True, locked=True)

            # Remove from tracking
            for key, tracked_thread in list(self._active_threads.items()):
                if tracked_thread.id == thread.id:
                    del self._active_threads[key]
                    break

            if thread.id in self._thread_metadata:
                del self._thread_metadata[thread.id]

            logger.info(f"Closed thread {thread.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to close thread {thread.id}: {e}")
            return False
