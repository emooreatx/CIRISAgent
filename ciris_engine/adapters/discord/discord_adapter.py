import discord
from discord.errors import Forbidden, NotFound, InvalidData, HTTPException, ConnectionClosed
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Callable, Awaitable, Optional, List, Dict, Any
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage, FetchedMessage
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService
from ciris_engine.adapters.base import Service
from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

logger = logging.getLogger(__name__)



class DiscordAdapter(Service, CommunicationService, WiseAuthorityService, ToolService):
    """
    Discord adapter implementing CommunicationService, WiseAuthorityService, and ToolService protocols.
    Provides communication, guidance/deferral, and tool functionality without an internal event queue.
    """
    def __init__(self, token: str,
                 guidance_channel_id: str = None, deferral_channel_id: str = None,
                 tool_registry: Optional[Any] = None, bot: discord.Client = None,
                 on_message: Optional[Callable[[DiscordMessage], Awaitable[None]]] = None) -> None:
        # Configure retry settings for Discord API operations
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": 3,
                    "base_delay": 2.0,  # Discord rate limits need longer delays
                    "max_delay": 30.0,
                },
                "discord_api": {
                    "retryable_exceptions": (HTTPException, ConnectionClosed, asyncio.TimeoutError),
                    "non_retryable_exceptions": (Forbidden, NotFound, InvalidData),
                }
            }
        }
        super().__init__(config=retry_config)
        
        self.token = token
        self.client = bot  # Discord client instance
        self.guidance_channel_id = guidance_channel_id
        self.deferral_channel_id = deferral_channel_id
        self.tool_registry = tool_registry
        self.on_message_callback = on_message
        self._tool_results = {}  # correlation_id -> ToolResult

    # --- CommunicationService ---
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Implementation of CommunicationService.send_message"""
        correlation_id = str(uuid.uuid4())
        try:
            await self.send_output(channel_id, content)
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="send_message",
                    request_data={"channel_id": channel_id, "content": content},
                    response_data={"sent": True},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat(),
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message via Discord: {e}")
            return False

    async def fetch_messages(self, channel_id: str, limit: int) -> List[FetchedMessage]:
        """Implementation of CommunicationService.fetch_messages"""
        if not self.client:
            logger.error("Discord client is not initialized.")
            return []
        
        try:
            return await self.retry_with_backoff(
                self._fetch_messages_impl,
                channel_id, limit,
                operation_name="fetch_messages",
                config_key="discord_api"
            )
        except Exception as e:
            logger.exception(f"Failed to fetch messages from Discord channel {channel_id}: {e}")
            return []

    async def _fetch_messages_impl(self, channel_id: str, limit: int, **kwargs) -> List[FetchedMessage]:
        """Internal implementation of fetch_messages for retry wrapping"""
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(channel_id))
        
        if channel:
            messages: List[FetchedMessage] = []
            async for message in channel.history(limit=limit):
                messages.append(
                    FetchedMessage(
                        id=str(message.id),
                        content=message.content,
                        author_id=str(message.author.id),
                        author_name=message.author.display_name,
                        timestamp=message.created_at.isoformat(),
                        is_bot=message.author.bot,
                    )
                )
            return messages
        else:
            logger.error(f"Could not find Discord channel with ID {channel_id}")
            return []

    # --- WiseAuthorityService ---
    async def fetch_guidance(self, context: dict) -> dict:
        """Send a guidance request to the configured guidance channel and wait for a response."""
        if not self.client or not self.guidance_channel_id:
            logger.error("DiscordAdapter: Guidance channel or client not configured.")
            raise RuntimeError("Guidance channel or client not configured.")

        try:
            correlation_id = str(uuid.uuid4())
            guidance = await self.retry_with_backoff(
                self._fetch_guidance_impl,
                context,
                operation_name="fetch_guidance",
                config_key="discord_api"
            )
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="fetch_guidance",
                    request_data=context,
                    response_data=guidance,
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat(),
                )
            )
            return guidance
        except Exception as e:
            logger.exception(f"Failed to fetch guidance from Discord: {e}")
            raise

    async def _fetch_guidance_impl(self, context: dict, **kwargs) -> dict:
        """Internal implementation of fetch_guidance for retry wrapping"""
        channel = self.client.get_channel(int(self.guidance_channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.guidance_channel_id))
        if channel is None:
            logger.error(f"DiscordAdapter: Could not find guidance channel {self.guidance_channel_id}")
            raise RuntimeError("Guidance channel not found.")
        
        # Post the guidance request
        request_content = f"[CIRIS Guidance Request]\nContext: ```json\n{context}\n```"
        await channel.send(request_content)
        
        # For demo: fetch the latest bot response as guidance (in real use, implement a more robust protocol)
        async for message in channel.history(limit=10):
            if message.author.bot and message.content.startswith("[CIRIS Guidance Reply]"):
                # Parse guidance from message
                try:
                    # Assume guidance is in a code block after the prefix
                    guidance = message.content.split('```', 1)[-1].rsplit('```', 1)[0]
                    return {"guidance": guidance}
                except Exception:
                    continue
        logger.warning("DiscordAdapter: No guidance reply found in channel history.")
        return {"guidance": None}

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        """Send a deferral report to the configured deferral channel."""
        if not self.client or not self.deferral_channel_id:
            logger.error("DiscordAdapter: Deferral channel or client not configured.")
            return False
        
        try:
            correlation_id = str(uuid.uuid4())
            await self.retry_with_backoff(
                self._send_deferral_impl,
                thought_id, reason,
                operation_name="send_deferral",
                config_key="discord_api"
            )
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="discord",
                    handler_name="DiscordAdapter",
                    action_type="send_deferral",
                    request_data={"thought_id": thought_id, "reason": reason},
                    response_data={"status": "sent"},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat(),
                )
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to send deferral to Discord: {e}")
            return False

    async def _send_deferral_impl(self, thought_id: str, reason: str, **kwargs) -> None:
        """Internal implementation of send_deferral for retry wrapping"""
        channel = self.client.get_channel(int(self.deferral_channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.deferral_channel_id))
        if channel is None:
            logger.error(f"DiscordAdapter: Could not find deferral channel {self.deferral_channel_id}")
            raise RuntimeError("Deferral channel not found.")
        
        report = f"[CIRIS Deferral Report]\nThought ID: `{thought_id}`\nReason: {reason}"
        await channel.send(report)

    # --- ToolService ---
    async def execute_tool(self, tool_name: str, tool_args: dict) -> dict:
        """Execute a registered Discord tool via the tool registry and store the result."""
        if not self.tool_registry:
            logger.error("DiscordAdapter: Tool registry not configured.")
            raise RuntimeError("Tool registry not configured.")
        
        return await self.retry_with_backoff(
            self._execute_tool_impl,
            tool_name, tool_args,
            operation_name="execute_tool",
            config_key="discord_api"
        )

    async def _execute_tool_impl(self, tool_name: str, tool_args: dict, **kwargs) -> dict:
        """Internal implementation of execute_tool for retry wrapping"""
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            logger.error(f"DiscordAdapter: Tool handler for '{tool_name}' not found.")
            raise RuntimeError(f"Tool handler for '{tool_name}' not found.")
        
        correlation_id = tool_args.get("correlation_id", str(uuid.uuid4()))
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="discord",
                handler_name="DiscordAdapter",
                action_type=tool_name,
                request_data=tool_args,
                status=ServiceCorrelationStatus.PENDING,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
        )
        result = await handler({**tool_args, "bot": self.client})

        if correlation_id:
            self._tool_results[correlation_id] = result if isinstance(result, dict) else result.__dict__
            persistence.update_correlation(
                correlation_id,
                response_data=result if isinstance(result, dict) else result.__dict__,
                status=ServiceCorrelationStatus.COMPLETED,
            )
        return result if isinstance(result, dict) else result.__dict__

    async def get_tool_result(self, correlation_id: str, timeout: int = 10) -> dict:
        """Fetch a tool result by correlation ID from the internal cache."""
        # Wait up to timeout seconds for the result to appear
        for _ in range(timeout * 10):
            if correlation_id in self._tool_results:
                return self._tool_results.pop(correlation_id)
            await asyncio.sleep(0.1)
        logger.warning(f"DiscordAdapter: Tool result for correlation_id {correlation_id} not found after {timeout}s.")
        return {"correlation_id": correlation_id, "status": "not_found"}

    async def get_available_tools(self) -> list[str]:
        """Return names of registered Discord tools."""
        if not self.tool_registry:
            return []
        return list(self.tool_registry.tools.keys())  # type: ignore[union-attr]

    async def validate_parameters(self, tool_name: str, parameters: dict) -> bool:
        """Basic parameter validation using tool registry schemas."""
        if not self.tool_registry:
            return False
        schema = self.tool_registry.get_schema(tool_name)
        if not schema:
            return False
        # Simple validation: ensure required keys exist
        return all(k in parameters for k in schema.keys())  # type: ignore[union-attr]

    # --- Capabilities ---
    def get_capabilities(self) -> list[str]:
        return [
            "send_message", "fetch_messages",
            "fetch_guidance", "send_deferral",
            "execute_tool", "get_tool_result"
        ]

    async def send_output(self, channel_id: str, content: str) -> None:
        """Send output to a Discord channel with retry logic"""
        if not self.client:
            logger.error("Discord client is not initialized.")
            return
        
        await self.retry_with_backoff(
            self._send_output_impl,
            channel_id, content
        )

    async def _send_output_impl(self, channel_id: str, content: str, **kwargs) -> None:
        """Internal implementation of send_output for retry wrapping"""
        # Wait for the client to be ready before sending
        if hasattr(self.client, 'wait_until_ready'):
            await self.client.wait_until_ready()
        
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(channel_id))
        if channel:
            await channel.send(content)
        else:
            logger.error(f"Could not find Discord channel with ID {channel_id}")
            raise RuntimeError(f"Discord channel {channel_id} not found")

    async def on_message(self, message) -> None:
        # Only process messages from users (not bots)
        if message.author.bot:
            return
        # Build DiscordMessage object
        incoming = DiscordMessage(
            message_id=str(message.id),
            content=message.content,
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            channel_id=str(message.channel.id),
            is_bot=message.author.bot,
            is_dm=isinstance(message.channel, discord.DMChannel),
            _raw_message=message
        )
        if self.on_message_callback:
            await self.on_message_callback(incoming)

    def attach_to_client(self, client) -> None:
        # Attach the on_message event to the Discord client
        @client.event
        async def on_message(message) -> None:
            await self.on_message(message)

    async def start(self) -> None:
        """
        Start the Discord adapter.
        Note: This doesn't start the Discord client connection - that's handled by the runtime.
        """
        try:
            await super().start()  # Initialize base Service
            
            if self.client:
                logger.info("Discord adapter started with existing client (not yet connected)")
            else:
                logger.warning("Discord adapter started without client - attach_to_client() must be called separately")
                
            logger.info("Discord adapter started successfully")
        except Exception as e:
            logger.exception(f"Failed to start Discord adapter: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the Discord adapter and clean up resources.
        """
        try:
            logger.info("Stopping Discord adapter...")
            
            # Clear tool results cache
            self._tool_results.clear()
            
            # Call base Service stop
            await super().stop()
            
            logger.info("Discord adapter stopped successfully")
        except Exception as e:
            logger.exception(f"Error stopping Discord adapter: {e}")
            raise
