from typing import Union, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

from .foundational_schemas import (
    ObservationSourceType,
    CIRISKnowledgeAssetUAL,
    VeilidDID,
)


class ObserveParams(BaseModel):
    sources: List[str]
    filters: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    perform_active_look: bool = False


class SpeakParams(BaseModel):
    content: str
    target_channel: Optional[str] = None
    target_agent_did: Optional[VeilidDID] = None
    modality: Optional[str] = None
    correlation_id: Optional[str] = None


class ActParams(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


class PonderParams(BaseModel):
    key_questions: List[str]
    focus_areas: Optional[List[str]] = None
    max_ponder_rounds: Optional[int] = None


class RejectParams(BaseModel):
    reason: str
    rejection_code: Optional[str] = None


class DeferParams(BaseModel):
    reason: str
    target_wa_ual: CIRISKnowledgeAssetUAL
    deferral_package_content: Dict[str, Any]


class MemorizeParams(BaseModel):
    knowledge_unit_description: str
    knowledge_data: Union[Dict[str, Any], str]
    knowledge_type: str
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    publish_to_dkg: bool = False
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None
    channel_metadata: Optional[Dict[str, Any]] = None


class RememberParams(BaseModel):
    query: str
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None
    max_results: int = 1


class ForgetParams(BaseModel):
    item_description: Optional[str] = None
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None
    reason: str
