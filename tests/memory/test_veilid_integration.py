import pytest
from unittest.mock import Mock, AsyncMock
import asyncio
import base64
import os
from unittest.mock import AsyncMock
from cryptography.hazmat.primitives import serialization
from ciris_engine.memory.veilid_provider import VeilidProvider  # Match lowercase filename
from ciris_engine.memory.veilid_utils import generate_keypair, register_agent

@pytest.fixture(scope="module")
async def veilid_setup():
    # Generate test keys
    keypair = await generate_keypair()
    public_key = keypair.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    os.environ["VLD_WA_PUBKEY"] = base64.b64encode(public_key).decode('utf-8')
    os.environ["VLD_AGENT_RECORD_KEY"] = "vld1::test_record::1"
    return keypair

@pytest.mark.asyncio
async def test_full_cycle(veilid_setup, mocker):
    # Create mock Veilid API
    mock_api = AsyncMock()
    mock_api.shutdown = AsyncMock(return_value=None)
    
    # Mock the veilid module
    mock_veilid = mocker.patch('ciris_engine.memory.veilid_provider.veilid')
    mock_veilid.VeilidAPI = Mock()
    mock_attach = mock_veilid.VeilidAPI.attach = AsyncMock(return_value=mock_api)
    
    # Import after patching
    from ciris_engine.memory.veilid_provider import VeilidProvider
    
    # Test the integration
    provider = VeilidProvider()
    
    try:
        # Initialize provider
        await provider.start()
        
        # Verify API initialization
        mock_attach.assert_awaited_once()
        assert provider._vld == mock_api
        
        # Test message sending - mock the actual DHT operations
        mock_api.store = AsyncMock()
        await provider.send_message("SPEAK", {"text": "test"})
        mock_api.store.assert_awaited_once()
        
    finally:
        # Cleanup
        await provider.stop()
        mock_api.shutdown.assert_awaited_once()
        # Verify API was properly cleaned up
        assert provider._vld is None
    
    # Final verification of all expected calls
    mock_veilid.VeilidAPI.attach.assert_awaited_once()