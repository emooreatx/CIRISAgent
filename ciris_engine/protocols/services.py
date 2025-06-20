"""
Service protocols for the CIRIS Agent registry system.
These protocols define clear contracts for different types of services.
All service implementations must inherit from the Service base class for lifecycle management.
"""
from typing import Optional, Dict, Any, List, Type, Tuple, Union
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
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus, MemoryQuery
from ciris_engine.schemas.network_schemas_v1 import AgentIdentity, NetworkPresence
from ciris_engine.schemas.community_schemas_v1 import MinimalCommunityContext
from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext, DeferralContext
from ciris_engine.schemas.secrets_schemas_v1 import SecretReference
from ciris_engine.schemas.runtime_control_schemas import ProcessorControlResponse
from ciris_engine.schemas.protocol_schemas_v1 import (
    MemorySearchResult, TimeSeriesDataPoint, IdentityUpdateRequest,
    EnvironmentUpdateRequest, ToolExecutionRequest, ToolExecutionResult,
    ToolInfo, ActionContext, GuardrailCheckResult, AuditEntry,
    LLMStatus, NetworkQueryRequest, MetricDataPoint, ServiceStatus,
    ResourceLimits, ProcessorQueueStatus, AdapterConfig, AdapterInfo,
    ConfigValue, SecretInfo, SecretsServiceStats
)


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
    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """
        Fetch guidance from the wise authority.
        
        Args:
            context: Typed context for the guidance request
            
        Returns:
            Guidance text if available, None otherwise
        """
        ...
    
    @abstractmethod
    async def send_deferral(self, context: DeferralContext) -> bool:
        """
        Send a thought for deferral to wise authority.
        
        Args:
            context: Typed context containing deferral information
            
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
    async def recall(self, recall_query: MemoryQuery) -> List[GraphNode]:
        """Retrieve nodes from memory based on query."""
        ...
    
    @abstractmethod
    async def forget(self, node: GraphNode) -> MemoryOpResult:
        """Delete a node from memory."""
        ...
    
    async def search_memories(self, query: str, scope: str = "default", limit: int = 10) -> List[MemorySearchResult]:
        """
        Search memories by query.
        
        Args:
            query: Search query
            scope: The memory scope
            limit: Maximum number of results
            
        Returns:
            List of matching memories with relevance scores
        """
        return []
    
    async def recall_timeseries(self, scope: str = "default", hours: int = 24, correlation_types: Optional[List[str]] = None) -> List[TimeSeriesDataPoint]:
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
    
    async def export_identity_context(self) -> str:
        """Export identity nodes as string representation."""
        return ""
    
    async def update_identity_graph(self, update_request: IdentityUpdateRequest) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        return MemoryOpResult(status=MemoryOpStatus.DENIED, error="Not implemented")
    
    async def update_environment_graph(self, update_request: EnvironmentUpdateRequest) -> MemoryOpResult:
        """Update environment graph based on adapter feedback."""
        return MemoryOpResult(status=MemoryOpStatus.DENIED, error="Not implemented")
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["memorize", "recall", "forget", "export_identity_context", "update_identity_graph", "update_environment_graph"]


class ToolService(Service):
    """Abstract base class for tool services (LLM tools, external APIs, etc.)"""
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolExecutionResult:
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
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """
        Get detailed information about a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Complete tool information including schema, or None if not found
        """
        ...
    
    @abstractmethod
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """
        Get detailed information about all available tools.
        
        Returns:
            List of tool information for all tools provided by this service
        """
        ...
    
    @abstractmethod
    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
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
    
    async def get_adapter_id(self) -> str:
        """
        Get the unique identifier of the adapter providing these tools.
        
        Returns:
            Adapter instance ID
        """
        return "default"
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["execute_tool", "get_available_tools", "get_tool_info", 
                "get_all_tool_info", "get_tool_result", "get_adapter_id"]


class AuditService(Service):
    """Abstract base class for audit and logging services"""
    
    async def log_action(self, action_type: HandlerActionType, context: ActionContext, outcome: Optional[str] = None) -> bool:
        """
        Log an action for audit purposes.
        
        Args:
            action_type: Type of action being logged (HandlerActionType enum)
            context: Context information
            outcome: Optional outcome description
            
        Returns:
            True if logged successfully
        """
        return True
    
    @abstractmethod
    async def log_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Log a general event.
        
        Args:
            event_type: Type of event being logged
            event_data: Event data and context
        """
        ...
    
    async def log_guardrail_event(self, guardrail_name: str, action_type: str, result: GuardrailCheckResult) -> None:
        """
        Log guardrail check events.
        
        Args:
            guardrail_name: Name of the guardrail
            action_type: Type of action being checked
            result: Guardrail check result
        """
        pass
    
    @abstractmethod
    async def get_audit_trail(self, entity_id: str, limit: int = 100) -> List[AuditEntry]:
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
    ) -> List[AuditEntry]:
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
        return await self.get_audit_trail("", limit)
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["log_event", "get_audit_trail"]


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
    
    async def get_status(self) -> LLMStatus:
        """Get LLM service status including model info and usage metrics."""
        return LLMStatus(
            available=True,
            model="unknown",
            usage={},
            rate_limit_remaining=None,
            response_time_avg=None
        )
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["call_llm_structured", "get_available_models", "get_status"]


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
    async def query_network(self, request: NetworkQueryRequest) -> Any:
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
    async def record_resource_usage(self, service_name: str, usage: ResourceUsage) -> bool:
        """
        Record resource usage for a service.
        
        Args:
            service_name: Name of the service
            usage: Resource usage data
            
        Returns:
            True if resource usage was recorded successfully
        """
        ...
    
    @abstractmethod
    async def query_metrics(self, _metric_names: Optional[List[str]] = None, _service_names: Optional[List[str]] = None, _time_range: Optional[Tuple[datetime, datetime]] = None, _tags: Optional[Dict[str, str]] = None, _aggregation: Optional[str] = None) -> List[MetricDataPoint]:
        """
        Query metrics with filtering and aggregation options.
        
        Args:
            metric_names: Optional list of metric names to filter by
            service_names: Optional list of service names to filter by
            time_range: Optional tuple of (start_time, end_time)
            tags: Optional tag filters
            aggregation: Optional aggregation type (e.g., 'sum', 'avg', 'max', 'min')
            
        Returns:
            List of metric data points
        """
        ...
    
    @abstractmethod
    async def get_service_status(self, service_name: Optional[str] = None) -> Union[ServiceStatus, Dict[str, ServiceStatus]]:
        """
        Get service status information.
        
        Args:
            service_name: Optional specific service name. If None, returns all services.
            
        Returns:
            Dictionary with service status information
        """
        ...
    
    @abstractmethod
    async def get_resource_limits(self) -> ResourceLimits:
        """
        Get resource limits and quotas.
        
        Returns:
            Dictionary with resource limits for various metrics
        """
        ...
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return ["record_metric", "record_resource_usage", "query_metrics", "get_service_status", "get_resource_limits"]


