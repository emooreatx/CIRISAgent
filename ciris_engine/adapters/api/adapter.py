import asyncio
import logging
from typing import List, Any, Dict, Optional
from aiohttp import web

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import APIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
from ciris_engine.adapters.api.api_adapter import (
    APICommunicationService, 
    APIWiseAuthorityService, 
    APIToolService, 
    APIMemoryService,
    APIAuditService
)
from ciris_engine.adapters.api.api_observer import APIObserver # Handles incoming messages
from ciris_engine.adapters.api.api_comms import APICommsRoutes
from ciris_engine.adapters.api.api_memory import APIMemoryRoutes  
from ciris_engine.adapters.api.api_tools import APIToolsRoutes
from ciris_engine.adapters.api.api_audit import APIAuditRoutes
from ciris_engine.adapters.api.api_logs import APILogsRoutes
from ciris_engine.adapters.api.api_wa import APIWARoutes
from ciris_engine.adapters.api.api_system import APISystemRoutes
from ciris_engine.telemetry.comprehensive_collector import ComprehensiveTelemetryCollector

logger = logging.getLogger(__name__)

class ApiPlatform(PlatformAdapter):
    def __init__(self, runtime: "CIRISRuntime", **kwargs: Any) -> None:
        self.runtime = runtime
        
        # Initialize configuration with defaults and override from kwargs
        self.config = APIAdapterConfig()
        if "host" in kwargs and kwargs["host"] is not None:
            self.config.host = kwargs["host"]
        if "port" in kwargs and kwargs["port"] is not None:
            self.config.port = int(kwargs["port"])
        
        # Load environment variables
        self.config.load_env_vars()
        
        # Create separate service instances
        self.communication_service = APICommunicationService()
        self.wa_service = APIWiseAuthorityService()
        self.tool_service = APIToolService()
        self.memory_service = APIMemoryService()
        self.audit_service = APIAuditService()
        
        # Use config values
        self.host = self.config.host
        self.port = self.config.port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._web_server_stopped_event: Optional[asyncio.Event] = None

        self.api_observer = APIObserver(
            on_observe=self._default_observe_callback,
            memory_service=getattr(self.runtime, 'memory_service', None),
            multi_service_sink=getattr(self.runtime, 'multi_service_sink', None),
            api_adapter=self.communication_service  # Use communication service for observer
        )
        
        # Initialize comprehensive telemetry collector
        self.telemetry_collector = ComprehensiveTelemetryCollector(self.runtime)
        
        self._setup_routes()

    def _ensure_stop_event(self) -> None:
        """Ensure stop event is created when needed in async context."""
        if self._web_server_stopped_event is None:
            try:
                self._web_server_stopped_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create stop event outside of async context")

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
        # Legacy route for backwards compatibility
        self.app.router.add_post("/api/v1/message", self._handle_incoming_api_message)
        
        # Register comprehensive API routes
        comms_routes = APICommsRoutes(self.api_observer, self.communication_service)
        comms_routes.register(self.app)
        
        # Register other API route modules
        memory_routes = APIMemoryRoutes(getattr(self.runtime, 'multi_service_sink', None))
        memory_routes.register(self.app)
        
        tools_routes = APIToolsRoutes(getattr(self.runtime, 'multi_service_sink', None))
        tools_routes.register(self.app)
        
        audit_routes = APIAuditRoutes(self.audit_service)
        audit_routes.register(self.app)
        
        logs_routes = APILogsRoutes(getattr(self.runtime, 'multi_service_sink', None))
        logs_routes.register(self.app)
        
        wa_routes = APIWARoutes(self.wa_service)
        wa_routes.register(self.app)
        
        # Register system telemetry and control routes
        system_routes = APISystemRoutes(self.telemetry_collector)
        system_routes.register(self.app)
        
        logger.info("ApiPlatform: Comprehensive API routes registered (v1/messages, v1/memory, v1/tools, v1/audit, v1/logs, v1/wa, v1/system)")

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
        comm_handlers = ["SpeakHandler", "ObserveHandler"]
        memory_handlers = ["MemorizeHandler", "RecallHandler", "ForgetHandler"]
        wa_handlers = ["DeferHandler", "SpeakHandler"]
        audit_handlers = ["TaskCompleteHandler", "ObserveHandler", "DeferHandler"]

        registrations = [
            ServiceRegistration(ServiceType.COMMUNICATION, self.communication_service, Priority.HIGH, comm_handlers, ["send_message", "receive_message"]),
            ServiceRegistration(ServiceType.TOOL, self.tool_service, Priority.HIGH, ["ToolHandler"], ["execute_tool", "list_tools"]),
            ServiceRegistration(ServiceType.WISE_AUTHORITY, self.wa_service, Priority.HIGH, wa_handlers, ["send_deferral", "fetch_guidance"]),
            ServiceRegistration(ServiceType.MEMORY, self.memory_service, Priority.HIGH, memory_handlers, ["memorize", "recall", "forget"]),
            ServiceRegistration(ServiceType.AUDIT, self.audit_service, Priority.HIGH, audit_handlers, ["log_action", "get_audit_trail"]),
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
        
        self._ensure_stop_event()
        if self._web_server_stopped_event:
            self._web_server_stopped_event.clear()

        tasks_to_wait = [agent_run_task]
        if self._web_server_stopped_event:
            tasks_to_wait.append(asyncio.create_task(self._web_server_stopped_event.wait()))

        done, pending = await asyncio.wait(
            tasks_to_wait,
            return_when=asyncio.FIRST_COMPLETED
        )

        if self._web_server_stopped_event and self._web_server_stopped_event.is_set():
            logger.info("ApiPlatform: Web server stop event received, lifecycle ending.")
        if agent_run_task in done:
            logger.info(f"ApiPlatform: Agent run task completed (Result: {agent_run_task.result() if not agent_run_task.cancelled() else 'Cancelled'}). Signalling web server shutdown.")
            if self._web_server_stopped_event:
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
        if self._web_server_stopped_event:
            self._web_server_stopped_event.set()

        await self._shutdown_server_components()

        if hasattr(self.api_observer, 'stop'):
            await self.api_observer.stop()
        logger.info("ApiPlatform: Stopped.")
