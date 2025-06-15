from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from .graph_schemas_v1 import GraphScope, GraphNode

class ObserveParams(BaseModel):
    channel_id: Optional[str] = None
    active: bool = False
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def __init__(self, **data: Any) -> None:
        if 'context' not in data or data['context'] is None:
            data['context'] = {}
        super().__init__(**data)

class SpeakParams(BaseModel):
    channel_id: Optional[str] = None
    content: str

    model_config = ConfigDict(extra="forbid")

class ToolParams(BaseModel):
    name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

class PonderParams(BaseModel):
    questions: List[str]

    model_config = ConfigDict(extra="forbid")

class RejectParams(BaseModel):
    reason: str
    create_filter: bool = Field(default=False, description="Whether to create an adaptive filter to prevent similar requests")
    filter_pattern: Optional[str] = Field(default=None, description="Pattern to filter (regex or keywords)")
    filter_type: Optional[str] = Field(default="regex", description="Type of filter: regex, semantic, keyword")
    filter_priority: Optional[str] = Field(default="high", description="Priority level: critical, high, medium")

    model_config = ConfigDict(extra="forbid")

class DeferParams(BaseModel):
    reason: str
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
    reason: str
    no_audit: bool = False

    model_config = ConfigDict(extra="forbid")

    @property
    def scope(self) -> GraphScope:
        return self.node.scope

class TaskCompleteParams(BaseModel):
    """Parameters for TASK_COMPLETE action - mission-critical schema compliance."""
    
    completion_reason: str = "Task completed successfully"
    context: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(extra="forbid")