class RuntimeControlService(Service):
    """Abstract base class for runtime control services"""
    
    @abstractmethod
    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        ...
    
    @abstractmethod
    async def pause_processing(self) -> ProcessorControlResponse:
        """Pause the processor."""
        ...
    
    @abstractmethod
    async def resume_processing(self) -> ProcessorControlResponse:
        """Resume the processor."""
        ...
    
    @abstractmethod
    async def get_processor_queue_status(self) -> ProcessorQueueStatus:
        """Get processor queue status."""
        ...
    
    @abstractmethod
    async def shutdown_runtime(self, reason: str) -> ProcessorControlResponse:
        """Shutdown the runtime."""
        ...
    
    @abstractmethod
    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: str,
        config: Dict[str, Any],  # Keep as dict for flexibility
        auto_start: bool = True
    ) -> AdapterInfo:
        """Load a new adapter instance."""
        ...
    
    @abstractmethod
    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterInfo:
        """Unload an adapter instance."""
        ...
    
    @abstractmethod
    async def list_adapters(self) -> List[AdapterInfo]:
        """List all loaded adapters."""
        ...
    
    @abstractmethod
    async def get_adapter_info(self, adapter_id: str) -> AdapterInfo:
        """Get detailed information about a specific adapter."""
        ...
    
    @abstractmethod
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Union[ConfigValue, Dict[str, ConfigValue]]:
        """Get configuration value(s)."""
        ...
    
    @abstractmethod
    async def get_runtime_status(self) -> Dict[str, Any]:  # Complex status, keep as dict
        """
        Get current runtime status.
        
        Returns:
            Dictionary containing runtime status information
        """
        ...
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "single_step", "pause_processing", "resume_processing",
            "get_processor_queue_status", "shutdown_runtime",
            "load_adapter", "unload_adapter", "list_adapters", "get_adapter_info",
            "get_config", "get_runtime_status"
        ]


