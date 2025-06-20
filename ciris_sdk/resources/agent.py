"""Agent resource - primary interface for communicating with the CIRIS agent."""
from typing import Any, Dict, List, Optional
from ..transport import Transport


class AgentResource:
    """Resource for agent interaction endpoints."""
    
    def __init__(self, transport: Transport) -> None:
        self._transport = transport
    
    async def send_message(
        self,
        content: str,
        channel_id: str = "api_default",
        author_id: str = "api_user",
        author_name: str = "API User",
        reference_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to the agent.
        
        Args:
            content: The message content
            channel_id: Channel to send to (default: "api_default")
            author_id: Author ID (default: "api_user")
            author_name: Author display name (default: "API User")
            reference_message_id: Optional message being replied to
            
        Returns:
            Response with message_id and status
        """
        data = {
            "content": content,
            "channel_id": channel_id,
            "author_id": author_id,
            "author_name": author_name
        }
        if reference_message_id:
            data["reference_message_id"] = reference_message_id
            
        return await self._transport.request(
            "POST",
            "/v1/agent/messages",
            json=data
        )
    
    async def get_messages(
        self,
        channel_id: str,
        limit: int = 100,
        after_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get messages from a channel.
        
        Args:
            channel_id: Channel to get messages from
            limit: Maximum number of messages (default: 100)
            after_message_id: Get messages after this ID
            
        Returns:
            Messages and metadata
        """
        params = {"limit": limit}
        if after_message_id:
            params["after_message_id"] = after_message_id
            
        return await self._transport.request(
            "GET",
            f"/v1/agent/messages/{channel_id}",
            params=params
        )
    
    async def wait_for_response(
        self,
        channel_id: str,
        after_message_id: str,
        timeout: float = 30.0,
        poll_interval: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """Wait for agent response after sending a message.
        
        Args:
            channel_id: Channel to monitor
            after_message_id: Message ID to wait for response after
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds
            
        Returns:
            First new message from agent or None if timeout
        """
        import asyncio
        import time
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                response = await self.get_messages(
                    channel_id,
                    limit=10,
                    after_message_id=after_message_id
                )
                
                messages = response.get("messages", [])
                # Look for messages from the agent
                for msg in messages:
                    if msg.get("author_id") == "ciris_agent":
                        return msg
                        
            except Exception:
                pass  # Continue polling
                
            await asyncio.sleep(poll_interval)
            
        return None
    
    async def list_channels(self) -> Dict[str, Any]:
        """List all active channels.
        
        Returns:
            List of channels with activity info
        """
        return await self._transport.request("GET", "/v1/agent/channels")
    
    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get information about a specific channel.
        
        Args:
            channel_id: Channel to get info for
            
        Returns:
            Channel statistics and metadata
        """
        return await self._transport.request(
            "GET",
            f"/v1/agent/channels/{channel_id}"
        )
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the agent's current status.
        
        Returns:
            Agent status including identity and processor state
        """
        return await self._transport.request("GET", "/v1/agent/status")
    
    # Convenience methods for common patterns
    
    async def send(self, content: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for sending a message."""
        return await self.send_message(content, **kwargs)
    
    async def ask(
        self,
        question: str,
        channel_id: str = "api_default",
        timeout: float = 30.0
    ) -> Optional[str]:
        """Ask a question and wait for response.
        
        Args:
            question: Question to ask
            channel_id: Channel to use
            timeout: Maximum time to wait
            
        Returns:
            Agent's response content or None if timeout
        """
        # Send the question
        result = await self.send_message(question, channel_id=channel_id)
        message_id = result.get("message_id")
        
        if not message_id:
            return None
            
        # Wait for response
        response = await self.wait_for_response(
            channel_id,
            message_id,
            timeout=timeout
        )
        
        if response:
            return response.get("content")
            
        return None