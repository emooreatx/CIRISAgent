import asyncio
import logging
from typing import List, Any

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import CLIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage
from .cli_adapter import CLIAdapter

logger = logging.getLogger(__name__)

class CliPlatform(PlatformAdapter):
    def __init__(self, runtime: "CIRISRuntime", **kwargs: Any) -> None:
        self.runtime = runtime
        
        # Use provided adapter config or create defaults
        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            self.config = kwargs["adapter_config"]
            logger.info(f"CLI adapter using provided config: interactive={self.config.interactive}")
        else:
            # Initialize configuration with defaults and override from kwargs
            self.config = CLIAdapterConfig()
            if "interactive" in kwargs:
                self.config.interactive = bool(kwargs["interactive"])
            
            # Load configuration from profile if available
            profile = getattr(runtime, 'agent_profile', None)
            if profile and profile.cli_config:
                # Update config with profile settings
                for key, value in profile.cli_config.dict().items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        logger.debug(f"CliPlatform: Set config {key} = {value} from profile")
            
            # Load environment variables (can override profile settings)
            self.config.load_env_vars()
        
        # Create the simplified CLI adapter
        self.cli_adapter = CLIAdapter(
            interactive=self.config.interactive,
            on_message=self._handle_incoming_message,
            multi_service_sink=getattr(runtime, 'multi_service_sink', None)
        )

    async def _handle_incoming_message(self, msg: IncomingMessage) -> None:
        """Handle incoming messages from the CLI adapter."""
        logger.debug(f"CliPlatform: Received message: {msg.message_id}")
        
        sink = getattr(self.runtime, 'multi_service_sink', None)
        if not sink:
            logger.warning("CliPlatform: No multi_service_sink available")
            return
        
        try:
            await sink.observe_message("ObserveHandler", msg, {"source": "cli"})
            logger.debug("CliPlatform: Message sent to multi_service_sink")
        except Exception as e:
            logger.error(f"CliPlatform: Error handling message: {e}", exc_info=True)

    def get_services_to_register(self) -> List[ServiceRegistration]:
        """Register CLI services."""
        # The CLI adapter implements all three service types
        registrations = [
            ServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "fetch_messages"]
            ),
            ServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]
            ),
            ServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                handlers=["DeferHandler"],
                capabilities=["fetch_guidance", "send_deferral"]
            ),
        ]
        logger.info(f"CliPlatform: Registering {len(registrations)} services")
        return registrations

    async def start(self) -> None:
        """Start the CLI adapter."""
        logger.info("CliPlatform: Starting...")
        await self.cli_adapter.start()
        logger.info("CliPlatform: Started.")

    async def run_lifecycle(self, agent_run_task: asyncio.Task[Any]) -> None:
        """Run the CLI platform lifecycle."""
        logger.info("CliPlatform: Running lifecycle.")
        try:
            await agent_run_task
        except asyncio.CancelledError:
            logger.info("CliPlatform: Agent run task was cancelled.")
        except Exception as e:
            logger.error(f"CliPlatform: Agent run task error: {e}", exc_info=True)
        finally:
            logger.info("CliPlatform: Lifecycle ending.")

    async def stop(self) -> None:
        """Stop the CLI adapter."""
        logger.info("CliPlatform: Stopping...")
        await self.cli_adapter.stop()
        logger.info("CliPlatform: Stopped.")
