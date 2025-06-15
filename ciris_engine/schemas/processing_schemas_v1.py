from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import (
    ObserveParams, SpeakParams, ToolParams, PonderParams, RejectParams,
    DeferParams, MemorizeParams, RecallParams, ForgetParams, TaskCompleteParams
)

class DMAResults(BaseModel):
    """Container for DMA evaluation results."""
    ethical_pdma: Optional[EthicalDMAResult] = None
    csdma: Optional[CSDMAResult] = None
    dsdma: Optional[DSDMAResult] = None
    errors: List[str] = Field(default_factory=list)
    
class GuardrailResult(BaseModel):
    """Result from guardrail application."""
    original_action: ActionSelectionResult
    final_action: ActionSelectionResult
    overridden: bool = False
    override_reason: Optional[str] = None
    epistemic_data: Optional[Dict[str, Any]] = None


class ProcessedThoughtResult(BaseModel):
    """Result from thought processor containing both action and guardrail data."""
    action_result: ActionSelectionResult
    guardrail_result: Optional[GuardrailResult] = None
    
    @property
    def selected_action(self) -> HandlerActionType:
        """Convenience property for compatibility."""
        return self.action_result.selected_action
    
    @property
    def action_parameters(self) -> Union[
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
        TaskCompleteParams,
    ]:
        """Convenience property for compatibility."""
        return self.action_result.action_parameters
    
    @property
    def rationale(self) -> str:
        """Convenience property for compatibility."""
        return self.action_result.rationale
