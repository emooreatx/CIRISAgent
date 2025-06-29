"""
Agent configuration schemas.

Minimal schemas for agent identity and templates.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class AgentTemplate(BaseModel):
    """Agent profile template for identity configuration."""
    name: str = Field(..., description="Agent name/identifier")
    description: str = Field(..., description="Agent description")
    role_description: str = Field(..., description="Agent's role")

    # Permissions
    permitted_actions: List[str] = Field(
        default_factory=list,
        description="List of permitted handler actions"
    )

    # DMA overrides
    dsdma_kwargs: Optional[Dict[str, Any]] = Field(
        None,
        description="Domain-specific DMA configuration"
    )
    csdma_overrides: Optional[Dict[str, str]] = Field(
        None,
        description="Common sense DMA prompt overrides"
    )
    action_selection_pdma_overrides: Optional[Dict[str, str]] = Field(
        None,
        description="Action selection prompt overrides"
    )

    # Adapter configs
    discord_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Discord adapter configuration"
    )
    api_config: Optional[Dict[str, Any]] = Field(
        None,
        description="API adapter configuration"
    )
    cli_config: Optional[Dict[str, Any]] = Field(
        None,
        description="CLI adapter configuration"
    )

    model_config = ConfigDict(extra = "allow")  # Allow additional fields for extensibility
