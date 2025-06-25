import asyncio
import logging
from typing import List, Any

from ciris_engine.logic.adapters.base import Service
from .config import CLIAdapterConfig
from ciris_engine.logic.registries.base import Priority
from ciris_engine.schemas.adapters import AdapterServiceRegistration
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.runtime.messages import IncomingMessage
from .cli_adapter import CLIAdapter
from .cli_observer import CLIObserver

logger = logging.getLogger(__name__)

class CliPlatform(Service):
    def __init__(self, runtime: Any, **kwargs: Any) -> None:
        self.runtime = runtime
        
        # Generate stable adapter_id for observer persistence
        import os
        import socket
        # This adapter_id is used by AuthenticationService to find/create observer certificates
        self.adapter_id = f"cli_{os.getenv('USER', 'unknown')}@{socket.gethostname()}"
        logger.info(f"CLI adapter initialized with adapter_id: {self.adapter_id}")
        
        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            self.config = kwargs["adapter_config"]
            logger.info(f"CLI adapter using provided config: interactive={self.config.interactive}")
        else:
            self.config = CLIAdapterConfig()
            if "interactive" in kwargs:
                self.config.interactive = bool(kwargs["interactive"])
            
            template = getattr(runtime, 'template', None)
            if template and hasattr(template, 'cli_config') and template.cli_config:
                try:
                    config_dict = template.cli_config.dict() if hasattr(template.cli_config, 'dict') else {}
                    for key, value in config_dict.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
                            logger.debug(f"CliPlatform: Set config {key} = {value} from template")
                except Exception as e:
                    logger.debug(f"CliPlatform: Could not load config from template: {e}")
            
            self.config.load_env_vars()
        
        self.cli_adapter = CLIAdapter(
            interactive=self.config.interactive,
            on_message=self._handle_incoming_message,
            bus_manager=getattr(runtime, 'bus_manager', None),
            config=self.config
        )
        
        # Get time service from runtime
        time_service = None
        if hasattr(self.runtime, 'service_initializer') and self.runtime.service_initializer:
            time_service = getattr(self.runtime.service_initializer, 'time_service', None)
        
        # Create CLI observer
        self.cli_observer = CLIObserver(
            on_observe=lambda _: asyncio.sleep(0),  # Not used in multi-service pattern
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            bus_manager=getattr(self.runtime, 'bus_manager', None),  # multi_service_sink returns bus_manager now
            filter_service=getattr(self.runtime, 'filter_service', None),
            secrets_service=getattr(self.runtime, 'secrets_service', None),
            time_service=time_service,
            interactive=self.config.interactive,
            config=self.config
        )
    

    async def _handle_incoming_message(self, msg: IncomingMessage) -> None:
        """Handle incoming messages from the CLI adapter by routing through observer."""
        logger.debug(f"CliPlatform: Received message: {msg.message_id}")
        
        if not self.cli_observer:
            logger.warning("CliPlatform: CLIObserver not available.")
            return
        
        if not isinstance(msg, IncomingMessage):
            logger.warning(f"CliPlatform: Expected IncomingMessage, got {type(msg)}. Cannot process.")  # type: ignore[unreachable]
            return
        
        try:
            await self.cli_observer.handle_incoming_message(msg)
            logger.debug("CliPlatform: Message sent to CLIObserver")
        except Exception as e:
            logger.error(f"CliPlatform: Error handling message: {e}", exc_info=True)

    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Register CLI services."""
        registrations = [
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.cli_adapter,  # The actual service instance
                priority=Priority.HIGH,
                handlers=["SpeakHandler", "ObserveHandler"],  # Specific handlers
                capabilities=["send_message", "fetch_messages"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.cli_adapter,  # CLI adapter handles tools too
                priority=Priority.HIGH,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.cli_adapter,  # CLI adapter can handle WA too
                priority=Priority.HIGH,
                handlers=["DeferHandler", "SpeakHandler"],
                capabilities=["fetch_guidance", "send_deferral"]
            ),
        ]
        logger.info(f"CliPlatform: Registering {len(registrations)} services for adapter: {self.adapter_id}")
        return registrations

    async def start(self) -> None:
        """Start the CLI adapter and observer."""
        logger.info("CliPlatform: Starting...")
        await self.cli_adapter.start()
        if self.cli_observer:
            await self.cli_observer.start()
        logger.info("CliPlatform: Started.")

    async def run_lifecycle(self, agent_run_task: asyncio.Task[Any]) -> None:
        """Run the CLI platform lifecycle."""
        logger.info("CliPlatform: Running lifecycle.")
        
        # Create tasks to monitor
        tasks = [agent_run_task]
        
        # If we have an observer, monitor its stop event
        if self.cli_observer and hasattr(self.cli_observer, '_stop_event'):
            stop_event_task = asyncio.create_task(
                self.cli_observer._stop_event.wait(),
                name="CLIObserverStopEvent"
            )
            tasks.append(stop_event_task)
        
        try:
            # Wait for either agent task to complete or observer to signal stop
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Check what completed
            for task in done:
                if task.get_name() == "CLIObserverStopEvent":
                    logger.info("CliPlatform: Observer signaled stop (non-interactive mode)")
                    # Request global shutdown
                    from ciris_engine.logic.utils.shutdown_manager import request_global_shutdown
                    request_global_shutdown("CLI non-interactive mode completed")
                elif task == agent_run_task:
                    logger.info("CliPlatform: Agent run task completed")
                    
            # Cancel any remaining tasks
            for task in pending:
                if not task.done():
                    task.cancel()
                    
        except asyncio.CancelledError:
            logger.info("CliPlatform: Lifecycle was cancelled.")
        except Exception as e:
            logger.error(f"CliPlatform: Lifecycle error: {e}", exc_info=True)
        finally:
            logger.info("CliPlatform: Lifecycle ending.")

    async def stop(self) -> None:
        """Stop the CLI adapter and observer."""
        logger.info("CliPlatform: Stopping...")
        if self.cli_observer:
            await self.cli_observer.stop()
        await self.cli_adapter.stop()
        logger.info("CliPlatform: Stopped.")
