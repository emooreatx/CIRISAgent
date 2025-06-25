import discord
from discord.errors import HTTPException, ConnectionClosed
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Awaitable, Callable, List, Optional, TYPE_CHECKING, Any

from ciris_engine.schemas.runtime.messages import FetchedMessage, IncomingMessage
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine.schemas.services.context import GuidanceContext, DeferralContext
from ciris_engine.schemas.runtime.tools import ToolInfo, ToolParameterSchema, ToolExecutionResult
from ciris_engine.logic import persistence

from .discord_message_handler import DiscordMessageHandler
from .discord_guidance_handler import DiscordGuidanceHandler
from .discord_tool_handler import DiscordToolHandler
from .discord_channel_manager import DiscordChannelManager

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class DiscordAdapter(CommunicationService, WiseAuthorityService, ToolService):
    """
    Discord adapter implementing CommunicationService, WiseAuthorityService, and ToolService protocols.
    Coordinates specialized handlers for different aspects of Discord functionality.
    """
    def __init__(self, token: str,
                 tool_registry: Optional[Any] = None, bot: Optional[discord.Client] = None,
                 on_message: Optional[Callable[[IncomingMessage], Awaitable[None]]] = None,
                 time_service: Optional["TimeServiceProtocol"] = None,
                 bus_manager: Optional[Any] = None) -> None:
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": 3,
                    "base_delay": 2.0,
                    "max_delay": 30.0,
                },
                "discord_api": {
                    "retryable_exceptions": (HTTPException, ConnectionClosed, asyncio.TimeoutError),
                }
            }
        }
        super().__init__(config=retry_config)
        
        self.token = token
        self._time_service = time_service
        self.bus_manager = bus_manager
        
        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()
        
        self._channel_manager = DiscordChannelManager(token, bot, on_message)
        self._message_handler = DiscordMessageHandler(bot)
        self._guidance_handler = DiscordGuidanceHandler(bot, self._time_service)
        self._tool_handler = DiscordToolHandler(tool_registry, bot, self._time_service)

    async def _emit_telemetry(self, metric_name: str, tags: Optional[dict] = None) -> None:
        """Emit telemetry as TSDBGraphNode through memory bus."""
        if not self.bus_manager or not self.bus_manager.memory:
            return  # No bus manager, can't emit telemetry
        
        try:
            # Extract value from tags if it exists, otherwise default to 1.0
            value = 1.0
            if tags and "value" in tags:
                value = float(tags.pop("value"))
            elif tags and "execution_time" in tags:
                value = float(tags["execution_time"])
            elif tags and "success" in tags:
                # For boolean success, use 1.0 for true, 0.0 for false
                value = 1.0 if tags["success"] else 0.0
            
            # Convert all tag values to strings as required by memorize_metric
            string_tags = {k: str(v) for k, v in (tags or {}).items()}
            
            # Use memorize_metric instead of creating GraphNode directly
            await self.bus_manager.memory.memorize_metric(
                metric_name=metric_name,
                value=value,
                tags=string_tags,
                scope="local",
                handler_name="adapter.discord"
            )
        except Exception as e:
            logger.debug(f"Failed to emit telemetry {metric_name}: {e}")

    async def send_message(self, channel_id: str, content: str) -> bool:
        """Implementation of CommunicationService.send_message"""
        correlation_id = str(uuid.uuid4())
        try:
            result = await self.retry_with_backoff(
                self._message_handler.send_message_to_channel,
                channel_id, content,
                operation_name="send_message",
                config_key="discord_api"
            )
            # result contains the return value from send_message_to_channel
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="send_message",
                    request_data={"channel_id": channel_id, "content": content},
                    response_data={"sent": True},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=self._time_service.now().isoformat(),
                    updated_at=self._time_service.now().isoformat(),
                )
            )
            
            # Emit telemetry for message sent
            await self._emit_telemetry("message_sent", {
                "adapter_type": "discord",
                "channel_id": channel_id
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to send message via Discord: {e}")
            return False

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        """Implementation of CommunicationService.fetch_messages"""
        # Early return if no client is available - no point in retrying
        if not self._channel_manager.client:
            logger.debug(f"Discord client not initialized, cannot fetch messages from channel {channel_id}")
            return []
            
        try:
            return await self.retry_with_backoff(
                self._message_handler.fetch_messages_from_channel,  # type: ignore[arg-type]
                channel_id, limit,
                operation_name="fetch_messages",
                config_key="discord_api"
            )
        except Exception as e:
            logger.exception(f"Failed to fetch messages from Discord channel {channel_id}: {e}")
            return []

    # --- WiseAuthorityService ---
    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """Send a guidance request to the configured guidance channel and wait for a response."""
        # TODO: Refactor to use dependency injection instead of get_config
        
        config = get_config()
        deferral_channel_id = getattr(config, 'discord_deferral_channel_id', None)
        if not deferral_channel_id:
            logger.error("DiscordAdapter: Guidance channel not configured.")
            raise RuntimeError("Guidance channel not configured.")

        try:
            correlation_id = str(uuid.uuid4())
            guidance_result = await self.retry_with_backoff(
                self._guidance_handler.fetch_guidance_from_channel,
                deferral_channel_id, context.model_dump(),
                operation_name="fetch_guidance",
                config_key="discord_api"
            )
            # Type assertion: retry_with_backoff should return dict from fetch_guidance_from_channel
            guidance: dict = guidance_result  # type: ignore
            
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="fetch_guidance",
                    request_data=context.model_dump(),
                    response_data=guidance,
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=self._time_service.now().isoformat(),
                    updated_at=self._time_service.now().isoformat(),
                )
            )
            return guidance.get("guidance")
        except Exception as e:
            logger.exception(f"Failed to fetch guidance from Discord: {e}")
            raise

    async def send_deferral(self, context: DeferralContext) -> bool:
        """Send a deferral report to the configured deferral channel."""
        # TODO: Refactor to use dependency injection instead of get_config
        
        config = get_config()
        deferral_channel_id = getattr(config, 'discord_deferral_channel_id', None)
        if not deferral_channel_id:
            logger.error("DiscordAdapter: Deferral channel not configured.")
            return False
        
        try:
            correlation_id = str(uuid.uuid4())
            result = await self.retry_with_backoff(
                self._guidance_handler.send_deferral_to_channel,
                deferral_channel_id, context.thought_id, context.reason, context.model_dump(),
                operation_name="send_deferral",
                config_key="discord_api"
            )
            # result contains the return value from send_deferral_to_channel
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="send_deferral",
                    request_data=context.model_dump(),
                    response_data={"status": "sent"},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=self._time_service.now().isoformat(),
                    updated_at=self._time_service.now().isoformat(),
                )
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to send deferral to Discord: {e}")
            return False

    # --- ToolService ---
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """Execute a registered Discord tool via the tool registry and store the result."""
        # The handler returns ToolExecutionResult
        # Note: execute_tool is already async, so we call it directly
        result = await self._tool_handler.execute_tool(tool_name, parameters)
        
        # Emit telemetry for tool execution
        await self._emit_telemetry("tool_executed", {
            "adapter_type": "discord",
            "tool_name": tool_name,
            "success": result.success,
            "execution_time": result.execution_time
        })
        
        return result

    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool."""
        return await self._tool_handler.get_tool_info(tool_name)
    
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get detailed information about all available tools."""
        return await self._tool_handler.get_all_tool_info()
    
    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
        """Fetch a tool result by correlation ID from the internal cache."""
        return await self._tool_handler.get_tool_result(correlation_id, int(timeout))

    async def get_available_tools(self) -> List[str]:
        """Return names of registered Discord tools."""
        return await self._tool_handler.get_available_tools()

    async def validate_parameters(self, tool_name: str, parameters: dict) -> bool:
        """Basic parameter validation using tool registry schemas."""
        return await self._tool_handler.validate_tool_parameters(tool_name, parameters)

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        communication_caps = await super().get_capabilities()
        wise_authority_caps = ["fetch_guidance", "send_deferral"]
        tool_caps = ["execute_tool", "get_available_tools", "get_tool_result", 
                     "validate_parameters", "get_tool_info", "get_all_tool_info"]
        return communication_caps + wise_authority_caps + tool_caps

    async def _send_output(self, channel_id: str, content: str) -> None:
        """Send output to a Discord channel with retry logic"""
        result = await self.retry_with_backoff(
            self._message_handler.send_message_to_channel,
            channel_id, content,
            operation_name="send_output",
            config_key="discord_api"
        )
        # result contains the return value from send_message_to_channel

    async def _on_message(self, message: discord.Message) -> None:
        """Handle incoming Discord messages."""
        await self._channel_manager.on_message(message)
        
        # Emit telemetry for message received
        await self._emit_telemetry("message_received", {
            "adapter_type": "discord",
            "channel_id": str(message.channel.id),
            "author_id": str(message.author.id)
        })

    def attach_to_client(self, client: discord.Client) -> None:
        """Attach message handlers to a Discord client."""
        self._channel_manager.set_client(client)
        self._message_handler.set_client(client)
        self._guidance_handler.set_client(client)
        self._tool_handler.set_client(client)
        
        self._channel_manager.attach_to_client(client)

    async def start(self) -> None:
        """
        Start the Discord adapter.
        Note: This doesn't start the Discord client connection - that's handled by the runtime.
        """
        try:
            # Emit telemetry for adapter start
            await self._emit_telemetry("adapter_starting", {
                "adapter_type": "discord"
            })
            
            await super().start()
            
            client = self._channel_manager.client
            if client:
                logger.info("Discord adapter started with existing client (not yet connected)")
            else:
                logger.warning("Discord adapter started without client - attach_to_client() must be called separately")
                
            logger.info("Discord adapter started successfully")
            
            # Emit telemetry for successful start
            await self._emit_telemetry("adapter_started", {
                "adapter_type": "discord",
                "has_client": client is not None
            })
        except Exception as e:
            logger.exception(f"Failed to start Discord adapter: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the Discord adapter and clean up resources.
        """
        try:
            logger.info("Stopping Discord adapter...")
            
            # Emit telemetry for adapter stopping
            await self._emit_telemetry("adapter_stopping", {
                "adapter_type": "discord"
            })
            
            self._tool_handler.clear_tool_results()
            
            await super().stop()
            
            logger.info("Discord adapter stopped successfully")
            
            # Emit telemetry for successful stop
            await self._emit_telemetry("adapter_stopped", {
                "adapter_type": "discord"
            })
        except Exception as e:
            logger.exception(f"Error stopping Discord adapter: {e}")

    async def is_healthy(self) -> bool:
        """Check if the Discord adapter is healthy"""
        try:
            return await self._channel_manager.is_client_ready()
        except Exception:
            return False
    
    @property
    def _client(self) -> Optional[discord.Client]:
        """Get the Discord client instance."""
        return self._channel_manager.client
