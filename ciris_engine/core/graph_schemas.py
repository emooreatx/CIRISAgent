from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from .foundational_schemas import (
    CIRISSchemaVersion,
    CIRISAgentUAL,
)

class GraphScope(str, Enum):
    LOCAL = "task specific"            # users / channels
    IDENTITY = "identity"      # agent’s self-model (WA-gated)
    ENVIRONMENT = "environment"  # external, OriginTrail-mirrored

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
    id: str                                 # e.g. "User:1234"
    ual: Optional[str] = None               # optional global ID
    type: NodeType
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    source: str                             # node.id
    target: str
    label: EdgeLabel
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)

class GraphUpdateEvent(BaseModel):
    node: Optional[GraphNode] = None
    edge: Optional[GraphEdge] = None
    actor: CIRISAgentUAL                    # requester
    rationale: Optional[str] = None         # mandatory for IDENTITY writes

class MemoryActionType(str, Enum):
    MEMORIZE = "memorize"
    REMEMBER = "remember"
    FORGET = "forget"

class MemoryAction(BaseModel):
    """Generic message the MemoryHandler sends to the graph backend."""

    action: MemoryActionType
    scope: GraphScope
    payload: Optional[GraphUpdateEvent] = None
    query: Optional[str] = None
    actor: CIRISAgentUAL
