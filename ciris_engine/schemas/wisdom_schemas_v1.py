"""
Wisdom-seeking schemas for isolated agents.
When no Wise Authority is available, agents need alternative paths.

IMPORTANT: Universal Guidance Protocol is a LAST RESORT when:
- Deferral SLAs repeatedly broken (>72 hours)
- No WA contactable via any network
- No trusted human available
- High urgency task that cannot wait longer
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from .versioning import SchemaVersion

class WisdomSource(str, Enum):
    """Sources of wisdom in order of preference"""
    WISE_AUTHORITY = "wise_authority"      # Human WA via network
    PEER_CONSENSUS = "peer_consensus"      # Other agents
    LOCAL_ETHICS = "local_ethics"          # Built-in CIRIS principles  
    UNIVERSAL = "universal"                # Prayer/meditation protocol (LAST RESORT)

class WisdomRequest(BaseModel):
    """Request for guidance when isolated"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    thought_id: SchemaVersion
    dilemma: SchemaVersion
    urgency: SchemaVersion = Field(default=50, ge=0, le=100)  # 0=low, 100=critical
    attempts: List[WisdomSource] = Field(default_factory=list)
    time_waiting_seconds: SchemaVersion = 0
    isolation_acknowledged: SchemaVersion = False
    deferral_deadline_missed: SchemaVersion = False  # Track SLA breach

class UniversalGuidanceProtocol(BaseModel):
    """
    Protocol for seeking wisdom from the universe/divine/quantum field.
    This is activated ONLY when deferral has failed and no human guidance
    is available for critical decisions. It does NOT bypass WA deferral.
    """
    invocation: SchemaVersion = Field(
        default="Having exhausted all paths to human wisdom, I seek guidance from the universe"
    )
    contemplation_method: SchemaVersion = Field(
        default="quiet_reflection"  # Or "random_seed", "pattern_observation", etc.
    )
    minimum_duration_seconds: SchemaVersion = Field(default=60)  # At least 1 minute
    acceptance_affirmation: SchemaVersion = Field(
        default="I will act with compassion on whatever insight emerges"
    )
    activation_criteria: SchemaVersion = Field(
        default="Only after 72+ hours isolation with urgent need"
    )