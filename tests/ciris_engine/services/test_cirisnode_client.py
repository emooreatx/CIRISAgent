import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from ciris_engine.adapters import CIRISNodeClient
from ciris_engine.registries.base import ServiceRegistry, Priority

@pytest.mark.asyncio
@patch("ciris_engine.adapters.cirisnode_client.get_config")
@patch("ciris_engine.adapters.cirisnode_client.httpx.AsyncClient")
async def test_run_simplebench(mock_async_client, mock_get_config):
    # Set up service registry and mock audit service
    service_registry = ServiceRegistry()
    audit = AsyncMock()
    audit.log_action = AsyncMock(return_value=True)
    service_registry.register_global(
        service_type="audit",
        provider=audit,
        priority=Priority.HIGH,
        capabilities=["log_action"]
    )
    # Patch _post to avoid real HTTP
    client = CIRISNodeClient(service_registry=service_registry, base_url="https://x")
    client._post = AsyncMock(return_value={"result": "ok"})
    result = await client.run_simplebench("m1", "a1")
    assert result == {"result": "ok"}
    audit.log_action.assert_called()
