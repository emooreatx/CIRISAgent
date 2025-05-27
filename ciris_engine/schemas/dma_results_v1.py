# --- v1 DMA Results Schemas ---
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from .action_params_v1 import *
from .foundational_schemas_v1 import HandlerActionType

class ActionSelectionResult(BaseModel):
    """Minimal v1 result from action selection DMA."""
    selected_action: HandlerActionType
    action_parameters: Dict[str, Any]
    rationale: str
    confidence: Optional[float] = None
    raw_llm_response: Optional[str] = None

class EthicalDMAResult(BaseModel):
    """Minimal v1 result from ethical DMA."""
    alignment_check: Dict[str, Any]
    decision: str
    rationale: Optional[str] = None
    raw_llm_response: Optional[str] = None

class CSDMAResult(BaseModel):
    """Minimal v1 result from common sense DMA."""
    plausibility_score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    raw_llm_response: Optional[str] = None

class DSDMAResult(BaseModel):
    """Minimal v1 result from domain-specific DMA."""
    domain: str
    alignment_score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    recommended_action: Optional[str] = None
    raw_llm_response: Optional[str] = None

