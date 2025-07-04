"""
Integration tests for system management API endpoint extensions.

These tests verify the endpoints work correctly with real runtime components.
"""
import pytest
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient

from ciris_engine.logic.adapters.api.app import create_app
from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.logic.services.runtime.control_service import RuntimeControlService
from ciris_engine.logic.adapters.api.dependencies.auth import create_api_key
from ciris_engine.schemas.config.essential import EssentialConfig
from ciris_engine.schemas.adapters import AdapterServiceRegistration
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.logic.registries.base import Priority, SelectionStrategy


@pytest.fixture
async def test_runtime():
    """Create a test runtime with mock services."""
    config = EssentialConfig(
        model_provider="mock",
        agent_name="TestAgent",
        mock_llm_responses=True
    )
    
    runtime = CIRISRuntime(
        adapter_types=["api"],
        essential_config=config,
        startup_channel_id="test_channel"
    )
    
    # Initialize runtime
    await runtime.initialize()
    
    yield runtime
    
    # Cleanup
    await runtime.shutdown()


@pytest.fixture
def test_app(test_runtime):
    """Create test FastAPI app with runtime."""
    app = create_app(runtime=test_runtime)
    
    # Inject runtime control service
    app.state.runtime_control_service = test_runtime.service_initializer.runtime_control_service
    app.state.runtime = test_runtime
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Create auth headers for testing."""
    # Create test API key
    api_key = create_api_key("test_user", ["ADMIN"])
    return {"Authorization": f"Bearer test_user:{api_key}"}


class TestQueueStatusIntegration:
    """Integration tests for queue status endpoint."""
    
    def test_get_queue_status(self, test_client, auth_headers):
        """Test getting queue status from real runtime."""
        response = test_client.get(
            "/v1/system/runtime/queue",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        
        queue_status = data["data"]
        assert "processor_name" in queue_status
        assert "queue_size" in queue_status
        assert queue_status["processor_name"] == "agent"


class TestSingleStepIntegration:
    """Integration tests for single step endpoint."""
    
    def test_single_step_no_thoughts(self, test_client, auth_headers):
        """Test single step when no thoughts to process."""
        response = test_client.post(
            "/v1/system/runtime/step",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        result = data["data"]
        assert "success" in result
        assert "message" in result
        assert "processor_state" in result


class TestServiceHealthIntegration:
    """Integration tests for service health endpoint."""
    
    def test_get_service_health(self, test_client, auth_headers):
        """Test getting service health from real runtime."""
        response = test_client.get(
            "/v1/system/services/health",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        health = data["data"]
        assert "overall_health" in health
        assert "healthy_services" in health
        assert "unhealthy_services" in health
        assert "service_details" in health


class TestServicePriorityIntegration:
    """Integration tests for service priority management."""
    
    def test_update_service_priority(self, test_client, auth_headers, test_runtime):
        """Test updating service priority."""
        # First, register a test service
        if test_runtime.service_registry:
            test_runtime.service_registry.register_service(
                service_type=ServiceType.LLM,
                provider=MagicMock(),
                priority=Priority.NORMAL,
                capabilities=["test"],
                priority_group=0,
                strategy=SelectionStrategy.FALLBACK
            )
        
        # Get the provider name
        providers = test_runtime.service_registry.get_provider_info()
        llm_providers = providers.get("services", {}).get(ServiceType.LLM, [])
        if llm_providers:
            provider_name = llm_providers[0]["name"]
            
            # Update priority
            response = test_client.put(
                f"/v1/system/services/{provider_name}/priority",
                headers=auth_headers,
                json={
                    "priority": "HIGH",
                    "priority_group": 1,
                    "strategy": "ROUND_ROBIN"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker management."""
    
    def test_reset_circuit_breakers(self, test_client, auth_headers):
        """Test resetting circuit breakers."""
        response = test_client.post(
            "/v1/system/services/circuit-breakers/reset",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        result = data["data"]
        assert "success" in result


class TestServiceSelectionExplanationIntegration:
    """Integration tests for service selection explanation."""
    
    def test_get_selection_explanation(self, test_client, auth_headers):
        """Test getting service selection explanation."""
        response = test_client.get(
            "/v1/system/services/selection-logic",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        explanation = data["data"]
        assert "overview" in explanation
        assert "priority_groups" in explanation
        assert "priorities" in explanation
        assert "selection_strategies" in explanation
        assert "selection_flow" in explanation
        assert "circuit_breaker_info" in explanation
        
        # Verify content
        assert len(explanation["priorities"]) > 0
        assert "CRITICAL" in explanation["priorities"]
        assert "FALLBACK" in explanation["selection_strategies"]


class TestProcessorStatesIntegration:
    """Integration tests for processor states endpoint."""
    
    def test_get_processor_states(self, test_client, auth_headers):
        """Test getting processor states."""
        response = test_client.get(
            "/v1/system/processors",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        states = data["data"]
        assert len(states) == 6  # Should have 6 states
        
        # Verify all expected states are present
        state_names = [s["name"] for s in states]
        expected_states = ["WAKEUP", "WORK", "DREAM", "PLAY", "SOLITUDE", "SHUTDOWN"]
        for expected in expected_states:
            assert expected in state_names
        
        # At least one state should be active
        active_states = [s for s in states if s["is_active"]]
        assert len(active_states) >= 1
        
        # Each state should have capabilities
        for state in states:
            assert "capabilities" in state
            assert len(state["capabilities"]) > 0


class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""
    
    def test_unauthorized_access(self, test_client):
        """Test endpoints require authentication."""
        endpoints = [
            ("/v1/system/runtime/queue", "GET"),
            ("/v1/system/runtime/step", "POST"),
            ("/v1/system/services/health", "GET"),
            ("/v1/system/services/TestService/priority", "PUT"),
            ("/v1/system/services/circuit-breakers/reset", "POST"),
            ("/v1/system/services/selection-logic", "GET"),
            ("/v1/system/processors", "GET")
        ]
        
        for endpoint, method in endpoints:
            if method == "GET":
                response = test_client.get(endpoint)
            elif method == "POST":
                response = test_client.post(endpoint, json={})
            elif method == "PUT":
                response = test_client.put(endpoint, json={"priority": "HIGH"})
            
            assert response.status_code == 401
    
    def test_observer_cannot_modify(self, test_client):
        """Test observer role cannot access admin endpoints."""
        # Create observer API key
        api_key = create_api_key("observer_user", ["OBSERVER"])
        headers = {"Authorization": f"Bearer observer_user:{api_key}"}
        
        # These should fail for observer
        admin_endpoints = [
            ("/v1/system/runtime/step", "POST", {}),
            ("/v1/system/services/TestService/priority", "PUT", {"priority": "HIGH"}),
            ("/v1/system/services/circuit-breakers/reset", "POST", {})
        ]
        
        for endpoint, method, data in admin_endpoints:
            if method == "POST":
                response = test_client.post(endpoint, headers=headers, json=data)
            elif method == "PUT":
                response = test_client.put(endpoint, headers=headers, json=data)
            
            assert response.status_code == 403  # Forbidden


# Import MagicMock for test service
from unittest.mock import MagicMock