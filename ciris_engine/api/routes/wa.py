"""
Wise Authority Service endpoints for CIRIS API v1.

Manages human-in-the-loop deferrals and permissions.
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
import logging
import uuid

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode, ErrorDetail
from ciris_engine.schemas.api.wa import (
    DeferralListResponse,
    DeferralDetailResponse,
    ResolveDeferralRequest,
    ResolveDeferralResponse,
    RequestGuidanceRequest,
    RequestGuidanceResponse,
    PermissionsListResponse,
    GrantPermissionRequest,
    RevokePermissionRequest,
    PermissionOperationResponse
)
from ciris_engine.schemas.services.authority_core import (
    GuidanceRequest,
    GuidanceResponse,
    DeferralResponse,
    WAPermission
)
from ciris_engine.schemas.services.authority.wise_authority import (
    PendingDeferral,
    DeferralResolution
)
from ciris_engine.protocols.services.governance.wise_authority import WiseAuthorityServiceProtocol
from ciris_engine.api.dependencies.auth import require_authority, require_observer, AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wa", tags=["wise_authority"])


@router.get("/deferrals", response_model=SuccessResponse[DeferralListResponse])
async def get_deferrals(
    request: Request,
    wa_id: Optional[str] = Query(None, description="Filter by WA ID"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get list of pending deferrals.
    
    Returns all pending deferrals that need WA review. Can optionally
    filter by WA ID to see deferrals assigned to a specific authority.
    
    Requires OBSERVER role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Get pending deferrals
        deferrals = await wa_service.get_pending_deferrals(wa_id=wa_id)
        
        response = DeferralListResponse(
            deferrals=deferrals,
            total=len(deferrals)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Failed to get deferrals: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to retrieve deferrals: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.get("/deferrals/{deferral_id}", response_model=SuccessResponse[DeferralDetailResponse])
async def get_deferral_detail(
    request: Request,
    deferral_id: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get details of a specific deferral.
    
    Returns detailed information about a pending deferral including
    context, reason, and assignment information.
    
    Requires OBSERVER role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Get all deferrals and find the specific one
        deferrals = await wa_service.get_pending_deferrals()
        
        deferral = None
        for d in deferrals:
            if d.deferral_id == deferral_id:
                deferral = d
                break
        
        if not deferral:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.RESOURCE_NOT_FOUND,
                        message=f"Deferral {deferral_id} not found"
                    )
                ).model_dump(mode='json')
            )
        
        response = DeferralDetailResponse(deferral=deferral)
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deferral {deferral_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to retrieve deferral: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.post("/deferrals/{deferral_id}/resolve", response_model=SuccessResponse[ResolveDeferralResponse])
async def resolve_deferral(
    request: Request,
    deferral_id: str,
    resolve_request: ResolveDeferralRequest,
    auth: AuthContext = Depends(require_authority)
):
    """
    Resolve a pending deferral.
    
    Allows a WA with AUTHORITY role to approve, reject, or modify
    a deferred decision. The resolution includes guidance and any
    modifications to the original action.
    
    Requires AUTHORITY role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Create deferral response
        deferral_response = DeferralResponse(
            approved=(resolve_request.resolution == "approve"),
            reason=resolve_request.guidance,
            modified_time=None,  # Not implementing time modifications for now
            wa_id=auth.user_id,  # Use authenticated user as WA
            signature=f"api_{auth.user_id}_{datetime.now(timezone.utc).isoformat()}"  # Simple signature
        )
        
        # Resolve the deferral
        success = await wa_service.resolve_deferral(deferral_id, deferral_response)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Failed to resolve deferral - it may have already been resolved"
                    )
                ).model_dump(mode='json')
            )
        
        # If resolution is "modify", we would need to handle the modifications
        # This would typically involve updating the task/action with new parameters
        # For now, we just record the resolution
        
        response = ResolveDeferralResponse(
            success=True,
            deferral_id=deferral_id,
            resolved_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"Deferral {deferral_id} resolved by {auth.user_id} with resolution: {resolve_request.resolution}")
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve deferral {deferral_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to resolve deferral: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.post("/guidance", response_model=SuccessResponse[RequestGuidanceResponse])
async def request_guidance(
    request: Request,
    guidance_request: RequestGuidanceRequest,
    auth: AuthContext = Depends(require_observer)
):
    """
    Request guidance from Wise Authorities.
    
    Allows requesting guidance for a situation with multiple options.
    The WA service will provide recommendations based on context.
    
    Requires OBSERVER role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Create guidance request
        service_request = GuidanceRequest(
            context=guidance_request.context,
            options=guidance_request.options,
            recommendation=guidance_request.recommendation,
            urgency=guidance_request.urgency
        )
        
        # Get guidance
        guidance = await wa_service.get_guidance(service_request)
        
        response = RequestGuidanceResponse(guidance=guidance)
        
        logger.info(f"Guidance requested by {auth.user_id} for context: {guidance_request.context[:50]}...")
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Failed to get guidance: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to get guidance: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.get("/permissions", response_model=SuccessResponse[PermissionsListResponse])
async def get_permissions(
    request: Request,
    wa_id: Optional[str] = Query(None, description="WA ID to get permissions for (defaults to current user)"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get permissions for a WA.
    
    Returns all permissions granted to a specific WA. If no WA ID
    is provided, returns permissions for the authenticated user.
    
    Requires OBSERVER role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Use authenticated user's ID if no WA ID provided
        target_wa_id = wa_id or auth.user_id
        
        # Get permissions
        permissions = await wa_service.list_permissions(target_wa_id)
        
        response = PermissionsListResponse(
            permissions=permissions,
            wa_id=target_wa_id
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        logger.error(f"Failed to get permissions for {target_wa_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to retrieve permissions: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.post("/permissions/grant", response_model=SuccessResponse[PermissionOperationResponse])
async def grant_permission(
    request: Request,
    grant_request: GrantPermissionRequest,
    auth: AuthContext = Depends(require_authority)
):
    """
    Grant a permission to a WA.
    
    Allows granting specific permissions to Wise Authorities.
    Only WAs with AUTHORITY role can grant permissions.
    
    Requires AUTHORITY role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # Grant the permission
        success = await wa_service.grant_permission(
            wa_id=grant_request.wa_id,
            permission=grant_request.permission_name,
            resource=grant_request.resource
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Failed to grant permission - WA may not exist or permission may be invalid"
                    )
                ).model_dump(mode='json')
            )
        
        # Generate permission ID for response
        permission_id = f"perm_{uuid.uuid4().hex[:8]}"
        
        response = PermissionOperationResponse(
            success=True,
            wa_id=grant_request.wa_id,
            permission_id=permission_id,
            operation="grant",
            timestamp=datetime.now(timezone.utc)
        )
        
        logger.info(f"Permission {grant_request.permission_name} granted to {grant_request.wa_id} by {auth.user_id}")
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to grant permission: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to grant permission: {str(e)}"
                )
            ).model_dump(mode='json')
        )


