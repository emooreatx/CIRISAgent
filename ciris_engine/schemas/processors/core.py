"""
Processing schemas for thought and DMA evaluation.

Provides type-safe structures for thought processing results.
"""
from typing import (
    Dict,
    List,
    Optional,
    Type,
    Union
)
from pydantic import BaseModel, Field

from ..dma.results import EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionDMAResult
from ciris_engine.schemas.runtime.enums import HandlerActionType
from pydantic import Field
from ..actions.parameters import (
    ObserveParams, SpeakParams, ToolParams, PonderParams, RejectParams,
    DeferParams, MemorizeParams, RecallParams, ForgetParams, TaskCompleteParams
)

class DMAResults(BaseModel):
    """Container for DMA evaluation results."""
    ethical_pdma: Optional[EthicalDMAResult] = Field(None, description="Ethical evaluation")
    csdma: Optional[CSDMAResult] = Field(None, description="Common sense evaluation")
    dsdma: Optional[DSDMAResult] = Field(None, description="Domain-specific evaluation")
    errors: List[str] = Field(default_factory=list, description="Errors during evaluation")
    
    class Config:
        extra = "forbid"

class ConscienceResult(BaseModel):
    """Result from conscience application."""
    original_action: ActionSelectionDMAResult = Field(..., description="Original action selected")
    final_action: ActionSelectionDMAResult = Field(..., description="Final action after consciences")
    overridden: bool = Field(False, description="Whether action was overridden")
    override_reason: Optional[str] = Field(None, description="Reason for override")
    epistemic_data: Dict[str, str] = Field(default_factory=dict, description="Epistemic faculty data")
    
    class Config:
        extra = "forbid"

class ProcessedThoughtResult(BaseModel):
    """Result from thought processor containing both action and conscience data."""
    action_result: ActionSelectionDMAResult = Field(..., description="Action selection result")
    conscience_result: Optional[ConscienceResult] = Field(None, description="conscience application result")
    
    @property
    def selected_action(self) -> HandlerActionType:
        """Convenience property for compatibility."""
        return self.action_result.selected_action
    
    @property
    def action_parameters(self) -> Union[
        ObserveParams,
        SpeakParams,
        ToolParams,
        PonderParams,
        RejectParams,
        DeferParams,
        MemorizeParams,
        RecallParams,
        ForgetParams,
        TaskCompleteParams,
    ]:
        """Convenience property for compatibility."""
        return self.action_result.action_parameters
    
    class Config:
        extra = "forbid"

class ThoughtProcessingMetrics(BaseModel):
    """Metrics for thought processing."""
    processing_time_ms: float = Field(..., description="Total processing time")
    dma_time_ms: float = Field(..., description="DMA evaluation time")
    conscience_time_ms: float = Field(..., description="conscience application time")
    llm_calls: int = Field(..., description="Number of LLM calls")
    tokens_used: int = Field(..., description="Total tokens consumed")
    
    class Config:
        extra = "forbid"

class ProcessingError(BaseModel):
    """Error during thought processing."""
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    component: str = Field(..., description="Component that failed")
    recoverable: bool = Field(..., description="Whether error is recoverable")
    
    class Config:
        extra = "forbid"

__all__ = [
    "DMAResults",
    "ConscienceResult",
    "ProcessedThoughtResult",
    "ThoughtProcessingMetrics",
    "ProcessingError"
]