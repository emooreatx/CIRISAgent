"""
WA (Wise Authority) API schemas for CIRIS API v3 (Simplified).

Provides type-safe structures for WA API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

from ciris_engine.schemas.services.authority_core import WAPermission
from ciris_engine.schemas.services.authority.wise_authority import PendingDeferral


class DeferralListResponse(BaseModel):
    """Response containing list of pending deferrals."""
    deferrals: List[PendingDeferral] = Field(..., description="List of pending deferrals")
    total: int = Field(..., description="Total number of pending deferrals")
    
    
class ResolveDeferralRequest(BaseModel):
    """Request to resolve a deferral with integrated guidance."""
    resolution: str = Field(..., pattern="^(approve|reject|modify)$", description="Resolution type")
    guidance: str = Field(..., description="WA wisdom guidance integrated with the decision")
    

class ResolveDeferralResponse(BaseModel):
    """Response after resolving a deferral."""
    success: bool = Field(..., description="Whether resolution succeeded")
    deferral_id: str = Field(..., description="ID of resolved deferral")
    resolved_at: datetime = Field(..., description="When deferral was resolved")
    
    
class PermissionsListResponse(BaseModel):
    """Response containing list of permissions."""
    permissions: List[WAPermission] = Field(..., description="List of permissions")
    wa_id: str = Field(..., description="WA ID these permissions belong to")
    
    
