"""
Handler schemas for contract-driven architecture.

Replaces Dict[str, Any] in handler contexts and results.
"""

from typing import (
    Dict,
    Optional,
    Union
)
from pydantic import BaseModel, Field, ConfigDict

from .contexts import (
    SpeakContext, ToolContext, ObserveContext,
    MemorizeContext, RecallContext, ForgetContext,
    RejectContext, PonderContext, DeferContext,
    TaskCompleteContext
)
from ..actions import (
    SpeakParams as SpeakParameters,
    ToolParams as ToolParameters,
    ObserveParams as ObserveParameters,
    MemorizeParams as MemorizeParameters,
    RecallParams as RecallParameters,
    ForgetParams as ForgetParameters,
    RejectParams as RejectParameters,
    PonderParams as PonderParameters,
    DeferParams as DeferParameters,
    TaskCompleteParams as TaskCompleteParameters
)
from ..services.metadata import ServiceMetadata

# Union types for contexts and parameters
ActionContext = Union[
    SpeakContext,
    ToolContext,
    ObserveContext,
    MemorizeContext,
    RecallContext,
    ForgetContext,
    RejectContext,
    PonderContext,
    DeferContext,
    TaskCompleteContext,
]

ActionParameters = Union[
    SpeakParameters,
    ToolParameters,
    ObserveParameters,
    MemorizeParameters,
    RecallParameters,
    ForgetParameters,
    RejectParameters,
    PonderParameters,
    DeferParameters,
    TaskCompleteParameters,
]

class HandlerContext(BaseModel):
    """Typed context for all handlers."""
    action_type: str = Field(..., description="Type of action being handled")
    action_context: ActionContext = Field(..., description="Action-specific context")
    action_parameters: ActionParameters = Field(..., description="Action-specific parameters")
    metadata: ServiceMetadata = Field(..., description="Service metadata")

    model_config = ConfigDict(extra = "forbid")

class HandlerResult(BaseModel):
    """Typed result from all handlers."""
    success: bool = Field(..., description="Whether the handler succeeded")
    message: Optional[str] = Field(None, description="Result message")
    data: Optional[Dict[str, Union[str, int, float, bool, list]]] = Field(
        None, description="Additional result data"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(extra = "forbid")
