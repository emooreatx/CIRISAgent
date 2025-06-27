import asyncio
import logging
from typing import List, Optional, Any

import discord # Ensure discord.py is available

from ciris_engine.logic.adapters.base import Service
from ciris_engine.schemas.adapters import AdapterServiceRegistration
from ciris_engine.schemas.runtime.enums import ServiceType
from .config import DiscordAdapterConfig
from ciris_engine.logic.registries.base import Priority
from ciris_engine.schemas.runtime.messages import DiscordMessage

from ciris_engine.logic.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.logic.adapters.discord.discord_observer import DiscordObserver
# from ciris_engine.logic.adapters.discord.discord_tools import register_discord_tools

logger = logging.getLogger(__name__)

class DiscordPlatform(Service):
    def __init__(self, runtime: Any, **kwargs: Any) -> None:
        self.runtime = runtime
        
        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            self.config = kwargs["adapter_config"]
            logger.info(f"Discord adapter using provided config: channels={self.config.monitored_channel_ids}")
        else:
            self.config = DiscordAdapterConfig()
            if "discord_bot_token" in kwargs:
                self.config.bot_token = kwargs["discord_bot_token"]
            
            template = getattr(runtime, 'template', None)
            if template and hasattr(template, 'discord_config') and template.discord_config:
                try:
                    config_dict = template.discord_config.dict() if hasattr(template.discord_config, 'dict') else {}
                    for key, value in config_dict.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
                            logger.debug(f"DiscordPlatform: Set config {key} = {value} from template")
                except Exception as e:
                    logger.debug(f"DiscordPlatform: Could not load config from template: {e}")
            
            self.config.load_env_vars()
        
        if not self.config.bot_token:
            logger.error("DiscordPlatform: 'bot_token' not found in config. This is required.")
            raise ValueError("DiscordPlatform requires 'bot_token' in configuration.")
        
        self.token = self.config.bot_token
        intents = self.config.get_intents()
        
        # Create Discord client without explicit loop (discord.py will manage it)
        self.client = discord.Client(intents=intents)
        
        # Generate adapter_id - will be updated with actual guild_id when bot connects
        # The adapter_id is used by AuthenticationService for observer persistence
        self.adapter_id = "discord_pending"

        # Get time_service from runtime
        time_service = getattr(self.runtime, 'time_service', None)
        
        self.discord_adapter = DiscordAdapter(
            token=self.token,
            bot=self.client,
            on_message=self._handle_discord_message_event,
            time_service=time_service,
            config=self.config
        )

        if hasattr(self.discord_adapter, 'attach_to_client'):
             self.discord_adapter.attach_to_client(self.client)
        else:
            logger.warning("DiscordPlatform: DiscordAdapter may not have 'attach_to_client' method.")

        kwargs_channel_ids = kwargs.get("discord_monitored_channel_ids", [])
        kwargs_channel_id = kwargs.get("discord_monitored_channel_id")
        
        if kwargs_channel_ids:
            self.config.monitored_channel_ids.extend(kwargs_channel_ids)
        if kwargs_channel_id and kwargs_channel_id not in self.config.monitored_channel_ids:
            self.config.monitored_channel_ids.append(kwargs_channel_id)
            if not self.config.home_channel_id:
                self.config.home_channel_id = kwargs_channel_id
        
        if not self.config.monitored_channel_ids:
            logger.warning("DiscordPlatform: No channel configuration found. Please provide channel IDs via constructor kwargs or environment variables.")
        
        if self.config.monitored_channel_ids:
            logger.info(f"DiscordPlatform: Using {len(self.config.monitored_channel_ids)} channels: {self.config.monitored_channel_ids}")
        
        # Initialize observer as None - will be created in start() when services are ready
        self.discord_observer = None

        # Tool registry removed - tools are handled through ToolBus
        # self.tool_registry = ToolRegistry()
        # register_discord_tools(self.tool_registry, self.client)

        # if hasattr(self.discord_adapter, 'tool_registry'):
        #     self.discord_adapter.tool_registry = self.tool_registry

        self._discord_client_task: Optional[asyncio.Task] = None
    
    def get_channel_info(self) -> dict:
        """Provide guild info for authentication."""
        # Get first guild if connected
        if self.client.guilds:
            guild_id = str(self.client.guilds[0].id)
            # Update adapter_id with actual guild for observer persistence
            self.adapter_id = f"discord_{guild_id}"
            logger.info(f"Discord adapter updated with guild-specific adapter_id: {self.adapter_id}")
            return {'guild_id': guild_id}
        return {'guild_id': 'unknown'}

    async def _handle_discord_message_event(self, msg: DiscordMessage) -> None:
        logger.debug(f"DiscordPlatform: Received message from DiscordAdapter: {msg.message_id if msg else 'None'}")
        if not self.discord_observer:
            logger.warning("DiscordPlatform: DiscordObserver not available.")
            return
        if not isinstance(msg, DiscordMessage): # Ensure it's the correct type
            logger.warning(f"DiscordPlatform: Expected DiscordMessage, got {type(msg)}. Cannot process.")  # type: ignore[unreachable]
            return
        await self.discord_observer.handle_incoming_message(msg)

    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Register Discord services."""
        comm_handlers = ["SpeakHandler", "ObserveHandler", "ToolHandler"]
        wa_handlers = ["DeferHandler", "SpeakHandler"]

        registrations = [
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                handlers=comm_handlers,
                capabilities=["send_message", "fetch_messages"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                handlers=wa_handlers,
                capabilities=["fetch_guidance", "send_deferral"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]
            ),
        ]
        logger.info(f"DiscordPlatform: Registering {len(registrations)} services for adapter: {self.adapter_id}")
        return registrations

    async def start(self) -> None:
        logger.info("DiscordPlatform: Starting internal components...")
        
        # Create observer now that services are available
        secrets_service = getattr(self.runtime, 'secrets_service', None)
        if not secrets_service:
            logger.error("CRITICAL: secrets_service not available at start time!")
        else:
            logger.info("Found secrets_service from runtime")
            
        # Get time_service from runtime
        time_service = getattr(self.runtime, 'time_service', None)
        
        self.discord_observer = DiscordObserver(
            monitored_channel_ids=self.config.monitored_channel_ids,
            deferral_channel_id=self.config.deferral_channel_id,
            wa_user_ids=self.config.admin_user_ids,
            memory_service=getattr(self.runtime, 'memory_service', None),
            agent_id=getattr(self.runtime, 'agent_id', None),
            bus_manager=getattr(self.runtime, 'bus_manager', None),
            filter_service=getattr(self.runtime, 'adaptive_filter_service', None),
            secrets_service=secrets_service,
            communication_service=self.discord_adapter,
            time_service=time_service
        )
        
        # Secrets tools are now registered globally by SecretsToolService
        
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
            
            # Wait for Discord client to be ready with timeout
            logger.info("DiscordPlatform: Waiting for Discord client to be ready...")
            ready = await self.discord_adapter.wait_until_ready(timeout=30.0)
            
            if not ready:
                logger.error("DiscordPlatform: Discord client failed to become ready within timeout")
                if not agent_run_task.done():
                    agent_run_task.cancel()
                return
            
            logger.info(f"DiscordPlatform: Discord client ready! Logged in as: {self.client.user}")
            
            # Now wait for either the agent task or Discord client task to complete
            done, pending = await asyncio.wait(
                [agent_run_task, self._discord_client_task],
                return_when=asyncio.FIRST_COMPLETED
            )

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
                    if task is self._discord_client_task and not agent_run_task.done():
                        # Discord client failed - restart it
                        logger.warning("Discord client task failed. Attempting to restart Discord connection...")
                        # Clear the failed task
                        self._discord_client_task = None
                        # Try to restart the Discord client
                        try:
                            # Close the client if it's still open
                            if self.client and not self.client.is_closed():
                                await self.client.close()
                            # Wait a bit before reconnecting
                            await asyncio.sleep(5.0)
                            # Create a new task to restart the client
                            self._discord_client_task = asyncio.create_task(
                                self.client.start(self.token), 
                                name="DiscordClientTask"
                            )
                            logger.info("Discord client restart task created")
                            # Add the new task to the set we're waiting on
                            tasks.add(self._discord_client_task)
                        except Exception as e:
                            logger.error(f"Failed to restart Discord client: {e}")
                            # Only shutdown if we can't restart
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

        # Stop observer and adapter first
        if hasattr(self.discord_observer, 'stop'):
            await self.discord_observer.stop()
        if hasattr(self.discord_adapter, 'stop'):
            await self.discord_adapter.stop()

        # Close the Discord client before cancelling the task
        if self.client and not self.client.is_closed():
            logger.info("DiscordPlatform: Closing Discord client connection.")
            try:
                await self.client.close()
                logger.info("DiscordPlatform: Discord client connection closed.")
            except Exception as e:
                logger.error(f"DiscordPlatform: Error while closing Discord client: {e}", exc_info=True)

        # Then cancel the task
        if self._discord_client_task and not self._discord_client_task.done():
            logger.info("DiscordPlatform: Cancelling active Discord client task.")
            self._discord_client_task.cancel()
            try:
                await self._discord_client_task
            except asyncio.CancelledError:
                logger.info("DiscordPlatform: Discord client task successfully cancelled.")

        logger.info("DiscordPlatform: Stopped.")
