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
    CONFIG = "config"

class ConfigNodeType(str, Enum):
    """Types of configuration nodes with scope requirements"""

    # LOCAL scope
    FILTER_CONFIG = "filter_config"
    CHANNEL_CONFIG = "channel_config"
    USER_TRACKING = "user_tracking"
    RESPONSE_TEMPLATES = "response_templates"
    TOOL_PREFERENCES = "tool_preferences"

    # IDENTITY scope (requires WA approval)
    BEHAVIOR_CONFIG = "behavior_config"
    ETHICAL_BOUNDARIES = "ethical_boundaries"
    CAPABILITY_LIMITS = "capability_limits"
    TRUST_PARAMETERS = "trust_parameters"
    LEARNING_RULES = "learning_rules"

CONFIG_SCOPE_MAP = {
    ConfigNodeType.FILTER_CONFIG: GraphScope.LOCAL,
    ConfigNodeType.CHANNEL_CONFIG: GraphScope.LOCAL,
    ConfigNodeType.USER_TRACKING: GraphScope.LOCAL,
    ConfigNodeType.RESPONSE_TEMPLATES: GraphScope.LOCAL,
    ConfigNodeType.TOOL_PREFERENCES: GraphScope.LOCAL,
    ConfigNodeType.BEHAVIOR_CONFIG: GraphScope.IDENTITY,
    ConfigNodeType.ETHICAL_BOUNDARIES: GraphScope.IDENTITY,
    ConfigNodeType.CAPABILITY_LIMITS: GraphScope.IDENTITY,
    ConfigNodeType.TRUST_PARAMETERS: GraphScope.IDENTITY,
    ConfigNodeType.LEARNING_RULES: GraphScope.IDENTITY,
}


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
