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
        self.config: DiscordAdapterConfig

        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            # Ensure adapter_config is a DiscordAdapterConfig instance
            adapter_config = kwargs["adapter_config"]
            if isinstance(adapter_config, DiscordAdapterConfig):
                self.config = adapter_config
            elif isinstance(adapter_config, dict):
                self.config = DiscordAdapterConfig(**adapter_config)
            else:
                logger.warning(f"Invalid adapter_config type: {type(adapter_config)}. Creating default config.")
                self.config = DiscordAdapterConfig()
            logger.info(f"Discord adapter using provided config: channels={self.config.monitored_channel_ids}")
        else:
            # Check if config values are passed directly as kwargs (from API load_adapter)
            if "bot_token" in kwargs or "channel_id" in kwargs or "server_id" in kwargs:
                # Create config from direct kwargs
                config_dict = {}
                if "bot_token" in kwargs:
                    config_dict["bot_token"] = kwargs["bot_token"]
                if "channel_id" in kwargs:
                    config_dict["monitored_channel_ids"] = [kwargs["channel_id"]]
                    config_dict["home_channel_id"] = kwargs["channel_id"]
                if "server_id" in kwargs:
                    config_dict["server_id"] = kwargs["server_id"]
                # Add other config fields if present
                for key in ["deferral_channel_id", "admin_user_ids", "snore_channel_id"]:
                    if key in kwargs:
                        config_dict[key] = kwargs[key]
                
                self.config = DiscordAdapterConfig(**config_dict)
                logger.info(f"Discord adapter created config from direct kwargs: bot_token={'***' if self.config.bot_token else 'None'}, channels={self.config.monitored_channel_ids}")
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
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10

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
            logger.warning(f"DiscordPlatform: Expected DiscordMessage, got {type(msg)}. Cannot process.")
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

            # Give the client a moment to initialize before waiting
            await asyncio.sleep(1.0)
            
            # Wait for Discord client to be ready with timeout
            logger.info("DiscordPlatform: Waiting for Discord client to be ready...")
            ready = await self.discord_adapter.wait_until_ready(timeout=30.0)

            if not ready:
                logger.error("DiscordPlatform: Discord client failed to become ready within timeout")
                if not agent_run_task.done():
                    agent_run_task.cancel()
                return

            logger.info(f"DiscordPlatform: Discord client ready! Logged in as: {self.client.user}")

            # Reset reconnect attempts on successful connection
            self._reconnect_attempts = 0

            # Now wait for either the agent task or Discord client task to complete
            # Keep retrying Discord connection on transient errors
            while not agent_run_task.done():
                done, pending = await asyncio.wait(
                    [agent_run_task, self._discord_client_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Check if agent task completed
                if agent_run_task in done:
                    # Agent is shutting down, cancel Discord task
                    if self._discord_client_task and not self._discord_client_task.done():
                        self._discord_client_task.cancel()
                        try:
                            await self._discord_client_task
                        except asyncio.CancelledError:
                            pass
                    break

                # Check if Discord task failed
                if self._discord_client_task in done and self._discord_client_task.exception():
                    exc = self._discord_client_task.exception()
                    task_name = self._discord_client_task.get_name() if hasattr(self._discord_client_task, 'get_name') else 'DiscordClientTask'
                    logger.error(f"DiscordPlatform: Task '{task_name}' exited with error: {exc}", exc_info=exc)

                    # Determine if we should retry this error
                    should_retry = False
                    exc_str = str(exc)

                    # Known transient errors that should always retry
                    known_transient = [
                        "Concurrent call to receive() is not allowed",
                        "WebSocket connection is closed.",
                        "Shard ID None has stopped responding to the gateway.",
                        "Session is closed",
                        "Cannot write to closing transport",
                        "Connection reset by peer",
                        "Connection refused",
                        "Network is unreachable",
                        "Temporary failure in name resolution",
                        "Connection timed out",
                        "Remote end closed connection",
                        "HTTP 502", "HTTP 503", "HTTP 504",  # Gateway errors
                        "CloudFlare", "Cloudflare",  # CF errors
                        "rate limit", "Rate limit",  # Rate limiting
                        "429",  # Too Many Requests
                        "SSL", "TLS", "certificate",  # SSL/TLS errors
                        "ECONNRESET", "EPIPE", "ETIMEDOUT",  # Socket errors
                        "getaddrinfo failed",  # DNS errors
                        "Name or service not known"
                    ]

                    # Check for known transient errors
                    if any(msg in exc_str for msg in known_transient):
                        should_retry = True

                    # Connection/network related exceptions should retry
                    elif isinstance(exc, (
                        RuntimeError,
                        discord.ConnectionClosed,
                        discord.HTTPException,
                        discord.GatewayNotFound,
                        ConnectionError,
                        ConnectionResetError,
                        ConnectionAbortedError,
                        ConnectionRefusedError,
                        TimeoutError,
                        OSError
                    )):
                        should_retry = True

                    # Check for aiohttp exceptions
                    elif exc.__class__.__module__.startswith('aiohttp'):
                        should_retry = True

                    # Login failures should NOT retry (bad token, etc)
                    elif isinstance(exc, (discord.LoginFailure, discord.Forbidden)):
                        should_retry = False

                    # Default: treat unknown errors as transient (fail open, not closed)
                    else:
                        logger.warning(f"Unknown error type {type(exc).__name__}: {exc}. Treating as transient.")
                        should_retry = True

                    if should_retry:
                        error_type = type(exc).__name__
                        logger.warning(f"Discord client encountered error ({error_type}: {exc_str[:100]}...). Attempting to reconnect... (attempt {self._reconnect_attempts + 1}/{self._max_reconnect_attempts})")

                        # Check if we've exceeded max reconnect attempts
                        if self._reconnect_attempts >= self._max_reconnect_attempts:
                            logger.error(f"Exceeded maximum reconnect attempts ({self._max_reconnect_attempts}). Giving up.")
                            break

                        self._reconnect_attempts += 1
                        # Clear the failed task
                        self._discord_client_task = None
                        # Try to restart the Discord client
                        try:
                            # Close the client if it's still open
                            if self.client and not self.client.is_closed():
                                await self.client.close()
                            
                            # Clear all event handlers from the old client to prevent conflicts
                            if self.client:
                                self.client.clear()
                                # Give the client time to fully close
                                await asyncio.sleep(1.0)

                            # Always recreate the client for safety when reconnecting
                            # This ensures we have a fresh session and connection state
                            logger.info("Recreating Discord client for reconnection...")
                            # Create a new Discord client instance
                            intents = self.config.get_intents()
                            self.client = discord.Client(intents=intents)

                            # Reattach the adapter to the new client
                            if hasattr(self.discord_adapter, 'attach_to_client'):
                                # Update the adapter's on_message callback to ensure it routes to observer
                                self.discord_adapter._channel_manager.set_message_callback(self._handle_discord_message_event)
                                self.discord_adapter.attach_to_client(self.client)
                                self.discord_adapter.bot = self.client
                                logger.info("Discord adapter re-attached to new client with observer callback")

                            # Wait with exponential backoff before reconnecting
                            wait_time = min(5.0 * (2 ** (self._reconnect_attempts - 1)), 60.0)  # Max 60 seconds
                            logger.info(f"Waiting {wait_time:.1f} seconds before reconnecting...")
                            await asyncio.sleep(wait_time)

                            # Create a new task to start the client
                            self._discord_client_task = asyncio.create_task(
                                self.client.start(self.token),
                                name="DiscordClientTask"
                            )
                            logger.info("Discord client restart task created")

                            # Wait for Discord to be ready after reconnection
                            ready = await self.discord_adapter.wait_until_ready(timeout=30.0)
                            if ready:
                                logger.info(f"Discord client reconnected successfully! Logged in as: {self.client.user}")
                                self._reconnect_attempts = 0  # Reset on successful reconnection
                            else:
                                logger.warning("Discord client failed to become ready after reconnection attempt")

                            continue  # Continue the while loop with the new task
                        except Exception as e:
                            logger.error(f"Failed to restart Discord client: {e}")
                            # Only shutdown if we can't restart
                            break
                    else:
                        # Non-transient error, don't retry
                        logger.error(f"Discord client encountered non-transient error: {exc}")
                        break

        except discord.LoginFailure as e:
            logger.error(f"DiscordPlatform: Discord login failed: {e}. Check token and intents.", exc_info=True)
            if hasattr(self.runtime, 'request_shutdown'):
                self.runtime.request_shutdown("Discord login failure")
            if not agent_run_task.done(): agent_run_task.cancel()
        except Exception as e:
            logger.error(f"DiscordPlatform: Unexpected error in run_lifecycle: {e}", exc_info=True)
            error_type = type(e).__name__

            # Even top-level errors might be transient - try one more time
            if self._reconnect_attempts < self._max_reconnect_attempts:
                self._reconnect_attempts += 1
                logger.warning(f"Attempting to recover from lifecycle error ({error_type}). Restarting lifecycle...")

                # Wait before retrying
                await asyncio.sleep(10.0)

                # Recursively call run_lifecycle to retry
                try:
                    await self.run_lifecycle(agent_run_task)
                    return  # If successful, exit
                except Exception as retry_exc:
                    logger.error(f"Failed to recover from lifecycle error: {retry_exc}")

            # If we get here, we've failed to recover
            if not agent_run_task.done():
                agent_run_task.cancel()
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
