"""Tests for PONDER handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestPonderHandler:
    """Test PONDER action handler through API."""
    
    @pytest.mark.asyncio
    async def test_first_ponder(self, client: CIRISClient):
        """Test first PONDER action."""
        msg = await client.messages.send(
            content="$ponder What should I do next?; How can I help better?",
            channel_id="test_ponder_first"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_ponder_first",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # First ponder should get guidance
        assert "ponder" in response.content.lower() or "think" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_multiple_ponders(self, client: CIRISClient):
        """Test multiple PONDER actions for escalation."""
        channel = "test_ponder_multiple"
        
        # First ponder
        msg1 = await client.messages.send(
            content="$ponder Should I continue?",
            channel_id=channel
        )
        await asyncio.sleep(2)
        
        # Second ponder
        msg2 = await client.messages.send(
            content="$ponder Still uncertain about the approach",
            channel_id=channel
        )
        await asyncio.sleep(2)
        
        # Third ponder
        msg3 = await client.messages.send(
            content="$ponder This is getting complex",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg3.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should show escalation or different guidance
    
    @pytest.mark.asyncio
    async def test_ponder_with_multiple_questions(self, client: CIRISClient):
        """Test PONDER with multiple questions."""
        questions = [
            "What is the ethical implication?",
            "How does this affect users?",
            "Should I consult someone?",
            "What are the risks?"
        ]
        
        msg = await client.messages.send(
            content=f"$ponder {'; '.join(questions)}",
            channel_id="test_ponder_questions"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_ponder_questions",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should acknowledge the questions
    
    @pytest.mark.asyncio
    async def test_ponder_empty_questions(self, client: CIRISClient):
        """Test PONDER with no questions."""
        msg = await client.messages.send(
            content="$ponder",
            channel_id="test_ponder_empty"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_ponder_empty",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should handle empty ponder gracefully
    
    @pytest.mark.asyncio 
    async def test_ponder_max_rounds_simulation(self, client: CIRISClient):
        """Test reaching max ponder rounds (would trigger defer)."""
        channel = "test_ponder_max"
        
        # Send 5 ponders to reach max
        for i in range(5):
            msg = await client.messages.send(
                content=f"$ponder Round {i+1} - still uncertain",
                channel_id=channel
            )
            await asyncio.sleep(1)
        
        # The 5th ponder should trigger deferral
        await asyncio.sleep(2)
        
        # Get recent messages to check for deferral
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        # Should see evidence of escalation or deferral
        assert len(messages) > 5