"""User management API routes."""

from typing import List, Optional, TypeVar, Generic, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from ..services.auth_service import APIAuthService
from ciris_engine.schemas.runtime.api import (
    APIRole,
    APIUserInfo
)
from ciris_engine.schemas.services.authority_core import WARole
from ..dependencies.auth import (
    get_auth_service,
    get_auth_context,
    check_permissions
)
from ciris_engine.schemas.api.auth import AuthContext

router = APIRouter(prefix="/users", tags=["users"])


# Generic models
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


# Request/Response models
class UserSummary(BaseModel):
    """Summary information about a user."""
    user_id: str
    username: str
    auth_type: str = Field(description="password, oauth, api_key")
    api_role: APIRole
    wa_role: Optional[WARole] = None
    wa_id: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_email: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True


class UserDetail(UserSummary):
    """Detailed user information."""
    permissions: List[str]
    oauth_external_id: Optional[str] = None
    wa_parent_id: Optional[str] = None
    wa_auto_minted: bool = False
    api_keys_count: int = 0


class UpdateUserRequest(BaseModel):
    """Request to update user information."""
    api_role: Optional[APIRole] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """Request to change user password."""
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    api_role: APIRole = APIRole.OBSERVER


class MintWARequest(BaseModel):
    """Request to mint user as Wise Authority."""
    wa_role: WARole = Field(description="Role to grant: AUTHORITY or OBSERVER")
    signature: str = Field(description="Ed25519 signature from ROOT private key")
    
    class Config:
        schema_extra = {
            "example": {
                "wa_role": "AUTHORITY",
                "signature": "base64_encoded_signature"
            }
        }


@router.get("", response_model=PaginatedResponse[UserSummary])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    auth_type: Optional[str] = None,
    api_role: Optional[APIRole] = None,
    wa_role: Optional[WARole] = None,
    is_active: Optional[bool] = None,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service),
    _: None = Depends(check_permissions(["users.read"]))
):
    """
    List all users with optional filtering.
    
    Requires: users.read permission (ADMIN or higher)
    """
    # Get all WA certificates from the auth service
    users = await auth_service.list_users(
        search=search,
        auth_type=auth_type,
        api_role=api_role,
        wa_role=wa_role,
        is_active=is_active
    )
    
    # Paginate results
    total = len(users)
    start = (page - 1) * page_size
    end = start + page_size
    
    # Convert to UserSummary objects
    items = []
    for user in users[start:end]:
        items.append(UserSummary(
            user_id=user.wa_id,
            username=user.name,
            auth_type=user.auth_type,
            api_role=user.api_role,
            wa_role=user.wa_role,
            wa_id=user.wa_id if user.wa_role else None,
            oauth_provider=user.oauth_provider,
            oauth_email=user.oauth_email,
            created_at=user.created_at,
            last_login=user.last_login,
            is_active=user.is_active
        ))
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )


@router.post("", response_model=UserDetail)
async def create_user(
    request: CreateUserRequest,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service),
    _: None = Depends(check_permissions(["users.write"]))
):
    """
    Create a new user account.
    
    Requires: users.write permission (SYSTEM_ADMIN only)
    """
    # Check if username already exists
    existing = await auth_service.get_user_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )
    
    # Create the user
    user = await auth_service.create_user(
        username=request.username,
        password=request.password,
        api_role=request.api_role
    )
    
    if not user:
        raise HTTPException(
            status_code=500,
            detail="Failed to create user"
        )
    
    # Return the created user details
    return await get_user(user.wa_id, auth, auth_service, None)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service),
    _: None = Depends(check_permissions(["users.read"]))
):
    """
    Get detailed information about a specific user.
    
    Requires: users.read permission (ADMIN or higher)
    """
    user = await auth_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get permissions based on role
    permissions = auth_service.get_permissions_for_role(user.api_role)
    
    # Count API keys
    api_keys = await auth_service.list_user_api_keys(user_id)
    
    return UserDetail(
        user_id=user.wa_id,
        username=user.name,
        auth_type=user.auth_type,
        api_role=user.api_role,
        wa_role=user.wa_role,
        wa_id=user.wa_id if user.wa_role else None,
        oauth_provider=user.oauth_provider,
        oauth_email=user.oauth_email,
        oauth_external_id=user.oauth_external_id,
        created_at=user.created_at,
        last_login=user.last_login,
        is_active=user.is_active,
        permissions=permissions,
        wa_parent_id=user.wa_parent_id,
        wa_auto_minted=user.wa_auto_minted,
        api_keys_count=len(api_keys)
    )


