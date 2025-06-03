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
        service_registry, 
        multi_service_sink, 
        audit_service, 
        api_observer, 
        api_adapter, 
        host="0.0.0.0", 
        port=8080,
        profile_name: str = "default",
        app_config: Optional[AppConfig] = None,
    ):
        # Initialize parent CIRISRuntime with API adapter as io_adapter
        super().__init__(
            profile_name=profile_name,
            io_adapter=api_adapter,
            app_config=app_config,
            startup_channel_id="api",
            service_registry=service_registry,
            audit_service=audit_service,
            multi_service_sink=multi_service_sink,

        )
        
        # Override services with pre-built ones
        #self.multi_service_sink = multi_service_sink
        #self.audit_service = audit_service
        self.api_observer = api_observer
        #self.api_adapter = api_adapter
        
        # Web server configuration
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None
        self._web_server_stopped = False # For idempotency


        # Register all service routes
        APICommsRoutes(self.api_observer, self.api_adapter).register(self.app)
        APIMemoryRoutes(self.multi_service_sink).register(self.app)
        APIToolsRoutes(self.multi_service_sink).register(self.app)
        APIWARoutes(self.multi_service_sink).register(self.app)
        APIAuditRoutes(self.audit_service).register(self.app)
        APILogsRoutes().register(self.app)

    async def initialize(self) -> None:
        """Initialize the API runtime, extending parent initialization."""
        # First, do the parent CIRISRuntime initialization
        await super().initialize()
            
        logger.info("Initializing API-specific components...")
        
        try:
            # Start the API observer
            if self.api_observer:
                await self.api_observer.start()
                logger.info("API observer started")
            
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
