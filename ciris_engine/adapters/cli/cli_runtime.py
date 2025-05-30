import logging
from typing import Optional, Dict, Any

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.registries.base import Priority
from .cli_event_queues import CLIEventQueue
from .cli_adapter import CLIAdapter
from .cli_observer import CLIObserver

logger = logging.getLogger(__name__)


class CLIRuntime(CIRISRuntime):
    """Runtime for running the agent via the command line."""

    def __init__(self, profile_name: str = "default", interactive: bool = True):
        self.message_queue = CLIEventQueue[IncomingMessage]()
        self.cli_adapter = CLIAdapter(self.message_queue, interactive=interactive)
        super().__init__(profile_name=profile_name, io_adapter=self.cli_adapter, startup_channel_id="cli")
        self.cli_observer: Optional[CLIObserver] = None
        self.interactive = interactive

    async def initialize(self):
        await super().initialize()
        self.cli_observer = CLIObserver(on_observe=self._handle_observe_event, message_queue=self.message_queue)
        await self._register_cli_services()

    async def _handle_observe_event(self, payload: Dict[str, Any]):
        context = {"agent_mode": "cli"}
        await handle_discord_observe_event(payload, mode="passive", context=context)

    async def _register_cli_services(self):
        if not self.service_registry:
            return
        for handler in ["SpeakHandler", "ToolHandler", "ObserveHandler"]:
            self.service_registry.register(
                handler=handler,
                service_type="communication",
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                capabilities=["send_message"],
            )

    async def _build_action_dispatcher(self, dependencies):
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_ponder_rounds=self.app_config.workflow.max_ponder_rounds,
            action_sink=self.multi_service_sink,
            memory_service=self.memory_service,
            observer_service=self.cli_observer,
            io_adapter=self.cli_adapter,
        )

    async def shutdown(self):
        if self.cli_observer:
            await self.cli_observer.stop()
        await super().shutdown()
