"""
Service protocols for the CIRIS Agent registry system.
These protocols define clear contracts for different types of services.
All service implementations must inherit from the Service base class for lifecycle management.
"""
from typing import Optional, Dict, Any, List, Type, Tuple
from abc import abstractmethod
from datetime import datetime
from pydantic import BaseModel
from ciris_engine.adapters.base import Service
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
from ciris_engine.schemas.foundational_schemas_v1 import (
    HandlerActionType,
    FetchedMessage,
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.network_schemas_v1 import AgentIdentity, NetworkPresence
from ciris_engine.schemas.community_schemas_v1 import MinimalCommunityContext


class CommunicationService(Service):
    """Abstract base class for communication services (Discord, Veilid, etc)"""
    
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


class WiseAuthorityService(Service):
    """Abstract base class for Wise Authority services"""
    
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
    async def send_deferral(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a thought for deferral to wise authority.
        
        Args:
            thought_id: The ID of the thought to defer
            reason: Reason for deferral
            context: Additional context about the thought and task
            
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


class MemoryService(Service):
    """Abstract base class for memory services"""
    
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
    
    async def recall_timeseries(self, scope: str = "default", hours: int = 24, correlation_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recall time-series data from TSDB correlations.
        
        Args:
            scope: The memory scope to search
            hours: Number of hours to look back
            correlation_types: Optional filter by correlation types (e.g., ['METRIC_DATAPOINT', 'LOG_ENTRY'])
            
        Returns:
            List of time-series data points from correlations
        """
        return []
    
    async def memorize_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """
        Convenience method to memorize a metric as both a graph node and TSDB correlation.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags for the metric
            scope: Memory scope
            
        Returns:
            Memory operation result
        """
        return MemoryOpResult(status=MemoryOpStatus.DENIED, error="Not implemented")
    
    async def memorize_log(self, log_message: str, log_level: str = "INFO", tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """
        Convenience method to memorize a log entry as both a graph node and TSDB correlation.
        
        Args:
            log_message: Log message content
            log_level: Log level (INFO, WARNING, ERROR, etc.)
            tags: Optional tags for the log entry
            scope: Memory scope
            
        Returns:
            Memory operation result
        """
        return MemoryOpResult(status=MemoryOpStatus.DENIED, error="Not implemented")
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["memorize", "recall", "forget", "search_memories", "recall_timeseries", "memorize_metric", "memorize_log"]


class ToolService(Service):
    """Abstract base class for tool services (LLM tools, external APIs, etc.)"""
    
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


class AuditService(Service):
    """Abstract base class for audit and logging services"""
    
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
    
    async def query_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action_types: Optional[List[str]] = None,
        thought_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit trail with time-series filtering (TSDB-enabled services).
        
        Args:
            start_time: Start of time range
            end_time: End of time range  
            action_types: Filter by specific action types
            thought_id: Filter by thought ID
            task_id: Filter by task ID
            limit: Maximum number of results
            
        Returns:
            List of audit entries matching criteria
        """
        # Default implementation for non-TSDB services
        return await self.get_audit_trail("", limit)
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["log_action", "log_event", "log_guardrail_event", "get_audit_trail", "query_audit_trail"]


class LLMService(Service):
    """Abstract base class for Large Language Model services"""
    
    @abstractmethod
    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Tuple[BaseModel, ResourceUsage]:
        """
        Make a structured LLM call with Pydantic model response.
        
        Args:
            messages: Conversation messages
            response_model: Pydantic model class for response structure
            max_tokens: Maximum tokens in response
            temperature: Response randomness (0.0-1.0)
            **kwargs: Additional LLM parameters
            
        Returns:
            Tuple of (structured response, resource usage)
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
        return ["call_llm_structured"]


class NetworkService(Service):
    """Abstract base class for network participation services"""
    
    @abstractmethod
    async def register_agent(self, identity: AgentIdentity) -> bool:
        """Register agent on network"""
        ...
    
    @abstractmethod
    async def discover_peers(self, capabilities: Optional[List[str]] = None) -> List[NetworkPresence]:
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


class CommunityService(Service):
    """Abstract base class for community-aware services"""
    
    @abstractmethod
    async def get_community_context(self, community_id: str) -> MinimalCommunityContext:
        """Get current community context"""
        ...
    
    @abstractmethod
    async def report_community_metric(self, metric: str, value: int) -> bool:
        """Report a community health metric (0-100 scale)"""
        ...


class TelemetryService(Service):
    """Abstract base class for telemetry and metrics services"""
    
    @abstractmethod
    async def record_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> bool:
        """
        Record a metric value with optional tags.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags for categorization and filtering
            
        Returns:
            True if metric was recorded successfully
        """
        ...
    
    @abstractmethod
    async def get_metrics_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical metric data.
        
        Args:
            metric_name: Name of the metric to retrieve
            hours: Number of hours of history to retrieve
            
        Returns:
            List of metric data points with timestamps
        """
        ...
    
    async def record_log(self, log_message: str, log_level: str = "INFO", tags: Optional[Dict[str, str]] = None) -> bool:
        """
        Record a log entry for time-series analysis.
        
        Args:
            log_message: Log message content
            log_level: Log level (INFO, WARNING, ERROR, etc.)
            tags: Optional tags for categorization
            
        Returns:
            True if log was recorded successfully
        """
        return True
    
    async def query_telemetry(
        self,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query telemetry data with time-series filtering.
        
        Args:
            metric_names: Optional list of metric names to filter by
            start_time: Start of time range
            end_time: End of time range
            tags: Optional tag filters
            limit: Maximum number of results
            
        Returns:
            List of telemetry data points
        """
        return []
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health metrics.
        
        Returns:
            Dictionary with health status and key metrics
        """
        return {"status": "unknown", "metrics": {}}
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["record_metric", "get_metrics_history", "record_log", "query_telemetry", "get_system_health"]