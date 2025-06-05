from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from .graph_schemas_v1 import GraphScope, GraphNode

class ObserveParams(BaseModel):
    channel_id: Optional[str] = None
    active: GraphNode = False
    context: GraphNode = Field(default_factory=GraphNode)

    model_config = ConfigDict(extra="forbid")

    def __init__(self, **data: Any) -> None:
        if 'context' not in data or data['context'] is None:
            data['context'] = {}
        super().__init__(**data)

class SpeakParams(BaseModel):
    channel_id: Optional[str] = None
    content: GraphNode

    model_config = ConfigDict(extra="forbid")

class ToolParams(BaseModel):
    name: GraphNode
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

class PonderParams(BaseModel):
    questions: List[str]

    model_config = ConfigDict(extra="forbid")

class RejectParams(BaseModel):
    reason: GraphNode

    model_config = ConfigDict(extra="forbid")

class DeferParams(BaseModel):
    reason: GraphNode
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

class MemorizeParams(BaseModel):
    """Parameters for MEMORIZE action."""

    node: GraphNode

    model_config = ConfigDict(extra="forbid")

    @property
    def scope(self) -> GraphScope:
        return self.node.scope

class RecallParams(BaseModel):
    """Parameters for RECALL action."""

    node: GraphNode

    model_config = ConfigDict(extra="forbid")

    @property
    def scope(self) -> GraphScope:
        return self.node.scope

class ForgetParams(BaseModel):
    """Parameters for FORGET action."""

    node: GraphNode
    reason: GraphNode

    model_config = ConfigDict(extra="forbid")

    @property
    def scope(self) -> GraphScope:
        return self.node.scope
