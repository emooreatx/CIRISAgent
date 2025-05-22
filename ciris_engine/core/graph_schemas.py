from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from .foundational_schemas import (
    CIRISSchemaVersion,
    CIRISAgentUAL,
)


class GraphScope(str, Enum):
    LOCAL = "local"
    IDENTITY = "identity"
    ENVIRONMENT = "environment"


class NodeType(str, Enum):
    AGENT = "agent"
    USER = "user"
    CHANNEL = "channel"
    TASK = "task"
    KNOWLEDGE_ASSET = "knowledge_asset"
    EXTERNAL_ENTITY = "external_entity"


class EdgeLabel(str, Enum):
    PARTICIPATES_IN = "participates_in"
    ASSOCIATED_WITH = "associated_with"
    PRODUCES = "produces"
    DERIVED_FROM = "derived_from"


class ValidationState(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    DISPUTED = "disputed"


class EmergencyState(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    REVOKED = "revoked"


class PDMAComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    DEFERRED = "deferred"
    NONCOMPLIANT = "noncompliant"


class ConfidentialityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class GraphNode(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    id: str
    ual: Optional[str] = None
    type: NodeType
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)
    validated_by: Optional[List[str]] = None
    validation_state: ValidationState = ValidationState.PENDING
    consensus_timestamp: Optional[datetime] = None
    version: int = Field(default=1, ge=1)
    previous_versions: Optional[List[str]] = None
    forked_from: Optional[str] = None
    emergency_state: Optional[EmergencyState] = None
    emergency_timestamp: Optional[datetime] = None
    emergency_authorized_by: Optional[str] = None
    pdma_compliance_status: Optional[PDMAComplianceStatus] = None
    wbd_escalation_ref: Optional[str] = None
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.PUBLIC
    access_control_list: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_integrity(self):
        if self.emergency_state is not None and self.emergency_timestamp is None:
            raise ValueError("emergency_timestamp required when emergency_state is set")
        if self.validated_by is not None and self.validation_state is ValidationState.PENDING:
            raise ValueError("validation_state cannot be pending when validated_by provided")
        return self


class GraphEdge(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    source: str
    target: str
    label: EdgeLabel
    scope: GraphScope
    attrs: Dict[str, Any] = Field(default_factory=dict)
    validated_by: Optional[List[str]] = None
    validation_state: ValidationState = ValidationState.PENDING
    consensus_timestamp: Optional[datetime] = None
    version: int = Field(default=1, ge=1)
    previous_versions: Optional[List[str]] = None
    forked_from: Optional[str] = None
    emergency_state: Optional[EmergencyState] = None
    emergency_timestamp: Optional[datetime] = None
    emergency_authorized_by: Optional[str] = None
    pdma_compliance_status: Optional[PDMAComplianceStatus] = None
    wbd_escalation_ref: Optional[str] = None
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.PUBLIC
    access_control_list: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_integrity(self):
        if self.emergency_state is not None and self.emergency_timestamp is None:
            raise ValueError("emergency_timestamp required when emergency_state is set")
        if self.validated_by is not None and self.validation_state is ValidationState.PENDING:
            raise ValueError("validation_state cannot be pending when validated_by provided")
        return self


class GraphUpdateEvent(BaseModel):
    node: Optional[GraphNode] = None
    edge: Optional[GraphEdge] = None
    actor: CIRISAgentUAL
    rationale: Optional[str] = None
