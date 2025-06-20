from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from .foundational_schemas_v1 import CaseInsensitiveEnum
from ciris_engine.schemas.graph_schemas_v1 import NodeType, GraphScope, GraphNode

class MemoryOpStatus(CaseInsensitiveEnum):
    """Status of a memory operation."""
    OK = "ok"
    SUCCESS = "ok"  # Alias for OK
    DEFERRED = "deferred"
    DENIED = "denied"
    PENDING = "pending"
    ERROR = "error"
    FAILED = "error"  # Alias for ERROR

class MemoryOpAction(str, Enum):
    """Memory operation types."""
    MEMORIZE = "memorize"
    RECALL = "recall"
    FORGET = "forget"

class MemoryOpResult(BaseModel):
    """Result of a memory operation."""

    status: MemoryOpStatus
    reason: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None


class MemoryQuery(BaseModel):
    """Query parameters for memory recall operations."""
    
    node_id: str = Field(..., description="Unique identifier of the node to recall")
    scope: GraphScope = Field(..., description="Memory scope (LOCAL, IDENTITY, ENVIRONMENT)")
    type: Optional[NodeType] = Field(None, description="Optional node type filter")
    include_edges: bool = Field(False, description="Whether to include connected edges")
    depth: int = Field(1, description="Graph traversal depth for connected nodes")


class MemoryRecallResult(BaseModel):
    """Result of a memory recall operation."""
    
    nodes: List[GraphNode] = Field(default_factory=list, description="Retrieved graph nodes")
    total_count: int = Field(0, description="Total number of nodes found")
    
    
__all__ = [
    "MemoryOpStatus",
    "MemoryOpAction",
    "MemoryOpResult",
    "MemoryQuery",
    "MemoryRecallResult",
]

