"""
Unit tests for Wise Authority API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes import wa
from ciris_engine.schemas.api.auth import AuthContext, UserRole, Permission
from ciris_engine.schemas.services.authority.wise_authority import (
    PendingDeferral
)
from ciris_engine.schemas.services.authority_core import (
    WAPermission,
    DeferralResponse
)
from ciris_engine.api.dependencies.auth import get_auth_context
from ciris_engine.api.services.auth_service import APIAuthService


@pytest.fixture
def mock_wa_service():
    """Create a mock WA service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service."""
    service = Mock(spec=APIAuthService)
    return service


@pytest.fixture
def app(mock_wa_service, mock_auth_service):
    """Create FastAPI app with WA routes."""
    app = FastAPI()
    app.include_router(wa.router, prefix="/v1")
    
    # Add services to app state
    app.state.wise_authority_service = mock_wa_service
    app.state.auth_service = mock_auth_service
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def observer_auth():
    """Create observer auth context."""
    return AuthContext(
        user_id="test_observer",
        role=UserRole.OBSERVER,
        permissions={Permission.VIEW_LOGS, Permission.VIEW_MEMORY},
        api_key_id="test_key_1",
        authenticated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def authority_auth():
    """Create authority auth context."""
    return AuthContext(
        user_id="test_authority",
        role=UserRole.AUTHORITY,
        permissions={
            Permission.VIEW_LOGS, 
            Permission.VIEW_MEMORY,
            Permission.RESOLVE_DEFERRALS,
            Permission.GRANT_PERMISSIONS
        },
        api_key_id="test_key_2",
        authenticated_at=datetime.now(timezone.utc)
    )


def override_auth_dependency(auth_context: AuthContext):
    """Override auth dependency for testing."""
    async def _get_auth_context():
        return auth_context
    return _get_auth_context


class TestGetDeferrals:
    """Test GET /v1/wa/deferrals endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_deferrals_success(self, client, app, mock_wa_service, observer_auth):
        """Test successful retrieval of deferrals."""
        # Setup mock deferrals
        mock_deferrals = [
            PendingDeferral(
                deferral_id="def_123",
                created_at=datetime.now(timezone.utc),
                deferred_by="agent_001",
                task_id="task_456",
                thought_id="thought_789",
                reason="Requires human approval for sensitive action",
                channel_id="api_default",
                user_id="user_abc",
                priority="high",
                assigned_wa_id=None,
                requires_role="authority",
                status="pending",
                resolution=None,
                resolved_at=None
            )
        ]
        mock_wa_service.get_pending_deferrals.return_value = mock_deferrals
        
        # Override auth
        app.dependency_overrides[get_auth_context] = override_auth_dependency(observer_auth)
        
        # Make request
        response = client.get("/v1/wa/deferrals")
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
        assert data["data"]["total"] == 1
        assert len(data["data"]["deferrals"]) == 1
        assert data["data"]["deferrals"][0]["deferral_id"] == "def_123"
        
        mock_wa_service.get_pending_deferrals.assert_called_once_with(wa_id=None)
    
    @pytest.mark.asyncio
    async def test_get_deferrals_filtered(self, client, app, mock_wa_service, observer_auth):
        """Test getting deferrals filtered by WA ID."""
        mock_wa_service.get_pending_deferrals.return_value = []
        
        app.dependency_overrides[get_auth_context] = override_auth_dependency(observer_auth)
        
        response = client.get("/v1/wa/deferrals?wa_id=wa_specific")
        
        assert response.status_code == 200
        mock_wa_service.get_pending_deferrals.assert_called_once_with(wa_id="wa_specific")
    
    @pytest.mark.asyncio
    async def test_get_deferrals_unauthorized(self, client):
        """Test getting deferrals without auth."""
        response = client.get("/v1/wa/deferrals")
        assert response.status_code == 401


class TestResolveDeferral:
    """Test POST /v1/wa/deferrals/{id}/resolve endpoint."""
    
    @pytest.mark.asyncio
    async def test_resolve_deferral_approve(self, client, app, mock_wa_service, authority_auth):
        """Test approving a deferral."""
        mock_wa_service.resolve_deferral.return_value = True
        
        app.dependency_overrides[get_auth_context] = override_auth_dependency(authority_auth)
        
        request_data = {
            "resolution": "approve",
            "guidance": "Action approved with constraints"
        }
        
        response = client.post("/v1/wa/deferrals/def_123/resolve", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
        assert data["data"]["success"] is True
        assert data["data"]["deferral_id"] == "def_123"
        
        # Verify service was called
        mock_wa_service.resolve_deferral.assert_called_once()
        call_args = mock_wa_service.resolve_deferral.call_args
        assert call_args[0][0] == "def_123"
        assert isinstance(call_args[0][1], DeferralResponse)
        assert call_args[0][1].approved is True
    
    @pytest.mark.asyncio
    async def test_resolve_deferral_reject(self, client, app, mock_wa_service, authority_auth):
        """Test rejecting a deferral."""
        mock_wa_service.resolve_deferral.return_value = True
        
        app.dependency_overrides[get_auth_context] = override_auth_dependency(authority_auth)
        
        request_data = {
            "resolution": "reject",
            "guidance": "Action not permitted due to policy"
        }
        
        response = client.post("/v1/wa/deferrals/def_123/resolve", json=request_data)
        
        assert response.status_code == 200
        
        # Verify rejection
        call_args = mock_wa_service.resolve_deferral.call_args
        assert call_args[0][1].approved is False
    
    @pytest.mark.asyncio
    async def test_resolve_deferral_insufficient_permissions(self, client, app, observer_auth):
        """Test resolving deferral without authority role."""
        app.dependency_overrides[get_auth_context] = override_auth_dependency(observer_auth)
        
        request_data = {
            "resolution": "approve",
            "guidance": "Test"
        }
        
        response = client.post("/v1/wa/deferrals/def_123/resolve", json=request_data)
        
        assert response.status_code == 403


class TestPermissions:
    """Test permission-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_permissions(self, client, app, mock_wa_service, observer_auth):
        """Test getting permissions list."""
        # Setup mock permissions
        mock_permissions = [
            WAPermission(
                permission_id="perm_001",
                wa_id="test_observer",
                permission_type="action",
                permission_name="view_logs",
                resource=None,
                granted_by="root",
                granted_at=datetime.now(timezone.utc),
                expires_at=None,
                metadata={}
            )
        ]
        mock_wa_service.list_permissions.return_value = mock_permissions
        
        app.dependency_overrides[get_auth_context] = override_auth_dependency(observer_auth)
        
        response = client.get("/v1/wa/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
        assert data["data"]["wa_id"] == "test_observer"
        assert len(data["data"]["permissions"]) == 1
        
        mock_wa_service.list_permissions.assert_called_once_with("test_observer")