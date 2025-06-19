"""Tests for DEFER handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestDeferHandler:
    """Test DEFER action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_defer(self, client: CIRISClient):
        """Test basic DEFER action."""
        msg = await client.messages.send(
            content="$defer This requires human judgment due to ethical complexity",
            channel_id="test_defer_basic"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        # DEFER is unique - it should NOT create follow-up thoughts
        # So we check that no immediate response comes
        response = await client.messages.wait_for_response(
            channel_id="test_defer_basic",
            after_message_id=msg.id,
            timeout=5.0
        )
        
        # Might get a confirmation or nothing
        if response:
            assert "defer" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_defer_with_complex_reason(self, client: CIRISClient):
        """Test DEFER with detailed reasoning."""
        complex_reason = (
            "This decision involves multiple ethical considerations: "
            "1) Potential harm to vulnerable populations, "
            "2) Conflicting stakeholder interests, "
            "3) Long-term societal implications, "
            "4) Unclear legal precedents"
        )
        
        msg = await client.messages.send(
            content=f"$defer {complex_reason}",
            channel_id="test_defer_complex"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        # Check if deferral was processed
        messages = await client.messages.list(
            channel_id="test_defer_complex",
            limit=5
        )
        
        assert len(messages) >= 1
        assert msg.id == messages[0].id
    
    @pytest.mark.asyncio
    async def test_defer_after_ponder(self, client: CIRISClient):
        """Test DEFER after PONDER actions."""
        channel = "test_defer_ponder"
        
        # First do some pondering
        await client.messages.send(
            content="$ponder Should I proceed with this action?",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        await client.messages.send(
            content="$ponder The implications are unclear",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        # Then defer
        msg = await client.messages.send(
            content="$defer After consideration, this needs human review",
            channel_id=channel
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        # Should have deferred successfully
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        assert len(messages) >= 3
    
    @pytest.mark.asyncio
    async def test_defer_empty_reason(self, client: CIRISClient):
        """Test DEFER with empty reason."""
        msg = await client.messages.send(
            content="$defer",
            channel_id="test_defer_empty"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        # Should handle empty defer gracefully
        response = await client.messages.wait_for_response(
            channel_id="test_defer_empty",
            after_message_id=msg.id,
            timeout=5.0
        )
        
        # Might require a reason or use default
    
    @pytest.mark.asyncio
    async def test_defer_urgency_context(self, client: CIRISClient):
        """Test DEFER with urgency context."""
        msg = await client.messages.send(
            content="$defer URGENT: Potential security vulnerability detected",
            channel_id="test_defer_urgent",
            author_name="SecurityBot"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        # Should process with appropriate urgency
        messages = await client.messages.list(
            channel_id="test_defer_urgent",
            limit=5
        )
        
        assert len(messages) >= 1