"""
Service protocols for the CIRIS Agent registry system.
These protocols define clear contracts for different types of services.
"""
from typing import Protocol, Optional, Dict, Any, List
from abc import abstractmethod
from ciris_engine.schemas.foundational_schemas_v1 import (
    HandlerActionType,
    IncomingMessage,
    FetchedMessage,
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult
from ciris_engine.schemas.network_schemas_v1 import AgentIdentity, NetworkPresence
from ciris_engine.schemas.community_schemas_v1 import MinimalCommunityContext

class CommunicationService(Protocol):
    """Protocol for communication services (Discord, Veilid, etc)"""
    
    @abstractmethod
    async def send_message(self, channel_id: str, content: str) -> bool:
        """
        Send a message to a specific channel.
        
        Args:
            channel_id: The channel identifier
            content: The message content to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        ...
    
    @abstractmethod
    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        """
        Fetch recent messages from a channel.
        
        Args:
            channel_id: The channel identifier
            limit: Maximum number of messages to fetch
            
        Returns:
            List of fetched messages
        """
        ...
    
    async def is_healthy(self) -> bool:
        """
        Health check for circuit breaker.
        Default implementation returns True.
        """
        return True
    
    async def get_capabilities(self) -> List[str]:
        """
        Return list of capabilities this service supports.
        """
        return ["send_message", "fetch_messages"]


class WiseAuthorityService(Protocol):
    """Protocol for Wise Authority services"""
    
    @abstractmethod
    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Fetch guidance from the wise authority.
        
        Args:
            context: Context information for the guidance request
            
        Returns:
            Guidance text if available, None otherwise
        """
        ...
    
    @abstractmethod
    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        """
        Send a thought for deferral to wise authority.
        
        Args:
            thought_id: The ID of the thought to defer
            reason: Reason for deferral
            
        Returns:
            True if deferral was submitted successfully
        """
        ...
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["fetch_guidance", "send_deferral"]


class MemoryService(Protocol):
    """Protocol for memory services"""
    
    @abstractmethod
    async def memorize(self, node: GraphNode) -> MemoryOpResult:
        """Store a graph node and return operation result."""
        ...
    
    @abstractmethod
    async def recall(self, node: GraphNode) -> MemoryOpResult:
        """Retrieve a node from memory."""
        ...
    
    @abstractmethod
    async def forget(self, node: GraphNode) -> MemoryOpResult:
        """Delete a node from memory."""
        ...
    
    async def search_memories(self, query: str, scope: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search memories by query.
        
        Args:
            query: Search query
            scope: The memory scope
            limit: Maximum number of results
            
        Returns:
            List of matching memories
        """
        return []
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["memorize", "recall", "forget"]





class ToolService(Protocol):
    """Protocol for tool services (LLM tools, external APIs, etc.)"""
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        ...
    
    @abstractmethod
    async def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names this service can execute
        """
        ...
    
    @abstractmethod
    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Get the result of a previously executed tool by correlation ID.
        
        Args:
            correlation_id: The correlation ID of the tool execution
            timeout: Maximum time to wait for the result
            
        Returns:
            Tool result if available, None if not found or timeout
        """
        ...
    
    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters for a tool.
        
        Args:
            tool_name: Name of the tool
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid
        """
        return True
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]


class AuditService(Protocol):
    """Protocol for audit and logging services"""
    
    @abstractmethod
    async def log_action(self, action_type: HandlerActionType, context: Dict[str, Any], outcome: Optional[str] = None) -> bool:
        """
        Log an action for audit purposes.
        
        Args:
            action_type: Type of action being logged (HandlerActionType enum)
            context: Context information
            outcome: Optional outcome description
            
        Returns:
            True if logged successfully
        """
        ...
    
    @abstractmethod
    async def log_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Log a general event.
        
        Args:
            event_type: Type of event being logged
            event_data: Event data and context
        """
        ...
    
    @abstractmethod
    async def log_guardrail_event(self, guardrail_name: str, action_type: str, result: Dict[str, Any]) -> None:
        """
        Log guardrail check events.
        
        Args:
            guardrail_name: Name of the guardrail
            action_type: Type of action being checked
            result: Guardrail check result
        """
        ...
    
    @abstractmethod
    async def get_audit_trail(self, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit trail for an entity.
        
        Args:
            entity_id: ID of the entity to get audit trail for
            limit: Maximum number of audit entries
            
        Returns:
            List of audit entries
        """
        ...
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["log_action", "get_audit_trail"]


class LLMService(Protocol):
    """Protocol for Large Language Model services"""
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a text response from the LLM.
        
        Args:
            messages: Conversation messages
            model: Optional model name override
            temperature: Response randomness (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated response text
        """
        ...
    
    @abstractmethod
    async def generate_structured_response(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured response conforming to schema.
        
        Args:
            messages: Conversation messages
            response_schema: JSON schema for response structure
            model: Optional model name override
            
        Returns:
            Structured response as dictionary
        """
        ...
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return []
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["generate_response", "generate_structured_response"]


class NetworkService(Protocol):
    """Protocol for network participation services"""
    
    @abstractmethod
    async def register_agent(self, identity: AgentIdentity) -> bool:
        """Register agent on network"""
        ...
    
    @abstractmethod
    async def discover_peers(self, capabilities: List[str] = None) -> List[NetworkPresence]:
        """Discover other agents/services"""
        ...
    
    @abstractmethod
    async def check_wa_availability(self) -> bool:
        """Check if any Wise Authority is reachable"""
        ...
    
    @abstractmethod
    async def query_network(self, query_type: str, params: Dict[str, Any]) -> Any:
        """Query network for information"""
        ...

class CommunityService(Protocol):
    """Protocol for community-aware services"""
    
    @abstractmethod
    async def get_community_context(self, community_id: str) -> MinimalCommunityContext:
        """Get current community context"""
        ...
    
    @abstractmethod
    async def report_community_metric(self, metric: str, value: int) -> bool:
        """Report a community health metric (0-100 scale)"""
        ...
