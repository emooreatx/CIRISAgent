"""Unit tests for Wise Authority Service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock
import tempfile
import os

from ciris_engine.logic.services.governance.wise_authority import WiseAuthorityService
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.logic.services.infrastructure.authentication import AuthenticationService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.authority_core import (
    WARole, DeferralRequest, DeferralResponse, GuidanceRequest, GuidanceResponse,
    WAPermission, DeferralApprovalContext
)
from ciris_engine.schemas.services.context import (
    GuidanceContext, DeferralContext
)


@pytest.fixture
def time_service():
    """Create a time service for testing."""
    return TimeService()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


@pytest.fixture
async def auth_service(temp_db, time_service):
    """Create an authentication service for testing."""
    service = AuthenticationService(
        db_path=temp_db,
        time_service=time_service,
        key_dir=None
    )
    await service.start()
    
    # Mock some methods for testing
    service.get_wa = AsyncMock(return_value=MagicMock(
        wa_id="wa-2025-06-24-TEST01",
        role=WARole.AUTHORITY,
        active=True,
        created_at=datetime.now(timezone.utc)
    ))
    service.bootstrap_if_needed = AsyncMock()
    
    yield service
    await service.stop()


@pytest.fixture
async def wise_authority_service(auth_service, time_service, temp_db):
    """Create a wise authority service for testing."""
    service = WiseAuthorityService(
        time_service=time_service,
        auth_service=auth_service,
        db_path=temp_db
    )
    yield service


@pytest.mark.asyncio
async def test_wise_authority_lifecycle(wise_authority_service):
    """Test WiseAuthorityService start/stop lifecycle."""
    # Start
    await wise_authority_service.start()
    # Service should be ready
    assert wise_authority_service._started is True
    assert await wise_authority_service.is_healthy()
    
    # Stop
    await wise_authority_service.stop()
    # Should complete without error
    assert wise_authority_service._started is False


@pytest.mark.asyncio
async def test_check_authorization(wise_authority_service, auth_service):
    """Test authorization checking."""
    await wise_authority_service.start()
    
    # Test ROOT authorization - can do everything
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-ROOT01",
        role=WARole.ROOT,
        active=True
    )
    assert await wise_authority_service.check_authorization("wa-2025-06-24-ROOT01", "mint_wa") is True
    assert await wise_authority_service.check_authorization("wa-2025-06-24-ROOT01", "approve_deferrals") is True
    
    # Test AUTHORITY authorization - can't mint WAs
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-AUTH01",
        role=WARole.AUTHORITY,
        active=True
    )
    assert await wise_authority_service.check_authorization("wa-2025-06-24-AUTH01", "approve_deferrals") is True
    assert await wise_authority_service.check_authorization("wa-2025-06-24-AUTH01", "mint_wa") is False
    
    # Test OBSERVER authorization - limited permissions
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-OBS01",
        role=WARole.OBSERVER,
        active=True
    )
    assert await wise_authority_service.check_authorization("wa-2025-06-24-OBS01", "read") is True
    assert await wise_authority_service.check_authorization("wa-2025-06-24-OBS01", "send_message") is True
    assert await wise_authority_service.check_authorization("wa-2025-06-24-OBS01", "approve_deferrals") is False


@pytest.mark.asyncio
async def test_request_approval(wise_authority_service, time_service, auth_service):
    """Test requesting approval for actions."""
    await wise_authority_service.start()
    
    # Test auto-approval for ROOT
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-ROOT01",
        role=WARole.ROOT,
        active=True
    )
    
    context = DeferralApprovalContext(
        task_id="task-123",
        thought_id="thought-456",
        action_name="read_data",
        action_params={"resource": "public_data"},
        requester_id="wa-2025-06-24-ROOT01",
        channel_id="test-channel"
    )
    
    # ROOT should auto-approve
    approved = await wise_authority_service.request_approval("read_data", context)
    assert approved is True
    
    # Test deferral for unauthorized action
    # Update mock to return OBSERVER
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-OBS01",
        role=WARole.OBSERVER,
        active=True
    )
    
    context.requester_id = "wa-2025-06-24-OBS01"  # Observer can't approve
    approved = await wise_authority_service.request_approval("approve_deferrals", context)
    assert approved is False
    
    # Should have created a deferral
    assert len(wise_authority_service.deferrals) == 1


@pytest.mark.asyncio
async def test_send_deferral(wise_authority_service, time_service):
    """Test sending deferrals."""
    await wise_authority_service.start()
    
    # Create a deferral request
    deferral = DeferralRequest(
        task_id="task-789",
        thought_id="thought-101",
        reason="Requires human review for sensitive action",
        defer_until=time_service.now() + timedelta(hours=24),
        context={"action": "delete_user_data", "user_id": "user-123"}
    )
    
    # Send deferral
    deferral_id = await wise_authority_service.send_deferral(deferral)
    
    assert deferral_id is not None
    assert deferral_id.startswith("defer_")
    assert len(wise_authority_service.deferrals) == 1
    assert deferral_id in wise_authority_service.deferrals


@pytest.mark.asyncio
async def test_get_pending_deferrals(wise_authority_service, time_service):
    """Test getting pending deferrals."""
    await wise_authority_service.start()
    
    # Add some deferrals
    for i in range(3):
        deferral = DeferralRequest(
            task_id=f"task-{i}",
            thought_id=f"thought-{i}",
            reason=f"Test deferral {i}",
            defer_until=time_service.now() + timedelta(hours=i+1),
            context={"test": f"value-{i}"}
        )
        await wise_authority_service.send_deferral(deferral)
    
    # Get all pending deferrals
    pending = await wise_authority_service.get_pending_deferrals()
    assert len(pending) == 3
    
    # Check deferral structure
    first = pending[0]
    assert hasattr(first, 'deferral_id')
    assert hasattr(first, 'task_id')
    assert hasattr(first, 'thought_id')
    assert hasattr(first, 'reason')
    assert first.status == "pending"


@pytest.mark.asyncio
async def test_resolve_deferral(wise_authority_service, time_service):
    """Test resolving deferrals."""
    await wise_authority_service.start()
    
    # Create and send a deferral
    deferral = DeferralRequest(
        task_id="task-resolve",
        thought_id="thought-resolve",
        reason="Test resolution",
        defer_until=time_service.now() + timedelta(hours=1),
        context={}
    )
    deferral_id = await wise_authority_service.send_deferral(deferral)
    
    # Resolve it
    response = DeferralResponse(
        approved=True,
        reason="Approved after review",
        wa_id="wa-2025-06-24-AUTH01",
        signature="test-signature"
    )
    
    resolved = await wise_authority_service.resolve_deferral(deferral_id, response)
    assert resolved is True
    
    # Check it was marked as resolved
    context = wise_authority_service.deferrals[deferral_id]
    assert context.metadata["resolved"] is True
    assert context.metadata["approved"] is True
    assert context.metadata["resolved_by"] == "wa-2025-06-24-AUTH01"


def test_wise_authority_capabilities(wise_authority_service):
    """Test WiseAuthorityService.get_capabilities() returns correct info."""
    caps = wise_authority_service.get_capabilities()
    assert isinstance(caps, ServiceCapabilities)
    assert caps.service_name == "WiseAuthorityService"
    assert caps.version == "1.0.0"
    assert "check_authorization" in caps.actions
    assert "request_approval" in caps.actions
    assert "get_guidance" in caps.actions
    assert "send_deferral" in caps.actions
    assert "get_pending_deferrals" in caps.actions
    assert "resolve_deferral" in caps.actions
    assert "grant_permission" in caps.actions
    assert "revoke_permission" in caps.actions
    assert "list_permissions" in caps.actions
    assert "SecretsService" in caps.dependencies
    assert "GraphAuditService" in caps.dependencies


@pytest.mark.asyncio
async def test_wise_authority_status(wise_authority_service):
    """Test WiseAuthorityService.get_status() returns correct status."""
    await wise_authority_service.start()
    
    status = wise_authority_service.get_status()
    assert isinstance(status, ServiceStatus)
    assert status.service_name == "WiseAuthorityService"
    assert status.service_type == "governance_service"
    assert status.is_healthy is True
    assert "pending_deferrals" in status.metrics
    assert "total_deferrals" in status.metrics
    assert "pending_guidance_requests" in status.metrics


@pytest.mark.asyncio
async def test_list_permissions(wise_authority_service, auth_service):
    """Test listing permissions for a WA."""
    await wise_authority_service.start()
    
    # Test ROOT permissions
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-ROOT01",
        role=WARole.ROOT,
        active=True,
        created_at=datetime.now(timezone.utc)
    )
    permissions = await wise_authority_service.list_permissions("wa-2025-06-24-ROOT01")
    assert len(permissions) > 0
    assert any(p.permission_name == "*" for p in permissions)
    
    # Test AUTHORITY permissions
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-AUTH01",
        role=WARole.AUTHORITY,
        active=True,
        created_at=datetime.now(timezone.utc)
    )
    permissions = await wise_authority_service.list_permissions("wa-2025-06-24-AUTH01")
    assert len(permissions) > 0
    assert any(p.permission_name == "approve_deferrals" for p in permissions)
    assert not any(p.permission_name == "*" for p in permissions)
    
    # Test OBSERVER permissions
    auth_service.get_wa.return_value = MagicMock(
        wa_id="wa-2025-06-24-OBS01",
        role=WARole.OBSERVER,
        active=True,
        created_at=datetime.now(timezone.utc)
    )
    permissions = await wise_authority_service.list_permissions("wa-2025-06-24-OBS01")
    assert len(permissions) > 0
    assert any(p.permission_name == "read" for p in permissions)
    assert any(p.permission_name == "send_message" for p in permissions)
    assert not any(p.permission_name == "approve_deferrals" for p in permissions)


@pytest.mark.asyncio
async def test_fetch_guidance(wise_authority_service):
    """Test fetching guidance from WAs."""
    await wise_authority_service.start()
    
    # Create a guidance context
    context = GuidanceContext(
        thought_id="thought-guid-01",
        task_id="task-guid-01",
        question="Should I allow this user action?",
        ethical_considerations=["user_safety", "data_privacy"],
        domain_context={"action": "data_export"}
    )
    
    # Fetch guidance (should return None as no WA has provided guidance yet)
    guidance = await wise_authority_service.fetch_guidance(context)
    assert guidance is None  # No guidance available in test environment


@pytest.mark.asyncio
async def test_get_guidance(wise_authority_service):
    """Test getting guidance through protocol method."""
    await wise_authority_service.start()
    
    # Create a guidance request
    request = GuidanceRequest(
        context="Should I proceed with user data deletion?",
        options=["Delete immediately", "Confirm with user", "Archive instead"],
        recommendation="Confirm with user",
        urgency="high"
    )
    
    # Get guidance
    response = await wise_authority_service.get_guidance(request)
    
    assert isinstance(response, GuidanceResponse)
    assert response.wa_id == "system"  # No WA guidance available
    assert response.reasoning == "No Wise Authority guidance available yet"
    assert response.custom_guidance is None


@pytest.mark.asyncio
async def test_grant_revoke_permissions(wise_authority_service):
    """Test permission grant/revoke (currently role-based only)."""
    await wise_authority_service.start()
    
    # Try to grant permission (should fail - permissions are role-based)
    granted = await wise_authority_service.grant_permission(
        wa_id="wa-2025-06-24-TEST01",
        permission="special_access",
        resource="sensitive_data"
    )
    assert granted is False  # Can't grant dynamic permissions in beta
    
    # Try to revoke permission (should fail - permissions are role-based)
    revoked = await wise_authority_service.revoke_permission(
        wa_id="wa-2025-06-24-TEST01",
        permission="read",
        resource="public_data"
    )
    assert revoked is False  # Can't revoke role-based permissions


@pytest.mark.asyncio
async def test_deferral_with_modified_time(wise_authority_service, time_service):
    """Test resolving deferral with modified time."""
    await wise_authority_service.start()
    
    # Create and send a deferral
    original_defer_time = time_service.now() + timedelta(hours=1)
    deferral = DeferralRequest(
        task_id="task-mod-time",
        thought_id="thought-mod-time",
        reason="Needs extended review",
        defer_until=original_defer_time,
        context={}
    )
    deferral_id = await wise_authority_service.send_deferral(deferral)
    
    # Resolve with modified time
    new_defer_time = time_service.now() + timedelta(hours=48)
    response = DeferralResponse(
        approved=True,
        reason="Approved but needs more time",
        modified_time=new_defer_time,
        wa_id="wa-2025-06-24-AUTH01",
        signature="test-signature"
    )
    
    resolved = await wise_authority_service.resolve_deferral(deferral_id, response)
    assert resolved is True
    
    # Check the defer time was updated
    context = wise_authority_service.deferrals[deferral_id]
    assert context.defer_until == new_defer_time