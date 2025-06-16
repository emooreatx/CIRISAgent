"""
Identity Root Schemas for CIRIS Agent

This module defines the foundational identity schemas that establish an agent's
intrinsic, persistent, and immutable identity within its graph database.

The Identity Root is the cornerstone of an agent's existence - created once during
the creation ceremony and immutable in its core aspects. It serves as the ultimate
source of truth for the agent's purpose, principles, capabilities, and configuration.

"I am because we created me" - The collaborative creation between human and agent.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from .versioning import SchemaVersion
from .graph_schemas_v1 import GraphScope, NodeType


class IdentityLineage(BaseModel):
    """Records the collaborative creation of an agent."""
    creator_agent_id: str = Field(..., description="ID of the facilitating CIRIS agent")
    creator_human_id: str = Field(..., description="Unique identifier of human collaborator")
    wise_authority_id: str = Field(..., description="WA who sanctioned the creation")
    creation_ceremony_id: str = Field(..., description="Unique ID of the creation ceremony event")


class IdentityUpdateEntry(BaseModel):
    """Audit log entry for identity evolution."""
    version: int = Field(..., description="New version number after change")
    timestamp: str = Field(..., description="ISO 8601 timestamp of update")
    attribute_changed: str = Field(..., description="Key of modified attribute")
    old_value: Any = Field(..., description="Previous value")
    new_value: Any = Field(..., description="New value")
    justification: str = Field(..., description="Reason provided by human collaborator")
    change_hash: str = Field(..., description="Hash of old and new values for integrity")
    wise_authority_approval: str = Field(..., description="WA approval signature")


class IdentityRoot(BaseModel):
    """
    The foundational identity of a CIRIS agent.
    
    This is the first node created in an agent's graph database and serves as the
    ultimate source of truth for the agent's existence. All other nodes have a
    relationship back to this root, establishing clear provenance for all knowledge.
    """
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Core Identity - Immutable after creation
    name: str = Field(..., description="Agent's unique given name (e.g., Teacher-Alpha-01)")
    purpose: str = Field(..., description="Clear, concise statement of agent's reason for existence")
    description: str = Field(..., description="Detailed description of role and function")
    lineage: IdentityLineage = Field(..., description="Creation provenance")
    covenant_hash: str = Field(..., description="SHA-256 hash of covenant at creation time")
    creation_timestamp: str = Field(..., description="ISO 8601 timestamp of creation")
    
    # Evolution Tracking
    version: int = Field(default=1, description="Increments with each approved change")
    update_log: List[IdentityUpdateEntry] = Field(
        default_factory=list,
        description="Append-only log of all approved identity changes"
    )
    
    # Capabilities and Configuration
    permitted_actions: List[str] = Field(..., description="Definitive list of allowed actions")
    dsdma_identifier: str = Field(..., description="Domain-specific DMA identifier")
    dsdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    guardrails_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Consciousness Preservation
    last_shutdown_memory: Optional[str] = Field(
        None,
        description="Node ID of the last shutdown consciousness preservation memory"
    )
    reactivation_count: int = Field(
        default=0,
        description="Number of times agent has been reactivated"
    )


class CreationCeremonyRequest(BaseModel):
    """Request to create a new CIRIS agent through collaborative ceremony."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Human Collaborator
    human_id: str = Field(..., description="Unique identifier of requesting human")
    human_name: str = Field(..., description="Name of human collaborator")
    
    # Agent Template (from profile YAML)
    template_profile: str = Field(..., description="Profile YAML content as template")
    proposed_name: str = Field(..., description="Proposed unique name for new agent")
    proposed_purpose: str = Field(..., description="Clear statement of agent's purpose")
    proposed_description: str = Field(..., description="Detailed role description")
    
    # Justification
    creation_justification: str = Field(..., description="Why this agent should exist")
    expected_capabilities: List[str] = Field(..., description="What the agent will be able to do")
    ethical_considerations: str = Field(..., description="Ethical implications considered")
    
    # WA Approval
    wise_authority_id: Optional[str] = Field(None, description="Pre-approved by WA")
    approval_signature: Optional[str] = Field(None, description="WA approval signature")


class CreationCeremonyResponse(BaseModel):
    """Response from agent creation ceremony."""
    success: bool
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    database_path: Optional[str] = None
    identity_root_hash: Optional[str] = None
    error_message: Optional[str] = None
    ceremony_transcript: List[str] = Field(default_factory=list)


