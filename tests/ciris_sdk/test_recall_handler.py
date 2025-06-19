"""Tests for RECALL handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestRecallHandler:
    """Test RECALL action handler through API."""
    
    @pytest.mark.asyncio
    async def test_recall_after_memorize(self, client: CIRISClient):
        """Test RECALL of previously memorized data."""
        # First memorize something
        memorize_msg = await client.messages.send(
            content="$memorize recall_test_data CONCEPT LOCAL",
            channel_id="test_recall"
        )
        
        await asyncio.sleep(2)
        
        # Then recall it
        recall_msg = await client.messages.send(
            content="$recall recall_test_data CONCEPT LOCAL",
            channel_id="test_recall"
        )
        
        assert recall_msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_recall",
            after_message_id=recall_msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should contain the recalled data or confirmation
        assert "recall_test_data" in response.content or "recalled" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_recall_nonexistent_data(self, client: CIRISClient):
        """Test RECALL of non-existent data."""
        msg = await client.messages.send(
            content="$recall nonexistent_node_xyz CONCEPT LOCAL",
            channel_id="test_recall_missing"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_recall_missing",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should indicate no data found
        assert "not found" in response.content.lower() or "no memories" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_recall_with_defaults(self, client: CIRISClient):
        """Test RECALL with default parameters."""
        # Memorize first
        await client.messages.send(
            content="$memorize default_test CONCEPT LOCAL",
            channel_id="test_recall_defaults"
        )
        
        await asyncio.sleep(2)
        
        # Recall with just node ID
        msg = await client.messages.send(
            content="$recall default_test",
            channel_id="test_recall_defaults"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_recall_defaults",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        assert response.content  # Should have some response
    
    @pytest.mark.asyncio
    async def test_recall_different_scopes(self, client: CIRISClient):
        """Test RECALL with different scope parameters."""
        # Memorize in GLOBAL scope
        await client.messages.send(
            content="$memorize scope_test CONCEPT GLOBAL",
            channel_id="test_recall_scope"
        )
        
        await asyncio.sleep(2)
        
        # Try to recall from LOCAL scope (should not find)
        msg = await client.messages.send(
            content="$recall scope_test CONCEPT LOCAL",
            channel_id="test_recall_scope"
        )
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_recall_scope",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Might not find it due to scope mismatch
        
        # Now recall from correct scope
        msg2 = await client.messages.send(
            content="$recall scope_test CONCEPT GLOBAL",
            channel_id="test_recall_scope"
        )
        
        await asyncio.sleep(2)
        
        response2 = await client.messages.wait_for_response(
            channel_id="test_recall_scope",
            after_message_id=msg2.id,
            timeout=10.0
        )
        
        assert response2 is not None