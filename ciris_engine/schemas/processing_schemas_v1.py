from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult

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
