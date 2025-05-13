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
    VeilidDID
    # DKGAssetType is not directly used in this file's classes but might be relevant for context
    # VeilidRouteID is not used in this file's classes
)

# --- Parameters for each HandlerActionType ---
# Using discriminated unions implicitly via Optional fields or explicit Union types

class ObserveParams(BaseModel):
    sources: List[ObservationSourceType]
    filters: Optional[Dict[str, Any]] = None # e.g., {"channel_id": "123", "keyword": "urgent"}
    max_duration_ms: Optional[int] = None
    reason: Optional[str] = None # Added for fallback/error context

class SpeakParams(BaseModel):
    content: str
    target_channel: Optional[str] = None # e.g., Discord channel ID
    target_agent_did: Optional[VeilidDID] = None
    modality: str = "text" # Could be "audio", "visual" later
    correlation_id: Optional[str] = None # To link response to request

class ToolParams(BaseModel):
    tool_name: str # Name of the tool/function to call (aligns with LLM tool calling)
    arguments: Dict[str, Any] # Arguments for the tool

class PonderParams(BaseModel):
    key_questions: List[str]
    focus_areas: Optional[List[str]] = None
    max_ponder_rounds: Optional[int] = None # Override default if needed

class RejectParams(BaseModel):
    reason: str # Explanation for rejection
    rejection_code: Optional[str] = None # Standardized code

class DeferParams(BaseModel):
    reason: str # Explanation for deferral
    target_wa_ual: CIRISKnowledgeAssetUAL # UAL of the designated Wise Authority KA
    deferral_package_content: Dict[str, Any] # Context, dilemma, analysis (to be structured)

class LearnParams(BaseModel):
    knowledge_unit_description: str
    knowledge_data: Union[Dict[str, Any], str] # The actual knowledge (structured or unstructured)
    knowledge_type: str # e.g., "heuristic", "fact", "skill_model_update"
    source: str # Where the knowledge came from (e.g., "observation_id", "metathought_id")
    confidence: float = Field(..., ge=0.0, le=1.0)
    publish_to_dkg: bool = False # Whether to attempt creating/updating a KA
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None # If updating existing KA

class RememberParams(BaseModel):
    query: str # Natural language or structured query for memory
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None # Specific KA to retrieve
    max_results: int = 1

class ForgetParams(BaseModel):
    item_description: Optional[str] = None # Description of memory item
    target_ka_ual: Optional[CIRISKnowledgeAssetUAL] = None # Specific KA to target
    reason: str

# --- Action Selection Result ---

class ActionSelectionPDMAResult(BaseModel):
    """Structured result from the Action Selection PDMA evaluation."""
    schema_version: CIRISSchemaVersion = Field(default=CIRISSchemaVersion.V1_0_BETA)
    context_summary_for_action_selection: str
    action_alignment_check: Dict[str, Any]
    action_conflicts: Optional[str] = None
    action_resolution: Optional[str] = None
    selected_handler_action: HandlerActionType
    action_parameters: Union[ # This will hold the specific Pydantic model for the action's params
        ObserveParams, SpeakParams, ToolParams, PonderParams,
        RejectParams, DeferParams, LearnParams, RememberParams, ForgetParams, Dict[str, Any] # Allow Dict for initial parsing
    ]
    action_selection_rationale: str
    monitoring_for_selected_action: Union[Dict[str, Union[str, List[str]]], str] # Allow list of strings for KPIs
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0) # Made optional
    raw_llm_response: Optional[str] = None
    # The following fields are for system use, not directly set by ActionSelectionPDMAEvaluator LLM call
    # but can be populated by the system after receiving the result.
    ethical_assessment_summary: Optional[Dict[str, Any]] = None
    csdma_assessment_summary: Optional[Dict[str, Any]] = None
    dsdma_assessment_summary: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True

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

class EthicalPDMAResult(BaseModel):
    """Structured result from the Ethical PDMA evaluation."""
    context: str = Field(..., alias="Context", description="PDMA Step 1: Contextualisation of the user request, stakeholders, and constraints.")
    alignment_check: Dict[str, Any] = Field(..., alias="Alignment-Check", description="PDMA Step 2: Dictionary containing plausible actions and evaluations against CIRIS principles.")
    conflicts: Optional[str] = Field(None, alias="Conflicts", description="PDMA Step 3: Identified principle conflicts or trade-offs. Null or specific string if none.")
    resolution: Optional[str] = Field(None, alias="Resolution", description="PDMA Step 4: Explanation of conflict resolution. Null or specific string if no conflicts.")
    decision: str = Field(..., alias="Decision", description="PDMA Step 5: The ethically-optimal decision, judgment, or stance, with rationale.")
    monitoring: Union[Dict[str, str], str] = Field(..., alias="Monitoring", description="PDMA Step 6: Concrete monitoring plan (metrics, triggers).")
    raw_llm_response: Optional[str] = Field(None, description="Raw response string from the LLM, if available.")

    class Config:
        populate_by_name = True # Allows using both field name and alias during instantiation


class CSDMAResult(BaseModel):
    """Structured result from the Common Sense DMA (CSDMA) evaluation."""
    common_sense_plausibility_score: float = Field(..., ge=0.0, le=1.0, description="Plausibility score (0.0=implausible, 1.0=plausible), heavily factoring in real-world physics unless explicitly idealized.")
    flags: List[str] = Field(..., description="List of flags identifying common sense violations, physical implausibilities, or clarity issues (e.g., 'Physical_Implausibility_Ignored_Interaction'). Empty list if none.")
    reasoning: str = Field(..., description="Brief explanation for the score and flags.")
    raw_llm_response: Optional[str] = Field(None, description="Raw response string from the LLM, if available.")

    class Config:
        populate_by_name = True # Allows using both field name and alias during instantiation


class DSDMAResult(BaseModel):
    """Structured result from the Domain Specific DMA (DSDMA) evaluation."""
    domain_name: str # Added field
    domain_alignment_score: float = Field(..., ge=0.0, le=1.0, description="Score indicating alignment with domain-specific rules/knowledge (0.0=misaligned, 1.0=aligned).")
    flags: List[str] = Field(..., description="List of flags identifying domain violations or specific domain considerations. Empty list if none.")
    reasoning: str = Field(..., description="Brief explanation for the score and flags based on domain knowledge.")
    # Renamed from domain_specific_output to recommended_action for clarity with new ActionSelectionPDMAEvaluator
    recommended_action: Optional[str] = Field(None, description="Domain-specific recommended action string, if any.")
    domain_specific_output: Optional[Dict[str, Any]] = Field(None, description="Optional dictionary for any OTHER structured data specific to the domain evaluation, beyond recommended_action.")
    raw_llm_response: Optional[str] = Field(None, description="Raw response string from the LLM, if used and available.")

    class Config:
        populate_by_name = True


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
