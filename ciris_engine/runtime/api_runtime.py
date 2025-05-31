"""API runtime implementation for REST interfaces."""
import asyncio
import json
import logging
import uuid
from typing import Optional, Dict, Any

from aiohttp import web

from .ciris_runtime import CIRISRuntime
from ciris_engine.adapters.api import APIAdapter, APIEventQueue, APIObserver
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.registries.base import Priority

logger = logging.getLogger(__name__)


class APIRuntime(CIRISRuntime):
    """Runtime for running the agent via an HTTP API."""

    def __init__(self, profile_name: str = "default", port: int = 8080, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.message_queue = APIEventQueue[IncomingMessage]()
        self.api_adapter = APIAdapter(self.message_queue)

        super().__init__(profile_name=profile_name, io_adapter=self.api_adapter, startup_channel_id="api")

        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.api_observer: Optional[APIObserver] = None

    async def initialize(self) -> None:
        await super().initialize()

        self._setup_routes()
        await self._register_api_services()

        self.api_observer = APIObserver(on_observe=self._handle_observe_event, message_queue=self.message_queue)
        await self.api_observer.start()

    def _setup_routes(self) -> None:
        self.app.router.add_post('/v1/messages', self._handle_message)
        self.app.router.add_get('/v1/status', self._handle_status)
        self.app.router.add_post('/v1/defer', self._handle_defer)
        self.app.router.add_get('/v1/audit', self._handle_audit)
        self.app.router.add_post('/v1/tools/{tool_name}', self._handle_tool)

    async def _handle_message(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            message = IncomingMessage(
                message_id=data.get("id", str(uuid.uuid4())),
                content=data["content"],
                author_id=data.get("author_id", "api_user"),
                author_name=data.get("author_name", "API User"),
                channel_id=data.get("channel_id", "api"),
            )
            await self.message_queue.enqueue(message)
            return web.json_response({"status": "queued", "id": message.message_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_status(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_defer(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            thought_id = data.get("thought_id")
            reason = data.get("reason", "")
            await self.api_adapter.send_deferral(thought_id or "unknown", reason)
            return web.json_response({"status": "deferred"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_audit(self, request: web.Request) -> web.Response:
        return web.json_response({"entries": []})

    async def _handle_tool(self, request: web.Request) -> web.Response:
        tool_name = request.match_info.get('tool_name')
        try:
            data = await request.json()
        except Exception:
            data = {}
        if hasattr(self, 'api_tool_service'):
            result = await self.api_tool_service.execute_tool(tool_name, data)
        else:
            result = {"error": "no tool service"}
        return web.json_response(result)

    async def _handle_observe_event(self, payload: Dict[str, Any]):
        context = {
            "agent_mode": "api",
            "default_channel_id": "api",
        }
        return await handle_discord_observe_event(payload=payload, mode="passive", context=context)

    async def _register_api_services(self):
        if not self.service_registry:
            return

        if self.api_adapter:
            for handler in ["SpeakHandler", "ObserveHandler", "ToolHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="communication",
                    provider=self.api_adapter,
                    priority=Priority.HIGH,
                    capabilities=["send_message", "fetch_messages", "api"],
                )

        for handler in ["DeferHandler", "SpeakHandler"]:
            self.service_registry.register(
                handler=handler,
                service_type="wise_authority",
                provider=self.api_adapter,
                priority=Priority.NORMAL,
                capabilities=["fetch_guidance", "send_deferral"],
            )

        if hasattr(self, 'api_tool_service'):
            self.service_registry.register(
                handler="ToolHandler",
                service_type="tool",
                provider=self.api_tool_service,
                priority=Priority.HIGH,
                capabilities=["execute_tool", "get_tool_result"],
            )

    async def _build_action_dispatcher(self, dependencies):
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_rounds=self.app_config.workflow.max_rounds,
            action_sink=self.multi_service_sink,
            memory_service=self.memory_service,
            observer_service=self.api_observer,
            io_adapter=self.api_adapter,
        )

    async def run(self, max_rounds: Optional[int] = None):
        if not self._initialized:
            await self.initialize()

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"API server started on {self.host}:{self.port}")
        await super().run(max_rounds)

    async def shutdown(self):
        logger.info(f"Shutting down {self.__class__.__name__}...")
        services_to_stop = [self.api_observer, self.api_adapter]
        for service in services_to_stop:
            if service and hasattr(service, 'stop'):
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service.__class__.__name__}: {e}")
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
        await super().shutdown()
