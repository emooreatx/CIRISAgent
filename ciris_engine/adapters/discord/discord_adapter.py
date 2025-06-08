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
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": 3,
                    "base_delay": 2.0,
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
        self.client = bot
        # Guidance and deferral use the same channel
        self.deferral_channel_id = deferral_channel_id
        self.guidance_channel_id = deferral_channel_id  # Deprecated, same as deferral
        self.tool_registry = tool_registry
        self.on_message_callback = on_message
        self._tool_results = {}

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
        
        if channel and hasattr(channel, 'history'):
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
        if not self.deferral_channel_id:
            logger.error("DiscordAdapter: No deferral channel configured for guidance")
            raise RuntimeError("Deferral channel not configured.")
            
        channel = self.client.get_channel(int(self.deferral_channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.deferral_channel_id))
        if channel is None:
            logger.error(f"DiscordAdapter: Could not find deferral channel {self.deferral_channel_id}")
            raise RuntimeError("Deferral channel not found.")
        
        # Post the guidance request to deferral channel
        request_content = f"[CIRIS Guidance Request]\nContext: ```json\n{context}\n```"
        if hasattr(channel, 'send'):
            # For guidance requests, we need to track the first message
            chunks = self._split_message(request_content)
            request_message = None
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1 and i > 0:
                    chunk = f"*(Continued from previous message)*\n\n{chunk}"
                sent_msg = await channel.send(chunk)
                if i == 0:
                    request_message = sent_msg  # Track first message for replies
        else:
            logger.error(f"Channel {self.deferral_channel_id} does not support sending messages")
            return {"guidance": None}
        
        # Check recent messages from registered WAs (Wise Authorities)
        if hasattr(channel, 'history'):
            async for message in channel.history(limit=10):
                # Skip bot messages and our own request
                if message.author.bot or message.id == request_message.id:
                    continue
                    
                # TODO: Check if author is a registered WA
                # For now, accept any human message as potential guidance
                guidance_content = message.content.strip()
                
                # Check if it's a reply to our guidance request
                is_reply = (hasattr(message, 'reference') and 
                           message.reference and 
                           message.reference.message_id == request_message.id)
                
                return {
                    "guidance": guidance_content,
                    "is_reply": is_reply,
                    "is_unsolicited": not is_reply,
                    "author_id": str(message.author.id),
                    "author_name": message.author.display_name
                }
        
        logger.warning("DiscordAdapter: No guidance found in deferral channel.")
        return {"guidance": None}

    async def send_deferral(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Send a deferral report to the configured deferral channel."""
        if not self.client or not self.deferral_channel_id:
            logger.error("DiscordAdapter: Deferral channel or client not configured.")
            return False
        
        try:
            correlation_id = str(uuid.uuid4())
            await self.retry_with_backoff(
                self._send_deferral_impl,
                thought_id, reason, context,
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

    async def _send_deferral_impl(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """Internal implementation of send_deferral for retry wrapping"""
        channel = self.client.get_channel(int(self.deferral_channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.deferral_channel_id))
        if channel is None:
            logger.error(f"DiscordAdapter: Could not find deferral channel {self.deferral_channel_id}")
            raise RuntimeError("Deferral channel not found.")
        
        # Build richer deferral report
        report_lines = [
            "**[CIRIS Deferral Report]**",
            f"**Thought ID:** `{thought_id}`",
            f"**Reason:** {reason}",
            f"**Timestamp:** {datetime.utcnow().isoformat()}Z"
        ]
        
        if context:
            if "task_id" in context:
                report_lines.append(f"**Task ID:** `{context['task_id']}`")
            
            if "task_description" in context:
                task_desc = context["task_description"]
                if len(task_desc) > 200:
                    task_desc = task_desc[:197] + "..."
                report_lines.append(f"**Task:** {task_desc}")
            
            if "thought_content" in context:
                thought_content = context["thought_content"]
                if len(thought_content) > 300:
                    thought_content = thought_content[:297] + "..."
                report_lines.append(f"**Thought:** {thought_content}")
            
            if "conversation_context" in context:
                conv_context = context["conversation_context"]
                if len(conv_context) > 400:
                    conv_context = conv_context[:397] + "..."
                report_lines.append(f"**Context:** {conv_context}")
            
            if "priority" in context:
                report_lines.append(f"**Priority:** {context['priority']}")
            
            if "attempted_action" in context:
                report_lines.append(f"**Attempted Action:** {context['attempted_action']}")
            
            if "max_rounds_reached" in context and context["max_rounds_reached"]:
                report_lines.append("**Note:** Maximum processing rounds reached")
        
        report = "\n".join(report_lines)
        
        # Use the split message functionality
        chunks = self._split_message(report)
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                if i == 0:
                    chunk = f"{chunk}\n\n*(Report continues...)*"
                elif i < len(chunks) - 1:
                    chunk = f"*(Continued from previous report)*\n\n{chunk}\n\n*(Report continues...)*"
                else:
                    chunk = f"*(Continued from previous report)*\n\n{chunk}"
            await channel.send(chunk)
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)

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
        return all(k in parameters for k in schema.keys())

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

    def _split_message(self, content: str, max_length: int = 1950) -> List[str]:
        """Split a message into chunks that fit Discord's character limit.
        
        Args:
            content: The message content to split
            max_length: Maximum length per message (default 1950 to leave room for formatting)
            
        Returns:
            List of message chunks
        """
        if len(content) <= max_length:
            return [content]
        
        chunks = []
        lines = content.split('\n')
        current_chunk = ""
        
        for line in lines:
            # If a single line is longer than max_length, split it
            if len(line) > max_length:
                # First, add any accumulated content
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = ""
                
                # Split the long line
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
            else:
                # Check if adding this line would exceed the limit
                if len(current_chunk) + len(line) + 1 > max_length:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
        
        # Add any remaining content
        if current_chunk:
            chunks.append(current_chunk.rstrip())
        
        return chunks

    async def _send_output_impl(self, channel_id: str, content: str, **kwargs) -> None:
        """Internal implementation of send_output for retry wrapping"""
        if hasattr(self.client, 'wait_until_ready'):
            await self.client.wait_until_ready()
        
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(channel_id))
        if channel:
            # Split long messages
            chunks = self._split_message(content)
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                # Add continuation indicator for multi-part messages
                if len(chunks) > 1:
                    if i == 0:
                        chunk = f"{chunk}\n\n*(Message continues...)*"
                    elif i < len(chunks) - 1:
                        chunk = f"*(Continued from previous message)*\n\n{chunk}\n\n*(Message continues...)*"
                    else:
                        chunk = f"*(Continued from previous message)*\n\n{chunk}"
                
                await channel.send(chunk)
                
                # Small delay between messages to avoid rate limiting
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
        else:
            logger.error(f"Could not find Discord channel with ID {channel_id}")
            raise RuntimeError(f"Discord channel {channel_id} not found")

    async def on_message(self, message) -> None:
        if message.author.bot:
            return
        incoming = DiscordMessage(
            message_id=str(message.id),
            content=message.content,
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            channel_id=str(message.channel.id),
            is_bot=message.author.bot,
            is_dm=isinstance(message.channel, discord.DMChannel),
            raw_message=message
        )
        if self.on_message_callback:
            await self.on_message_callback(incoming)

    def attach_to_client(self, client) -> None:
        @client.event
        async def on_message(message) -> None:
            await self.on_message(message)

    async def start(self) -> None:
        """
        Start the Discord adapter.
        Note: This doesn't start the Discord client connection - that's handled by the runtime.
        """
        try:
            await super().start()
            
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
            
            self._tool_results.clear()
            
            await super().stop()
            
            logger.info("Discord adapter stopped successfully")
        except Exception as e:
            logger.exception(f"Error stopping Discord adapter: {e}")
            raise