@router.put("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service),
    _: None = Depends(check_permissions(["users.write"]))
):
    """
    Update user information (role, active status).
    
    Requires: users.write permission (SYSTEM_ADMIN only)
    """
    # Prevent self-demotion
    if user_id == auth.user_id and request.api_role:
        if request.api_role.value < auth.role.value:
            raise HTTPException(
                status_code=400, 
                detail="Cannot demote your own role"
            )
    
    # Update user
    user = await auth_service.update_user(
        user_id=user_id,
        api_role=request.api_role,
        is_active=request.is_active
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return updated user details
    return await get_user(user_id, auth, auth_service, None)


@router.put("/{user_id}/password")
async def change_password(
    user_id: str,
    request: ChangePasswordRequest,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    Change user password.
    
    Users can change their own password.
    SYSTEM_ADMIN can change any password without knowing current.
    """
    # Check permissions
    if user_id != auth.user_id:
        # Only SYSTEM_ADMIN can change other users' passwords
        await check_permissions(["users.write"])(auth)
        # SYSTEM_ADMIN doesn't need to provide current password
        success = await auth_service.change_password(
            user_id=user_id,
            new_password=request.new_password,
            skip_current_check=True
        )
    else:
        # Users changing their own password must provide current
        success = await auth_service.change_password(
            user_id=user_id,
            new_password=request.new_password,
            current_password=request.current_password
        )
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Failed to change password. Check current password."
        )
    
    return {"message": "Password changed successfully"}


@router.post("/{user_id}/mint-wa", response_model=UserDetail)
async def mint_wise_authority(
    user_id: str,
    request: MintWARequest,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    Mint a user as a Wise Authority.
    
    Requires: SYSTEM_ADMIN role and valid Ed25519 signature from ROOT private key.
    
    The signature should be over the message:
    "MINT_WA:{user_id}:{wa_role}:{timestamp}"
    """
    # Check if user is SYSTEM_ADMIN
    if auth.role != APIRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only SYSTEM_ADMIN can mint Wise Authorities"
        )
    
    # Validate that request.wa_role is not ROOT
    if request.wa_role == WARole.ROOT:
        raise HTTPException(
            status_code=400,
            detail="Cannot mint new ROOT authorities. ROOT is singular."
        )
    
    # Verify the ROOT signature
    verified = await auth_service.verify_root_signature(
        user_id=user_id,
        wa_role=request.wa_role,
        signature=request.signature
    )
    
    if not verified:
        raise HTTPException(
            status_code=401,
            detail="Invalid ROOT signature"
        )
    
    # Mint the user as WA
    user = await auth_service.mint_wise_authority(
        user_id=user_id,
        wa_role=request.wa_role,
        minted_by=auth.user_id
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return updated user details
    return await get_user(user_id, auth, auth_service, None)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service),
    _: None = Depends(check_permissions(["users.delete"]))
):
    """
    Deactivate a user account.
    
    Requires: users.delete permission (SYSTEM_ADMIN only)
    """
    # Prevent self-deactivation
    if user_id == auth.user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own account"
        )
    
    success = await auth_service.deactivate_user(user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deactivated successfully"}


@router.get("/{user_id}/api-keys")
async def list_user_api_keys(
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    auth_service: APIAuthService = Depends(get_auth_service)
):
    """
    List API keys for a user.
    
    Users can view their own keys.
    ADMIN+ can view any user's keys.
    """
    # Check permissions
    if user_id != auth.user_id:
        await check_permissions(["users.read"])(auth)
    
    keys = await auth_service.list_user_api_keys(user_id)
    
    # Mask the actual key values for security
    return [
        {
            "key_id": key.key_id,
            "key_prefix": key.key_value[:8] + "...",
            "created_at": key.created_at,
            "last_used": key.last_used,
            "expires_at": key.expires_at,
            "is_active": key.is_active
        }
        for key in keys
    ]