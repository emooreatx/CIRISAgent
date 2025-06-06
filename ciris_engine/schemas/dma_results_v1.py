from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from .action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RecallParams,
    ForgetParams,
)
from .foundational_schemas_v1 import HandlerActionType, ResourceUsage

class ActionSelectionResult(BaseModel):
    """Minimal v1 result from action selection DMA."""
    selected_action: HandlerActionType
    action_parameters: Union[
        Dict[str, Any],
        ObserveParams,
        SpeakParams,
        ToolParams,
        PonderParams,
        RejectParams,
        DeferParams,
        MemorizeParams,
        RecallParams,
        ForgetParams,
    ]
    rationale: str  # <- Fixed: should be string
    confidence: Optional[float] = None
    raw_llm_response: Optional[str] = None
    resource_usage: Optional[ResourceUsage] = None

    @property
    def typed_parameters(
        self,
    ) -> Union[
        ObserveParams,
        SpeakParams,
        ToolParams,
        PonderParams,
        RejectParams,
        DeferParams,
        MemorizeParams,
        RecallParams,
        ForgetParams,
        Dict[str, Any],
    ]:
        """Return action_parameters cast to the appropriate params model."""
        if isinstance(self.action_parameters, BaseModel):
            return self.action_parameters

        param_map = {
            HandlerActionType.OBSERVE: ObserveParams,
            HandlerActionType.SPEAK: SpeakParams,
            HandlerActionType.TOOL: ToolParams,
            HandlerActionType.PONDER: PonderParams,
            HandlerActionType.REJECT: RejectParams,
            HandlerActionType.DEFER: DeferParams,
            HandlerActionType.MEMORIZE: MemorizeParams,
            HandlerActionType.RECALL: RecallParams,
            HandlerActionType.FORGET: ForgetParams,
        }

        param_class = param_map.get(self.selected_action)
        if param_class and isinstance(self.action_parameters, dict):
            try:
                result = param_class(**self.action_parameters)
                return result  # type: ignore[no-any-return]
            except Exception:
                pass
        return self.action_parameters

class EthicalDMAResult(BaseModel):
    """Minimal v1 result from ethical DMA."""
    alignment_check: Dict[str, Any]
    decision: str  # <- Fixed
    rationale: Optional[str] = None
    raw_llm_response: Optional[str] = None
    resource_usage: Optional[ResourceUsage] = None

class CSDMAResult(BaseModel):
    """Minimal v1 result from common sense DMA."""
    plausibility_score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    raw_llm_response: Optional[str] = None
    resource_usage: Optional[ResourceUsage] = None

class DSDMAResult(BaseModel):
    """Minimal v1 result from domain-specific DMA."""
    domain: str
    score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    recommended_action: Optional[str] = None
    raw_llm_response: Optional[str] = None
    resource_usage: Optional[ResourceUsage] = None

