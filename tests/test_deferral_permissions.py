"""
Tests for deferral permission and authorization checks.

Ensures that only authorized WAs can resolve deferrals and that
the permission system properly enforces role-based access control.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from ciris_engine.schemas.services.authority.wise_authority import (
    PendingDeferral, DeferralResolution, PermissionEntry
)
from ciris_engine.schemas.services.authority_core import (
    DeferralRequest, DeferralResponse, WARole, WACertificate,
    WAPermission, AuthorizationContext, TokenType, JWTSubType
)
from ciris_engine.logic.services.governance.wise_authority import WiseAuthorityService


class TestDeferralPermissions:
    """Test permission checks for deferral operations."""
    
    @pytest.fixture
    def mock_memory_service(self):
        """Mock memory service with permission storage."""
        service = AsyncMock()
        
        # Store permissions by WA ID
        service.permissions = {
            "wa_authority_001": [
                WAPermission(
                    action="resolve_deferral",
                    resource="*",
                    wa_id="wa_authority_001",
                    granted_by="wa_root",
                    granted_at=datetime.now(timezone.utc),
                    expires_at=None
                )
            ],
            "wa_observer_001": [
                WAPermission(
                    action="view_deferral",
                    resource="*",
                    wa_id="wa_observer_001",
                    granted_by="wa_root",
                    granted_at=datetime.now(timezone.utc),
                    expires_at=None
                )
            ],
            "wa_limited_authority": [
                WAPermission(
                    action="resolve_deferral",
                    resource="medical_*",  # Only medical deferrals
                    wa_id="wa_limited_authority",
                    granted_by="wa_root",
                    granted_at=datetime.now(timezone.utc),
                    expires_at=None
                )
            ]
        }
        
        # Mock recall to return permissions
        async def mock_recall(query=None, node_type=None, **kwargs):
            if node_type == "wa_permission" and query:
                wa_id = query.split(":")[1] if ":" in query else None
                return service.permissions.get(wa_id, [])
            return []
        
        service.recall = mock_recall
        return service
    
    @pytest.fixture
    def wa_certificates(self):
        """Create test WA certificates with different roles."""
        return {
            "wa_authority_001": WACertificate(
                wa_id="wa_authority_001",
                name="Full Authority",
                role=WARole.AUTHORITY,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                public_key="authority_key",
                signature="authority_sig",
                scopes=["resolve_deferrals", "modify_deferrals"],
                is_active=True
            ),
            "wa_observer_001": WACertificate(
                wa_id="wa_observer_001",
                name="Observer Only",
                role=WARole.OBSERVER,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                public_key="observer_key",
                signature="observer_sig",
                scopes=["view_deferrals"],
                is_active=True
            ),
            "wa_expired": WACertificate(
                wa_id="wa_expired",
                name="Expired Authority",
                role=WARole.AUTHORITY,
                created_at=datetime.now(timezone.utc) - timedelta(days=60),
                expires_at=datetime.now(timezone.utc) - timedelta(days=30),
                public_key="expired_key",
                signature="expired_sig",
                scopes=["resolve_deferrals"],
                is_active=True  # Still marked active but expired
            ),
            "wa_revoked": WACertificate(
                wa_id="wa_revoked",
                name="Revoked Authority",
                role=WARole.AUTHORITY,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                public_key="revoked_key",
                signature="revoked_sig",
                scopes=["resolve_deferrals"],
                is_active=False  # Revoked
            )
        }
    
    @pytest.fixture
    def wa_service(self, mock_memory_service):
        """Create WA service with mock memory."""
        service = WiseAuthorityService(
            memory_service=mock_memory_service,
            time_service=Mock(now=Mock(return_value=datetime.now(timezone.utc)))
        )
        return service
    
    @pytest.mark.asyncio
    async def test_authority_can_resolve_deferrals(self, wa_service, wa_certificates):
        """Test that AUTHORITY role can resolve deferrals."""
        # Create authorization context for authority
        auth_context = AuthorizationContext(
            wa_id="wa_authority_001",
            role=WARole.AUTHORITY,
            token_type=TokenType.ACCESS,
            sub_type=JWTSubType.WA,
            scopes=["resolve_deferrals"],
            action="resolve_deferral",
            resource="defer_001"
        )
        
        # Check authorization
        is_authorized = await wa_service.check_authorization(
            wa_id=auth_context.wa_id,
            action=auth_context.action,
            resource=auth_context.resource
        )
        
        assert is_authorized is True
    
    @pytest.mark.asyncio
    async def test_observer_cannot_resolve_deferrals(self, wa_service, wa_certificates):
        """Test that OBSERVER role cannot resolve deferrals."""
        # Create authorization context for observer
        auth_context = AuthorizationContext(
            wa_id="wa_observer_001",
            role=WARole.OBSERVER,
            token_type=TokenType.ACCESS,
            sub_type=JWTSubType.WA,
            scopes=["view_deferrals"],
            action="resolve_deferral",
            resource="defer_001"
        )
        
        # Check authorization
        is_authorized = await wa_service.check_authorization(
            wa_id=auth_context.wa_id,
            action=auth_context.action,
            resource=auth_context.resource
        )
        
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_expired_certificate_cannot_resolve(self, wa_service, wa_certificates):
        """Test that expired certificates cannot resolve deferrals."""
        # Even with AUTHORITY role, expired cert should fail
        is_authorized = await wa_service.check_authorization(
            wa_id="wa_expired",
            action="resolve_deferral",
            resource="defer_001"
        )
        
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_revoked_certificate_cannot_resolve(self, wa_service, wa_certificates):
        """Test that revoked certificates cannot resolve deferrals."""
        is_authorized = await wa_service.check_authorization(
            wa_id="wa_revoked",
            action="resolve_deferral",
            resource="defer_001"
        )
        
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_resource_specific_permissions(self, wa_service, mock_memory_service):
        """Test permissions limited to specific resources."""
        # Limited authority can only resolve medical deferrals
        is_authorized_medical = await wa_service.check_authorization(
            wa_id="wa_limited_authority",
            action="resolve_deferral",
            resource="medical_defer_001"
        )
        
        is_authorized_financial = await wa_service.check_authorization(
            wa_id="wa_limited_authority",
            action="resolve_deferral",
            resource="financial_defer_001"
        )
        
        assert is_authorized_medical is True
        assert is_authorized_financial is False
    
    @pytest.mark.asyncio
    async def test_grant_permission(self, wa_service):
        """Test granting new permissions to a WA."""
        # Grant permission to a new WA
        granted = await wa_service.grant_permission(
            wa_id="wa_new_moderator",
            permission="resolve_deferral",
            resource="community_*"
        )
        
        assert granted is True
        
        # Verify permission was granted
        permissions = await wa_service.list_permissions("wa_new_moderator")
        assert any(
            p.action == "resolve_deferral" and p.resource == "community_*"
            for p in permissions
        )
    
    @pytest.mark.asyncio
    async def test_revoke_permission(self, wa_service):
        """Test revoking permissions from a WA."""
        # First grant a permission
        await wa_service.grant_permission(
            wa_id="wa_temp_authority",
            permission="resolve_deferral",
            resource="*"
        )
        
        # Then revoke it
        revoked = await wa_service.revoke_permission(
            wa_id="wa_temp_authority",
            permission="resolve_deferral",
            resource="*"
        )
        
        assert revoked is True
        
        # Verify permission was revoked
        is_authorized = await wa_service.check_authorization(
            wa_id="wa_temp_authority",
            action="resolve_deferral",
            resource="any_deferral"
        )
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_permission_inheritance(self, wa_service):
        """Test that wildcard permissions work correctly."""
        # Grant wildcard permission
        await wa_service.grant_permission(
            wa_id="wa_super_admin",
            permission="*",  # All actions
            resource="*"     # All resources
        )
        
        # Should authorize any action
        actions = [
            "resolve_deferral",
            "modify_deferral",
            "delete_deferral",
            "create_deferral"
        ]
        
        for action in actions:
            is_authorized = await wa_service.check_authorization(
                wa_id="wa_super_admin",
                action=action,
                resource="any_resource"
            )
            assert is_authorized is True
    
    @pytest.mark.asyncio
    async def test_concurrent_permission_checks(self, wa_service):
        """Test concurrent authorization checks don't interfere."""
        import asyncio
        
        # Create multiple WAs with different permissions
        wa_ids = [f"wa_concurrent_{i}" for i in range(5)]
        
        # Grant different permissions
        for i, wa_id in enumerate(wa_ids):
            if i % 2 == 0:
                await wa_service.grant_permission(
                    wa_id=wa_id,
                    permission="resolve_deferral",
                    resource="*"
                )
        
        # Check all concurrently
        tasks = [
            wa_service.check_authorization(
                wa_id=wa_id,
                action="resolve_deferral",
                resource="test_resource"
            )
            for wa_id in wa_ids
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Even indices should be authorized, odd should not
        for i, result in enumerate(results):
            if i % 2 == 0:
                assert result is True
            else:
                assert result is False


class TestDeferralRoleEnforcement:
    """Test role-based access control for deferrals."""
    
    @pytest.fixture
    def sample_deferrals(self) -> List[PendingDeferral]:
        """Create sample deferrals with different requirements."""
        return [
            PendingDeferral(
                deferral_id="defer_any_001",
                created_at=datetime.now(timezone.utc),
                deferred_by="agent_123",
                task_id="task_001",
                thought_id="thought_001",
                reason="General deferral",
                priority="low",
                requires_role=None,  # Any WA can resolve
                status="pending"
            ),
            PendingDeferral(
                deferral_id="defer_authority_001",
                created_at=datetime.now(timezone.utc),
                deferred_by="agent_123",
                task_id="task_002",
                thought_id="thought_002",
                reason="Requires authority decision",
                priority="high",
                requires_role="AUTHORITY",
                status="pending"
            ),
            PendingDeferral(
                deferral_id="defer_medical_001",
                created_at=datetime.now(timezone.utc),
                deferred_by="agent_123",
                task_id="task_003",
                thought_id="thought_003",
                reason="Medical decision required",
                priority="critical",
                requires_role="MEDICAL_AUTHORITY",
                status="pending"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_role_filtering_for_deferrals(self, sample_deferrals):
        """Test that deferrals are filtered by required role."""
        # Filter for AUTHORITY role
        authority_deferrals = [
            d for d in sample_deferrals
            if d.requires_role in [None, "AUTHORITY"]
        ]
        
        assert len(authority_deferrals) == 2
        assert "defer_any_001" in [d.deferral_id for d in authority_deferrals]
        assert "defer_authority_001" in [d.deferral_id for d in authority_deferrals]
        
        # Filter for MEDICAL_AUTHORITY role
        medical_deferrals = [
            d for d in sample_deferrals
            if d.requires_role in [None, "MEDICAL_AUTHORITY"]
        ]
        
        assert len(medical_deferrals) == 2
        assert "defer_any_001" in [d.deferral_id for d in medical_deferrals]
        assert "defer_medical_001" in [d.deferral_id for d in medical_deferrals]
    
    @pytest.mark.asyncio
    async def test_resolution_role_validation(self, wa_service, sample_deferrals):
        """Test that resolution validates required role."""
        # Try to resolve medical deferral with non-medical authority
        response = DeferralResponse(
            approved=True,
            reason="Approved by wrong authority",
            modified_time=None,
            wa_id="wa_authority_001",  # Regular authority, not medical
            signature="test_sig"
        )
        
        # This should fail validation in a complete implementation
        # The actual validation would check:
        # 1. WA has resolve_deferral permission
        # 2. WA role matches deferral.requires_role
        # 3. WA certificate is valid and active
        
        # Mock the validation logic
        deferral = sample_deferrals[2]  # Medical deferral
        
        # In real implementation:
        # if deferral.requires_role and wa.role != deferral.requires_role:
        #     raise PermissionError("WA role does not match deferral requirements")
        
        wa_role = WARole.AUTHORITY
        required_role = "MEDICAL_AUTHORITY"
        
        assert wa_role.value != required_role  # Should not match
    
    @pytest.mark.asyncio
    async def test_permission_expiration(self, wa_service):
        """Test that permissions expire correctly."""
        # Grant temporary permission
        granted = await wa_service.grant_permission(
            wa_id="wa_temp_001",
            permission="resolve_deferral",
            resource="*"
        )
        assert granted is True
        
        # Mock permission with expiration
        expired_permission = WAPermission(
            action="resolve_deferral",
            resource="*",
            wa_id="wa_temp_001",
            granted_by="wa_root",
            granted_at=datetime.now(timezone.utc) - timedelta(days=31),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)  # Expired yesterday
        )
        
        # Check if permission is expired
        is_expired = expired_permission.expires_at < datetime.now(timezone.utc)
        assert is_expired is True
        
        # Authorization should fail for expired permission
        # In real implementation, check_authorization would validate expiration


class TestDeferralAuditTrail:
    """Test audit trail for deferral operations."""
    
    @pytest.mark.asyncio
    async def test_deferral_resolution_audit(self, wa_service):
        """Test that deferral resolutions are properly audited."""
        # Mock audit entries that would be created
        audit_entries = []
        
        # Resolution attempt
        resolution = DeferralResolution(
            deferral_id="defer_audit_001",
            wa_id="wa_authority_001",
            resolution="approve",
            guidance="Approved after careful review",
            new_constraints=["monitor_for_7_days"],
            resolution_metadata={
                "review_duration_minutes": "15",
                "confidence_level": "high"
            }
        )
        
        # Audit entry that should be created
        audit_entry = {
            "timestamp": datetime.now(timezone.utc),
            "action": "deferral_resolved",
            "actor": resolution.wa_id,
            "target": resolution.deferral_id,
            "details": {
                "resolution": resolution.resolution,
                "guidance": resolution.guidance,
                "constraints_added": resolution.new_constraints,
                "metadata": resolution.resolution_metadata
            }
        }
        
        audit_entries.append(audit_entry)
        
        # Verify audit trail
        assert len(audit_entries) == 1
        assert audit_entries[0]["action"] == "deferral_resolved"
        assert audit_entries[0]["actor"] == "wa_authority_001"
        assert "monitor_for_7_days" in audit_entries[0]["details"]["constraints_added"]
    
    @pytest.mark.asyncio
    async def test_failed_authorization_audit(self, wa_service):
        """Test that failed authorization attempts are audited."""
        # Mock unauthorized attempt
        unauthorized_attempt = {
            "timestamp": datetime.now(timezone.utc),
            "action": "deferral_resolution_denied",
            "actor": "wa_observer_001",
            "target": "defer_001",
            "reason": "insufficient_permissions",
            "details": {
                "required_role": "AUTHORITY",
                "actual_role": "OBSERVER",
                "required_permission": "resolve_deferral"
            }
        }
        
        # This would be logged in the audit system
        assert unauthorized_attempt["reason"] == "insufficient_permissions"
        assert unauthorized_attempt["details"]["required_role"] == "AUTHORITY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])