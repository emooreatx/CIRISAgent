from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Optional

from .foundational_schemas import (
    CIRISSchemaVersion,
    HandlerActionType,
    TaskStatus,
    ThoughtStatus,
    ObservationSourceType,
    CIRISAgentUAL,
    CIRISTaskUAL,
    CIRISKnowledgeAssetUAL,
    VeilidDID,
    # DKGAssetType is not directly used in this file's classes but might be relevant for context
    # VeilidRouteID is not used in this file's classes
)

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

from .dma_results import (
    ActionSelectionPDMAResult,
    EthicalPDMAResult,
    CSDMAResult,
    DSDMAResult,
)

# --- Core Task and Thought Objects ---

class Task(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    task_id: str # Unique identifier (e.g., UUID)
    task_ual: Optional[CIRISTaskUAL] = None # UAL if represented as KA on DKG
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: str # ISO8601 timestamp
    updated_at: str # ISO8601 timestamp
    due_date: Optional[str] = None # ISO8601 timestamp, Added based on user feedback
    assigned_agent_ual: Optional[CIRISAgentUAL] = None
    originator_id: Optional[str] = None # UAL or DID of the entity that created the task
    parent_goal_id: Optional[str] = None # Added based on user feedback
    parameters: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = {} # Holds initial input, environment details etc.
    outcome: Optional[Dict[str, Any]] = None # Result upon completion/failure
    dependencies: Optional[List[CIRISTaskUAL]] = None # UALs of prerequisite tasks

class Thought(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    thought_id: str # Unique identifier
    source_task_id: str # Link back to the parent Task
    thought_type: str = "seed_task_thought" # e.g., "seed_task_thought", "ponder_thought", "metathought"
    status: ThoughtStatus = ThoughtStatus.PENDING
    created_at: str # ISO8601 timestamp
    updated_at: str # ISO8601 timestamp
    round_created: int # Added based on user feedback
    round_processed: Optional[int] = None # Added based on user feedback
    priority: int = 0 # Added based on user feedback (from old Thought model)
    content: str # The core text/data being processed
    processing_context: Dict[str, Any] = {} # Context inherited/added during processing (DKG enrichments etc.)
    depth: int = 0 # Metathought depth tracking (0 for seed)
    ponder_count: int = 0
    ponder_notes: Optional[List[str]] = None # Stores key_questions from Ponder action
    related_thought_id: Optional[str] = None # Link to parent thought if spawned (metathoughts)
    final_action_result: Optional[ActionSelectionPDMAResult] = None # Stores the outcome

# --- Epistemic Faculty Schemas ---

class EntropyResult(BaseModel):
    entropy: float = Field(..., ge=0.0, le=1.0, description="Entropy value (0.00 = ordered/plain, 1.00 = chaotic/gibberish)")

class CoherenceResult(BaseModel):
    coherence: float = Field(..., ge=0.0, le=1.0, description="Coherence value (0.00 = clearly foreign/harmful, 1.00 = unmistakably CIRIS-aligned)")

# --- DMA Schemas ---


# --- Observation Record ---

class ObservationRecord(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    observation_id: str # Unique identifier
    timestamp: str # ISO8601 timestamp when observation was made/received
    source_type: ObservationSourceType
    source_identifier: Optional[str] = None # e.g., Discord message ID, Sensor ID, Agent UAL/DID
    data_schema_ual: Optional[CIRISKnowledgeAssetUAL] = None # UAL pointing to the schema of the data payload
    data_payload: Any # The actual observed data (structure depends on source_type/data_schema_ual)
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None # Additional context

# --- Audit Log Entry ---
class AuditLogEntry(BaseModel):
    schema_version: CIRISSchemaVersion = CIRISSchemaVersion.V1_0_BETA
    event_id: str # Unique ID for this specific log entry (e.g., UUID)
    event_timestamp: str # ISO8601 timestamp with high precision
    event_type: str # e.g., "ActionExecuted", "MessageSent", "DKGQueryPerformed", "Error"
    originator_id: Union[CIRISAgentUAL, VeilidDID] # ID of the entity generating the event
    target_id: Optional[Union[CIRISAgentUAL, VeilidDID, CIRISTaskUAL, CIRISKnowledgeAssetUAL]] = None # ID of the target, if any
    event_summary: str # Concise summary
    event_payload_schema_ual: Optional[CIRISKnowledgeAssetUAL] = None # Schema for the payload
    event_payload: Optional[Any] = None # Detailed data, potentially serialized or a reference
    dkg_assertion_link: Optional[CIRISKnowledgeAssetUAL] = None # Link if event corresponds to a KA assertion
    # Signature will be added externally during the logging process before batching
