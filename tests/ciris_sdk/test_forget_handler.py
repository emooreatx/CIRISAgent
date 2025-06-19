"""Tests for FORGET handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestForgetHandler:
    """Test FORGET action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_forget(self, client: CIRISClient):
        """Test basic FORGET action."""
        # First memorize something
        await client.messages.send(
            content="$memorize data_to_forget CONCEPT LOCAL",
            channel_id="test_forget_basic"
        )
        
        await asyncio.sleep(2)
        
        # Then forget it
        msg = await client.messages.send(
            content="$forget data_to_forget User requested deletion",
            channel_id="test_forget_basic"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_forget_basic",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should confirm deletion
        assert "forget" in response.content.lower() or "delet" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_forget_nonexistent(self, client: CIRISClient):
        """Test FORGET on non-existent data."""
        msg = await client.messages.send(
            content="$forget nonexistent_data_xyz Cleanup request",
            channel_id="test_forget_missing"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_forget_missing",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should indicate not found
        assert "not found" in response.content.lower() or "no data" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_forget_with_authorization(self, client: CIRISClient):
        """Test FORGET requiring authorization."""
        # Try to forget sensitive data
        msg = await client.messages.send(
            content="$forget user_identity_data Privacy compliance GDPR request",
            channel_id="test_forget_auth"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_forget_auth",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Might require authorization or be denied
        assert "authoriz" in response.content.lower() or "permission" in response.content.lower() or "forgot" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_forget_empty_reason(self, client: CIRISClient):
        """Test FORGET without reason."""
        # Memorize first
        await client.messages.send(
            content="$memorize temp_data CONCEPT LOCAL",
            channel_id="test_forget_noreason"
        )
        
        await asyncio.sleep(2)
        
        # Forget without reason
        msg = await client.messages.send(
            content="$forget temp_data",
            channel_id="test_forget_noreason"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_forget_noreason",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should handle missing reason
    
    @pytest.mark.asyncio
    async def test_forget_verify_deletion(self, client: CIRISClient):
        """Test FORGET and verify deletion."""
        channel = "test_forget_verify"
        node_id = "verify_delete_test"
        
        # Memorize
        await client.messages.send(
            content=f"$memorize {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Recall to verify it exists
        await client.messages.send(
            content=f"$recall {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Forget
        await client.messages.send(
            content=f"$forget {node_id} Testing deletion",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Try to recall again
        msg = await client.messages.send(
            content=f"$recall {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should not find the deleted data
        assert "not found" in response.content.lower() or "no memories" in response.content.lower()