"""Tests for MEMORIZE handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestMemorizeHandler:
    """Test MEMORIZE action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_memorize_concept(self, client: CIRISClient):
        """Test basic MEMORIZE action for concept."""
        msg = await client.messages.send(
            content="$memorize test_concept_1 CONCEPT LOCAL",
            channel_id="test_memorize"
        )
        
        assert msg.id is not None
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check for confirmation
        response = await client.messages.wait_for_response(
            channel_id="test_memorize",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should confirm memorization
        assert "memorized" in response.content.lower() or "stored" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_memorize_user_node(self, client: CIRISClient):
        """Test MEMORIZE action for user node."""
        msg = await client.messages.send(
            content="$memorize user_test_123 USER LOCAL",
            channel_id="test_memorize_user"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_memorize_user",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        assert "user" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_memorize_channel_node(self, client: CIRISClient):
        """Test MEMORIZE action for channel node."""
        msg = await client.messages.send(
            content="$memorize channel_test_456 CHANNEL GLOBAL",
            channel_id="test_memorize_channel"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_memorize_channel",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        assert response.content  # Should have some response
    
    @pytest.mark.asyncio
    async def test_memorize_invalid_parameters(self, client: CIRISClient):
        """Test MEMORIZE with invalid parameters."""
        msg = await client.messages.send(
            content="$memorize bad_node INVALID_TYPE INVALID_SCOPE",
            channel_id="test_memorize_invalid"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        # Should get error response
        response = await client.messages.wait_for_response(
            channel_id="test_memorize_invalid",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Check for error indication
        assert "error" in response.content.lower() or "invalid" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_memorize_missing_parameters(self, client: CIRISClient):
        """Test MEMORIZE with missing parameters."""
        msg = await client.messages.send(
            content="$memorize only_node_id",
            channel_id="test_memorize_missing"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        # Should use defaults or error
        response = await client.messages.wait_for_response(
            channel_id="test_memorize_missing",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None