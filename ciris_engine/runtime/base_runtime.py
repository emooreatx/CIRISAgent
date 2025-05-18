import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Any, Callable

from datetime import datetime, timezone

from ciris_engine.core.config_manager import get_config_async
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.services.audit_service import AuditService
from ciris_engine.core import persistence
from ciris_engine.core.agent_core_schemas import Task, ActionSelectionPDMAResult
from ciris_engine.core.config_schemas import SerializableAgentProfile as AgentProfile
from ciris_engine.core.foundational_schemas import TaskStatus, HandlerActionType
from ciris_engine.utils.profile_loader import load_profile

logger = logging.getLogger(__name__)


def datetime_from_seconds(sec: float) -> str:
    return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()

@dataclass
class IncomingMessage:
    message_id: str
    author_id: str
    content: str
    channel_id: Optional[str] = None


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
        return [IncomingMessage(message_id=str(asyncio.get_event_loop().time()), author_id="local", content=line)]

    async def send_output(self, target: Any, content: str):
        print(content)


class DiscordAdapter(BaseIOAdapter):
    def __init__(self, token: str):
        import discord  # type: ignore

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.token = token
        self._queue: asyncio.Queue[IncomingMessage] = asyncio.Queue()

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author == self.client.user or message.author.bot:
                return
            await self._queue.put(
                IncomingMessage(
                    message_id=str(message.id),
                    author_id=str(message.author.id),
                    content=message.content,
                    channel_id=str(message.channel.id),
                )
            )

    async def start(self):
        await self.client.start(self.token)

    async def stop(self):
        await self.client.close()

    async def fetch_inputs(self) -> List[IncomingMessage]:
        messages: List[IncomingMessage] = []
        try:
            while True:
                messages.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass
        return messages

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

    def __init__(self, io_adapter: BaseIOAdapter, profile_path: str, snore_channel_id: Optional[str] = None):
        self.io_adapter = io_adapter
        self.profile_path = profile_path
        self.snore_channel_id = snore_channel_id
        self.audit_service = AuditService()
        self.dispatcher = ActionDispatcher(audit_service=self.audit_service)
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
        """Fetches messages from the adapter and creates tasks."""
        await self.start()
        try:
            while True:
                messages = await self.io_adapter.fetch_inputs()
                for msg in messages:
                    context = {
                        "origin_service": self.io_adapter.__class__.__name__.replace("Adapter", "").lower(),
                        "author_id": msg.author_id,
                        "author_name": msg.author_id,
                        "channel_id": msg.channel_id,
                    }
                    await self._create_task_if_new(msg.message_id, msg.content, context)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _dream_action_filter(self, result: ActionSelectionPDMAResult, ctx: dict) -> bool:
        allowed = result.selected_handler_action in self.DREAM_ALLOWED
        if not allowed:
            if self.audit_service:
                await self.audit_service.log_action(result.selected_handler_action, {"dream": True, **ctx})
        return allowed

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
        asyncio.run(self._main_loop())


