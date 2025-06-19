import asyncio
import logging
from typing import List, Any, Optional

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, RuntimeInterface
from .config import APIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
from .api_adapter import APIAdapter
from .api_observer import APIObserver

logger = logging.getLogger(__name__)

class ApiPlatform(PlatformAdapter):
    def __init__(self, runtime: "RuntimeInterface", **kwargs: Any) -> None:
        self.runtime = runtime
        
        self.config = APIAdapterConfig()
        if "host" in kwargs and kwargs["host"] is not None:
            self.config.host = kwargs["host"]
        if "port" in kwargs and kwargs["port"] is not None:
            self.config.port = int(kwargs["port"])
        
        template = getattr(runtime, 'template', None)
        if template and hasattr(template, 'api_config') and template.api_config:
            try:
                config_dict = template.api_config.dict() if hasattr(template.api_config, 'dict') else {}
                for key, value in config_dict.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        logger.debug(f"ApiPlatform: Set config {key} = {value} from template")
            except Exception as e:
                logger.debug(f"ApiPlatform: Could not load config from template: {e}")
        
        self.config.load_env_vars()
        
        from ciris_engine.telemetry.comprehensive_collector import ComprehensiveTelemetryCollector
        self.telemetry_collector = ComprehensiveTelemetryCollector(self.runtime)
        
        from ciris_engine.runtime.runtime_control import RuntimeControlService
        self.runtime_control_service = RuntimeControlService(
            telemetry_collector=self.telemetry_collector,
            adapter_manager=getattr(self.runtime, 'adapter_manager', None),
            config_manager=getattr(self.runtime, 'config_manager', None)
        )
        
        # Generate stable adapter_id based on host and port
        self.adapter_id = f"api:{self.config.host}:{self.config.port}"
        
        # Store runtime reference - services will be accessed lazily
        self.runtime = runtime
        
        self.api_adapter = APIAdapter(
            host=self.config.host,
            port=self.config.port,
            bus_manager=None,  # Will be set lazily
            service_registry=None,    # Will be set lazily
            runtime_control=self.runtime_control_service,
            telemetry_collector=self.telemetry_collector,
            runtime=runtime,
            on_message=self._handle_api_message_event  # Add callback for messages
        )
        
        # Create API observer
        self.api_observer = APIObserver(
            on_observe=lambda _: asyncio.sleep(0),  # Not used in multi-service pattern
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            bus_manager=getattr(self.runtime, 'bus_manager', None),  # multi_service_sink returns bus_manager now
            api_adapter=self.api_adapter,
            secrets_service=getattr(self.runtime, 'secrets_service', None)
        )
        
        self._web_server_stopped_event: Optional[asyncio.Event] = None
    
    async def _handle_api_message_event(self, msg: IncomingMessage) -> None:
        """Handle incoming API messages by routing through observer."""
        logger.debug(f"ApiPlatform: Received message from APIAdapter: {msg.message_id if msg else 'None'}")
        if not self.api_observer:
            logger.warning("ApiPlatform: APIObserver not available.")
            return
        if not isinstance(msg, IncomingMessage):
            logger.warning(f"ApiPlatform: Expected IncomingMessage, got {type(msg)}. Cannot process.")  # type: ignore[unreachable]
            return
        await self.api_observer.handle_incoming_message(msg)
    
    def get_channel_info(self) -> dict[str, Any]:
        """Provide host and port info for authentication."""
        return {
            'host': self.config.host,
            'port': self.config.port
        }

    def _ensure_stop_event(self) -> None:
        """Ensure stop event is created when needed in async context."""
        if self._web_server_stopped_event is None:
            try:
                self._web_server_stopped_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create stop event outside of async context")

    def get_services_to_register(self) -> List[ServiceRegistration]:
        """Register the API adapter as a communication service."""
        basic_capabilities = ["send_message", "fetch_messages", "health_check"]
        
        registrations = [
            ServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.api_adapter,
                priority=Priority.NORMAL,
                handlers=["SpeakHandler"],  # API primarily responds
                capabilities=basic_capabilities
            )
        ]
        logger.info(f"ApiPlatform: Registering API communication service with basic capabilities: {basic_capabilities}")
        return registrations

    async def start(self) -> None:
        """Start the API adapter."""
        logger.info("ApiPlatform: Starting...")
        
        # Update services now that they should be initialized
        if hasattr(self.runtime, 'service_initializer') and self.runtime.service_initializer:
            if hasattr(self.runtime.service_initializer, 'bus_manager'):
                self.api_adapter.bus_manager = self.runtime.service_initializer.bus_manager
                self.api_observer.bus_manager = self.runtime.service_initializer.bus_manager
                logger.info(f"ApiPlatform: Set bus_manager")
            else:
                logger.warning("ApiPlatform: bus_manager not available from runtime")
        else:
            logger.warning("ApiPlatform: service_initializer not available from runtime")
            
        if hasattr(self.runtime, 'service_registry'):
            self.api_adapter.service_registry = self.runtime.service_registry
            logger.info(f"ApiPlatform: Set service_registry: {self.api_adapter.service_registry}")
        else:
            logger.warning("ApiPlatform: service_registry not available from runtime")
            
        # Update observer services
        if hasattr(self.runtime, 'memory_service'):
            self.api_observer.memory_service = self.runtime.memory_service
            logger.info("ApiPlatform: Set memory_service on observer")
            
        if hasattr(self.runtime, 'agent_identity') and self.runtime.agent_identity:
            self.api_observer.agent_id = getattr(self.runtime.agent_identity, 'agent_id', None)
            logger.info(f"ApiPlatform: Set agent_id on observer: {self.api_observer.agent_id}")
            
        if hasattr(self.runtime, 'secrets_service'):
            self.api_observer.secrets_service = self.runtime.secrets_service
            logger.info("ApiPlatform: Set secrets_service on observer")
        
        await self.api_adapter.start()
        self._ensure_stop_event()
        logger.info("ApiPlatform: Started.")
    
    async def run_lifecycle(self, agent_run_task: asyncio.Task[Any]) -> None:
        """Run the API platform lifecycle."""
        logger.info("ApiPlatform: Running lifecycle.")
        self._ensure_stop_event()
        
        if self._web_server_stopped_event:
            done, pending = await asyncio.wait(
                [agent_run_task, asyncio.create_task(self._web_server_stopped_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            await agent_run_task
    
    async def stop(self) -> None:
        """Stop the API adapter."""
        logger.info("ApiPlatform: Stopping...")
        await self.api_adapter.stop()
        if self._web_server_stopped_event:
            self._web_server_stopped_event.set()
        logger.info("ApiPlatform: Stopped.")
