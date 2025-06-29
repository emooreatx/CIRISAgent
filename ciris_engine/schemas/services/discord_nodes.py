"""Discord-specific graph node schemas."""
from typing import Dict, Optional, List, Any, Literal
from datetime import datetime
from pydantic import Field

from ciris_engine.schemas.services.graph_typed_nodes import TypedGraphNode, register_node_type


@register_node_type("DISCORD_DEFERRAL")
class DiscordDeferralNode(TypedGraphNode):
    """Represents a deferral stored in the graph."""
    type: Literal["DISCORD_DEFERRAL"] = Field(default="DISCORD_DEFERRAL")

    # Deferral details
    deferral_id: str = Field(..., description="Unique deferral ID")
    task_id: str = Field(..., description="Associated task ID")
    thought_id: str = Field(..., description="Associated thought ID")
    reason: str = Field(..., description="Reason for deferral")
    defer_until: datetime = Field(..., description="When to reconsider")

    # Discord specifics
    channel_id: str = Field(..., description="Discord channel ID")
    message_id: Optional[str] = Field(None, description="Discord message ID")

    # Resolution details
    status: str = Field(default="pending", description="Status: pending, resolved, expired")
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution: Optional[str] = None

    # Context
    context: Dict[str, Any] = Field(default_factory=dict)


@register_node_type("DISCORD_APPROVAL")
class DiscordApprovalNode(TypedGraphNode):
    """Represents an approval request stored in the graph."""
    type: Literal["DISCORD_APPROVAL"] = Field(default="DISCORD_APPROVAL")

    # Approval details
    approval_id: str = Field(..., description="Unique approval ID")
    action: str = Field(..., description="Action requiring approval")
    request_type: str = Field(..., description="Type of approval request")

    # Discord specifics
    channel_id: str = Field(..., description="Discord channel ID")
    message_id: str = Field(..., description="Discord message ID")

    # Context
    task_id: Optional[str] = None
    thought_id: Optional[str] = None
    requester_id: str = Field(..., description="Who requested approval")

    # Resolution
    status: str = Field(default="pending", description="Status: pending, approved, denied, timeout")
    resolved_at: Optional[datetime] = None
    resolver_id: Optional[str] = None
    resolver_name: Optional[str] = None

    # Additional context
    context: Dict[str, Any] = Field(default_factory=dict)
    action_params: Dict[str, Any] = Field(default_factory=dict)


@register_node_type("DISCORD_WA")
class DiscordWANode(TypedGraphNode):
    """Represents a Discord Wise Authority in the graph."""
    type: Literal["DISCORD_WA"] = Field(default="DISCORD_WA")

    # Discord identity
    discord_id: str = Field(..., description="Discord user ID")
    discord_name: str = Field(..., description="Discord username")
    discriminator: Optional[str] = Field(None, description="Discord discriminator")

    # WA details
    wa_id: str = Field(..., description="CIRIS WA ID")
    roles: List[str] = Field(default_factory=list, description="Discord roles")

    # Permissions
    has_authority: bool = Field(default=False, description="Has AUTHORITY role")
    has_observer: bool = Field(default=False, description="Has OBSERVER role")

    # Activity tracking
    last_seen: datetime = Field(..., description="Last activity time")
    approval_count: int = Field(default=0, description="Number of approvals made")
    deferral_count: int = Field(default=0, description="Number of deferrals resolved")

    # Guild information
    guilds: List[Dict[str, str]] = Field(default_factory=list, description="List of guilds user is in")


# Discord-specific node types are registered via the @register_node_type decorator
