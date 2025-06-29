"""
Contract-driven architecture schemas.

This module provides typed replacements for all Dict[str, Any] usage
in the CIRIS codebase, ensuring type safety and validation throughout.
"""

# Re-export all schemas for convenience

from .services.metadata import ServiceMetadata
from .services.requests import (
    ServiceRequest,
    ServiceResponse,
    MemorizeRequest,
    MemorizeResponse,
    RecallRequest,
    RecallResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    LLMRequest,
    LLMResponse,
    AuditRequest,
    AuditResponse,
)

from .handlers.contexts import (
    BaseActionContext,
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
)

from .actions import (
    SpeakParams as SpeakParameters,
    ToolParams as ToolParameters,
    ObserveParams as ObserveParameters,
    MemorizeParams as MemorizeParameters,
    RecallParams as RecallParameters,
    ForgetParams as ForgetParameters,
    RejectParams as RejectParameters,
    PonderParams as PonderParameters,
    DeferParams as DeferParameters,
    TaskCompleteParams as TaskCompleteParameters,
)

from .processors.cognitive import (
    WakeupState,
    WorkState,
    PlayState,
    SolitudeState,
    DreamState,
    ShutdownState,
)

from .dma.decisions import (
    PDMADecision,
    CSDMADecision,
    DSDMADecision,
    ActionSelectionDecision,
)

from .handlers.schemas import (
    HandlerContext,
    HandlerResult,
    ActionContext,
    ActionParameters,
)

# Faculty assessments removed - merged into consciences

# ConscienceResult import removed - module doesn't exist

__all__ = [
    # Service schemas
    "ServiceMetadata",
    "ServiceRequest",
    "ServiceResponse",
    "MemorizeRequest",
    "MemorizeResponse",
    "RecallRequest",
    "RecallResponse",
    "ToolExecutionRequest",
    "ToolExecutionResponse",
    "LLMRequest",
    "LLMResponse",
    "AuditRequest",
    "AuditResponse",
    # Action contexts
    "BaseActionContext",
    "SpeakContext",
    "ToolContext",
    "ObserveContext",
    "MemorizeContext",
    "RecallContext",
    "ForgetContext",
    "RejectContext",
    "PonderContext",
    "DeferContext",
    "TaskCompleteContext",
    # Action parameters
    "SpeakParameters",
    "ToolParameters",
    "ObserveParameters",
    "MemorizeParameters",
    "RecallParameters",
    "ForgetParameters",
    "RejectParameters",
    "PonderParameters",
    "DeferParameters",
    "TaskCompleteParameters",
    # Cognitive states
    "WakeupState",
    "WorkState",
    "PlayState",
    "SolitudeState",
    "DreamState",
    "ShutdownState",
    # DMA decisions
    "PDMADecision",
    "CSDMADecision",
    "DSDMADecision",
    "ActionSelectionDecision",
    # Handler schemas
    "HandlerContext",
    "HandlerResult",
    "ActionContext",
    "ActionParameters",
    # conscience results
    "ConscienceResult",
]
