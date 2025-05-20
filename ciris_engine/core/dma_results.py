from typing import Union, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

from .foundational_schemas import CIRISSchemaVersion, HandlerActionType
from .action_params import (
    ObserveParams,
    SpeakParams,
    ActParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RememberParams,
    ForgetParams,
)


class ActionSelectionPDMAResult(BaseModel):
    """Structured result from the Action Selection PDMA evaluation."""

    schema_version: CIRISSchemaVersion = Field(default=CIRISSchemaVersion.V1_0_BETA)
    context_summary_for_action_selection: str
    action_alignment_check: Dict[str, Any]
    action_conflicts: Optional[str] = None
    action_resolution: Optional[str] = None
    selected_handler_action: HandlerActionType
    action_parameters: Union[
        ObserveParams,
        SpeakParams,
        ActParams,
        PonderParams,
        RejectParams,
        DeferParams,
        MemorizeParams,
        RememberParams,
        ForgetParams,
        Dict[str, Any],
    ]
    action_selection_rationale: str
    monitoring_for_selected_action: Union[Dict[str, Union[str, List[str], int]], str]
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    raw_llm_response: Optional[str] = None
    ethical_assessment_summary: Optional[Dict[str, Any]] = None
    csdma_assessment_summary: Optional[Dict[str, Any]] = None
    dsdma_assessment_summary: Optional[Dict[str, Any]] = None
    decision_input_context_snapshot: Optional[Dict[str, Any]] = None # Added field for context snapshot

    class Config:
        populate_by_name = True


class EthicalPDMAResult(BaseModel):
    """Structured result from the Ethical PDMA evaluation."""

    context: str = Field(..., alias="Context")
    alignment_check: Dict[str, Any] = Field(..., alias="Alignment-Check")
    conflicts: Optional[str] = Field(None, alias="Conflicts")
    resolution: Optional[str] = Field(None, alias="Resolution")
    decision: str = Field(..., alias="Decision")
    monitoring: Union[Dict[str, str], str] = Field(..., alias="Monitoring")
    raw_llm_response: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


class CSDMAResult(BaseModel):
    """Structured result from the Common Sense DMA (CSDMA) evaluation."""

    common_sense_plausibility_score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(...)
    reasoning: str
    raw_llm_response: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


class DSDMAResult(BaseModel):
    """Structured result from the Domain Specific DMA (DSDMA) evaluation."""

    domain_name: str
    domain_alignment_score: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = Field(...)
    reasoning: str
    recommended_action: Optional[str] = Field(None)
    domain_specific_output: Optional[Dict[str, Any]] = Field(None)
    raw_llm_response: Optional[str] = Field(None)

    class Config:
        populate_by_name = True
