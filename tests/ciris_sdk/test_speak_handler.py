"""Tests for SPEAK handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestSpeakHandler:
    """Test SPEAK action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_speak_action(self, client: CIRISClient):
        """Test basic SPEAK action."""
        # Send SPEAK command
        msg = await client.messages.send(
            content="$speak Hello from SDK test!",
            channel_id="test_speak_channel"
        )
        
        assert msg.id is not None
        assert msg.content == "$speak Hello from SDK test!"
        
        # Wait a bit for processing
        await asyncio.sleep(2)
        
        # Check for response
        response = await client.messages.wait_for_response(
            channel_id="test_speak_channel",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        # With mock LLM, we should get a response
        assert response is not None
        assert response.author_id != "sdk_user"
        assert "Hello from SDK test!" in response.content
    
    @pytest.mark.asyncio
    async def test_speak_with_long_content(self, client: CIRISClient):
        """Test SPEAK action with long content."""
        long_content = "This is a very long message " * 20
        
        msg = await client.messages.send(
            content=f"$speak {long_content}",
            channel_id="test_speak_long"
        )
        
        assert msg.id is not None
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check that long content is handled
        response = await client.messages.wait_for_response(
            channel_id="test_speak_long",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Verify at least part of the content is in response
        assert "This is a very long message" in response.content
    
    @pytest.mark.asyncio
    async def test_speak_empty_message(self, client: CIRISClient):
        """Test SPEAK action with empty message."""
        msg = await client.messages.send(
            content="$speak",
            channel_id="test_speak_empty"
        )
        
        assert msg.id is not None
        
        # Even with empty speak, task should be created
        await asyncio.sleep(2)
        
        # May get an error response or default message
        messages = await client.messages.list(
            channel_id="test_speak_empty",
            limit=5
        )
        
        assert len(messages) >= 1