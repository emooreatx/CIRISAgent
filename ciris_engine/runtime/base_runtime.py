import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Any, Callable

from datetime import datetime, timezone

from ciris_engine.config.config_manager import get_config_async
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.services.audit_service import AuditService
from ciris_engine import persistence
from ciris_engine.schemas.agent_core_schemas_v1 import Task, ActionSelectionResult
from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, HandlerActionType
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.utils import extract_user_nick

logger = logging.getLogger(__name__)


def datetime_from_seconds(sec: float) -> str:
    return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()

# IncomingMessage is now defined in the schemas module
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

class BaseIOAdapter:
    """Abstract interface for runtime I/O."""

    async def start(self):
        pass

    async def stop(self):
        pass

    async def fetch_inputs(self) -> List[IncomingMessage]:
        return []

    async def send_output(self, target: Any, content: str):
        raise NotImplementedError


class CLIAdapter(BaseIOAdapter):
    async def fetch_inputs(self) -> List[IncomingMessage]:
        line = await asyncio.to_thread(input, ">>> ")
        if not line:
            return []
        return [IncomingMessage(message_id=str(asyncio.get_event_loop().time()),
                               author_id="local",
                               author_name="local",
                               content=line,
                               reference_message_id=None)]

    async def send_output(self, target: Any, content: str):
        print(content)


from ciris_engine.services.discord_event_queue import DiscordEventQueue # Import the generic queue

class DiscordAdapter(BaseIOAdapter):
    def __init__(self, token: str, message_queue: DiscordEventQueue[IncomingMessage]): # Use DiscordEventQueue[IncomingMessage]
        import discord  # type: ignore

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.token = token
        self.message_queue = message_queue # Store the provided DiscordEventQueue
        self._client_task: Optional[asyncio.Task] = None

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author == self.client.user or message.author.bot:
                return
            # Put the message onto the externally provided DiscordEventQueue
            incoming = IncomingMessage(
                message_id=str(message.id),
                author_id=str(message.author.id),
                author_name=(await extract_user_nick(message=message)) or message.author.name,
                content=message.content,
                channel_id=str(message.channel.id),
                reference_message_id=str(message.reference.message_id) if message.reference and message.reference.message_id else None,
            )
            setattr(incoming, "_raw_message", message)
            await self.message_queue.enqueue(incoming)

    async def start(self):
        if not self._client_task:
            self._client_task = asyncio.create_task(self.client.start(self.token))
            await asyncio.sleep(0)  # yield control so the client can connect

    async def stop(self):
        if self.client.is_closed():
            return
        await self.client.close()
        if self._client_task:
            try:
                await self._client_task
            except Exception:
                pass
            self._client_task = None

    async def fetch_inputs(self) -> List[IncomingMessage]:
        # This method is now a no-op for DiscordAdapter regarding task creation by BaseRuntime.
        # BaseRuntime._main_loop will call this, get an empty list, and not create tasks for Discord.
        # Task creation for Discord messages will be handled by DiscordObserver via the message_queue.
        return []

    async def send_output(self, target: Any, content: str):
        channel = self.client.get_channel(int(target))
        if channel:
            await channel.send(content)


class BaseRuntime:
    """Unified runtime with audit logging and dream protocol."""

    DREAM_ALLOWED = {
        HandlerActionType.MEMORIZE,
        HandlerActionType.REMEMBER,
        HandlerActionType.DEFER,
        HandlerActionType.REJECT,
        HandlerActionType.PONDER,
    }

    def __init__(self, 
                 io_adapter: BaseIOAdapter, 
                 profile_path: str, 
                 action_dispatcher: ActionDispatcher, # Expect a pre-configured dispatcher
                 snore_channel_id: Optional[str] = None,
                 processor: Optional[Any] = None):  # Add processor parameter
        self.io_adapter = io_adapter
        self.profile_path = profile_path
        self.snore_channel_id = snore_channel_id
        self.audit_service = AuditService() # AuditService could also be passed in if needed elsewhere
        self.dispatcher = action_dispatcher # Use the passed, configured dispatcher
        self.processor = processor  # Store the processor
        self.dreaming = False
        self._dream_task: Optional[asyncio.Task] = None

    async def _load_profile(self) -> AgentProfile:
        profile = await load_profile(self.profile_path)
        if not profile:
            raise FileNotFoundError(self.profile_path)
        return profile

    async def _create_task_if_new(self, message_id: str, content: str, context: dict) -> bool:
        """Create a task only if one with the message_id doesn't already exist."""
        if persistence.task_exists(message_id):
            return False
        now = asyncio.get_event_loop().time()
        now_iso = datetime_from_seconds(now)
        task = Task(
            task_id=message_id,
            description=content,
            status=TaskStatus.PENDING,
            priority=1,
            created_at=now_iso,
            updated_at=now_iso,
            context=context,
        )
        persistence.add_task(task)
        return True

    async def start(self):
        await self.io_adapter.start()

    async def stop(self):
        await self.io_adapter.stop()

    async def _main_loop(self):
        """
        For CLI adapter: fetches messages and creates tasks.
        For Discord adapter: returns immediately as Discord uses event-based processing.
        """
        await self.start()
        try:
            # For Discord, this will return immediately as fetch_inputs returns []
            # For CLI, this will loop and create tasks
            while True:
                messages = await self.io_adapter.fetch_inputs()
                if not messages and isinstance(self.io_adapter, DiscordAdapter):
                    # Discord uses event-based processing through DiscordObserver
                    # Just keep the loop alive
                    await asyncio.sleep(60)
                    continue
                    
                for msg in messages:
                    context = {
                        "origin_service": self.io_adapter.__class__.__name__.replace("Adapter", "").lower(),
                        "author_id": msg.author_id,
                        "author_name": msg.author_name,
                        "channel_id": msg.channel_id,
                    }
                    await self._create_task_if_new(msg.message_id, msg.content, context)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _dream_action_filter(self, result: ActionSelectionResult, ctx: dict) -> bool:
        allowed = result.selected_action in self.DREAM_ALLOWED
        if not allowed and self.audit_service:
            await self.audit_service.log_action(
                result.selected_action,
                {"dream": True, **ctx},
            )
        # Return True when the action should be skipped (i.e., not allowed)
        return not allowed

    async def run_dream(self, duration: float = 3600, pulse_interval: float = 300):
        self.dreaming = True
        self.dispatcher.action_filter = self._dream_action_filter
        end_time = asyncio.get_event_loop().time() + duration
        pulse = 0
        while asyncio.get_event_loop().time() < end_time:
            await asyncio.sleep(pulse_interval)
            pulse += 1
            snore_msg = f"*snore* pulse {pulse}"
            if self.snore_channel_id:
                await self.io_adapter.send_output(self.snore_channel_id, snore_msg)
            await self.audit_service.log_action(HandlerActionType.PONDER, {"dream": True, "event_summary": snore_msg})
        summary = "Dream ended"
        if self.snore_channel_id:
            await self.io_adapter.send_output(self.snore_channel_id, summary)
        await self.audit_service.log_action(HandlerActionType.REMEMBER, {"dream": True, "event_summary": summary})
        self.dispatcher.action_filter = None
        self.dreaming = False

    def run(self):
        """For CLI-based runtimes"""
        asyncio.run(self._main_loop())
