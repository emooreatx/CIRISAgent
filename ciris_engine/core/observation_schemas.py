from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from .foundational_schemas import (
    CIRISSchemaVersion,
    ObservationSourceType,
    CIRISKnowledgeAssetUAL,
)


class ObservationRecord(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    observation_id: str
    timestamp: str
    source_type: ObservationSourceType
    source_identifier: Optional[str] = None
    data_schema_ual: Optional[CIRISKnowledgeAssetUAL] = None
    data_payload: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None
