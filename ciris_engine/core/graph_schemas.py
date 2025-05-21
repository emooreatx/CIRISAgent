from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from .foundational_schemas import (
    CIRISSchemaVersion,
    CIRISAgentUAL,
)


class GraphScope(str, Enum):
    LOCAL = "local"
    IDENTITY = "identity"
    ENVIRONMENT = "environment"


class NodeType(str, Enum):
    AGENT = "agent"
    USER = "user"
    CHANNEL = "channel"
    TASK = "task"
    KNOWLEDGE_ASSET = "knowledge_asset"
    EXTERNAL_ENTITY = "external_entity"


class EdgeLabel(str, Enum):
    PARTICIPATES_IN = "participates_in"
    ASSOCIATED_WITH = "associated_with"
    PRODUCES = "produces"
    DERIVED_FROM = "derived_from"


class GraphNode(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    id: str
    ual: Optional[str] = None
    type: NodeType
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    source: str
    target: str
    label: EdgeLabel
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)


class GraphUpdateEvent(BaseModel):
    node: Optional[GraphNode] = None
    edge: Optional[GraphEdge] = None
    actor: CIRISAgentUAL
    rationale: Optional[str] = None
