import asyncio
import logging
from typing import Any, List, Optional

from ciris_engine.logic.adapters.base import Service
from ciris_engine.schemas.adapters import AdapterServiceRegistration
from .config import APIAdapterConfig
from ciris_engine.schemas.runtime.messages import IncomingMessage
from .api_adapter import APIAdapter
from .api_observer import APIObserver

logger = logging.getLogger(__name__)

class ApiPlatform(Service):
    def __init__(self, runtime: Any, **kwargs: Any) -> None:
        # Initialize the parent Service class
        super().__init__(config=kwargs.get('adapter_config'))
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
        
        from ciris_engine.logic.services.runtime.control_service import RuntimeControlService
        self.runtime_control_service = RuntimeControlService(
            runtime=self.runtime,
            adapter_manager=getattr(self.runtime, 'adapter_manager', None),
            config_manager=getattr(self.runtime, 'config_manager', None)
        )
        
        # Generate stable adapter_id based on host and port
        # This is used by AuthenticationService for observer persistence
        self.adapter_id = f"api_{self.config.host}:{self.config.port}"
        logger.info(f"API adapter initialized with adapter_id: {self.adapter_id}")
        
        # Store runtime reference - services will be accessed lazily
        self.runtime = runtime
        
        # Store config for lazy initialization
        self.api_adapter = None
        self.api_observer = None
        
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
    
    def get_channel_info(self) -> dict:
        """Provide host and port info for authentication."""
        return {
            'host': self.config.host,
            'port': str(self.config.port)  # ChannelIdentity expects all metadata to be strings
        }

    def _ensure_stop_event(self) -> None:
        """Ensure stop event is created when needed in async context."""
        if self._web_server_stopped_event is None:
            try:
                self._web_server_stopped_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create stop event outside of async context")

    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Register the API adapter services."""
        from ciris_engine.schemas.runtime.enums import ServiceType
        from ciris_engine.logic.registries.base import Priority
        
        registrations = [
            # API adapter provides runtime control capabilities
            AdapterServiceRegistration(
                service_type=ServiceType.RUNTIME_CONTROL,
                provider=self.runtime_control_service,
                priority=Priority.HIGH,
                handlers=None,  # Global service
                capabilities=["get_status", "set_state", "shutdown", "manage_adapters", "update_config"]
            ),
            # API adapter also provides communication via REST endpoints
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self,  # The adapter itself handles REST communication
                priority=Priority.NORMAL,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "fetch_messages"]
            ),
        ]
        logger.info(f"ApiPlatform: Registering {len(registrations)} services for adapter: {self.adapter_id}")
        return registrations

    async def start(self) -> None:
        """Start the API adapter."""
        logger.info("ApiPlatform: Starting...")
        
        # Get bus manager from runtime
        bus_manager = None
        if hasattr(self.runtime, 'service_initializer') and self.runtime.service_initializer:
            if hasattr(self.runtime.service_initializer, 'bus_manager'):
                bus_manager = self.runtime.service_initializer.bus_manager
                logger.info(f"ApiPlatform: Got bus_manager from service_initializer")
            else:
                logger.warning("ApiPlatform: bus_manager not available from service_initializer")
        else:
            # Try direct access
            bus_manager = getattr(self.runtime, 'bus_manager', None)
            if bus_manager:
                logger.info("ApiPlatform: Got bus_manager directly from runtime")
            else:
                logger.warning("ApiPlatform: bus_manager not available from runtime")
        
        service_registry = getattr(self.runtime, 'service_registry', None)
        
        # Create API adapter now that we have dependencies
        self.api_adapter = APIAdapter(
            host=self.config.host,
            port=self.config.port,
            bus_manager=bus_manager,
            service_registry=service_registry,
            runtime_control=self.runtime_control_service,
            runtime=self.runtime,
            on_message=self._handle_api_message_event
        )
        
        # Get time service from runtime
        time_service = None
        if hasattr(self.runtime, 'service_initializer') and self.runtime.service_initializer:
            time_service = getattr(self.runtime.service_initializer, 'time_service', None)
        
        # Create API observer
        self.api_observer = APIObserver(
            on_observe=lambda _: asyncio.sleep(0),
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            bus_manager=bus_manager,
            api_adapter=self.api_adapter,
            secrets_service=getattr(self.runtime, 'secrets_service', None),
            time_service=time_service
        )
        
        # Update observer services if available
        if hasattr(self.runtime, 'agent_identity') and self.runtime.agent_identity:
            self.api_observer.agent_id = getattr(self.runtime.agent_identity, 'agent_id', None)
            logger.info(f"ApiPlatform: Set agent_id on observer: {self.api_observer.agent_id}")
        
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
        if self.api_adapter:
            await self.api_adapter.stop()
        if self._web_server_stopped_event:
            self._web_server_stopped_event.set()
        logger.info("ApiPlatform: Stopped.")
    
    # Communication service interface methods
    async def send_message(self, channel_id: str, content: str, reference_message_id: Optional[str] = None) -> bool:
        """Send a message via API response."""
        # API adapter stores messages for HTTP responses
        if self.api_observer:
            return await self.api_observer.send_message(channel_id, content, reference_message_id)
        return False
    
    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[IncomingMessage]:
        """Fetch messages from API requests."""
        # API adapter doesn't actively fetch - it receives via HTTP
        return []
