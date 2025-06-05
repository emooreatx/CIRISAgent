"""Entrypoint for CIRISAgent API runtime, wires up all service routes."""
import asyncio
import logging
from typing import Optional
from aiohttp import web
from ciris_engine.adapters.api import APIAdapter, APIObserver
from ciris_engine.runtime.api.api_comms import APICommsRoutes
from ciris_engine.runtime.api.api_memory import APIMemoryRoutes
from ciris_engine.runtime.api.api_tools import APIToolsRoutes
from ciris_engine.runtime.api.api_wa import APIWARoutes
from ciris_engine.runtime.api.api_audit import APIAuditRoutes
from ciris_engine.runtime.api.api_logs import APILogsRoutes
from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.config_schemas_v1 import AppConfig

logger = logging.getLogger(__name__)

class APIRuntimeEntrypoint(CIRISRuntime):
    """API runtime entrypoint that extends CIRISRuntime with web server functionality."""
    
    def __init__(
        self, 
        service_registry=None, 
        multi_service_sink=None, 
        audit_service=None, 
        api_observer=None, 
        api_adapter=None, 
        host="0.0.0.0", 
        port=8080,
        profile_name: str = "default",
        app_config: Optional[AppConfig] = None,
    ) -> None:
        # Create API adapter if not provided
        if api_adapter is None:
            from ciris_engine.adapters.api import APIAdapter
            api_adapter = APIAdapter()
        
        # Initialize parent CIRISRuntime with API adapter as io_adapter
        super().__init__(
            profile_name=profile_name,
            io_adapter=api_adapter,
            app_config=app_config,
            startup_channel_id="api",
        )
        
        # Store the API adapter
        self.api_adapter = api_adapter
        
        # Initialize api_observer to None first
        self.api_observer = api_observer
        
        # Override services with pre-built ones if provided
        if service_registry:
            self.service_registry = service_registry
        if multi_service_sink:
            self.multi_service_sink = multi_service_sink
        if audit_service:
            self.audit_service = audit_service
        
        # Web server configuration
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None
        self._web_server_stopped = False # For idempotency

    async def _register_core_services(self) -> None:
        """Register core services including API-specific ones."""
        # First, call parent to register standard services
        await super()._register_core_services()
        
        # Now register API adapter for all communication needs
        if self.api_adapter and self.service_registry:
            from ciris_engine.registries.base import Priority
            
            # Register for all handlers that need communication
            for handler in ["SpeakHandler", "ObserveHandler", "ToolHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="communication",
                    provider=self.api_adapter,
                    priority=Priority.HIGH,
                    capabilities=["send_message", "fetch_messages"]
                )
            
            # Register as tool service. Allow overriding the provider for tests.
            tool_provider = getattr(self, "api_tool_service", self.api_adapter)
            self.service_registry.register(
                handler="ToolHandler",
                service_type="tool",
                provider=tool_provider,
                priority=Priority.HIGH,
                capabilities=[
                    "execute_tool",
                    "get_available_tools",
                    "get_tool_result",
                    "validate_parameters",
                ],
            )
            
            # Register as wise authority service
            for handler in ["DeferHandler", "SpeakHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="wise_authority",
                    provider=self.api_adapter,
                    priority=Priority.HIGH,
                    capabilities=["fetch_guidance", "send_deferral"]
                )
            
            # Register as memory service for handlers that need it
            for handler in ["MemorizeHandler", "RecallHandler", "ForgetHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="memory",
                    provider=self.api_adapter,
                    priority=Priority.HIGH,
                    capabilities=["memorize", "recall", "forget"]
                )
            
            logger.info("Registered APIAdapter for all service types during core service registration")

    def _register_routes(self) -> None:
        """Register all API routes after services are initialized."""
        # Store comms routes so tests can invoke handlers directly
        self._comms_routes = APICommsRoutes(self.api_observer, self.api_adapter)
        self._comms_routes.register(self.app)
        APIMemoryRoutes(self.multi_service_sink).register(self.app)
        APIToolsRoutes(self.multi_service_sink).register(self.app)
        APIWARoutes(self.multi_service_sink).register(self.app)
        APIAuditRoutes(self.audit_service).register(self.app)
        APILogsRoutes().register(self.app)
        logger.info("Registered all API routes")

    async def _register_api_services(self) -> None:
        """Hook for registering API specific services.

        Historically this method exposed registration logic separate from core
        services. Services are now registered during _register_core_services(),
        but this method is kept for backward compatibility with older tests and extensions.
        It's a no-op since services are already registered during core registration."""
        
        # Services are now registered in _register_core_services() 
        # This method is kept for backward compatibility
        logger.debug("_register_api_services called - services already registered during core registration")

    async def _handle_message(self, request: web.Request) -> web.Response:
        """Legacy handler shim used by older tests."""
        if hasattr(self, "_comms_routes"):
            return await self._comms_routes._handle_message(request)
        # Fallback if routes haven't been registered yet
        routes = APICommsRoutes(self.api_observer, self.api_adapter)
        return await routes._handle_message(request)

    async def initialize(self) -> None:
        """Initialize the API runtime, extending parent initialization."""
        # First, do the parent CIRISRuntime initialization
        # This includes _register_core_services() which now registers API services
        await super().initialize()
        
        # Call _register_api_services for backward compatibility with tests
        await self._register_api_services()
            
        logger.info("Initializing API-specific components...")
        
        try:
            # Create API observer if not provided
            if self.api_observer is None:
                from ciris_engine.adapters.api import APIObserver
                self.api_observer = APIObserver(
                    on_observe=None,  # Will be set later if needed
                    memory_service=self.memory_service,
                    multi_service_sink=self.multi_service_sink,
                    api_adapter=self.api_adapter,
                )
            
            # Start the API observer
            if self.api_observer:
                await self.api_observer.start()
                logger.info("API observer started")
            
            # Register all API routes after observer is created
            self._register_routes()
            
            logger.info("API Runtime initialization complete")
            
        except Exception as e:
            logger.critical(f"API Runtime initialization failed: {e}")
            raise

    async def _shutdown_web_server(self) -> None:
        """Shutdown the web server components idempotently."""
        if self._web_server_stopped:
            logger.debug("Web server already stopped or stopping.")
            return
        
        logger.info("Shutting down web server...")
        self._web_server_stopped = True # Set flag early

        # Stop web server
        if self.site:
            try:
                await self.site.stop()
                logger.info("Web server site stopped")
            except RuntimeError as e:
                logger.warning(f"Error stopping web server site (may already be stopped): {e}")
            except Exception as e:
                logger.error(f"Unexpected error stopping web server site: {e}")
            self.site = None # Clear it after trying to stop
        
        if self.runner:
            try:
                await self.runner.cleanup()
                logger.info("Web runner cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up web runner: {e}")
            self.runner = None # Clear it
        logger.info("Web server shutdown sequence complete.")

    async def run(self, num_rounds: Optional[int] = None) -> None:
        """Run the API server alongside the parent runtime processing."""
        if not self._initialized: # _initialized should be set by super().initialize()
            await self.initialize()
        
        logger.info(f"Starting API server on {self.host}:{self.port}")
        
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"API server running on http://{self.host}:{self.port}")
            await super().run(num_rounds=num_rounds)
            
        except asyncio.CancelledError:
            logger.info("API Runtime run task cancelled.")
            # Let the main shutdown handler deal with cleanup via self.shutdown()
            raise # Re-raise CancelledError so run_with_shutdown_handler can see it
        except Exception as e:
            logger.error(f"API server error during run: {e}")
            raise # Re-raise for higher level handling

    async def shutdown(self) -> None:
        """Gracefully shutdown the API runtime and all services."""
        logger.info("Shutting down API Runtime...")
        
        # Shutdown web server first
        await self._shutdown_web_server()
        
        # Stop API observer
        if self.api_observer and hasattr(self.api_observer, "stop"):
            try:
                await self.api_observer.stop()
                logger.info("API observer stopped")
            except Exception as e:
                logger.error(f"Error stopping API observer: {e}")
        
        # Call parent shutdown to handle all base services
        await super().shutdown()
        
        logger.info("API Runtime shutdown complete")