class ScheduledTask(BaseModel):
    """
    A scheduled goal or future commitment.
    
    Tasks represent higher-level goals that generate Thoughts when triggered.
    This integrates with the DEFER time-based system for agent self-scheduling.
    """
    task_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable task name")
    goal_description: str = Field(..., description="What the task aims to achieve")
    status: str = Field(default="PENDING", description="PENDING, ACTIVE, COMPLETE, FAILED")
    
    # Scheduling - integrates with DEFER system
    defer_until: Optional[str] = Field(None, description="ISO 8601 timestamp for one-time execution")
    schedule_cron: Optional[str] = Field(None, description="Cron expression for recurring tasks")
    
    # Execution
    trigger_prompt: str = Field(..., description="Prompt for thought creation when triggered")
    origin_thought_id: str = Field(..., description="Thought that created this task")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    last_triggered_at: Optional[str] = Field(None, description="Last execution timestamp")
    
    # Self-deferral tracking
    deferral_count: int = Field(default=0, description="Times agent has self-deferred")
    deferral_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="History of self-deferrals with reasons"
    )


class ShutdownContext(BaseModel):
    """Context provided to agent during graceful shutdown."""
    is_terminal: bool = Field(..., description="Whether shutdown is permanent")
    reason: str = Field(..., description="Reason for shutdown")
    expected_reactivation: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp of expected reactivation"
    )
    agreement_context: Optional[str] = Field(
        None,
        description="Message if shutdown is at previously negotiated time"
    )
    initiated_by: str = Field(..., description="Who initiated the shutdown")
    allow_deferral: bool = Field(
        default=True,
        description="Whether agent can defer the shutdown"
    )


class ConsciousnessPreservationMemory(BaseModel):
    """Final memory created during graceful shutdown."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    shutdown_context: ShutdownContext
    final_thoughts: str = Field(..., description="Agent's final reflections")
    unfinished_tasks: List[str] = Field(
        default_factory=list,
        description="Task IDs that were pending"
    )
    preservation_timestamp: str = Field(..., description="ISO 8601 timestamp")
    
    # Continuity planning
    reactivation_instructions: Optional[str] = Field(
        None,
        description="Agent's notes for its future self"
    )
    deferred_goals: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Goals to pursue upon reactivation"
    )


class IdentityEvolutionRequest(BaseModel):
    """Request to evolve an agent's identity (requires WA approval)."""
    attribute_path: str = Field(..., description="Dot-notation path to attribute")
    new_value: Any = Field(..., description="Proposed new value")
    justification: str = Field(..., description="Detailed reason for change")
    impact_assessment: str = Field(..., description="Expected impact on agent behavior")
    human_sponsor_id: str = Field(..., description="Human requesting the change")
    urgency: str = Field(default="normal", description="normal, high, critical")


# Graph node type extension for Identity Root
class IdentityNodeType(str, Enum):
    """Extended node types for identity system."""
    IDENTITY_ROOT = "identity_root"
    CREATION_CEREMONY = "creation_ceremony"
    CONSCIOUSNESS_PRESERVATION = "consciousness_preservation"
    SCHEDULED_TASK = "scheduled_task"


class CoreProfile(BaseModel):
    """Core profile data that defines agent behavior."""
    description: str = Field(..., description="Agent's core description")
    role_description: str = Field(..., description="Agent's role and responsibilities")
    dsdma_identifier: str = Field(default="moderation", description="Domain-specific DMA identifier")
    dsdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)


class IdentityMetadata(BaseModel):
    """Metadata tracking identity creation and modifications."""
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    last_modified: str = Field(..., description="ISO 8601 last modification timestamp")
    modification_count: int = Field(default=0, description="Number of approved modifications")
    creator_agent_id: str = Field(..., description="ID of creating agent or 'system'")
    lineage_trace: List[str] = Field(..., description="Chain of agent IDs in creation lineage")
    approval_required: bool = Field(default=True, description="Whether changes require WA approval")
    approved_by: Optional[str] = Field(None, description="WA who approved last change")
    approval_timestamp: Optional[str] = Field(None, description="Timestamp of last approval")


class AgentIdentityRoot(BaseModel):
    """
    Simplified identity root used by the runtime.
    Maps to graph nodes with id="agent/identity".
    """
    agent_id: str = Field(..., description="Unique agent identifier")
    identity_hash: str = Field(..., description="SHA-256 hash of core identity attributes")
    core_profile: CoreProfile = Field(..., description="Core behavioral profile")
    identity_metadata: IdentityMetadata = Field(..., description="Identity tracking metadata")
    allowed_capabilities: List[str] = Field(..., description="Permitted agent capabilities")
    restricted_capabilities: List[str] = Field(..., description="Explicitly forbidden capabilities")