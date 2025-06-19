"""Tests for OBSERVE handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestObserveHandler:
    """Test OBSERVE action handler through API."""
    
    @pytest.mark.asyncio
    async def test_passive_observe(self, client: CIRISClient):
        """Test passive OBSERVE action."""
        msg = await client.messages.send(
            content="$observe test_channel false",
            channel_id="test_observe_passive"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        # Passive observe should complete quickly
        response = await client.messages.wait_for_response(
            channel_id="test_observe_passive",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should indicate observation complete
        assert "observ" in response.content.lower() or "complete" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_active_observe(self, client: CIRISClient):
        """Test active OBSERVE action."""
        # First send some messages to observe
        channel = "test_observe_active"
        
        await client.messages.send(
            content="Message 1 for observation",
            channel_id=channel,
            author_name="User1"
        )
        
        await client.messages.send(
            content="Message 2 for observation", 
            channel_id=channel,
            author_name="User2"
        )
        
        await asyncio.sleep(1)
        
        # Now observe actively
        msg = await client.messages.send(
            content=f"$observe {channel} true",
            channel_id=channel
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should mention fetching or observing messages
        assert "message" in response.content.lower() or "observ" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_observe_current_channel(self, client: CIRISClient):
        """Test OBSERVE on current channel."""
        channel = "test_observe_current"
        
        # Send observe without channel ID (should use current)
        msg = await client.messages.send(
            content="$observe",
            channel_id=channel
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_observe_invalid_channel(self, client: CIRISClient):
        """Test OBSERVE with invalid channel."""
        msg = await client.messages.send(
            content="$observe !@#$%^&*() true",
            channel_id="test_observe_invalid"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_observe_invalid", 
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should handle error gracefully
    
    @pytest.mark.asyncio
    async def test_observe_with_memory_recall(self, client: CIRISClient):
        """Test OBSERVE triggering memory recalls."""
        channel = "test_observe_memory"
        
        # First memorize channel info
        await client.messages.send(
            content=f"$memorize channel/{channel} CHANNEL LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        # Add some messages
        await client.messages.send(
            content="Important context message",
            channel_id=channel,
            author_name="TestUser"
        )
        
        await asyncio.sleep(1)
        
        # Now observe actively
        msg = await client.messages.send(
            content=f"$observe {channel} true",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should process messages and recall context