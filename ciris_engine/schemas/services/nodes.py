"""
Graph node type schemas for CIRIS.

These define all the specialized node types that can be stored in the graph.
Everything in the graph is a memory - these are the different types of memories.
"""
from typing import Optional, Dict, List, Union
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, GraphNodeAttributes
from ciris_engine.schemas.services.graph_typed_nodes import TypedGraphNode, register_node_type

class AuditEntryContext(BaseModel):
    """Typed context for audit entries."""
    service_name: Optional[str] = None
    method_name: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    additional_data: Optional[Dict[str, Union[str, int, float, bool]]] = None

@register_node_type("AUDIT_ENTRY")
class AuditEntry(TypedGraphNode):
    """An audit trail entry stored as a graph memory."""
    action: str = Field(..., description="The action that was performed")
    actor: str = Field(..., description="Who/what performed the action")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: AuditEntryContext = Field(..., description="Typed action context")
    signature: Optional[str] = Field(None, description="Cryptographic signature if signed")
    hash_chain: Optional[str] = Field(None, description="Previous hash for chain integrity")
    
    # Required TypedGraphNode fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="audit_service")
    updated_by: str = Field(default="audit_service")
    
    # Graph node type
    type: NodeType = Field(default=NodeType.AUDIT_ENTRY)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        # Get all fields
        all_attrs = self.model_dump()
        
        # Extract base GraphNode fields
        node_id = all_attrs.get("id", f"audit_{self.timestamp.strftime('%Y%m%d_%H%M%S')}_{self.actor}")
        node_type = self.type
        node_scope = all_attrs.get("scope", GraphScope.LOCAL)
        node_version = all_attrs.get("version", 1)
        
        # Remove base fields from attrs to avoid duplication
        extra_attrs = {k: v for k, v in all_attrs.items() 
                      if k not in ["id", "type", "scope", "version", "created_at", "updated_at", "created_by", "updated_by", "attributes"]}
        
        # Convert datetime fields
        extra_attrs["timestamp"] = self.timestamp.isoformat()
        
        # Convert context to dict
        extra_attrs["context"] = self.context.model_dump()
        
        # Mark for deserialization
        extra_attrs["_node_class"] = "AuditEntry"
        
        # Build attributes dict with required fields and extra data
        attributes_dict = {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "tags": [f"action:{self.action}", f"actor:{self.actor}"],
            **extra_attrs
        }
        
        return GraphNode(
            id=node_id,
            type=node_type,
            scope=node_scope,
            attributes=attributes_dict,  # Pass as dict, not GraphNodeAttributes
            version=node_version
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> "AuditEntry":
        """Reconstruct from GraphNode."""
        # Handle both dict and GraphNodeAttributes
        if isinstance(node.attributes, dict):
            attrs = node.attributes
        elif hasattr(node.attributes, 'model_dump'):
            attrs = node.attributes.model_dump()
        else:
            raise ValueError(f"Invalid attributes type: {type(node.attributes)}")
        
        # Deserialize timestamp
        timestamp = cls._deserialize_datetime(attrs.get("timestamp", attrs.get("created_at")))
        created_at = cls._deserialize_datetime(attrs.get("created_at", attrs.get("timestamp")))
        updated_at = cls._deserialize_datetime(attrs.get("updated_at", attrs.get("created_at")))
        
        # Deserialize context
        context_data = attrs.get("context", {})
        if isinstance(context_data, dict):
            context = AuditEntryContext(**context_data)
        else:
            context = AuditEntryContext()
        
        return cls(
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=node.attributes,  # Pass through the attributes
            action=attrs.get("action", "unknown"),
            actor=attrs.get("actor", "unknown"),
            timestamp=timestamp,
            context=context,
            signature=attrs.get("signature"),
            hash_chain=attrs.get("hash_chain"),
            created_at=created_at,
            updated_at=updated_at,
            created_by=attrs.get("created_by", "audit_service"),
            updated_by=attrs.get("updated_by", "audit_service"),
            version=node.version
        )

class ConfigValue(BaseModel):
    """Typed configuration value wrapper."""
    string_value: Optional[str] = None
    int_value: Optional[int] = None
    float_value: Optional[float] = None
    bool_value: Optional[bool] = None
    list_value: Optional[List[Union[str, int, float, bool]]] = None
    dict_value: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None  # Allow None values in dict
    
    @property
    def value(self):
        """Get the actual value."""
        for field_name, field_value in self.model_dump().items():
            if field_value is not None:
                return field_value
        return None

@register_node_type("config")
class ConfigNode(TypedGraphNode):
    """A configuration value stored as a graph memory with versioning."""
    key: str = Field(..., description="Configuration key")
    value: ConfigValue = Field(..., description="Typed configuration value")
    version: int = Field(default=1, description="Version number")
    updated_by: str = Field(..., description="Who updated this config")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_version: Optional[str] = Field(None, description="Node ID of previous version")
    
    # Graph node type - use the enum value
    type: NodeType = Field(default=NodeType.CONFIG)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        # Include both GraphNodeAttributes required fields AND ConfigNode extra fields
        extra_fields = {
            # Required GraphNodeAttributes fields
            "created_at": self.updated_at.isoformat(),  # Use updated_at as created_at
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.updated_by,
            "tags": [f"config:{self.key.split('.')[0]}"],
            # ConfigNode specific fields
            "key": self.key,
            "value": self.value.model_dump(),
            # Don't duplicate version in attributes - it's already in GraphNode.version
            "previous_version": self.previous_version,
            "_node_class": "ConfigNode"
        }
        
        return GraphNode(
            id=self.id,
            type=self.type,
            scope=self.scope,
            attributes=extra_fields,
            version=self.version,
            updated_by=self.updated_by,
            updated_at=self.updated_at
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> 'ConfigNode':
        """Reconstruct from GraphNode."""
        # Handle both dict and GraphNodeAttributes
        if isinstance(node.attributes, dict):
            attrs = node.attributes
        elif hasattr(node.attributes, 'model_dump'):
            attrs = node.attributes.model_dump()
        else:
            raise ValueError(f"Invalid attributes type: {type(node.attributes)}")
        
        # ConfigNode requires updated_by and updated_at, but GraphNode has them as Optional
        # Fall back to values from attributes if the GraphNode fields are None
        updated_by = node.updated_by or attrs.get("created_by", "unknown")
        updated_at = node.updated_at or cls._deserialize_datetime(attrs.get("updated_at", attrs.get("created_at")))
        
        return cls(
            # Base fields from GraphNode
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=node.attributes,  # Must pass this for GraphNode base class
            version=node.version,  # Use GraphNode's version, not from attributes
            updated_by=updated_by,
            updated_at=updated_at or datetime.now(timezone.utc),  # Final fallback
            # Extra fields from attributes
            key=attrs["key"],
            value=ConfigValue(**attrs["value"]),
            previous_version=attrs.get("previous_version")
        )

class ConfigChangeType(str, Enum):
    """Types of configuration changes."""
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"

class ConfigChange(BaseModel):
    """A single configuration change in an adaptation proposal."""
    change_type: ConfigChangeType
    config_key: str
    old_value: Optional[ConfigValue] = None
    new_value: Optional[ConfigValue] = None
    reason: str

@register_node_type("ADAPTATION_PROPOSAL")
class AdaptationProposal(TypedGraphNode):
    """A proposed adaptation stored as a graph memory."""
    proposal_id: str = Field(..., description="Unique proposal identifier")
    proposed_by: str = Field(..., description="Component that proposed this")
    trigger: str = Field(..., description="What triggered this proposal")
    changes: List[ConfigChange] = Field(..., description="Typed proposed changes")
    reasoning: str = Field(..., description="Reasoning for the proposal")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in proposal")
    risk_level: str = Field(..., description="Risk assessment: low, medium, high")
    status: str = Field(default="proposed", description="proposed, evaluating, approved, applied, rejected")
    
    # Required TypedGraphNode fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="self_configuration")
    updated_by: str = Field(default="self_configuration")
    
    # Graph node type
    type: NodeType = Field(default=NodeType.ADAPTATION_PROPOSAL)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        attrs = self.model_dump()
        
        # Convert datetime fields
        attrs["created_at"] = self.created_at.isoformat()
        attrs["updated_at"] = self.updated_at.isoformat()
        
        # Convert changes list to dicts
        attrs["changes"] = [change.model_dump() for change in self.changes]
        
        # Mark for deserialization
        attrs["_node_class"] = "AdaptationProposal"
        
        return GraphNode(
            id=attrs.get("id", f"proposal_{self.proposal_id}"),
            type=self.type,
            scope=attrs.get("scope", GraphScope.LOCAL),
            attributes=GraphNodeAttributes(
                created_at=self.created_at,
                updated_at=self.updated_at,
                created_by=self.created_by,
                updated_by=self.updated_by,
                tags=attrs.get("tags", [f"status:{self.status}", f"risk:{self.risk_level}"]),
                **attrs
            ),
            version=attrs.get("version", 1)
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> "AdaptationProposal":
        """Reconstruct from GraphNode."""
        attrs = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else dict(node.attributes)
        
        # Deserialize datetimes
        created_at = cls._deserialize_datetime(attrs.get("created_at"))
        updated_at = cls._deserialize_datetime(attrs.get("updated_at", attrs.get("created_at")))
        
        # Deserialize changes
        changes_data = attrs.get("changes", [])
        changes = [ConfigChange(**change) if isinstance(change, dict) else change for change in changes_data]
        
        return cls(
            id=node.id,
            type=node.type,
            scope=node.scope,
            proposal_id=attrs.get("proposal_id", "unknown"),
            proposed_by=attrs.get("proposed_by", "unknown"),
            trigger=attrs.get("trigger", "unknown"),
            changes=changes,
            reasoning=attrs.get("reasoning", ""),
            confidence=attrs.get("confidence", 0.5),
            risk_level=attrs.get("risk_level", "medium"),
            status=attrs.get("status", "proposed"),
            created_at=created_at,
            updated_at=updated_at,
            created_by=attrs.get("created_by", "self_configuration"),
            updated_by=attrs.get("updated_by", "self_configuration"),
            version=node.version
        )

@register_node_type("IDENTITY_SNAPSHOT")
class IdentitySnapshot(TypedGraphNode):
    """An identity snapshot stored as a graph memory."""
    baseline_hash: str = Field(..., description="Hash of baseline identity")
    current_hash: str = Field(..., description="Hash of current identity")
    drift_percentage: float = Field(..., ge=0.0, le=100.0, description="Drift from baseline")
    changed_components: List[str] = Field(default_factory=list, description="What changed")
    measurement_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Required TypedGraphNode fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="identity_monitor")
    updated_by: str = Field(default="identity_monitor")
    
    # Graph node type
    type: NodeType = Field(default=NodeType.IDENTITY_SNAPSHOT)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        attrs = self.model_dump()
        
        # Convert datetime fields
        attrs["measurement_time"] = self.measurement_time.isoformat()
        attrs["created_at"] = self.created_at.isoformat()
        attrs["updated_at"] = self.updated_at.isoformat()
        
        # Mark for deserialization
        attrs["_node_class"] = "IdentitySnapshot"
        
        return GraphNode(
            id=attrs.get("id", f"identity_{self.measurement_time.strftime('%Y%m%d_%H%M%S')}"),
            type=self.type,
            scope=attrs.get("scope", GraphScope.LOCAL),
            attributes=GraphNodeAttributes(
                created_at=self.created_at,
                updated_at=self.updated_at,
                created_by=self.created_by,
                updated_by=self.updated_by,
                tags=attrs.get("tags", [f"drift:{self.drift_percentage:.1f}%"]),
                **attrs
            ),
            version=attrs.get("version", 1)
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> "IdentitySnapshot":
        """Reconstruct from GraphNode."""
        attrs = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else dict(node.attributes)
        
        # Deserialize datetimes
        measurement_time = cls._deserialize_datetime(attrs.get("measurement_time", attrs.get("created_at")))
        created_at = cls._deserialize_datetime(attrs.get("created_at", attrs.get("measurement_time")))
        updated_at = cls._deserialize_datetime(attrs.get("updated_at", attrs.get("created_at")))
        
        return cls(
            id=node.id,
            type=node.type,
            scope=node.scope,
            baseline_hash=attrs.get("baseline_hash", ""),
            current_hash=attrs.get("current_hash", ""),
            drift_percentage=attrs.get("drift_percentage", 0.0),
            changed_components=attrs.get("changed_components", []),
            measurement_time=measurement_time,
            created_at=created_at,
            updated_at=updated_at,
            created_by=attrs.get("created_by", "identity_monitor"),
            updated_by=attrs.get("updated_by", "identity_monitor"),
            version=node.version
        )

class ErrorContext(BaseModel):
    """Typed context for errors."""
    service_name: Optional[str] = None
    method_name: Optional[str] = None
    task_id: Optional[str] = None
    thought_id: Optional[str] = None
    correlation_id: Optional[str] = None
    additional_info: Optional[Dict[str, Union[str, int, float, bool]]] = None

class ErrorMemory(GraphNode):
    """An error stored as a learning opportunity in the graph."""
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = Field(None, description="Stack trace if available")
    context: ErrorContext = Field(..., description="Typed error context")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    grace_extended: bool = Field(True, description="Grace extended for this error")
    lessons_learned: List[str] = Field(default_factory=list, description="What we learned")
    
    # Graph node type
    type: str = Field(default="ERROR_MEMORY")

class DMAScore(BaseModel):
    """Score from a single DMA."""
    dma_name: str
    score: float
    confidence: float
    reasoning: Optional[str] = None

class DecisionMemory(GraphNode):
    """A decision made by DMAs stored as a graph memory."""
    decision_id: str = Field(..., description="Unique decision identifier")
    action_chosen: str = Field(..., description="Action that was chosen")
    alternatives: List[str] = Field(..., description="Other options considered")
    dma_scores: List[DMAScore] = Field(..., description="Typed scores from each DMA")
    reasoning: str = Field(..., description="Decision reasoning")
    ethical_principles: List[str] = Field(default_factory=list, description="Principles considered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Graph node type
    type: str = Field(default="DECISION")

@register_node_type("TSDB_SUMMARY")
class TSDBSummary(TypedGraphNode):
    """
    6-hour summary of TSDB metrics for permanent memory.
    
    These summaries are the agent's diary - permanent records of activity
    that enable queries like "what did I do on June 3rd, 2025?"
    """
    # Period information
    period_start: datetime = Field(..., description="Start of 6-hour period (UTC)")
    period_end: datetime = Field(..., description="End of 6-hour period (UTC)")
    period_label: str = Field(..., description="Human-readable period (e.g., '2024-12-22-morning')")
    
    # Aggregated metrics - simple stats for each metric
    metrics: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="metric_name -> {count, sum, min, max, avg}"
    )
    
    # Resource totals for accountability
    total_tokens: int = Field(default=0, description="Total tokens used in period")
    total_cost_cents: float = Field(default=0.0, description="Total cost in cents")
    total_carbon_grams: float = Field(default=0.0, description="Total CO2 emissions in grams")
    total_energy_kwh: float = Field(default=0.0, description="Total energy in kilowatt-hours")
    
    # Action summary - what the agent did
    action_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each action type (SPEAK, TOOL, PONDER, etc.)"
    )
    error_count: int = Field(default=0, description="Total errors in period")
    success_rate: float = Field(default=1.0, description="Percentage of successful operations")
    
    # Consolidation metadata
    source_node_count: int = Field(..., description="Number of TSDB nodes consolidated")
    consolidation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data_expired: bool = Field(
        default=False, 
        description="True if raw TSDB nodes have been deleted (>24hr old)"
    )
    
    # Graph node type
    type: NodeType = Field(default=NodeType.TSDB_SUMMARY)
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for storage."""
        # Include both GraphNodeAttributes required fields AND TSDBSummary extra fields
        extra_fields = {
            # Required GraphNodeAttributes fields
            "created_at": self.consolidation_timestamp.isoformat(),
            "updated_at": self.consolidation_timestamp.isoformat(),
            "created_by": "TSDBConsolidationService",
            "tags": [f"period:{self.period_label}", "tsdb_summary"],
            # TSDBSummary specific fields
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_label": self.period_label,
            "metrics": self.metrics,
            "total_tokens": self.total_tokens,
            "total_cost_cents": self.total_cost_cents,
            "total_carbon_grams": self.total_carbon_grams,
            "total_energy_kwh": self.total_energy_kwh,
            "action_counts": self.action_counts,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "source_node_count": self.source_node_count,
            "consolidation_timestamp": self.consolidation_timestamp.isoformat(),
            "raw_data_expired": self.raw_data_expired,
            "_node_class": "TSDBSummary"
        }
        
        return GraphNode(
            id=self.id,
            type=self.type,
            scope=self.scope,
            attributes=extra_fields,
            version=self.version,
            updated_by=self.updated_by or "TSDBConsolidationService",
            updated_at=self.updated_at or self.consolidation_timestamp
        )
    
    @classmethod
    def from_graph_node(cls, node: GraphNode) -> 'TSDBSummary':
        """Reconstruct from GraphNode."""
        attrs = node.attributes if isinstance(node.attributes, dict) else {}
        
        return cls(
            # Base fields from GraphNode
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=node.attributes,  # Must pass this for GraphNode base class
            version=node.version,
            updated_by=node.updated_by,
            updated_at=node.updated_at,
            # Extra fields from attributes
            period_start=cls._deserialize_datetime(attrs["period_start"]),
            period_end=cls._deserialize_datetime(attrs["period_end"]),
            period_label=attrs["period_label"],
            metrics=attrs.get("metrics", {}),
            total_tokens=attrs.get("total_tokens", 0),
            total_cost_cents=attrs.get("total_cost_cents", 0.0),
            total_carbon_grams=attrs.get("total_carbon_grams", 0.0),
            total_energy_kwh=attrs.get("total_energy_kwh", 0.0),
            action_counts=attrs.get("action_counts", {}),
            error_count=attrs.get("error_count", 0),
            success_rate=attrs.get("success_rate", 1.0),
            source_node_count=attrs["source_node_count"],
            consolidation_timestamp=cls._deserialize_datetime(attrs.get("consolidation_timestamp")),
            raw_data_expired=attrs.get("raw_data_expired", False)
        )