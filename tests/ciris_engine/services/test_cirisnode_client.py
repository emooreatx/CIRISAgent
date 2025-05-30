import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from ciris_engine.adapters import CIRISNodeClient

@pytest.mark.asyncio
@patch("ciris_engine.adapters.cirisnode_client.get_config")
@patch("ciris_engine.adapters.cirisnode_client.httpx.AsyncClient")
async def test_run_simplebench(mock_async_client, mock_get_config):
    audit = AsyncMock()
    mock_client = AsyncMock()
    mock_async_client.return_value = mock_client
    mock_client.post.return_value.json = AsyncMock(return_value={"result": "ok"})
    mock_client.post.return_value.raise_for_status = Mock(return_value=None)
    mock_get_config.return_value = MagicMock(cirisnode=MagicMock(base_url="https://x", load_env_vars=lambda: None))
    client = CIRISNodeClient(audit)
    result = await client.run_simplebench("m1", "a1")
    assert result == {"result": "ok"}
    audit.log_action.assert_called()
