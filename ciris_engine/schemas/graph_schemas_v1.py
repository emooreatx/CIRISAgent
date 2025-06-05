from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class GraphScope(str, Enum):
    LOCAL = "local"
    IDENTITY = "identity"
    ENVIRONMENT = "environment"
    COMMUNITY = "community"
    NETWORK = "network"


class NodeType(str, Enum):
    AGENT = "agent"
    USER = "user"
    CHANNEL = "channel"
    CONCEPT = "concept"


class GraphNode(BaseModel):
    """Minimal node for v1"""

    id: str
    type: NodeType
    scope: GraphScope
    attributes: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    updated_by: Optional[str] = None  # WA feedback tracking
    updated_at: Optional[str] = None


class GraphEdge(BaseModel):
    """Minimal edge for v1"""

    source: str
    target: str
    relationship: str
    scope: GraphScope
    weight: float = 1.0
    attributes: Dict[str, Any] = Field(default_factory=dict)