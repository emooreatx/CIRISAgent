"""
Wise Authority Service - Authorization and Guidance

This service handles:
- Authorization checks (what can you do?)
- Decision deferrals to humans
- Guidance for complex situations
- Permission management

Authentication (who are you?) is handled by AuthenticationService.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import jwt

from ciris_engine.protocols.services.governance.wise_authority import WiseAuthorityServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.logic.adapters.base import Service
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.authority_core import (
    WACertificate, WARole, WACertificateRequest,
    DeferralRequest, DeferralResponse,
    GuidanceRequest, GuidanceResponse,
    WARoleMintRequest, WAToken,
    DeferralApprovalContext, WAPermission
)
from ciris_engine.schemas.services.authority.wise_authority import (
    AuthenticationResult, WAUpdate, TokenVerification, PendingDeferral,
    DeferralResolution
)
from ciris_engine.schemas.services.context import DeferralContext, GuidanceContext
from ciris_engine.logic.services.infrastructure.authentication import AuthenticationService
from ciris_engine.logic.config import get_sqlite_db_full_path

logger = logging.getLogger(__name__)

class WiseAuthorityService(Service, WiseAuthorityServiceProtocol, ServiceProtocol):
    """
    Wise Authority Service for authorization and guidance.
    
    Handles:
    - Authorization checks
    - Decision deferrals
    - Guidance requests
    - Permission management
    """
    
    def __init__(self, time_service: TimeService, auth_service: AuthenticationService, db_path: Optional[str] = None):
        """Initialize the WA authorization service."""
        # Use configured database if not specified
        self.db_path = db_path or get_sqlite_db_full_path()
        
        # Store injected services
        self.time_service = time_service
        self.auth_service = auth_service
        
        # Deferral tracking
        self.deferrals: Dict[str, DeferralContext] = {}
        self.pending_guidance: List[GuidanceRequest] = []
        
        # Service state
        self._initialized = False
        self._started = False
        
        logger.info(f"Consolidated WA Service initialized with DB: {self.db_path}")
    
    async def start(self) -> None:
        """Start the service."""
        if self._started:
            return
            
        # Bootstrap if needed
        await self.auth_service.bootstrap_if_needed()
        
        # Load any pending deferrals from persistence
        # TODO: Implement deferral persistence
        
        self._started = True
        logger.info("Consolidated WA Service started")
    
    async def stop(self) -> None:
        """Stop the service."""
        self._started = False
        logger.info("Consolidated WA Service stopped")
    
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="WiseAuthorityService",
            actions=[
                # Authorization
                "check_authorization", "request_approval",
                # Guidance
                "get_guidance",
                # Deferrals
                "send_deferral", "get_pending_deferrals", "resolve_deferral",
                # Permissions
                "grant_permission", "revoke_permission", "list_permissions"
            ],
            version="1.0.0",
            dependencies=["SecretsService", "GraphAuditService"]
        )
    
    # ========== Authorization Operations ==========
    
    async def check_authorization(self, wa_id: str, action: str, resource: Optional[str] = None) -> bool:
        """Check if a WA is authorized for an action on a resource.
        
        Simple role-based authorization:
        - ROOT: Can do everything
        - AUTHORITY: Can approve/reject deferrals, provide guidance (no minting)
        - OBSERVER: Can only read and send messages
        """
        wa = await self.auth_service.get_wa(wa_id)
        if not wa or not wa.active:
            return False
        
        # Root can do anything
        if wa.role == WARole.ROOT:
            return True
        
        # Authority can do most things except mint WAs
        if wa.role == WARole.AUTHORITY:
            return action not in ["mint_wa", "create_wa", "bootstrap_root"]
        
        # Observer can only read and send messages
        if wa.role == WARole.OBSERVER:
            return action in ["read", "send_message", "observe", "get_status"]
        
        return False
    
    async def request_approval(self, action: str, context: DeferralApprovalContext) -> bool:
        """Request approval for an action - may defer to human.
        
        Returns True if immediately approved (e.g., requester is ROOT),
        False if deferred to human WA.
        """
        # Check if requester can self-approve
        can_self_approve = await self.check_authorization(
            context.requester_id, 
            action,
            context.metadata.get("resource") if context.metadata else None
        )
        
        if can_self_approve:
            logger.info(f"Action {action} auto-approved for {context.requester_id}")
            return True
        
        # Create a deferral for human approval
        deferral_context = {
            "action": action,
            "requester": context.requester_id,
        }
        # Flatten action params into context
        for key, value in context.action_params.items():
            deferral_context[f"param_{key}"] = str(value)
            
        deferral = DeferralRequest(
            task_id=context.task_id,
            thought_id=context.thought_id,
            reason=f"Action '{action}' requires human approval",
            defer_until=self.time_service.now() + timedelta(hours=24),
            context=deferral_context
        )
        
        deferral_id = await self.send_deferral(deferral)
        logger.info(f"Created deferral {deferral_id} for action {action}")
        return False
    
    async def grant_permission(self, wa_id: str, _permission: str, resource: Optional[str] = None) -> bool:
        """Grant a permission to a WA.
        
        In our simplified model, permissions are role-based.
        This method could be used to promote a WA to a higher role.
        """
        # For beta, we don't support dynamic permission grants
        # Permissions are determined by role
        logger.warning(f"grant_permission called but permissions are role-based. "
                      f"Use update_wa to change roles instead.")
        return False
    
    async def revoke_permission(self, wa_id: str, _permission: str, resource: Optional[str] = None) -> bool:
        """Revoke a permission from a WA.
        
        In our simplified model, permissions are role-based.
        This method could be used to demote or deactivate a WA.
        """
        # For beta, we don't support dynamic permission revocation
        # Permissions are determined by role
        logger.warning(f"revoke_permission called but permissions are role-based. "
                      f"Use update_wa to change roles or revoke_wa to deactivate.")
        return False
    
    async def list_permissions(self, wa_id: str) -> List[WAPermission]:
        """List all permissions for a WA.
        
        Returns permissions based on the WA's role.
        """
        wa = await self.auth_service.get_wa(wa_id)
        if not wa:
            return []
        
        # Define role-based permissions
        role_permissions = {
            WARole.ROOT: [
                "*"  # Root can do everything
            ],
            WARole.AUTHORITY: [
                "read", "write", "approve_deferrals", "provide_guidance",
                "manage_tasks", "access_audit", "manage_memory"
            ],
            WARole.OBSERVER: [
                "read", "send_message", "observe"
            ]
        }
        
        permissions = role_permissions.get(wa.role, [])
        
        # Convert to WAPermission objects for protocol compliance
        return [
            WAPermission(
                permission_id=f"{wa.wa_id}_{perm}",
                wa_id=wa.wa_id,
                permission_type="role_based",
                permission_name=perm,
                resource=None,
                granted_by="system",
                granted_at=wa.created_at,
                expires_at=None,
                metadata={"role": wa.role.value}
            )
            for perm in permissions
        ]
    
    
    
    
    
    
    # ========== Deferral Operations ==========
    
    async def send_deferral(self, deferral: DeferralRequest) -> str:
        """Send a deferral to appropriate WA."""
        try:
            # Generate deferral ID
            deferral_id = f"defer_{deferral.thought_id}_{self.time_service.timestamp()}"
            
            # Convert to DeferralContext for internal storage
            context = DeferralContext(
                task_id=deferral.task_id,
                thought_id=deferral.thought_id,
                reason=deferral.reason,
                defer_until=deferral.defer_until,
                priority="normal",  # Default priority
                metadata=deferral.context
            )
            
            self.deferrals[deferral_id] = context
            
            # TODO: Notify appropriate WA based on context
            # For now, just log
            logger.info(f"Deferral created: {deferral_id} for thought {deferral.thought_id}")
            
            # TODO: Send notification via appropriate channel (email, webhook, etc.)
            
            return deferral_id
        except Exception as e:
            logger.error(f"Failed to send deferral: {e}")
            raise
    
    async def get_pending_deferrals(self, wa_id: Optional[str] = None) -> List[PendingDeferral]:
        """Get pending deferrals."""
        result = []
        for def_id, context in self.deferrals.items():
            if context.metadata and context.metadata.get("resolved"):
                continue
                
            deferral = PendingDeferral(
                deferral_id=def_id,
                created_at=datetime.fromisoformat(context.metadata.get("created_at", self.time_service.now().isoformat())) if context.metadata else self.time_service.now(),
                deferred_by="ciris_agent",  # TODO: Get from context
                task_id=context.task_id,
                thought_id=context.thought_id,
                reason=context.reason,
                channel_id=context.metadata.get("channel_id") if context.metadata else None,
                user_id=context.metadata.get("user_id") if context.metadata else None,
                priority=context.priority.value if hasattr(context.priority, 'value') else str(context.priority),
                assigned_wa_id=context.metadata.get("assigned_to") if context.metadata else None,
                requires_role=context.metadata.get("requires_role") if context.metadata else None,
                status="pending"
            )
            
            # Filter by WA if specified
            if wa_id and deferral.assigned_wa_id != wa_id:
                continue
                
            result.append(deferral)
        
        return result
    
    async def resolve_deferral(self, deferral_id: str, response: DeferralResponse) -> bool:
        """Resolve a deferral."""
        if deferral_id not in self.deferrals:
            logger.error(f"Deferral {deferral_id} not found")
            return False
        
        context = self.deferrals[deferral_id]
        if not context.metadata:
            context.metadata = {}
            
        context.metadata["resolved"] = True
        context.metadata["approved"] = response.approved
        context.metadata["resolution_reason"] = response.reason or ""
        context.metadata["resolved_by"] = response.wa_id
        context.metadata["resolved_at"] = self.time_service.now().isoformat()
        
        # If response modified the defer time, update it
        if response.modified_time:
            context.defer_until = response.modified_time
        
        logger.info(f"Deferral {deferral_id} {'approved' if response.approved else 'rejected'} by {response.wa_id}")
        
        # TODO: Trigger task reactivation if appropriate
        
        return True
    
    # ========== Guidance Operations ==========
    
    async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]:
        """Fetch guidance from a Wise Authority for a given context.
        
        This is the WiseBus-compatible method that adapters call.
        Guidance comes ONLY from authorized Wise Authorities - never 
        generated by the system.
        """
        try:
            # Log the guidance request
            logger.info(f"Guidance requested for thought {context.thought_id}: {context.question}")
            
            # Check if we have any stored guidance for this context
            # In the full implementation, this would query the database
            # for guidance provided by WAs through the API or other channels
            
            # TODO: Implement actual guidance fetching from WA responses
            # This would typically:
            # 1. Check if any WA has responded to this specific guidance request
            # 2. Return the guidance if available
            # 3. Return None if no WA has provided guidance yet
            
            logger.debug(f"No WA guidance available yet for thought {context.thought_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch guidance: {e}", exc_info=True)
            return None
    
    async def get_guidance(self, request: GuidanceRequest) -> GuidanceResponse:
        """Get guidance for a situation (Protocol method).
        
        This wraps fetch_guidance to comply with the protocol.
        """
        # Convert GuidanceRequest to GuidanceContext for internal use
        context = GuidanceContext(
            thought_id=f"guidance_{self.time_service.timestamp()}",
            task_id=f"guidance_task_{self.time_service.timestamp()}",
            question=request.context,
            ethical_considerations=[],  # Could extract from options
            domain_context={
                "urgency": request.urgency,
                "options": ", ".join(request.options) if request.options else "",
                "recommendation": request.recommendation or ""
            }
        )
        
        # Use the existing fetch_guidance method
        guidance = await self.fetch_guidance(context)
        
        if guidance:
            # Parse the guidance response (assuming it's structured)
            return GuidanceResponse(
                selected_option=None,  # Would be parsed from guidance
                custom_guidance=guidance,
                reasoning="Guidance provided by Wise Authority",
                wa_id="unknown",  # Would come from the actual WA
                signature=""  # Would be signed by the WA
            )
        else:
            # No guidance available
            return GuidanceResponse(
                selected_option=None,
                custom_guidance=None,
                reasoning="No Wise Authority guidance available yet",
                wa_id="system",
                signature=""
            )
    
    
    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        pending_count = len([d for d in self.deferrals.values() 
                           if not (d.metadata and d.metadata.get("resolved"))])
        
        return ServiceStatus(
            service_name="WiseAuthorityService",
            service_type="governance_service",
            is_healthy=self._started,
            uptime_seconds=0.0,  # Would need to track start time
            last_error=None,
            metrics={
                "pending_deferrals": float(pending_count),
                "total_deferrals": float(len(self.deferrals)),
                "pending_guidance_requests": float(len(self.pending_guidance))
            },
            last_health_check=self.time_service.now()
        )
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._started
    
    
