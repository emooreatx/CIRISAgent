"""
Unit tests for Initialization Service API endpoints.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.init import router
from ciris_engine.schemas.services.lifecycle.initialization import (
    InitializationStatus, InitializationVerification
)
from ciris_engine.schemas.services.operations import InitializationPhase


@pytest.fixture
def mock_init_service():
    """Create a mock initialization service."""
    service = Mock()
    
    # Setup async methods
    service.get_initialization_status = AsyncMock()
    service.verify_initialization = AsyncMock()
    service.is_healthy = AsyncMock()
    
    return service


@pytest.fixture
def test_app(mock_init_service):
    """Create a test FastAPI app with initialization routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add mock service to app state
    app.state.initialization_service = mock_init_service
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestInitializationStatus:
    """Test /v1/init/status endpoint."""
    
    def test_get_status_success(self, client, mock_init_service):
        """Test successful status retrieval."""
        # Setup mock response
        mock_status = InitializationStatus(
            complete=True,
            start_time=datetime.now(timezone.utc),
            duration_seconds=45.3,
            completed_steps=[
                "infrastructure/TimeService",
                "infrastructure/ShutdownService",
                "database/SQLite",
                "memory/SecretsService",
                "memory/MemoryService"
            ],
            phase_status={
                "infrastructure": "completed",
                "database": "completed",
                "memory": "completed"
            },
            error=None,
            total_steps=5
        )
        mock_init_service.get_initialization_status.return_value = mock_status
        
        # Make request
        response = client.get("/v1/init/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["complete"] is True
        assert data["data"]["duration_seconds"] == 45.3
        assert len(data["data"]["completed_steps"]) == 5
        assert data["data"]["phase_status"]["infrastructure"] == "completed"
        assert data["data"]["error"] is None
        assert data["data"]["total_steps"] == 5
    
    def test_get_status_incomplete(self, client, mock_init_service):
        """Test status when initialization is incomplete."""
        # Setup mock response
        mock_status = InitializationStatus(
            complete=False,
            start_time=datetime.now(timezone.utc),
            duration_seconds=None,
            completed_steps=["infrastructure/TimeService"],
            phase_status={"infrastructure": "in_progress"},
            error=None,
            total_steps=10
        )
        mock_init_service.get_initialization_status.return_value = mock_status
        
        # Make request
        response = client.get("/v1/init/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["complete"] is False
        assert data["data"]["duration_seconds"] is None
        assert len(data["data"]["completed_steps"]) == 1
        assert data["data"]["phase_status"]["infrastructure"] == "in_progress"
    
    def test_get_status_with_error(self, client, mock_init_service):
        """Test status when initialization failed."""
        # Setup mock response
        mock_status = InitializationStatus(
            complete=False,
            start_time=datetime.now(timezone.utc),
            duration_seconds=10.5,
            completed_steps=["infrastructure/TimeService"],
            phase_status={"infrastructure": "failed"},
            error="Failed to initialize database",
            total_steps=10
        )
        mock_init_service.get_initialization_status.return_value = mock_status
        
        # Make request
        response = client.get("/v1/init/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["complete"] is False
        assert data["data"]["error"] == "Failed to initialize database"
    
    def test_get_status_no_service(self, client):
        """Test status when initialization service is not available."""
        # Remove service from app state
        del client.app.state.initialization_service
        
        # Make request
        response = client.get("/v1/init/status")
        
        # Verify error response
        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "Initialization service not available" in data["error"]["message"]
    
    def test_get_status_service_error(self, client, mock_init_service):
        """Test status when service throws an error."""
        # Setup mock to raise exception
        mock_init_service.get_initialization_status.side_effect = Exception("Service error")
        
        # Make request
        response = client.get("/v1/init/status")
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert "Service error" in data["error"]["message"]


class TestInitializationSequence:
    """Test /v1/init/sequence endpoint."""
    
    def test_get_sequence_success(self, client, mock_init_service):
        """Test successful sequence retrieval."""
        # Setup mock response
        mock_status = InitializationStatus(
            complete=True,
            start_time=datetime.now(timezone.utc),
            duration_seconds=45.3,
            completed_steps=[
                "infrastructure/TimeService",
                "infrastructure/ShutdownService",
                "database/SQLite"
            ],
            phase_status={
                "infrastructure": "completed",
                "database": "completed"
            },
            error=None,
            total_steps=3
        )
        mock_init_service.get_initialization_status.return_value = mock_status
        
        # Make request
        response = client.get("/v1/init/sequence")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check phases
        assert "infrastructure" in data["data"]["phases"]
        assert "database" in data["data"]["phases"]
        assert "memory" in data["data"]["phases"]
        
        # Check current phase (should be None since all completed)
        assert data["data"]["current_phase"] is None
        
        # Check steps
        assert len(data["data"]["steps"]) == 3
        assert data["data"]["steps"][0]["phase"] == "infrastructure"
        assert data["data"]["steps"][0]["name"] == "TimeService"
        assert data["data"]["steps"][0]["status"] == "completed"
        
        # Check total duration
        assert data["data"]["total_duration_ms"] == 45300
    
    def test_get_sequence_in_progress(self, client, mock_init_service):
        """Test sequence when initialization is in progress."""
        # Setup mock response
        mock_status = InitializationStatus(
            complete=False,
            start_time=datetime.now(timezone.utc),
            duration_seconds=10.5,
            completed_steps=["infrastructure/TimeService"],
            phase_status={
                "infrastructure": "completed",
                "database": "in_progress"
            },
            error=None,
            total_steps=10
        )
        mock_init_service.get_initialization_status.return_value = mock_status
        
        # Make request
        response = client.get("/v1/init/sequence")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check current phase
        assert data["data"]["current_phase"] == "database"
        
        # Check steps
        assert len(data["data"]["steps"]) == 1
        assert data["data"]["steps"][0]["phase"] == "infrastructure"


class TestInitializationHealth:
    """Test /v1/init/health endpoint."""
    
    def test_get_health_success(self, client, mock_init_service):
        """Test successful health check."""
        # Setup mock responses
        mock_verification = InitializationVerification(
            system_initialized=True,
            no_errors=True,
            all_steps_completed=True,
            phase_results={
                "infrastructure": True,
                "database": True,
                "memory": True
            }
        )
        mock_status = InitializationStatus(
            complete=True,
            start_time=datetime.now(timezone.utc),
            duration_seconds=45.3,
            completed_steps=["infrastructure/TimeService"],
            phase_status={"infrastructure": "completed"},
            error=None,
            total_steps=1
        )
        
        mock_init_service.verify_initialization.return_value = mock_verification
        mock_init_service.get_initialization_status.return_value = mock_status
        mock_init_service.is_healthy.return_value = True
        
        # Make request
        response = client.get("/v1/init/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["system_ready"] is True
        assert data["data"]["initialization_complete"] is True
        assert len(data["data"]["components"]) >= 1
        assert data["data"]["components"][0]["component_name"] == "InitializationService"
        assert data["data"]["components"][0]["is_healthy"] is True
        assert len(data["data"]["warnings"]) == 0
    
    def test_get_health_with_warnings(self, client, mock_init_service):
        """Test health check with warnings."""
        # Setup mock responses
        mock_verification = InitializationVerification(
            system_initialized=True,
            no_errors=True,
            all_steps_completed=False,  # Some steps skipped
            phase_results={
                "infrastructure": True,
                "database": True,
                "memory": False
            }
        )
        mock_status = InitializationStatus(
            complete=True,
            start_time=datetime.now(timezone.utc),
            duration_seconds=45.3,
            completed_steps=["infrastructure/TimeService"],
            phase_status={"infrastructure": "completed"},
            error=None,
            total_steps=2
        )
        
        mock_init_service.verify_initialization.return_value = mock_verification
        mock_init_service.get_initialization_status.return_value = mock_status
        mock_init_service.is_healthy.return_value = True
        
        # Make request
        response = client.get("/v1/init/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["system_ready"] is True
        assert data["data"]["initialization_complete"] is True
        assert len(data["data"]["warnings"]) == 1
        assert "Some initialization steps were skipped" in data["data"]["warnings"][0]
    
    def test_get_health_unhealthy(self, client, mock_init_service):
        """Test health check when system is unhealthy."""
        # Setup mock responses
        mock_verification = InitializationVerification(
            system_initialized=False,
            no_errors=False,
            all_steps_completed=False,
            phase_results={
                "infrastructure": True,
                "database": False
            }
        )
        mock_status = InitializationStatus(
            complete=False,
            start_time=datetime.now(timezone.utc),
            duration_seconds=10.5,
            completed_steps=["infrastructure/TimeService"],
            phase_status={"database": "failed"},
            error="Database initialization failed",
            total_steps=10
        )
        
        mock_init_service.verify_initialization.return_value = mock_verification
        mock_init_service.get_initialization_status.return_value = mock_status
        mock_init_service.is_healthy.return_value = False
        
        # Make request
        response = client.get("/v1/init/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["system_ready"] is False
        assert data["data"]["initialization_complete"] is False
        assert data["data"]["components"][0]["is_healthy"] is False
    
    def test_get_health_with_service_registry(self, client, mock_init_service):
        """Test health check with service registry."""
        # Setup mock responses
        mock_verification = InitializationVerification(
            system_initialized=True,
            no_errors=True,
            all_steps_completed=True,
            phase_results={}
        )
        mock_status = InitializationStatus(
            complete=True,
            start_time=datetime.now(timezone.utc),
            duration_seconds=45.3,
            completed_steps=[],
            phase_status={},
            error=None,
            total_steps=0
        )
        
        mock_init_service.verify_initialization.return_value = mock_verification
        mock_init_service.get_initialization_status.return_value = mock_status
        mock_init_service.is_healthy.return_value = True
        
        # Add mock service registry
        mock_service = Mock()
        mock_service.__class__.__name__ = "TestService"
        mock_service.is_healthy = AsyncMock(return_value=True)
        
        mock_registry = Mock()
        mock_registry.get_services_by_type.return_value = [mock_service]
        
        client.app.state.service_registry = mock_registry
        
        # Make request
        response = client.get("/v1/init/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Should have at least 2 components (InitService + TestService)
        assert len(data["data"]["components"]) >= 2
        component_names = [c["component_name"] for c in data["data"]["components"]]
        assert "InitializationService" in component_names
        assert "TestService" in component_names