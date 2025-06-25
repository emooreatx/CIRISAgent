"""
DMA result schemas for typed decision outputs.

Provides type-safe results from each Decision Making Algorithm.
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ..runtime.enums import HandlerActionType
from ..actions.parameters import (
    ObserveParams, SpeakParams, ToolParams, PonderParams, RejectParams,
    DeferParams, MemorizeParams, RecallParams, ForgetParams, TaskCompleteParams
)

class EthicalDMAResult(BaseModel):
    """Result from Principled Decision Making Algorithm (PDMA)."""
    decision: str = Field(..., description="Decision: approve, reject, defer, caution")
    reasoning: str = Field(..., description="Ethical reasoning")
    alignment_check: Dict[str, Any] = Field(..., description="Alignment check results")
    
    class Config:
        extra = "forbid"

class CSDMAResult(BaseModel):
    """Result from Common Sense Decision Making Algorithm."""
    plausibility_score: float = Field(..., ge=0.0, le=1.0, description="Plausibility rating")
    flags: List[str] = Field(default_factory=list, description="Common sense flags raised")
    reasoning: str = Field(..., description="Common sense reasoning")
    
    class Config:
        extra = "forbid"

class DSDMAResult(BaseModel):
    """Result from Domain Specific Decision Making Algorithm."""
    domain: str = Field(..., description="Primary domain of expertise")
    domain_alignment: float = Field(..., ge=0.0, le=1.0, description="How well aligned with domain")
    flags: List[str] = Field(default_factory=list, description="Domain-specific flags")
    reasoning: str = Field(..., description="Domain-specific reasoning")
    
    class Config:
        extra = "forbid"

class ActionSelectionDMAResult(BaseModel):
    """Result from Action Selection DMA - the meta-decision maker."""
    # Core fields matching handler expectations
    selected_action: HandlerActionType = Field(..., description="The chosen handler action")
    action_parameters: Union[
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
    ] = Field(..., description="Parameters for the selected action")
    rationale: str = Field(..., description="Reasoning for this action selection")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence in selection")
    
    # LLM metadata
    raw_llm_response: Optional[str] = Field(None, description="Raw LLM response")
    
    # Processing metadata
    reasoning: Optional[str] = Field(None, description="Detailed reasoning process")
    evaluation_time_ms: Optional[float] = Field(None, description="Time taken for evaluation")
    resource_usage: Optional[Dict[str, Any]] = Field(None, description="Resource usage details")
    
    class Config:
        extra = "forbid"


__all__ = [
    "EthicalDMAResult",
    "CSDMAResult", 
    "DSDMAResult",
    "ActionSelectionDMAResult"
]