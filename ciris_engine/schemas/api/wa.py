"""
WA (Wise Authority) API schemas for CIRIS.

Provides type-safe structures for WA API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

from ciris_engine.schemas.services.authority_core import (
    WARole,
    DeferralRequest,
    DeferralResponse,
    GuidanceRequest,
    GuidanceResponse,
    WAPermission
)
from ciris_engine.schemas.services.authority.wise_authority import (
    PendingDeferral
)


class DeferralListResponse(BaseModel):
    """Response containing list of pending deferrals."""
    deferrals: List[PendingDeferral] = Field(..., description="List of pending deferrals")
    total: int = Field(..., description="Total number of pending deferrals")
    
    
class DeferralDetailResponse(BaseModel):
    """Response containing detailed deferral information."""
    deferral: PendingDeferral = Field(..., description="Deferral details")
    
    
class ResolveDeferralRequest(BaseModel):
    """Request to resolve a deferral."""
    resolution: str = Field(..., pattern="^(approve|reject|modify)$", description="Resolution type")
    guidance: Optional[str] = Field(None, description="WA guidance text")
    modified_action: Optional[str] = Field(None, description="Modified action if resolution is 'modify'")
    modified_parameters: Optional[Dict[str, str]] = Field(None, description="Modified parameters if applicable")
    new_constraints: List[str] = Field(default_factory=list, description="New constraints to add")
    removed_constraints: List[str] = Field(default_factory=list, description="Constraints to remove")
    

class ResolveDeferralResponse(BaseModel):
    """Response after resolving a deferral."""
    success: bool = Field(..., description="Whether resolution succeeded")
    deferral_id: str = Field(..., description="ID of resolved deferral")
    resolved_at: datetime = Field(..., description="When deferral was resolved")
    
    
class RequestGuidanceRequest(BaseModel):
    """Request for WA guidance."""
    context: str = Field(..., description="Context requiring guidance")
    options: List[str] = Field(..., description="Available options")
    recommendation: Optional[str] = Field(None, description="Agent's recommendation")
    urgency: str = Field("normal", pattern="^(low|normal|high|critical)$", description="Urgency level")
    

class RequestGuidanceResponse(BaseModel):
    """Response containing WA guidance."""
    guidance: GuidanceResponse = Field(..., description="WA guidance details")
    
    
class PermissionsListResponse(BaseModel):
    """Response containing list of permissions."""
    permissions: List[WAPermission] = Field(..., description="List of permissions")
    wa_id: str = Field(..., description="WA ID these permissions belong to")
    
    
class GrantPermissionRequest(BaseModel):
    """Request to grant a permission."""
    wa_id: str = Field(..., description="WA to grant permission to")
    permission_name: str = Field(..., description="Permission name (e.g., 'approve_deferrals')")
    permission_type: str = Field("action", description="Type of permission (action, resource, scope)")
    resource: Optional[str] = Field(None, description="Optional resource identifier")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration time")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")
    

class RevokePermissionRequest(BaseModel):
    """Request to revoke a permission."""
    wa_id: str = Field(..., description="WA to revoke permission from")
    permission_id: str = Field(..., description="Permission ID to revoke")
    

class PermissionOperationResponse(BaseModel):
    """Response after permission operation."""
    success: bool = Field(..., description="Whether operation succeeded")
    wa_id: str = Field(..., description="WA ID affected")
    permission_id: Optional[str] = Field(None, description="Permission ID (for grant operations)")
    operation: str = Field(..., description="Operation performed (grant/revoke)")
    timestamp: datetime = Field(..., description="When operation occurred")