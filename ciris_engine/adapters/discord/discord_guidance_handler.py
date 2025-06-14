"""Discord guidance handling component for wise authority operations."""
import discord
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DiscordGuidanceHandler:
    """Handles Discord wise authority guidance and deferral operations."""
    
    def __init__(self, client: Optional[discord.Client] = None) -> None:
        """Initialize the guidance handler.
        
        Args:
            client: Discord client instance
        """
        self.client = client
    
    def set_client(self, client: discord.Client) -> None:
        """Set the Discord client after initialization.
        
        Args:
            client: Discord client instance
        """
        self.client = client
    
    async def fetch_guidance_from_channel(self, deferral_channel_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Send a guidance request to a Discord channel and check for responses.
        
        Args:
            deferral_channel_id: The Discord channel ID for guidance requests
            context: Context information for the guidance request
            
        Returns:
            Dictionary containing guidance information or None if no guidance found
            
        Raises:
            RuntimeError: If client is not initialized or channel not found
        """
        if not self.client:
            raise RuntimeError("Discord client is not initialized")
        
        channel = await self._resolve_channel(deferral_channel_id)
        if not channel:
            raise RuntimeError(f"Deferral channel {deferral_channel_id} not found")
        
        request_content = f"[CIRIS Guidance Request]\nContext: ```json\n{context}\n```"
        
        if not hasattr(channel, 'send'):
            logger.error(f"Channel {deferral_channel_id} does not support sending messages")
            return {"guidance": None}
        
        chunks = self._split_message(request_content)
        request_message = None
        
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1 and i > 0:
                chunk = f"*(Continued from previous message)*\n\n{chunk}"
            sent_msg = await channel.send(chunk)
            if i == 0:
                request_message = sent_msg  # Track first message for replies
        
        if hasattr(channel, 'history'):
            async for message in channel.history(limit=10):
                if message.author.bot or (request_message and message.id == request_message.id):
                    continue
                
                # TODO: Check if author is a registered WA
                guidance_content = message.content.strip()
                
                is_reply = bool(hasattr(message, 'reference') and 
                               message.reference and 
                               request_message and
                               hasattr(message.reference, 'message_id') and
                               message.reference.message_id == request_message.id)
                
                return {
                    "guidance": guidance_content,
                    "is_reply": is_reply,
                    "is_unsolicited": not is_reply,
                    "author_id": str(message.author.id),
                    "author_name": message.author.display_name
                }
        
        logger.warning("No guidance found in deferral channel")
        return {"guidance": None}
    
    async def send_deferral_to_channel(
        self, 
        deferral_channel_id: str, 
        thought_id: str, 
        reason: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a deferral report to a Discord channel.
        
        Args:
            deferral_channel_id: The Discord channel ID for deferral reports
            thought_id: The ID of the thought being deferred
            reason: Reason for deferral
            context: Additional context about the thought and task
            
        Raises:
            RuntimeError: If client is not initialized or channel not found
        """
        if not self.client:
            raise RuntimeError("Discord client is not initialized")
        
        channel = await self._resolve_channel(deferral_channel_id)
        if not channel:
            raise RuntimeError(f"Deferral channel {deferral_channel_id} not found")
        
        report = self._build_deferral_report(thought_id, reason, context)
        
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
    
    def _build_deferral_report(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build a formatted deferral report.
        
        Args:
            thought_id: The ID of the thought being deferred
            reason: Reason for deferral
            context: Additional context information
            
        Returns:
            Formatted deferral report as a string
        """
        report_lines = [
            "**[CIRIS Deferral Report]**",
            f"**Thought ID:** `{thought_id}`",
            f"**Reason:** {reason}",
            f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}Z"
        ]
        
        if context:
            if "task_id" in context:
                report_lines.append(f"**Task ID:** `{context['task_id']}`")
            
            if "task_description" in context:
                task_desc = self._truncate_text(context["task_description"], 200)
                report_lines.append(f"**Task:** {task_desc}")
            
            if "thought_content" in context:
                thought_content = self._truncate_text(context["thought_content"], 300)
                report_lines.append(f"**Thought:** {thought_content}")
            
            if "conversation_context" in context:
                conv_context = self._truncate_text(context["conversation_context"], 400)
                report_lines.append(f"**Context:** {conv_context}")
            
            if "priority" in context:
                report_lines.append(f"**Priority:** {context['priority']}")
            
            if "attempted_action" in context:
                report_lines.append(f"**Attempted Action:** {context['attempted_action']}")
            
            if "max_rounds_reached" in context and context["max_rounds_reached"]:
                report_lines.append("**Note:** Maximum processing rounds reached")
        
        return "\n".join(report_lines)
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to a maximum length with ellipsis.
        
        Args:
            text: Text to truncate
            max_length: Maximum length allowed
            
        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def _split_message(self, content: str, max_length: int = 1950) -> List[str]:
        """Split a message into chunks that fit Discord's character limit.
        
        Args:
            content: The message content to split
            max_length: Maximum length per message
            
        Returns:
            List of message chunks
        """
        if len(content) <= max_length:
            return [content]
        
        chunks = []
        lines = content.split('\n')
        current_chunk = ""
        
        for line in lines:
            if len(line) > max_length:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = ""
                
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
            else:
                if len(current_chunk) + len(line) + 1 > max_length:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.rstrip())
        
        return chunks
    
    async def _resolve_channel(self, channel_id: str) -> Optional[Any]:
        """Resolve a Discord channel by ID.
        
        Args:
            channel_id: The Discord channel ID
            
        Returns:
            Discord channel object or None if not found
        """
        if not self.client:
            return None
        
        try:
            channel_id_int = int(channel_id)
            channel = self.client.get_channel(channel_id_int)
            if channel is None:
                channel = await self.client.fetch_channel(channel_id_int)
            return channel
        except (ValueError, discord.NotFound, discord.Forbidden):
            logger.error(f"Could not resolve Discord channel {channel_id}")
            return None