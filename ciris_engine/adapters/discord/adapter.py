import asyncio
import logging
from typing import List, Any, Optional

import discord # Ensure discord.py is available

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration, CIRISRuntime
from .config import DiscordAdapterConfig
from ciris_engine.registries.base import Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, DiscordMessage

from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.secrets.tools import register_secrets_tools
from ciris_engine.adapters.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class DiscordPlatform(PlatformAdapter):
    def __init__(self, runtime: "CIRISRuntime", **kwargs: Any) -> None:
        self.runtime = runtime
        
        # Use provided adapter config or create defaults
        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            self.config = kwargs["adapter_config"]
            logger.info(f"Discord adapter using provided config: channels={self.config.monitored_channel_ids}")
        else:
            # Initialize configuration with defaults and override from kwargs
            self.config = DiscordAdapterConfig()
            if "discord_bot_token" in kwargs:
                self.config.bot_token = kwargs["discord_bot_token"]
            
            # Load configuration from profile if available
            profile = getattr(runtime, 'agent_profile', None)
            if profile and profile.discord_config:
                # Update config with profile settings
                for key, value in profile.discord_config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        logger.debug(f"DiscordPlatform: Set config {key} = {value} from profile")
            
            # Load environment variables (can override profile settings)
            self.config.load_env_vars()
        
        # Validate required configuration
        if not self.config.bot_token:
            logger.error("DiscordPlatform: 'bot_token' not found in config. This is required.")
            raise ValueError("DiscordPlatform requires 'bot_token' in configuration.")
        
        # Use config values
        self.token = self.config.bot_token
        intents = self.config.get_intents()
        self.client = discord.Client(intents=intents)

        self.discord_adapter = DiscordAdapter(
            token=self.token,
            on_message=self._handle_discord_message_event
        )

        self.discord_adapter.client = self.client

        if hasattr(self.discord_adapter, 'attach_to_client'):
             self.discord_adapter.attach_to_client(self.client)
        else:
            logger.warning("DiscordPlatform: DiscordAdapter may not have 'attach_to_client' method.")

        # Get channel IDs from kwargs and app_config, merge into config
        kwargs_channel_ids = kwargs.get("discord_monitored_channel_ids", [])
        kwargs_channel_id = kwargs.get("discord_monitored_channel_id")
        
        if kwargs_channel_ids:
            self.config.monitored_channel_ids.extend(kwargs_channel_ids)
        if kwargs_channel_id and kwargs_channel_id not in self.config.monitored_channel_ids:
            self.config.monitored_channel_ids.append(kwargs_channel_id)
            if not self.config.home_channel_id:
                self.config.home_channel_id = kwargs_channel_id
        
        # Discord configuration should be provided via kwargs or environment variables
        if not self.config.monitored_channel_ids:
            logger.warning("DiscordPlatform: No channel configuration found. Please provide channel IDs via constructor kwargs or environment variables.")
        
        if self.config.monitored_channel_ids:
            logger.info(f"DiscordPlatform: Using {len(self.config.monitored_channel_ids)} channels: {self.config.monitored_channel_ids}")
        
        self.discord_observer = DiscordObserver(
            monitored_channel_ids=self.config.monitored_channel_ids,
            deferral_channel_id=self.config.deferral_channel_id,
            wa_user_ids=self.config.admin_user_ids,
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            multi_service_sink=getattr(self.runtime, 'multi_service_sink', None),
            filter_service=getattr(self.runtime, 'adaptive_filter_service', None),
            secrets_service=getattr(self.runtime, 'secrets_service', None),
            communication_service=self.discord_adapter
        )

        self.tool_registry = ToolRegistry()
        secrets_service = getattr(self.runtime, 'secrets_service', None)

        register_discord_tools(self.tool_registry, self.client)
        if secrets_service:
            register_secrets_tools(self.tool_registry, secrets_service)
        else:
            logger.warning("DiscordPlatform: SecretsService not available for register_secrets_tools.")

        if hasattr(self.discord_adapter, 'tool_registry'):
            self.discord_adapter.tool_registry = self.tool_registry

        self._discord_client_task: Optional[asyncio.Task] = None

    async def _handle_discord_message_event(self, msg: DiscordMessage) -> None:
        logger.debug(f"DiscordPlatform: Received message from DiscordAdapter: {msg.message_id if msg else 'None'}")
        if not self.discord_observer:
            logger.warning("DiscordPlatform: DiscordObserver not available.")
            return
        if not isinstance(msg, DiscordMessage): # Ensure it's the correct type
            logger.warning(f"DiscordPlatform: Expected DiscordMessage, got {type(msg)}. Cannot process.")
            return
        await self.discord_observer.handle_incoming_message(msg)

    def get_services_to_register(self) -> List[ServiceRegistration]:
        comm_handlers = ["SpeakHandler", "ObserveHandler", "ToolHandler"]
        wa_handlers = ["DeferHandler", "SpeakHandler"]

        registrations = [
            ServiceRegistration(ServiceType.COMMUNICATION, self.discord_adapter, Priority.HIGH, comm_handlers, ["send_message", "receive_message"]),
            ServiceRegistration(ServiceType.WISE_AUTHORITY, self.discord_adapter, Priority.HIGH, wa_handlers, ["send_deferral", "fetch_guidance"]),
            ServiceRegistration(ServiceType.TOOL, self.discord_adapter, Priority.HIGH, ["ToolHandler"], ["execute_tool", "list_tools"]),
        ]
        logger.info(f"DiscordPlatform: Services to register: {[(reg.service_type.value, reg.handlers) for reg in registrations]}")
        return registrations

    async def start(self) -> None:
        logger.info("DiscordPlatform: Starting internal components...")
        if hasattr(self.discord_observer, 'start'):
            await self.discord_observer.start()
        if hasattr(self.discord_adapter, 'start'):
            await self.discord_adapter.start()
        logger.info("DiscordPlatform: Internal components started. Discord client connection deferred to run_lifecycle.")

    async def run_lifecycle(self, agent_run_task: asyncio.Task) -> None:
        logger.info("DiscordPlatform: Running lifecycle - attempting to start Discord client.")
        if not self.client or not self.token:
            logger.error("DiscordPlatform: Discord client or token not properly initialized. Cannot start.")
            if not agent_run_task.done():
                agent_run_task.cancel()
            return

        try:
            self._discord_client_task = asyncio.create_task(self.client.start(self.token), name="DiscordClientTask")
            logger.info("DiscordPlatform: Discord client start initiated.")
            
            # Wait for either the Discord client to be ready or the agent task to complete
            ready_task = asyncio.create_task(self.client.wait_until_ready(), name="DiscordReadyWait")
            
            done, pending = await asyncio.wait(
                [agent_run_task, self._discord_client_task, ready_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Check if Discord client is ready
            if ready_task in done and not ready_task.exception():
                logger.info(f"DiscordPlatform: Discord client ready! Logged in as: {self.client.user}")
                # Cancel the ready task since we've confirmed it's ready
                if not ready_task.done():
                    ready_task.cancel()
                
                # Now wait for either agent completion or Discord client failure
                done, pending = await asyncio.wait(
                    [agent_run_task, self._discord_client_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
            elif ready_task in done and ready_task.exception():
                logger.error(f"DiscordPlatform: Discord client failed to become ready: {ready_task.exception()}")
                # Cancel other tasks since Discord failed to initialize
                for task in pending:
                    task.cancel()
                if not agent_run_task.done():
                    agent_run_task.cancel()
                return

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            for task in done: # Check completed tasks for exceptions
                if task.exception():
                    task_name = task.get_name() if hasattr(task, 'get_name') else 'Unnamed task'
                    logger.error(f"DiscordPlatform: Task '{task_name}' exited with error: {task.exception()}", exc_info=task.exception())
                    # If discord client failed, ensure agent task is also stopped.
                    if task is self._discord_client_task and not agent_run_task.done():
                        agent_run_task.cancel()
                        try: await agent_run_task
                        except asyncio.CancelledError: pass

        except discord.LoginFailure as e:
            logger.error(f"DiscordPlatform: Discord login failed: {e}. Check token and intents.", exc_info=True)
            if hasattr(self.runtime, 'request_shutdown'):
                self.runtime.request_shutdown("Discord login failure")
            if not agent_run_task.done(): agent_run_task.cancel()
        except Exception as e:
            logger.error(f"DiscordPlatform: Unexpected error in run_lifecycle: {e}", exc_info=True)
            if not agent_run_task.done(): agent_run_task.cancel()
        finally:
            logger.info("DiscordPlatform: Lifecycle ending. Ensuring Discord client is properly closed.")
            if self.client and not self.client.is_closed():
                await self.client.close()
            logger.info("DiscordPlatform: Discord client closed.")

    async def stop(self) -> None:
        logger.info("DiscordPlatform: Stopping...")

        if hasattr(self.discord_observer, 'stop'):
            await self.discord_observer.stop()
        if hasattr(self.discord_adapter, 'stop'):
            await self.discord_adapter.stop()

        if self._discord_client_task and not self._discord_client_task.done():
            logger.info("DiscordPlatform: Cancelling active Discord client task.")
            self._discord_client_task.cancel()
            try:
                await self._discord_client_task
            except asyncio.CancelledError:
                logger.info("DiscordPlatform: Discord client task successfully cancelled.")

        if self.client and not self.client.is_closed():
            logger.info("DiscordPlatform: Closing Discord client connection.")
            try:
                await self.client.close()
                logger.info("DiscordPlatform: Discord client connection closed.")
            except Exception as e:
                logger.error(f"DiscordPlatform: Error while closing Discord client: {e}", exc_info=True)

        logger.info("DiscordPlatform: Stopped.")
