import asyncio
import logging
from typing import List, Any, Optional

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import CLIAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, IncomingMessage

from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_observer import CLIObserver
from ciris_engine.adapters.cli.cli_tools import CLIToolService
from ciris_engine.adapters.cli.cli_wa_service import CLIWiseAuthorityService

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
        
        # Use config values
        self.interactive = self.config.interactive

        self.cli_adapter = CLIAdapter() # For sending messages
        self.cli_tool_service = CLIToolService()
        self.cli_wa_service = CLIWiseAuthorityService()

        # CLIObserver constructor takes: on_observe, memory_service, agent_id, multi_service_sink,
        # filter_service, secrets_service, interactive
        self.cli_observer = CLIObserver(
            on_observe=self._handle_observe_event,
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            multi_service_sink=getattr(self.runtime, 'multi_service_sink', None),
            filter_service=getattr(self.runtime, 'adaptive_filter_service', None), # Assuming this is the intended filter service
            secrets_service=getattr(self.runtime, 'secrets_service', None),
            interactive=self.config.interactive,
            config=self.config
        )

    async def _handle_observe_event(self, payload: Any) -> None: # payload can be Dict or IncomingMessage
        logger.debug(f"CliPlatform: Received observe event: {payload}")
        sink = getattr(self.runtime, 'multi_service_sink', None)
        if not sink:
            logger.warning("CliPlatform: No multi_service_sink available for observe payload")
            return

        try:
            msg: Optional[IncomingMessage] = None
            if isinstance(payload, IncomingMessage):
                msg = payload
            elif isinstance(payload, dict):
                content = payload.get("content", "")
                message_id = str(payload.get("message_id", f"cli_{asyncio.get_event_loop().time()}"))
                author_id = str(payload.get("author_id", payload.get("context", {}).get("author_id", "local_user")))
                author_name = str(payload.get("author_name", payload.get("context", {}).get("author_name", "User")))
                channel_id = str(payload.get("channel_id", payload.get("context", {}).get("channel_id", "cli")))

                additional_fields = {}
                # For Pydantic v2, model_fields can be used. For v1, __fields__
                model_fields = getattr(IncomingMessage, 'model_fields', getattr(IncomingMessage, '__fields__', {}))
                for key_from_payload in payload: # Renamed to avoid clash with model_fields key
                    if key_from_payload not in ["content", "message_id", "author_id", "author_name", "channel_id", "context"] and key_from_payload in model_fields:
                        additional_fields[key_from_payload] = payload[key_from_payload]

                msg = IncomingMessage(
                    message_id=message_id,
                    author_id=author_id,
                    author_name=author_name,
                    content=content,
                    destination_id=channel_id, # Alias for channel_id
                    **additional_fields
                )
            else:
                logger.error(f"CliPlatform: Observe callback received unknown data type: {type(payload)}")
                return

            if msg:
                await sink.observe_message("ObserveHandler", msg, {"source": "cli"})
                logger.debug(f"CliPlatform: Message sent to multi_service_sink.")

        except Exception as e:
            logger.error(f"CliPlatform: Error in _handle_observe_event: {e}", exc_info=True)

    def get_services_to_register(self) -> List[ServiceRegistration]:
        comms_handlers = [
            "SpeakHandler", "ObserveHandler", "ToolHandler",
            "DeferHandler", "MemorizeHandler", "RecallHandler", "ForgetHandler"
        ]

        registrations = [
            ServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.cli_adapter,
                priority=Priority.NORMAL,
                handlers=comms_handlers,
                capabilities=["send_message", "receive_message"]
            ),
            ServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.cli_tool_service,
                priority=Priority.NORMAL,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "list_tools"]
            ),
            ServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.cli_wa_service,
                priority=Priority.NORMAL,
                handlers=["DeferHandler", "SpeakHandler"],
                capabilities=["send_deferral", "fetch_guidance"]
            ),
        ]
        logger.info(f"CliPlatform: Services to register: {[(reg.service_type.value, reg.handlers) for reg in registrations]}")
        return registrations

    async def start(self) -> None:
        logger.info("CliPlatform: Starting...")
        if hasattr(self.cli_adapter, 'start'):
            await self.cli_adapter.start()
        if hasattr(self.cli_observer, 'start'):
            await self.cli_observer.start()
        logger.info("CliPlatform: Started.")

    async def run_lifecycle(self, agent_run_task: asyncio.Task) -> None:
        logger.info("CliPlatform: Running lifecycle.")
        try:
            await agent_run_task
        except asyncio.CancelledError:
            logger.info("CliPlatform: Agent run task was cancelled.")
        finally:
            logger.info("CliPlatform: Agent run task finished or cancelled. Lifecycle ending.")

    async def stop(self) -> None:
        logger.info("CliPlatform: Stopping...")

        if hasattr(self.cli_observer, 'stop'):
            await self.cli_observer.stop()
        if hasattr(self.cli_adapter, 'stop'):
            await self.cli_adapter.stop()

        # CLIToolService and CLIWiseAuthorityService might not have async stop
        # or even stop methods at all. Handle this gracefully.
        for service_name, service_instance in [("CLIWiseAuthorityService", self.cli_wa_service),
                                               ("CLIToolService", self.cli_tool_service)]:
            if hasattr(service_instance, 'stop'):
                try:
                    stop_method = getattr(service_instance, 'stop')
                    if asyncio.iscoroutinefunction(stop_method):
                        await stop_method()
                    else:
                        stop_method() # Call synchronously if not a coroutine
                except Exception as e:
                    logger.error(f"Error stopping {service_name}: {e}")

        logger.info("CliPlatform: Stopped.")
