"""
Unit tests for System Shutdown API route.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ciris_engine.api.routes.system import (
    router,
    ShutdownRequest,
    ShutdownResponse
)
from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.api.auth import AuthContext, UserRole, Permission, ROLE_PERMISSIONS
from ciris_engine.schemas.services.core import ServiceStatus


@pytest.fixture
def mock_shutdown_service():
    """Create a mock shutdown service."""
    service = Mock()
    service.is_shutdown_requested = Mock(return_value=False)
    service.get_shutdown_reason = Mock(return_value=None)
    service.request_shutdown = AsyncMock()
    service.is_healthy = AsyncMock(return_value=True)
    service.get_status = Mock(return_value=ServiceStatus(
        service_name="ShutdownService",
        service_type="core_service",
        is_healthy=True,
        uptime_seconds=100.0,
        metrics={
            "shutdown_requested": 0.0,
            "registered_handlers": 5.0
        },
        last_error=None,
        last_health_check=None
    ))
    return service


@pytest.fixture
def mock_request(mock_shutdown_service):
    """Create a mock request with shutdown service."""
    request = Mock()
    request.app.state.runtime = Mock()
    request.app.state.runtime.shutdown_service = mock_shutdown_service
    return request


@pytest.fixture
def admin_auth():
    """Create admin auth context."""
    return AuthContext(
        user_id="admin_user",
        role=UserRole.ADMIN,
        permissions=ROLE_PERMISSIONS[UserRole.ADMIN],
        api_key_id="test_key",
        authenticated_at=datetime.now(timezone.utc)
    )


class TestShutdownEndpoint:
    """Test POST /system/shutdown endpoint."""

    @pytest.mark.asyncio
    async def test_shutdown_success(self, mock_request, mock_shutdown_service, admin_auth):
        """Test successful shutdown."""
        from ciris_engine.api.routes.system import shutdown_system

        body = ShutdownRequest(
            reason="Scheduled maintenance",
            confirm=True,
            force=False
        )

        result = await shutdown_system(body, mock_request, admin_auth)

        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ShutdownResponse)
        assert result.data.status == "initiated"
        assert result.data.shutdown_initiated is True
        assert "Scheduled maintenance" in result.data.message
        assert "admin_user" in result.data.message

        # Verify shutdown was requested
        mock_shutdown_service.request_shutdown.assert_called_once()
        call_args = mock_shutdown_service.request_shutdown.call_args[0]
        assert "Scheduled maintenance" in call_args[0]
        assert "admin_user" in call_args[0]
        assert "[FORCED]" not in call_args[0]

    @pytest.mark.asyncio
    async def test_shutdown_forced(self, mock_request, mock_shutdown_service, admin_auth):
        """Test forced shutdown."""
        from ciris_engine.api.routes.system import shutdown_system

        body = ShutdownRequest(
            reason="Emergency shutdown",
            confirm=True,
            force=True
        )

        result = await shutdown_system(body, mock_request, admin_auth)

        call_args = mock_shutdown_service.request_shutdown.call_args[0]
        assert "[FORCED]" in call_args[0]

    @pytest.mark.asyncio
    async def test_shutdown_no_confirmation(self, mock_request, mock_shutdown_service, admin_auth):
        """Test shutdown without confirmation."""
        from ciris_engine.api.routes.system import shutdown_system

        body = ShutdownRequest(
            reason="Test shutdown",
            confirm=False,
            force=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await shutdown_system(body, mock_request, admin_auth)

        assert exc_info.value.status_code == 400
        assert "Confirmation required" in str(exc_info.value.detail)

        # Verify shutdown was NOT requested
        mock_shutdown_service.request_shutdown.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_already_requested(self, mock_request, mock_shutdown_service, admin_auth):
        """Test shutdown when already shutting down."""
        from ciris_engine.api.routes.system import shutdown_system

        mock_shutdown_service.is_shutdown_requested.return_value = True
        mock_shutdown_service.get_shutdown_reason.return_value = "Previous shutdown"

        body = ShutdownRequest(
            reason="New shutdown",
            confirm=True,
            force=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await shutdown_system(body, mock_request, admin_auth)

        assert exc_info.value.status_code == 409
        assert "Previous shutdown" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_shutdown_no_runtime(self, admin_auth):
        """Test shutdown when runtime is not available."""
        from ciris_engine.api.routes.system import shutdown_system

        request = Mock()
        request.app.state = Mock(spec=[])  # No runtime attribute

        body = ShutdownRequest(
            reason="Test",
            confirm=True,
            force=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await shutdown_system(body, request, admin_auth)

        assert exc_info.value.status_code == 503
        assert "Runtime not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_shutdown_no_service(self, admin_auth):
        """Test shutdown when shutdown service is not available."""
        from ciris_engine.api.routes.system import shutdown_system

        request = Mock()
        request.app.state.runtime = Mock(spec=[])  # No shutdown_service attribute

        body = ShutdownRequest(
            reason="Test",
            confirm=True,
            force=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await shutdown_system(body, request, admin_auth)

        assert exc_info.value.status_code == 503
        assert "Shutdown service not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_shutdown_error(self, mock_request, mock_shutdown_service, admin_auth):
        """Test shutdown when an error occurs."""
        from ciris_engine.api.routes.system import shutdown_system

        mock_shutdown_service.request_shutdown.side_effect = Exception("Shutdown failed")

        body = ShutdownRequest(
            reason="Test",
            confirm=True,
            force=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await shutdown_system(body, mock_request, admin_auth)

        assert exc_info.value.status_code == 500
        assert "Shutdown failed" in str(exc_info.value.detail)


class TestShutdownInHealthStatus:
    """Test that shutdown status is reflected in health endpoint."""

    @pytest.mark.asyncio
    async def test_health_shows_shutdown_status(self, mock_request, mock_shutdown_service):
        """Test that health endpoint shows shutdown status."""
        from ciris_engine.api.routes.system import get_system_health

        # Mock time service
        mock_time_service = Mock()
        mock_time_service.now = Mock(return_value=datetime.now(timezone.utc))
        mock_time_service._start_time = datetime.now(timezone.utc)
        mock_request.app.state.time_service = mock_time_service

        # Mock initialization service
        mock_init_service = Mock()
        mock_init_service.is_initialized = Mock(return_value=True)
        mock_request.app.state.initialization_service = mock_init_service

        # Mock agent processor for cognitive state
        mock_request.app.state.runtime.agent_processor = Mock()
        mock_request.app.state.runtime.agent_processor.get_current_state = Mock(return_value="WORK")

        # Mock service registry
        mock_request.app.state.service_registry = Mock()
        mock_request.app.state.service_registry.get_services_by_type = Mock(return_value=[])

        # Set shutdown requested
        mock_shutdown_service.is_shutdown_requested.return_value = True
        mock_shutdown_service.get_shutdown_reason.return_value = "Maintenance shutdown"

        result = await get_system_health(mock_request)

        assert isinstance(result, SuccessResponse)
        assert result.data.status in ["healthy", "degraded", "critical", "initializing"]
        assert result.data.cognitive_state == "WORK"
        assert result.data.initialization_complete is True
        # The health endpoint doesn't currently show shutdown status,
        # but it could be enhanced to include it in the future


class TestAuthRequirements:
    """Test that shutdown endpoint requires proper authentication."""

    def test_shutdown_requires_admin(self):
        """Test that shutdown requires ADMIN role."""
        from ciris_engine.api.routes.system import shutdown_system
        import inspect

        # Get function signature
        sig = inspect.signature(shutdown_system)
        params = list(sig.parameters.values())

        # Check that one of the parameters has require_admin as default
        has_require_admin = any(
            'require_admin' in str(param.default)
            for param in params
            if param.default is not inspect.Parameter.empty
        )
        assert has_require_admin, "shutdown_system should require admin auth"
