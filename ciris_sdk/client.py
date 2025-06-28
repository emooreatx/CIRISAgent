from __future__ import annotations

import asyncio
from typing import Any, Optional, Dict

from .transport import Transport
from .resources.agent import AgentResource, InteractResponse, AgentStatus, AgentIdentity, ConversationHistory
from .resources.audit import AuditResource
from .resources.memory import MemoryResource
from .resources.visibility import VisibilityResource
from .resources.telemetry import TelemetryResource
from .resources.runtime import RuntimeResource
from .resources.auth import AuthResource
from .resources.wa import WiseAuthorityResource
from .resources.config import ConfigResource
from .exceptions import CIRISTimeoutError, CIRISConnectionError

class CIRISClient:
    """Main client for interacting with CIRIS API.
    
    The client provides access to all API resources through a clean, typed interface.
    It handles authentication, retries, and connection management automatically.
    
    Example:
        async with CIRISClient() as client:
            # Simple interaction
            response = await client.interact("Hello, CIRIS!")
            print(response.response)
            
            # Get agent status
            status = await client.status()
            print(f"Agent state: {status.cognitive_state}")
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize CIRIS client.
        
        Args:
            base_url: Base URL of CIRIS API (default: http://localhost:8080)
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds (default: 30.0)
            max_retries: Number of retries for failed requests (default: 3)
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = Transport(base_url, api_key, timeout)

        # Core resources matching new API structure
        self.agent = AgentResource(self._transport)
        self.audit = AuditResource(self._transport)
        self.memory = MemoryResource(self._transport)
        self.visibility = VisibilityResource(self._transport)
        self.telemetry = TelemetryResource(self._transport)
        self.runtime = RuntimeResource(self._transport)
        self.auth = AuthResource(self._transport)
        self.wa = WiseAuthorityResource(self._transport)
        self.config = ConfigResource(self._transport)

    async def __aenter__(self) -> "CIRISClient":
        await self._transport.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._transport.__aexit__(exc_type, exc, tb)

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> Any:
        for attempt in range(self.max_retries):
            try:
                return await self._transport.request(method, path, **kwargs)
            except CIRISConnectionError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
    
    # Convenience methods for primary agent interactions
    
    async def interact(self, message: str, context: Optional[Dict[str, Any]] = None) -> InteractResponse:
        """Send message and get response from agent.
        
        This is the primary method for interacting with the agent.
        It sends your message and waits for the agent's response.
        
        Args:
            message: Message to send to the agent
            context: Optional context for the interaction
            
        Returns:
            InteractResponse with the agent's response and metadata
            
        Example:
            response = await client.interact("What is the weather like?")
            print(response.response)  # Agent's response text
            print(f"Processing took {response.processing_time_ms}ms")
        """
        return await self.agent.interact(message, context)
    
    async def ask(self, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Ask a question and get just the response text.
        
        Convenience method that returns only the response content.
        
        Args:
            question: Question to ask the agent
            context: Optional context
            
        Returns:
            Agent's response as a string
            
        Example:
            answer = await client.ask("What is 2 + 2?")
            print(answer)  # "4"
        """
        return await self.agent.ask(question, context)
    
    async def history(self, limit: int = 50) -> ConversationHistory:
        """Get conversation history.
        
        Args:
            limit: Maximum messages to return (1-200)
            
        Returns:
            ConversationHistory with recent messages
        """
        return await self.agent.get_history(limit)
    
    async def status(self) -> AgentStatus:
        """Get agent status and cognitive state.
        
        Returns:
            AgentStatus with current state information
        """
        return await self.agent.get_status()
    
    async def identity(self) -> AgentIdentity:
        """Get agent identity and capabilities.
        
        Returns:
            AgentIdentity with comprehensive identity info
        """
        return await self.agent.get_identity()
    
    # Authentication helpers
    
    async def login(self, username: str, password: str) -> None:
        """Login to the API and store authentication token.
        
        Args:
            username: Username for authentication
            password: Password for authentication
        """
        response = await self.auth.login(username, password)
        self._transport.set_api_key(response.access_token)
    
    async def logout(self) -> None:
        """Logout and invalidate current token."""
        await self.auth.logout()
        self._transport.set_api_key(None)
