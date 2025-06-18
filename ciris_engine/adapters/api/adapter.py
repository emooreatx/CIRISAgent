import asyncio
import logging
from typing import List, Any, Optional

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import APIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from .api_adapter import APIAdapter

logger = logging.getLogger(__name__)

class ApiPlatform(PlatformAdapter):
    def __init__(self, runtime: "CIRISRuntime", **kwargs: Any) -> None:
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
        
        self.api_adapter = APIAdapter(
            host=self.config.host,
            port=self.config.port,
            multi_service_sink=getattr(runtime, 'multi_service_sink', None),
            service_registry=getattr(runtime, 'service_registry', None),
            runtime_control=self.runtime_control_service,
            telemetry_collector=self.telemetry_collector,
            runtime=runtime
        )
        
        self._web_server_stopped_event: Optional[asyncio.Event] = None
    
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
