"""
Test service registry integration for DreamProcessor and CIRISNodeClient.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, List

from ciris_engine.processor.dream_processor import DreamProcessor
from ciris_engine.adapters.cirisnode_client import CIRISNodeClient
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentTemplate
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.registries.base import ServiceRegistry, Priority


class MockAuditService:
    """Mock audit service for testing."""
    
    async def log_action(self, action_type: HandlerActionType, context: Dict[str, Any], outcome: str = None) -> bool:
        return True
    
    async def get_audit_trail(self, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return []
    
    async def is_healthy(self) -> bool:
        return True
    
    async def get_capabilities(self) -> List[str]:
        return ["log_action", "get_audit_trail"]


class MockCIRISNodeClient:
    """Mock CIRISNode client for testing."""
    
    def __init__(self, service_registry=None, base_url="https://localhost:8001"):
        self.service_registry = service_registry
        self.base_url = base_url
        self._closed = False
    
    async def run_he300(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        print("MockCIRISNodeClient.run_he300 called")
        return {"topic": "Test Dream Topic", "score": 85}
    
    async def run_simplebench(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        print("MockCIRISNodeClient.run_simplebench called")
        return {"score": 92, "details": "Test benchmark"}
    
    async def close(self):
        print(f"MockCIRISNodeClient.close called on id={id(self)}")
        self._closed = True


@pytest.fixture
def mock_app_config():
    """Create a mock app config."""
    config = MagicMock(spec=AppConfig)
    config.llm_services = MagicMock()
    config.llm_services.openai = MagicMock()
    config.llm_services.openai.model_name = "test-model"
    return config


@pytest.fixture
def mock_template():
    """Create a mock agent template."""
    template = MagicMock(spec=AgentTemplate)
    template.name = "test-agent"
    return template


@pytest.fixture
def service_registry():
    """Create a service registry with mock audit service."""
    registry = ServiceRegistry()
    audit_service = MockAuditService()
    
    # Register audit service globally
    registry.register_global(
        service_type="audit",
        provider=audit_service,
        priority=Priority.HIGH,
        capabilities=["log_action", "get_audit_trail"]
    )
    
    return registry


@pytest.mark.asyncio
async def test_dream_processor_with_service_registry(mock_app_config, mock_template, service_registry):
    """Test that DreamProcessor correctly uses service registry."""
    
    # Create DreamProcessor with service registry
    dream_processor = DreamProcessor(
        app_config=mock_app_config,
        # DreamProcessor no longer needs template
        service_registry=service_registry
    )
    
    # Verify service registry is stored
    assert dream_processor.service_registry is service_registry
    
    # Verify CIRISNodeClient can be created (but not actually create it yet)
    assert dream_processor.cirisnode_client is None


@pytest.mark.asyncio
async def test_cirisnode_client_with_service_registry(service_registry):
    """Test that CIRISNodeClient correctly uses service registry."""
    
    # Create CIRISNodeClient with service registry
    client = CIRISNodeClient(
        service_registry=service_registry,
        base_url="https://test-url:8001"
    )
    
    # Verify service registry is stored
    assert client.service_registry is service_registry
    assert client.base_url == "https://test-url:8001"
    
    # Test that audit service can be retrieved
    audit_service = await client._get_audit_service()
    assert audit_service is not None
    assert hasattr(audit_service, 'log_action')
    
    # Test caching - should return same instance
    audit_service2 = await client._get_audit_service()
    assert audit_service is audit_service2


@pytest.mark.asyncio
async def test_cirisnode_client_audit_logging(service_registry):
    """Test that CIRISNodeClient correctly logs audit events."""

    # Create mock audit service with spy capabilities
    audit_service = AsyncMock(spec=MockAuditService)
    audit_service.log_action = AsyncMock(return_value=True)
    audit_service.is_healthy = AsyncMock(return_value=True)
    audit_service.get_capabilities = AsyncMock(return_value=["log_action", "get_audit_trail"])

    # Replace the audit service in registry
    service_registry.clear_all()
    service_registry.register_global(
        service_type="audit",
        provider=audit_service,
        priority=Priority.HIGH,
        capabilities=["log_action", "get_audit_trail"]
    )

    client = CIRISNodeClient(
        service_registry=service_registry,
        base_url="https://test-url:8001"
    )

    # Mock the HTTP methods to avoid actual network calls
    client._post = AsyncMock(return_value={"topic": "test", "score": 90})

    # Test run_he300 with audit logging
    result = await client.run_he300("test-model", "test-agent")

    # Verify audit logging was called
    audit_service.log_action.assert_called()
    call_args = audit_service.log_action.call_args
    assert call_args[0][0] == HandlerActionType.TOOL  # action_type should be enum
    context = call_args[0][1]  # ActionContext object
    assert context.task_id == "he300"
    assert context.handler_name == "cirisnode_client"
    assert result == {"topic": "test", "score": 90}


@pytest.mark.asyncio
async def test_dream_processor_start_dreaming_with_service_registry(mock_app_config, mock_template, service_registry, monkeypatch):
    """Test that DreamProcessor start_dreaming creates CIRISNodeClient with service registry."""
    
    # Mock CIRISNodeClient to avoid actual network calls
    mock_client_instance = MockCIRISNodeClient(service_registry=service_registry)
    
    # Track all created mock clients
    created_clients = []
    def mock_cirisnode_client_constructor(service_registry=None, base_url=None):
        client = MockCIRISNodeClient(service_registry=service_registry)
        created_clients.append(client)
        return client

    monkeypatch.setattr("ciris_engine.processor.dream_processor.CIRISNodeClient", mock_cirisnode_client_constructor)
    
    # Add cirisnode config to enable CIRISNode client creation
    mock_app_config.cirisnode = MagicMock()
    mock_app_config.cirisnode.base_url = "https://test-cirisnode:8001"
    
    dream_processor = DreamProcessor(
        app_config=mock_app_config,
        # DreamProcessor no longer needs template
        service_registry=service_registry,
        pulse_interval=0.1  # Short interval for testing
    )
    
    # Start dreaming for a longer duration to ensure at least one pulse
    await dream_processor.start_dreaming(duration=0.5)

    # Wait longer for the dream to complete and client to be closed
    await asyncio.sleep(1.0)
    
    # Verify CIRISNodeClient was created with service registry
    assert dream_processor.cirisnode_client is not None
    print(f"Test sees dream_processor.cirisnode_client id={id(dream_processor.cirisnode_client)}")
    assert dream_processor.cirisnode_client.service_registry is service_registry
    
    # Stop dreaming
    await dream_processor.stop_dreaming()
    
    # Verify at least one client was closed
    assert any(client._closed for client in created_clients)
    
    # Verify the last created client was closed
    assert created_clients[-1]._closed


@pytest.mark.asyncio
async def test_cirisnode_client_without_service_registry():
    """Test that CIRISNodeClient handles missing service registry gracefully."""
    
    client = CIRISNodeClient(
        service_registry=None,
        base_url="https://test-url:8001"
    )
    
    # Should not crash when trying to get audit service
    audit_service = await client._get_audit_service()
    assert audit_service is None
    
    # Should still work for basic operations (with mocked HTTP methods)
    client._post = AsyncMock(return_value={"topic": "test", "score": 90})
    
    result = await client.run_he300("test-model", "test-agent")
    assert result == {"topic": "test", "score": 90}
    
    # Clean up
    await client.close()


@pytest.mark.asyncio
async def test_service_registry_fallback():
    """Test service registry fallback to global services."""
    
    registry = ServiceRegistry()
    audit_service = MockAuditService()
    
    # Register as global service
    registry.register_global(
        service_type="audit",
        provider=audit_service,
        priority=Priority.NORMAL,
        capabilities=["log_action"]
    )
    
    # Request service for a specific handler should fall back to global
    service = await registry.get_service(
        handler="TestHandler",
        service_type="audit",
        fallback_to_global=True
    )
    
    assert service is audit_service


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
