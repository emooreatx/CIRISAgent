"""
Unit tests for Shutdown Service API routes.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ciris_engine.api.routes.shutdown import (
    router,
    get_shutdown_service,
    ShutdownStatus,
    ShutdownPrepareResponse,
    ShutdownExecuteResponse,
    ShutdownAbortResponse
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


class TestGetShutdownService:
    """Test get_shutdown_service dependency."""
    
    @pytest.mark.asyncio
    async def test_get_shutdown_service_success(self, mock_request):
        """Test successful service retrieval."""
        service = await get_shutdown_service(mock_request)
        assert service == mock_request.app.state.runtime.shutdown_service
    
    @pytest.mark.asyncio
    async def test_get_shutdown_service_no_runtime(self):
        """Test when runtime is not available."""
        request = Mock()
        request.app.state = Mock(spec=[])  # No runtime attribute
        
        with pytest.raises(HTTPException) as exc_info:
            await get_shutdown_service(request)
        
        assert exc_info.value.status_code == 503
        assert "Runtime not available" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_shutdown_service_no_service(self):
        """Test when shutdown service is not available."""
        request = Mock()
        request.app.state.runtime = Mock(spec=[])  # No shutdown_service attribute
        
        with pytest.raises(HTTPException) as exc_info:
            await get_shutdown_service(request)
        
        assert exc_info.value.status_code == 503
        assert "Shutdown service not available" in str(exc_info.value.detail)


class TestShutdownStatus:
    """Test GET /shutdown/status endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_status_not_requested(self, mock_request, mock_shutdown_service):
        """Test status when shutdown not requested."""
        from ciris_engine.api.routes.shutdown import get_shutdown_status
        
        result = await get_shutdown_status(mock_request, mock_shutdown_service)
        
        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ShutdownStatus)
        assert result.data.shutdown_requested is False
        assert result.data.shutdown_reason is None
        assert result.data.registered_handlers == 5
        assert result.data.service_healthy is True
    
    @pytest.mark.asyncio
    async def test_get_status_shutdown_requested(self, mock_request, mock_shutdown_service):
        """Test status when shutdown is requested."""
        from ciris_engine.api.routes.shutdown import get_shutdown_status
        
        mock_shutdown_service.is_shutdown_requested.return_value = True
        mock_shutdown_service.get_shutdown_reason.return_value = "User requested shutdown"
        
        result = await get_shutdown_status(mock_request, mock_shutdown_service)
        
        assert result.data.shutdown_requested is True
        assert result.data.shutdown_reason == "User requested shutdown"
    
    @pytest.mark.asyncio
    async def test_get_status_service_unhealthy(self, mock_request, mock_shutdown_service):
        """Test status when service is unhealthy."""
        from ciris_engine.api.routes.shutdown import get_shutdown_status
        
        mock_shutdown_service.is_healthy.return_value = False
        
        result = await get_shutdown_status(mock_request, mock_shutdown_service)
        
        assert result.data.service_healthy is False
    
    @pytest.mark.asyncio
    async def test_get_status_error(self, mock_request, mock_shutdown_service):
        """Test status when an error occurs."""
        from ciris_engine.api.routes.shutdown import get_shutdown_status
        
        mock_shutdown_service.is_shutdown_requested.side_effect = Exception("Test error")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_shutdown_status(mock_request, mock_shutdown_service)
        
        assert exc_info.value.status_code == 500
        assert "Test error" in str(exc_info.value.detail)


class TestPrepareShutdown:
    """Test POST /shutdown/prepare endpoint."""
    
    @pytest.mark.asyncio
    async def test_prepare_success(self, mock_request, mock_shutdown_service, admin_auth):
        """Test successful shutdown preparation."""
        from ciris_engine.api.routes.shutdown import prepare_shutdown, ShutdownPrepareRequest
        
        body = ShutdownPrepareRequest(reason="Scheduled maintenance")
        
        result = await prepare_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ShutdownPrepareResponse)
        assert result.data.status == "prepared"
        assert "Scheduled maintenance" in result.data.message
        assert result.data.handlers_notified == 5
    
    @pytest.mark.asyncio
    async def test_prepare_already_shutting_down(self, mock_request, mock_shutdown_service, admin_auth):
        """Test prepare when shutdown already requested."""
        from ciris_engine.api.routes.shutdown import prepare_shutdown, ShutdownPrepareRequest
        
        mock_shutdown_service.is_shutdown_requested.return_value = True
        mock_shutdown_service.get_shutdown_reason.return_value = "Previous shutdown"
        
        body = ShutdownPrepareRequest(reason="New shutdown")
        
        with pytest.raises(HTTPException) as exc_info:
            await prepare_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 409
        assert "Previous shutdown" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_prepare_error(self, mock_request, mock_shutdown_service, admin_auth):
        """Test prepare when an error occurs."""
        from ciris_engine.api.routes.shutdown import prepare_shutdown, ShutdownPrepareRequest
        
        mock_shutdown_service.get_status.side_effect = Exception("Service error")
        
        body = ShutdownPrepareRequest(reason="Test")
        
        with pytest.raises(HTTPException) as exc_info:
            await prepare_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 500


