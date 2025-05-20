from pydantic import BaseModel
from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

from .foundational_schemas import (
    CIRISSchemaVersion,
    CIRISAgentUAL,
    CIRISTaskUAL,
    CIRISKnowledgeAssetUAL,
    VeilidDID,
)


class AuditLogEntry(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    event_id: str
    event_timestamp: str
    event_type: str
    originator_id: Union[CIRISAgentUAL, VeilidDID]
    target_id: Optional[Union[CIRISAgentUAL, VeilidDID, CIRISTaskUAL, CIRISKnowledgeAssetUAL]] = None
    event_summary: str
    event_payload_schema_ual: Optional[CIRISKnowledgeAssetUAL] = None
    event_payload: Optional[Any] = None
    dkg_assertion_link: Optional[CIRISKnowledgeAssetUAL] = None
