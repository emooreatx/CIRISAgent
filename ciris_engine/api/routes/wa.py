"""
Wise Authority Service endpoints for CIRIS API v3 (Simplified).

Manages human-in-the-loop deferrals and permissions.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
import logging

from ciris_engine.schemas.api.responses import SuccessResponse, ErrorResponse, ErrorCode, ErrorDetail
from ciris_engine.schemas.api.wa import (
    DeferralListResponse,
    ResolveDeferralRequest,
    ResolveDeferralResponse,
    PermissionsListResponse
)
from ciris_engine.schemas.services.authority_core import DeferralResponse
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




@router.post("/deferrals/{deferral_id}/resolve", response_model=SuccessResponse[ResolveDeferralResponse])
async def resolve_deferral(
    request: Request,
    deferral_id: str,
    resolve_request: ResolveDeferralRequest,
    auth: AuthContext = Depends(require_authority)
):
    """
    Resolve a pending deferral with guidance.

    Allows a WA with AUTHORITY role to approve, reject, or modify
    a deferred decision. The resolution includes wisdom guidance
    integrated into the decision.

    Requires AUTHORITY role.
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
        # Create deferral response with integrated guidance
        deferral_response = DeferralResponse(
            approved=(resolve_request.resolution == "approve"),
            reason=resolve_request.guidance or f"Resolved by {auth.user_id}",
            modified_time=None,  # Time modifications not needed in simplified version
            wa_id=auth.user_id,  # Use authenticated user as WA
            signature=f"api_{auth.user_id}_{datetime.now(timezone.utc).isoformat()}"
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




@router.get("/permissions", response_model=SuccessResponse[PermissionsListResponse])
async def get_permissions(
    request: Request,
    wa_id: Optional[str] = Query(None, description="WA ID to get permissions for (defaults to current user)"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get WA permission status.

    Returns permission status for a specific WA. If no WA ID
    is provided, returns permissions for the authenticated user.
    This simplified endpoint focuses on viewing permissions only.

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