class SecretsService(Service):
    """Abstract base class for secrets management services"""
    
    @abstractmethod
    async def process_incoming_text(
        self, 
        text: str, 
        context_hint: str = "",
        source_message_id: Optional[str] = None
    ) -> Tuple[str, List[SecretReference]]:
        """
        Process incoming text for secrets detection and replacement.
        
        Args:
            text: Original text to process
            context_hint: Safe context description
            source_message_id: ID of source message for tracking
            
        Returns:
            Tuple of (filtered_text, secret_references)
        """
        ...
    
    @abstractmethod
    async def decapsulate_secrets_in_parameters(
        self,
        parameters: Any,
        action_type: str,
        context: Dict[str, Any]
    ) -> Any:
        """
        Replace secret UUIDs with actual values in action parameters.
        
        Args:
            parameters: Action parameters that may contain secret UUID references
            action_type: Type of action being performed (for access control)
            context: Context information for the decapsulation
            
        Returns:
            Parameters with secrets decapsulated
        """
        ...
    
    @abstractmethod
    async def list_stored_secrets(
        self,
        limit: int = 10
    ) -> List[SecretReference]:
        """
        Get references to stored secrets for SystemSnapshot.
        
        Args:
            limit: Maximum number of secrets to return
            
        Returns:
            List of SecretReference objects for agent introspection
        """
        ...
    
    @abstractmethod
    async def recall_secret(
        self,
        secret_uuid: str,
        purpose: str,
        accessor: str = "agent",
        decrypt: bool = False
    ) -> Optional[SecretInfo]:
        """
        Recall a stored secret for agent use.
        
        Args:
            secret_uuid: UUID of secret to recall
            purpose: Purpose for accessing secret (for audit)
            accessor: Who is accessing the secret
            decrypt: Whether to return decrypted value
            
        Returns:
            Secret information dict or None if not found/denied
        """
        ...
    
    @abstractmethod
    async def update_filter_config(
        self,
        updates: Dict[str, Any],
        accessor: str = "agent"
    ) -> Dict[str, Any]:  # Keep as dict for flexibility
        """
        Update filter configuration settings.
        
        Args:
            updates: Dictionary of configuration updates
            accessor: Who is making the update
            
        Returns:
            Dictionary with operation result
        """
        ...
    
    @abstractmethod
    async def forget_secret(
        self,
        secret_uuid: str,
        accessor: str = "agent"
    ) -> bool:
        """
        Delete/forget a stored secret.
        
        Args:
            secret_uuid: UUID of secret to forget
            accessor: Who is forgetting the secret
            
        Returns:
            True if successfully forgotten
        """
        ...
    
    async def auto_forget_task_secrets(self) -> List[str]:
        """
        Automatically forget secrets from current task.
        
        Returns:
            List of forgotten secret UUIDs
        """
        return []
    
    async def get_service_stats(self) -> SecretsServiceStats:
        """
        Get service statistics for monitoring.
        
        Returns:
            Dictionary with service statistics
        """
        return SecretsServiceStats(
            secrets_stored=0,
            filter_active=True,
            patterns_enabled=[],
            recent_detections=0,
            storage_size_bytes=0
        )
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker"""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "process_incoming_text", "decapsulate_secrets_in_parameters",
            "list_stored_secrets", "recall_secret", "update_filter_config",
            "forget_secret", "auto_forget_task_secrets", "get_service_stats"
        ]