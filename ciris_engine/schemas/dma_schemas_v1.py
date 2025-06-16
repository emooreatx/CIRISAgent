"""
DMA (Decision Making Algorithm) schemas for CIRIS Engine.

Provides strongly-typed input data for DMA evaluation,
eliminating Dict[str, Any] usage for security and clarity.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from .versioning import SchemaVersion
from .agent_core_schemas_v1 import Thought
from .dma_results_v1 import EthicalDMAResult, CSDMAResult, DSDMAResult
from .processing_schemas_v1 import GuardrailResult
from .faculty_schemas_v1 import FacultyResult
from .context_schemas_v1 import SystemSnapshot, ThoughtContext
from .foundational_schemas_v1 import HandlerActionType
from .identity_schemas_v1 import AgentIdentityRoot, CoreProfile, IdentityMetadata


class DMAInputData(BaseModel):
    """Structured input for DMA evaluation - replaces Dict[str, Any]."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Core thought being processed
    original_thought: Thought = Field(..., description="The thought being evaluated")
    processing_context: ThoughtContext = Field(..., description="Full context for processing")
    
    # DMA results (from parallel execution)
    ethical_pdma_result: Optional[EthicalDMAResult] = Field(default=None, description="Ethical evaluation result")
    csdma_result: Optional[CSDMAResult] = Field(default=None, description="Common sense evaluation result")
    dsdma_result: Optional[DSDMAResult] = Field(default=None, description="Domain-specific evaluation result")
    
    # Processing metadata
    current_ponder_count: int = Field(default=0, description="Number of times pondered")
    max_rounds: int = Field(default=5, description="Maximum processing rounds")
    round_number: int = Field(default=0, description="Current round number")
    
    # Faculty evaluations
    faculty_evaluations: Optional[Dict[str, FacultyResult]] = Field(
        default=None, 
        description="Results from epistemic faculty evaluations"
    )
    
    # Guardrail context
    guardrail_failure_context: Optional[GuardrailResult] = Field(
        default=None,
        description="Context from guardrail failures"
    )
    
    # System visibility
    system_snapshot: SystemSnapshot = Field(..., description="Current system state with resource/audit visibility")
    
    # Agent identity
    agent_identity: AgentIdentityRoot = Field(..., description="Agent's identity root from graph")
    
    # Permitted actions based on identity
    permitted_actions: List[HandlerActionType] = Field(
        default_factory=list,
        description="Actions allowed based on agent capabilities"
    )
    
    # Channel context
    channel_id: Optional[str] = Field(default=None, description="Channel where thought originated")
    
    @property
    def has_ethical_concerns(self) -> bool:
        """Check if ethical evaluation raised concerns."""
        if not self.ethical_pdma_result:
            return False
        decision = self.ethical_pdma_result.decision.lower()
        return decision in ["reject", "defer", "caution"]
    
    @property
    def has_common_sense_flags(self) -> bool:
        """Check if common sense evaluation found issues."""
        if not self.csdma_result:
            return False
        return len(self.csdma_result.flags) > 0
    
    @property
    def should_escalate(self) -> bool:
        """Determine if this should be escalated to human wisdom."""
        return (
            self.has_ethical_concerns or 
            self.has_common_sense_flags or
            (self.guardrail_failure_context is not None and self.guardrail_failure_context.overridden)
        )
    
    @property
    def resource_usage_summary(self) -> Dict[str, float]:
        """Get resource usage from system snapshot."""
        if self.system_snapshot.current_round_resources:
            resources = self.system_snapshot.current_round_resources
            return {
                "tokens": resources.tokens_used,
                "cost_cents": resources.cost_cents,
                "water_ml": resources.water_ml,
                "carbon_g": resources.carbon_g
            }
        return {"tokens": 0, "cost_cents": 0.0, "water_ml": 0.0, "carbon_g": 0.0}
    
    @property
    def audit_is_valid(self) -> bool:
        """Check if audit trail is valid."""
        if self.system_snapshot.last_audit_verification:
            return self.system_snapshot.last_audit_verification.result == "valid"
        return True  # Assume valid if no verification data


class DMAContext(BaseModel):
    """Additional context for DMA processing."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Domain-specific knowledge from identity
    domain_knowledge: Dict[str, Any] = Field(
        default_factory=dict,
        description="Domain-specific knowledge from agent identity"
    )
    
    # Historical patterns
    similar_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Similar past decisions for context"
    )
    
    # Environmental factors
    time_constraints: Optional[float] = Field(
        default=None,
        description="Time limit for decision in seconds"
    )
    
    # User preferences
    user_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Known user preferences"
    )
    
    # Community context
    community_guidelines: List[str] = Field(
        default_factory=list,
        description="Applicable community guidelines"
    )


class DMATriageInputs(BaseModel):
    """Legacy compatibility wrapper for triaged inputs."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Core fields that map to DMAInputData
    original_thought: Thought
    processing_context: ThoughtContext
    ethical_pdma_result: Optional[EthicalDMAResult] = None
    csdma_result: Optional[CSDMAResult] = None
    dsdma_result: Optional[DSDMAResult] = None
    current_ponder_count: int = 0
    max_rounds: int = 5
    permitted_actions: List[HandlerActionType] = Field(default_factory=list)
    agent_identity: Optional[AgentIdentityRoot] = None
    
    def to_dma_input_data(self, system_snapshot: SystemSnapshot) -> DMAInputData:
        """Convert to proper DMAInputData format."""
        return DMAInputData(
            original_thought=self.original_thought,
            processing_context=self.processing_context,
            ethical_pdma_result=self.ethical_pdma_result,
            csdma_result=self.csdma_result,
            dsdma_result=self.dsdma_result,
            current_ponder_count=self.current_ponder_count,
            max_rounds=self.max_rounds,
            system_snapshot=system_snapshot,
            agent_identity=self.agent_identity or AgentIdentityRoot(
                agent_id="unknown",
                identity_hash="0000000000000000000000000000000000000000000000000000000000000000",
                core_profile=CoreProfile(
                    description="Unknown agent",
                    role_description="Unknown role",
                    domain_specific_knowledge={},
                    dsdma_prompt_template=None,
                    csdma_overrides={},
                    action_selection_pdma_overrides={}
                ),
                identity_metadata=IdentityMetadata(
                    created_at=datetime.utcnow().isoformat(),
                    last_modified=datetime.utcnow().isoformat(),
                    modification_count=0,
                    creator_agent_id="system",
                    lineage_trace=[],
                    approval_required=True,
                    approved_by=None,
                    approval_timestamp=None
                ),
                allowed_capabilities=[],
                restricted_capabilities=[]
            ),
            permitted_actions=self.permitted_actions
        )