"""Authority service schemas."""

from ciris_engine.schemas.services.authority.wise_authority import (
    PermissionEntry,
    ApprovalRequestContext,
    AuthenticationResult,
    WAUpdate,
    TokenVerification,
    PendingDeferral,
    DeferralResolution,
    WAResource,
    OAuthConfig
)

from ciris_engine.schemas.services.authority.jwt import (
    JWTAlgorithm,
    JWTHeader,
    JWTClaims,
    JWTToken,
    JWTValidationResult
)

__all__ = [
    # Wise Authority schemas
    "PermissionEntry",
    "ApprovalRequestContext", 
    "AuthenticationResult",
    "WAUpdate",
    "TokenVerification",
    "PendingDeferral",
    "DeferralResolution",
    "WAResource",
    "OAuthConfig",
    # JWT schemas
    "JWTAlgorithm",
    "JWTHeader",
    "JWTClaims",
    "JWTToken",
    "JWTValidationResult"
]