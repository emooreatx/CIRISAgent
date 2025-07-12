"""
Correlation node for storing service interactions as graph memories.

This enables correlations to be part of the unified graph memory system
instead of a separate SQLite table.
"""
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from pydantic import Field

from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.graph_typed_nodes import TypedGraphNode, register_node_type
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation, ServiceCorrelationStatus, CorrelationType,
    ServiceRequestData, ServiceResponseData, MetricData, LogData, TraceContext
)


@register_node_type("CORRELATION")
class CorrelationNode(TypedGraphNode, ServiceCorrelation):
    """
    A service correlation stored as a graph memory.
    
    Combines ServiceCorrelation with TypedGraphNode to enable:
    - Graph relationships between correlations and other nodes
    - Time-based queries across all system events
    - Unified storage in the memory graph
    """
    
    # Required TypedGraphNode fields
    id: str = Field(..., description="Unique node ID (uses correlation_id)")
    type: NodeType = Field(default=NodeType.CORRELATION, description="Node type")
    scope: GraphScope = Field(default=GraphScope.LOCAL, description="Correlation scope")
    version: int = Field(default=1, description="Schema version")
    
    # Override to use correlation_id as node ID
    def __init__(self, **data) -> None:
        # Use correlation_id as the node ID
        if "correlation_id" in data and "id" not in data:
            data["id"] = f"correlation_{data['correlation_id']}"
        super().__init__(**data)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        # Extract all ServiceCorrelation fields
        extra_fields = {
            # Core correlation fields
            "correlation_id": self.correlation_id,
            "correlation_type": self.correlation_type.value,
            "service_type": self.service_type,
            "handler_name": self.handler_name,
            "action_type": self.action_type,
            "status": self.status.value,
            
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            
            # Structured data
            "request_data": self.request_data.model_dump() if self.request_data else None,
            "response_data": self.response_data.model_dump() if self.response_data else None,
            
            # TSDB fields
            "metric_data": self.metric_data.model_dump() if self.metric_data else None,
            "log_data": self.log_data.model_dump() if self.log_data else None,
            "trace_context": self.trace_context.model_dump() if self.trace_context else None,
            
            # Other fields
            "tags": self.tags,
            "retention_policy": self.retention_policy,
            "ttl_seconds": self.ttl_seconds,
            "parent_correlation_id": self.parent_correlation_id,
            "child_correlation_ids": self.child_correlation_ids,
            
            # Type hint for deserialization
            "_node_class": "CorrelationNode"
        }
        
        # Remove None values to save space
        extra_fields = {k: v for k, v in extra_fields.items() if v is not None}
        
        return GraphNode(
            id=self.id,
            type=self.type,
            scope=self.scope,
            attributes=extra_fields,
            version=self.version,
            updated_by=self.updated_by or self.handler_name,
            updated_at=self.updated_at
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> 'CorrelationNode':
        """Reconstruct from GraphNode."""
        attrs = node.attributes if isinstance(node.attributes, dict) else {}
        
        # Parse timestamps
        created_at = cls._deserialize_datetime(attrs.get("created_at"))
        updated_at = cls._deserialize_datetime(attrs.get("updated_at"))
        timestamp = cls._deserialize_datetime(attrs.get("timestamp"))
        
        # Reconstruct structured data
        request_data = None
        if attrs.get("request_data"):
            request_data = ServiceRequestData(**attrs["request_data"])
        
        response_data = None
        if attrs.get("response_data"):
            response_data = ServiceResponseData(**attrs["response_data"])
        
        metric_data = None
        if attrs.get("metric_data"):
            metric_data = MetricData(**attrs["metric_data"])
        
        log_data = None
        if attrs.get("log_data"):
            log_data = LogData(**attrs["log_data"])
        
        trace_context = None
        if attrs.get("trace_context"):
            trace_context = TraceContext(**attrs["trace_context"])
        
        return cls(
            # Base fields from GraphNode
            id=node.id,
            type=node.type,
            scope=node.scope,
            version=node.version,
            updated_by=node.updated_by,
            updated_at=node.updated_at,
            
            # Correlation fields
            correlation_id=attrs.get("correlation_id", node.id.replace("correlation_", "")),
            correlation_type=CorrelationType(attrs.get("correlation_type", "service_interaction")),
            service_type=attrs.get("service_type", "unknown"),
            handler_name=attrs.get("handler_name", "unknown"),
            action_type=attrs.get("action_type", "unknown"),
            status=ServiceCorrelationStatus(attrs.get("status", "pending")),
            
            # Timestamps
            created_at=created_at or datetime.now(timezone.utc),
            timestamp=timestamp or created_at or datetime.now(timezone.utc),
            
            # Structured data
            request_data=request_data,
            response_data=response_data,
            metric_data=metric_data,
            log_data=log_data,
            trace_context=trace_context,
            
            # Other fields
            tags=attrs.get("tags", {}),
            retention_policy=attrs.get("retention_policy", "raw"),
            ttl_seconds=attrs.get("ttl_seconds"),
            parent_correlation_id=attrs.get("parent_correlation_id"),
            child_correlation_ids=attrs.get("child_correlation_ids", [])
        )


# Example relationships for correlations
CORRELATION_RELATIONSHIPS = {
    # Connect observe/speak pairs
    "RESPONDS_TO": "Links a speak action to the observe it responds to",
    
    # Connect to tasks/thoughts
    "TRIGGERED_BY": "Links correlation to the task/thought that triggered it",
    "RESULTED_IN": "Links correlation to resulting tasks/thoughts",
    
    # Chain correlations
    "FOLLOWS": "Links sequential correlations in a flow",
    "CAUSED": "Links correlations in a causal chain",
    
    # Error tracking
    "ERROR_IN": "Links error correlations to the action that failed",
    "RETRY_OF": "Links retry attempts"
}