@router.post("/permissions/revoke", response_model=SuccessResponse[PermissionOperationResponse])
async def revoke_permission(
    request: Request,
    revoke_request: RevokePermissionRequest,
    auth: AuthContext = Depends(require_authority)
):
    """
    Revoke a permission from a WA.
    
    Allows revoking specific permissions from Wise Authorities.
    Only WAs with AUTHORITY role can revoke permissions.
    
    Requires AUTHORITY role or higher.
    """
    # Get WA service from app state
    if not hasattr(request.app.state, 'wise_authority_service'):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Wise Authority service not available"
                )
            ).model_dump(mode='json')
        )
    
    wa_service: WiseAuthorityServiceProtocol = request.app.state.wise_authority_service
    
    try:
        # For this implementation, we'll need to extract the permission name from the ID
        # In a real system, we'd look up the permission by ID
        # For now, we'll use a simplified approach
        
        # Get current permissions to find the one to revoke
        permissions = await wa_service.list_permissions(revoke_request.wa_id)
        
        permission_found = False
        permission_name = None
        resource = None
        
        for perm in permissions:
            if perm.permission_id == revoke_request.permission_id:
                permission_found = True
                permission_name = perm.permission_name
                resource = perm.resource
                break
        
        if not permission_found:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.RESOURCE_NOT_FOUND,
                        message=f"Permission {revoke_request.permission_id} not found"
                    )
                ).model_dump(mode='json')
            )
        
        # Revoke the permission
        success = await wa_service.revoke_permission(
            wa_id=revoke_request.wa_id,
            permission=permission_name,
            resource=resource
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Failed to revoke permission"
                    )
                ).model_dump(mode='json')
            )
        
        response = PermissionOperationResponse(
            success=True,
            wa_id=revoke_request.wa_id,
            permission_id=revoke_request.permission_id,
            operation="revoke",
            timestamp=datetime.now(timezone.utc)
        )
        
        logger.info(f"Permission {revoke_request.permission_id} revoked from {revoke_request.wa_id} by {auth.user_id}")
        
        return SuccessResponse(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke permission: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to revoke permission: {str(e)}"
                )
            ).model_dump(mode='json')
        )