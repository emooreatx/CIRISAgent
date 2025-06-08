import asyncio
import logging
from typing import List, Any, Dict, Optional
from aiohttp import web

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
from ciris_engine.adapters.api.api_adapter import APIAdapter  # Actual service provider
from ciris_engine.adapters.api.api_observer import APIObserver # Handles incoming messages

logger = logging.getLogger(__name__)

class ApiPlatform(PlatformAdapter):
    def __init__(self, runtime: "CIRISRuntime", **kwargs: Any) -> None:
        self.runtime = runtime
        self.api_adapter = APIAdapter()
        self.host = kwargs.get("host", "0.0.0.0")
        self.port = int(kwargs.get("port", 8080))
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._web_server_stopped_event = asyncio.Event()

        self.api_observer = APIObserver(
            on_observe=self._default_observe_callback,
            memory_service=getattr(self.runtime, 'memory_service', None),
            multi_service_sink=getattr(self.runtime, 'multi_service_sink', None),
            api_adapter=self.api_adapter
        )
        self._setup_routes()

    async def _default_observe_callback(self, data: Dict[str, Any]) -> None:
        logger.debug(f"ApiPlatform: Default observe callback received data: {data}")
        if hasattr(self.runtime, 'multi_service_sink') and self.runtime.multi_service_sink:
            try:
                if isinstance(data, IncomingMessage):
                    msg = data
                elif isinstance(data, dict):
                    # Ensure all required fields for IncomingMessage are present in data
                    # This is a simplified example; more robust validation might be needed
                    msg = IncomingMessage(**data)
                else:
                    logger.error(f"ApiPlatform: Observe callback received unknown data type: {type(data)}")
                    return

                await self.runtime.multi_service_sink.observe_message("ObserveHandler", msg, {"source": "api"})
                logger.debug(f"ApiPlatform: Message sent to multi_service_sink via observe_message")
            except Exception as e:
                logger.error(f"ApiPlatform: Error in observe callback processing message: {e}", exc_info=True)
        else:
            logger.warning("ApiPlatform: multi_service_sink not available on runtime for observe callback.")

    def _setup_routes(self) -> None:
        self.app.router.add_post("/api/v1/message", self._handle_incoming_api_message)
        logger.info("ApiPlatform: Basic API routes set up. (/api/v1/message)")

    async def _handle_incoming_api_message(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            if not all(k in data for k in ["message_id", "author_id", "author_name", "content"]):
                 return web.json_response({"error": "Missing required fields for IncomingMessage"}, status=400)

            message_data = {
                "message_id": data["message_id"],
                "author_id": data["author_id"],
                "author_name": data["author_name"],
                "content": data["content"],
                "destination_id": data.get("channel_id", data.get("destination_id", "api_default_channel")),
                "reference_message_id": data.get("reference_message_id"),
                "timestamp": data.get("timestamp"),
            }
            # Add any other optional fields from data if they exist in IncomingMessage's FieldInfo
            # For Pydantic v2, model_fields can be used. For v1, __fields__
            model_fields = getattr(IncomingMessage, 'model_fields', getattr(IncomingMessage, '__fields__', {}))
            for key in data:
                if key not in message_data and key in model_fields:
                     message_data[key] = data[key]

            msg = IncomingMessage(**message_data)

            await self.api_observer.handle_incoming_message(msg)

            return web.json_response({"status": "message received for processing"}, status=202)
        except Exception as e:
            logger.error(f"ApiPlatform: Error handling incoming API message: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    def get_services_to_register(self) -> List[ServiceRegistration]:
        comm_handlers = ["SpeakHandler", "ObserveHandler", "ToolHandler"]
        memory_handlers = ["MemorizeHandler", "RecallHandler", "ForgetHandler"]
        wa_handlers = ["DeferHandler", "SpeakHandler"]

        registrations = [
            ServiceRegistration(ServiceType.COMMUNICATION, self.api_adapter, Priority.HIGH, comm_handlers),
            ServiceRegistration(ServiceType.TOOL, self.api_adapter, Priority.HIGH, ["ToolHandler"]),
            ServiceRegistration(ServiceType.WISE_AUTHORITY, self.api_adapter, Priority.HIGH, wa_handlers),
            ServiceRegistration(ServiceType.MEMORY, self.api_adapter, Priority.HIGH, memory_handlers),
        ]
        logger.info(f"ApiPlatform: Services to register: {[(reg.service_type.value, reg.handlers) for reg in registrations]}")
        return registrations

    async def start(self) -> None:
        logger.info("ApiPlatform: Starting...")
        if hasattr(self.api_observer, 'start'):
            await self.api_observer.start()
        logger.info("ApiPlatform: Started.")

    async def run_lifecycle(self, agent_run_task: asyncio.Task) -> None:
        logger.info(f"ApiPlatform: Starting API server on {self.host}:{self.port}")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"ApiPlatform: API server running on http://{self.host}:{self.port}")
        self._web_server_stopped_event.clear()

        done, pending = await asyncio.wait(
            [agent_run_task, self._web_server_stopped_event.wait()],
            return_when=asyncio.FIRST_COMPLETED
        )

        if self._web_server_stopped_event.is_set():
            logger.info("ApiPlatform: Web server stop event received, lifecycle ending.")
        if agent_run_task in done:
            logger.info(f"ApiPlatform: Agent run task completed (Result: {agent_run_task.result() if not agent_run_task.cancelled() else 'Cancelled'}). Signalling web server shutdown.")
            self._web_server_stopped_event.set()

        for task in pending:
            task.cancel()
            try:
                await task # Allow cleanup for cancelled tasks
            except asyncio.CancelledError:
                pass # Expected

        await self._shutdown_server_components()

    async def _shutdown_server_components(self) -> None:
        logger.info("ApiPlatform: Shutting down web server components...")
        if self.site:
            try:
                await self.site.stop()
                logger.info("ApiPlatform: Web server site stopped.")
            except Exception as e:
                logger.error(f"ApiPlatform: Error stopping web server site: {e}", exc_info=True)
            self.site = None

        if self.runner:
            try:
                await self.runner.cleanup()
                logger.info("ApiPlatform: Web runner cleaned up.")
            except Exception as e:
                logger.error(f"ApiPlatform: Error cleaning up web runner: {e}", exc_info=True)
            self.runner = None
        logger.info("ApiPlatform: Web server components shutdown complete.")

    async def stop(self) -> None:
        logger.info("ApiPlatform: Stopping...")
        self._web_server_stopped_event.set()

        await self._shutdown_server_components()

        if hasattr(self.api_observer, 'stop'):
            await self.api_observer.stop()
        logger.info("ApiPlatform: Stopped.")