class TestExecuteShutdown:
    """Test POST /shutdown/execute endpoint."""
    
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_request, mock_shutdown_service, admin_auth):
        """Test successful shutdown execution."""
        from ciris_engine.api.routes.shutdown import execute_shutdown, ShutdownExecuteRequest
        
        body = ShutdownExecuteRequest(confirm=True, force=False)
        
        result = await execute_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ShutdownExecuteResponse)
        assert result.data.status == "initiated"
        assert result.data.shutdown_initiated is True
        
        # Verify shutdown was requested
        mock_shutdown_service.request_shutdown.assert_called_once()
        call_args = mock_shutdown_service.request_shutdown.call_args[0]
        assert "admin_user" in call_args[0]
        assert "forced" not in call_args[0]
    
    @pytest.mark.asyncio
    async def test_execute_forced(self, mock_request, mock_shutdown_service, admin_auth):
        """Test forced shutdown execution."""
        from ciris_engine.api.routes.shutdown import execute_shutdown, ShutdownExecuteRequest
        
        body = ShutdownExecuteRequest(confirm=True, force=True)
        
        result = await execute_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        call_args = mock_shutdown_service.request_shutdown.call_args[0]
        assert "(forced)" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_execute_no_confirmation(self, mock_request, mock_shutdown_service, admin_auth):
        """Test execute without confirmation."""
        from ciris_engine.api.routes.shutdown import execute_shutdown, ShutdownExecuteRequest
        
        body = ShutdownExecuteRequest(confirm=False, force=False)
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 400
        assert "Confirmation required" in str(exc_info.value.detail)
        
        # Verify shutdown was NOT requested
        mock_shutdown_service.request_shutdown.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_error(self, mock_request, mock_shutdown_service, admin_auth):
        """Test execute when an error occurs."""
        from ciris_engine.api.routes.shutdown import execute_shutdown, ShutdownExecuteRequest
        
        mock_shutdown_service.request_shutdown.side_effect = Exception("Shutdown failed")
        
        body = ShutdownExecuteRequest(confirm=True, force=False)
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_shutdown(body, mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 500
        assert "Shutdown failed" in str(exc_info.value.detail)


class TestAbortShutdown:
    """Test POST /shutdown/abort endpoint."""
    
    @pytest.mark.asyncio
    async def test_abort_no_shutdown(self, mock_request, mock_shutdown_service, admin_auth):
        """Test abort when no shutdown in progress."""
        from ciris_engine.api.routes.shutdown import abort_shutdown
        
        mock_shutdown_service.is_shutdown_requested.return_value = False
        
        result = await abort_shutdown(mock_request, admin_auth, mock_shutdown_service)
        
        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ShutdownAbortResponse)
        assert result.data.status == "no_shutdown"
        assert result.data.was_active is False
    
    @pytest.mark.asyncio
    async def test_abort_shutdown_in_progress(self, mock_request, mock_shutdown_service, admin_auth):
        """Test abort when shutdown is in progress."""
        from ciris_engine.api.routes.shutdown import abort_shutdown
        
        mock_shutdown_service.is_shutdown_requested.return_value = True
        
        with pytest.raises(HTTPException) as exc_info:
            await abort_shutdown(mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 501
        assert "not implemented" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_abort_error(self, mock_request, mock_shutdown_service, admin_auth):
        """Test abort when an error occurs."""
        from ciris_engine.api.routes.shutdown import abort_shutdown
        
        mock_shutdown_service.is_shutdown_requested.side_effect = Exception("Check failed")
        
        with pytest.raises(HTTPException) as exc_info:
            await abort_shutdown(mock_request, admin_auth, mock_shutdown_service)
        
        assert exc_info.value.status_code == 500
        assert "Check failed" in str(exc_info.value.detail)


class TestAuthRequirements:
    """Test that endpoints require proper authentication."""
    
    def test_prepare_requires_admin(self):
        """Test that prepare requires ADMIN role."""
        from ciris_engine.api.routes.shutdown import prepare_shutdown
        import inspect
        
        # Get function signature
        sig = inspect.signature(prepare_shutdown)
        params = list(sig.parameters.values())
        
        # Check that one of the parameters has require_admin as default
        has_require_admin = any(
            'require_admin' in str(param.default) 
            for param in params 
            if param.default is not inspect.Parameter.empty
        )
        assert has_require_admin, "prepare_shutdown should require admin auth"
    
    def test_execute_requires_admin(self):
        """Test that execute requires ADMIN role."""
        from ciris_engine.api.routes.shutdown import execute_shutdown
        import inspect
        
        # Get function signature
        sig = inspect.signature(execute_shutdown)
        params = list(sig.parameters.values())
        
        # Check that one of the parameters has require_admin as default
        has_require_admin = any(
            'require_admin' in str(param.default) 
            for param in params 
            if param.default is not inspect.Parameter.empty
        )
        assert has_require_admin, "execute_shutdown should require admin auth"
    
    def test_abort_requires_admin(self):
        """Test that abort requires ADMIN role."""
        from ciris_engine.api.routes.shutdown import abort_shutdown
        import inspect
        
        # Get function signature
        sig = inspect.signature(abort_shutdown)
        params = list(sig.parameters.values())
        
        # Check that one of the parameters has require_admin as default
        has_require_admin = any(
            'require_admin' in str(param.default) 
            for param in params 
            if param.default is not inspect.Parameter.empty
        )
        assert has_require_admin, "abort_shutdown should require admin auth"