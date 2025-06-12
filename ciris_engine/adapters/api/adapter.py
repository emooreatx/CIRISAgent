import asyncio
import logging
from typing import List, Any, Dict, Optional
from aiohttp import web

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import APIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
# Remove mock service imports - we'll use runtime services directly
from ciris_engine.adapters.api.api_observer import APIObserver # Handles incoming messages
from ciris_engine.adapters.api.api_comms import APICommsRoutes
from ciris_engine.adapters.api.api_memory import APIMemoryRoutes  
from ciris_engine.adapters.api.api_tools import APIToolsRoutes
from ciris_engine.adapters.api.api_audit import APIAuditRoutes
from ciris_engine.adapters.api.api_logs import APILogsRoutes
from ciris_engine.adapters.api.api_wa import APIWARoutes
from ciris_engine.adapters.api.api_system import APISystemRoutes
from ciris_engine.adapters.api.api_runtime_control import APIRuntimeControlRoutes
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
        
        # Load configuration from profile if available
        profile = getattr(runtime, 'agent_profile', None)
        if profile and profile.api_config:
            # Update config with profile settings
            for key, value in profile.api_config.dict().items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    logger.debug(f"ApiPlatform: Set config {key} = {value} from profile")
        
        # Load environment variables (can override profile settings)
        self.config.load_env_vars()
        
        # Get real services from runtime registry
        self._service_registry = getattr(runtime, 'service_registry', None)
        self._multi_service_sink = getattr(runtime, 'multi_service_sink', None)
        self._audit_service_pending = False
        
        # We'll access services through the registry when needed
        # No more creating mock service instances
        
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
            api_adapter=None  # No mock service needed
        )
        
        # Initialize comprehensive telemetry collector
        self.telemetry_collector = ComprehensiveTelemetryCollector(self.runtime)
        
        # Initialize runtime control service
        from ciris_engine.runtime.runtime_control import RuntimeControlService
        self.runtime_control_service = RuntimeControlService(
            telemetry_collector=self.telemetry_collector,
            adapter_manager=getattr(self.runtime, 'adapter_manager', None),
            config_manager=getattr(self.runtime, 'config_manager', None)
        )
        
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
        
        # Get real services from runtime
        multi_service_sink = getattr(self.runtime, 'multi_service_sink', None)
        
        # For now, try to get audit service from runtime cache
        audit_service = None
        if hasattr(self.runtime, '_main_registry_cache'):
            audit_service = self.runtime._main_registry_cache.get('_audit_service')
        
        # If not in cache, we'll need to get it asynchronously later
        self._audit_service_pending = audit_service is None
        
        # Register comprehensive API routes
        # Communications routes need special handling due to observer
        comms_routes = APICommsRoutes(self.api_observer, None)
        comms_routes.register(self.app)
        
        # Register other API route modules using real services
        memory_routes = APIMemoryRoutes(multi_service_sink)
        memory_routes.register(self.app)
        
        tools_routes = APIToolsRoutes(multi_service_sink)
        tools_routes.register(self.app)
        
        if audit_service:
            audit_routes = APIAuditRoutes(audit_service)
            audit_routes.register(self.app)
        else:
            logger.warning("Audit service not available, audit routes not registered")
        
        logs_routes = APILogsRoutes(multi_service_sink)
        logs_routes.register(self.app)
        
        # WA routes use multi_service_sink not direct WA service
        wa_routes = APIWARoutes(multi_service_sink)
        wa_routes.register(self.app)
        
        # Register system telemetry and control routes
        system_routes = APISystemRoutes(self.telemetry_collector)
        system_routes.register(self.app)
        
        # Register runtime control routes
        runtime_control_routes = APIRuntimeControlRoutes(self.runtime_control_service)
        runtime_control_routes.register(self.app)
        
        logger.info("ApiPlatform: Comprehensive API routes registered using runtime services")

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
        # API adapter should not register any services - it uses runtime services
        # Return empty list since we're just a transport layer
        registrations = []
        logger.info("ApiPlatform: Not registering any services (using runtime services)")
        return registrations

    async def start(self) -> None:
        logger.info("ApiPlatform: Starting...")
        if hasattr(self.api_observer, 'start'):
            await self.api_observer.start()
            
        # Get audit service asynchronously if needed
        if self._audit_service_pending and self._service_registry:
            try:
                audit_service = await self._service_registry.get_service("APIAdapter", "audit")
                if audit_service:
                    # Re-register audit routes with real service
                    audit_routes = APIAuditRoutes(audit_service)
                    audit_routes.register(self.app)
                    logger.info("ApiPlatform: Audit routes registered with real service")
            except Exception as e:
                logger.warning(f"Could not get audit service: {e}")
                
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
