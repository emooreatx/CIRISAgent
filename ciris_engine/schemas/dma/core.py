"""
Core DMA schemas for typed decision-making.

Replaces Dict[str, Any] with properly typed structures.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.runtime.system_context import SystemSnapshot, ThoughtContext, ConscienceResult
from .decisions import PDMADecision, CSDMADecision, DSDMADecision
from .results import EthicalDMAResult, CSDMAResult, DSDMAResult

class DMAInputData(BaseModel):
    """Structured input for DMA evaluation - replaces Dict[str, Any]."""
    
    # Core thought being processed
    original_thought: Thought = Field(..., description="The thought being evaluated")
    processing_context: ThoughtContext = Field(..., description="Full context for processing")
    
    # DMA results (from parallel execution)
    ethical_pdma_result: Optional[EthicalDMAResult] = Field(None, description="Ethical evaluation result")
    csdma_result: Optional[CSDMAResult] = Field(None, description="Common sense evaluation result")
    dsdma_result: Optional[DSDMAResult] = Field(None, description="Domain-specific evaluation result")
    
    # Processing metadata
    current_thought_depth: int = Field(0, description="Number of times pondered")
    max_rounds: int = Field(5, description="Maximum processing rounds")
    round_number: int = Field(0, description="Current round number")
    
    # conscience feedback (formerly faculty evaluations)
    faculty_evaluations: Optional[Dict[str, Any]] = Field(
        None, 
        description="conscience feedback for ASPDMA retry (legacy field name retained for compatibility)"
    )
    
    # conscience context
    conscience_failure_context: Optional[ConscienceResult] = Field(
        None,
        description="Context from conscience failures"
    )
    
    # System visibility
    system_snapshot: SystemSnapshot = Field(..., description="Current system state")
    
    # Agent identity
    agent_identity: 'AgentIdentityRoot' = Field(..., description="Agent's identity root from graph")
    
    # Permitted actions based on identity
    permitted_actions: List[str] = Field(
        default_factory=list,
        description="Actions allowed based on agent capabilities"
    )
    
    # Channel context
    channel_id: Optional[str] = Field(None, description="Channel where thought originated")
    
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
            (self.conscience_failure_context is not None and self.conscience_failure_context.overridden)
        )
    
    @property
    def resource_usage_summary(self) -> Dict[str, float]:
        """Get resource usage from system snapshot."""
        if self.system_snapshot.current_round_resources:
            resources = self.system_snapshot.current_round_resources
            return {
                "tokens": resources.tokens_used,
                "cost_cents": resources.cost_cents,
                "carbon_grams": resources.carbon_grams
            }
        return {"tokens": 0, "cost_cents": 0.0, "carbon_grams": 0.0}
    
    @property
    def audit_is_valid(self) -> bool:
        """Check if audit trail is valid."""
        if self.system_snapshot.last_audit_verification:
            return self.system_snapshot.last_audit_verification.result == "valid"
        return True  # Assume valid if no verification data
    
    class Config:
        extra = "forbid"

class DMAContext(BaseModel):
    """Additional context for DMA processing."""
    
    # Domain-specific knowledge from identity
    domain_knowledge: Dict[str, str] = Field(
        default_factory=dict,
        description="Domain-specific knowledge from agent identity"
    )
    
    # Historical patterns
    similar_decisions: List['DMADecision'] = Field(
        default_factory=list,
        description="Similar past decisions for context"
    )
    
    # Environmental factors
    time_constraints: Optional[float] = Field(
        None,
        description="Time limit for decision in seconds"
    )
    
    # User preferences
    user_preferences: Dict[str, str] = Field(
        default_factory=dict,
        description="Known user preferences"
    )
    
    # Community context
    community_guidelines: List[str] = Field(
        default_factory=list,
        description="Applicable community guidelines"
    )
    
    class Config:
        extra = "forbid"

class DMADecision(BaseModel):
    """A decision made by a DMA."""
    dma_type: str = Field(..., description="Type of DMA: PDMA, CSDMA, DSDMA, ActionSelection")
    decision: str = Field(..., description="The decision: approve, reject, defer, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    reasoning: str = Field(..., description="Explanation of the decision")
    timestamp: datetime = Field(..., description="Decision timestamp")
    
    # Additional context
    factors_considered: List[str] = Field(default_factory=list, description="Factors in decision")
    alternatives_evaluated: List[str] = Field(default_factory=list, description="Alternatives considered")
    
    class Config:
        extra = "forbid"

class PrincipleEvaluation(BaseModel):
    """Evaluation of ethical principles."""
    principles_upheld: List[str] = Field(default_factory=list, description="Principles followed")
    principles_violated: List[str] = Field(default_factory=list, description="Principles violated")
    ethical_score: float = Field(..., ge=0.0, le=1.0, description="Overall ethical score")
    severity: str = Field(..., description="Severity of violations: none, low, medium, high, critical")
    
    # Detailed analysis
    violation_details: Dict[str, str] = Field(default_factory=dict, description="Details per violation")
    mitigation_suggestions: List[str] = Field(default_factory=list, description="How to mitigate")
    
    class Config:
        extra = "forbid"

class CommonSenseEvaluation(BaseModel):
    """Evaluation of common sense aspects."""
    makes_sense: bool = Field(..., description="Whether action makes common sense")
    practicality_score: float = Field(..., ge=0.0, le=1.0, description="How practical")
    reasoning_chain: List[str] = Field(..., description="Step by step reasoning")
    
    # Risk assessment
    identified_risks: List[Dict[str, str]] = Field(default_factory=list, description="Risks identified")
    risk_level: str = Field(..., description="Overall risk: negligible, low, medium, high, extreme")
    
    class Config:
        extra = "forbid"

class DomainEvaluation(BaseModel):
    """Domain-specific evaluation."""
    domain: str = Field(..., description="Domain of expertise")
    alignment_score: float = Field(..., ge=0.0, le=1.0, description="Domain alignment")
    domain_requirements: List[str] = Field(..., description="Domain requirements")
    requirements_met: List[str] = Field(default_factory=list, description="Requirements satisfied")
    requirements_failed: List[str] = Field(default_factory=list, description="Requirements not met")
    
    # Domain expertise
    relevant_knowledge: List[str] = Field(default_factory=list, description="Relevant domain knowledge")
    recommendations: List[str] = Field(default_factory=list, description="Domain-specific recommendations")
    
    class Config:
        extra = "forbid"

class RecursiveReasoning(BaseModel):
    """Recursive ethical reasoning about the selection process itself."""
    selection_method: str = Field(..., description="How selection was performed")
    method_ethical_score: float = Field(..., ge=0.0, le=1.0, description="Ethics of method")
    
    # Meta-ethical analysis
    selection_principles_used: List[str] = Field(..., description="Principles for selection")
    selection_biases_detected: List[str] = Field(default_factory=list, description="Biases found")
    fairness_measures: List[str] = Field(..., description="How fairness was ensured")
    
    # Recursive depth
    recursion_level: int = Field(1, description="How deep the recursion")
    meta_insights: List[str] = Field(default_factory=list, description="Insights from recursion")
    
    # Validation
    selection_validated: bool = Field(..., description="Whether selection process was valid")
    validation_reasoning: str = Field(..., description="Why valid or not")
    
    class Config:
        extra = "forbid"

# These are imported from other v1 schemas
from ciris_engine.schemas.runtime.core import AgentIdentityRoot

__all__ = [
    "DMAInputData",
    "DMAContext",
    "DMADecision",
    "PrincipleEvaluation",
    "CommonSenseEvaluation",
    "DomainEvaluation",
    "RecursiveReasoning"
]