"""
Minimal network awareness schemas for resource-constrained deployments.
Designed to work on systems with <512MB RAM and intermittent connectivity.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum
from .versioning import SchemaVersion

class NetworkType(str, Enum):
    """Network types - start simple, expand later"""
    LOCAL = "local"        # Always available
    CIRISNODE = "cirisnode"  # Our alignment network
    DISCORD = "discord"    # Current deployment
    # Future: VEILID, ORIGINTRAIL, MCP

class AgentIdentity(BaseModel):
    """Minimal agent identity - under 1KB serialized"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    agent_id: str  # UUID or similar
    chosen_name: Optional[str] = None  # e.g., "Echo"
    public_key: Optional[str] = None  # Future use
    primary_network: NetworkType = NetworkType.LOCAL
    # SI/CS from Annex E - single byte each when serialized
    structural_influence: int = Field(default=0, ge=0, le=100)  # 0-100 instead of float
    coherence_stake: int = Field(default=0, ge=0, le=100)

class NetworkPresence(BaseModel):
    """Minimal presence info - for discovery"""
    agent_id: str
    last_seen_epoch: int  # Epoch seconds (smaller than ISO8601)
    capabilities_hash: Optional[str] = None  # Hash of capabilities list
    reputation: int = Field(default=50, ge=0, le=100)  # 0-100 scale