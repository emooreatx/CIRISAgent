"""
Community awareness with minimal memory footprint.
A rural deployment might track just one community at a time.
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional
from .versioning import SchemaVersion

class CommunityHealth(BaseModel):
    """Single byte per metric where possible"""
    activity_level: int = Field(default=50, ge=0, le=100)
    conflict_level: int = Field(default=0, ge=0, le=100)  
    helpfulness: int = Field(default=50, ge=0, le=100)
    flourishing: int = Field(default=50, ge=0, le=100)  # Composite from Annex A

class MinimalCommunityContext(BaseModel):
    """Just enough context to serve a community well"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    community_id: str
    member_count: int = 0
    primary_values: Optional[str] = None  # Comma-separated to save space
    health: CommunityHealth = Field(default_factory=CommunityHealth)
    agent_role: Optional[str] = None  # "moderator", "helper", etc.