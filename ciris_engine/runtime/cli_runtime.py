import logging
import os
import asyncio
from typing import Optional, Dict, Any

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.action_handlers.cli_observe_handler import handle_cli_observe_event # Changed import
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.registries.base import Priority
from ciris_engine.sinks import MultiServiceActionSink, MultiServiceDeferralSink
from ..adapters.cli.cli_event_queues import CLIEventQueue
from ..adapters.cli.cli_adapter import CLIAdapter
from ..adapters.cli.cli_observer import CLIObserver
from ..adapters.cli.cli_tools import CLIToolService
from ..adapters.cli.cli_wa_service import CLIWiseAuthorityService

logger = logging.getLogger(__name__)


class CLIRuntime(CIRISRuntime):
    """Runtime for running the agent via the command line."""

    def __init__(self, profile_name: str = "default", interactive: bool = True):
        self.cli_queue = CLIEventQueue[IncomingMessage]()
        self.cli_adapter = CLIAdapter(self.cli_queue, interactive=interactive)
        super().__init__(profile_name=profile_name, io_adapter=self.cli_adapter, startup_channel_id="cli")

        self.cli_observer: Optional[CLIObserver] = None
        self.cli_tool_service: Optional[CLIToolService] = None
        self.cli_wa_service: Optional[CLIWiseAuthorityService] = None

        self.action_sink: Optional[MultiServiceActionSink] = None
        self.deferral_sink: Optional[MultiServiceDeferralSink] = None

        self.interactive = interactive

    async def initialize(self):
        await super().initialize()

        # Create all CLI services
        self.cli_wa_service = CLIWiseAuthorityService()

        # Create sinks if not already created by base runtime
        if not self.action_sink:
            self.action_sink = MultiServiceActionSink(
                service_registry=self.service_registry,
                fallback_channel_id="cli"
            )
        if not self.deferral_sink:
            self.deferral_sink = MultiServiceDeferralSink(
                service_registry=self.service_registry,
                fallback_channel_id="cli"
            )

        # Ensure observer has proper event handling
        self.cli_observer = CLIObserver(
            on_observe=self._handle_observe_event,
            message_queue=self.cli_queue,
            deferral_sink=self.deferral_sink,
        )

        # Create tool service
        self.cli_tool_service = CLIToolService()

        # Register all services
        await self._register_cli_services()

        # Start all services
        await asyncio.gather(
            self.cli_observer.start(),
            self.cli_adapter.start(),
        )

        # Start sinks as background tasks since they contain infinite loops
        self.action_sink_task = asyncio.create_task(self.action_sink.start())
        self.deferral_sink_task = asyncio.create_task(self.deferral_sink.start())

        logger.info("Starting agent processing with WAKEUP sequence...")
        if self.agent_processor:
            asyncio.create_task(
                self.agent_processor.start_processing(
                    num_rounds=self.app_config.workflow.max_rounds
                )
            )

    async def _handle_observe_event(self, payload: Dict[str, Any]):
        """Enhanced observe event handling with CLI context"""
        context = {
            "cli_mode": True,
            "agent_mode": "cli",
            "default_channel_id": "cli",
            "home_directory": os.path.expanduser("~"),
            "current_directory": os.getcwd(),
        }

        # Use the new CLI-specific handler
        return await handle_cli_observe_event(
            payload=payload,
            context=context,
        )

    async def _register_cli_services(self):
        """Register CLI-specific services matching Discord's pattern"""
        if not self.service_registry:
            return

        # 1. Register CLI adapter for all handlers needing communication
        handler_names = [
            "SpeakHandler", "ObserveHandler", "ToolHandler",
            "DeferHandler", "MemorizeHandler", "RecallHandler",
            "TaskCompleteHandler",
        ]

        for handler in handler_names:
            self.service_registry.register(
                handler=handler,
                service_type="communication",
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                capabilities=["send_message", "fetch_messages"],
            )

        # 2. Register CLI observer service
        if self.cli_observer:
            self.service_registry.register(
                handler="ObserveHandler",
                service_type="observer",
                provider=self.cli_observer,
                priority=Priority.NORMAL,
                capabilities=[
                    "observe_messages", "get_recent_messages", "handle_incoming_message"
                ],
            )

        # 3. Register CLI tool service with proper capabilities
        if self.cli_tool_service:
            self.service_registry.register(
                handler="ToolHandler",
                service_type="tool",
                provider=self.cli_tool_service,
                priority=Priority.NORMAL,
                capabilities=[
                    "execute_tool", "get_tool_result", "get_available_tools", "validate_parameters"
                ],
            )

        # 4. Register a CLI-based WA service (new component needed)
        if self.cli_wa_service:
            for handler in ["DeferHandler", "SpeakHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="wise_authority",
                    provider=self.cli_wa_service,
                    priority=Priority.NORMAL,
                    capabilities=["fetch_guidance", "send_deferral"],
                )

    async def _build_action_dispatcher(self, dependencies):
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_rounds=self.app_config.workflow.max_rounds,
            action_sink=self.multi_service_sink,
            memory_service=self.memory_service,
            observer_service=self.cli_observer,
            io_adapter=self.cli_adapter,
            deferral_sink=self.deferral_sink,
        )

    async def shutdown(self):
        logger.info(f"Shutting down {self.__class__.__name__}...")

        services_to_stop = [
            self.cli_observer,
            self.cli_adapter,
            self.action_sink,
            self.deferral_sink,
            self.cli_wa_service,
            self.cli_tool_service,
        ]

        for service in services_to_stop:
            if service and hasattr(service, "stop"):
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service.__class__.__name__}: {e}")

        await super().shutdown()
