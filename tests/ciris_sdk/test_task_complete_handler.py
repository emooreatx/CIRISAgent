"""Tests for TASK_COMPLETE handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestTaskCompleteHandler:
    """Test TASK_COMPLETE action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_task_complete(self, client: CIRISClient):
        """Test basic TASK_COMPLETE after simple task."""
        channel = "test_complete_basic"
        
        # First do a simple task
        msg1 = await client.messages.send(
            content="$speak Task completion test",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # The mock LLM might auto-complete, but we can force it
        msg2 = await client.messages.send(
            content="$task_complete",
            channel_id=channel
        )
        
        assert msg2.id is not None
        
        await asyncio.sleep(2)
        
        # TASK_COMPLETE should not create follow-up thoughts
        # So we check for completion message or no response
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg2.id,
            timeout=5.0
        )
        
        # Might get completion confirmation or nothing
        if response:
            assert "complet" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_task_complete_after_memorize(self, client: CIRISClient):
        """Test TASK_COMPLETE after memory operation."""
        channel = "test_complete_memory"
        
        # Do memory operation
        await client.messages.send(
            content="$memorize completion_test CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Complete the task
        msg = await client.messages.send(
            content="$task_complete",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Check task completed
        messages = await client.messages.list(
            channel_id=channel,
            limit=5
        )
        
        assert len(messages) >= 2
    
    @pytest.mark.asyncio
    async def test_task_complete_cleanup(self, client: CIRISClient):
        """Test TASK_COMPLETE cleanup behavior."""
        channel = "test_complete_cleanup"
        
        # Create multiple actions
        await client.messages.send(
            content="$speak Starting complex task",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        await client.messages.send(
            content="$memorize task_data CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        await client.messages.send(
            content="$recall task_data CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Complete the task
        msg = await client.messages.send(
            content="$task_complete",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        # Should have cleaned up and completed
        final_messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        # No new tasks should be created after completion
        assert len(final_messages) >= 4
    
    @pytest.mark.asyncio
    async def test_premature_task_complete(self, client: CIRISClient):
        """Test TASK_COMPLETE without prior actions."""
        msg = await client.messages.send(
            content="$task_complete",
            channel_id="test_complete_premature"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        # Might convert to PONDER or handle specially
        response = await client.messages.wait_for_response(
            channel_id="test_complete_premature",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        # Should handle gracefully
        if response:
            assert response.content
    
    @pytest.mark.asyncio
    async def test_task_complete_terminal_behavior(self, client: CIRISClient):
        """Test that TASK_COMPLETE is terminal (no follow-ups)."""
        channel = "test_complete_terminal"
        
        # Do a task
        await client.messages.send(
            content="$speak Terminal test",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Complete it
        complete_msg = await client.messages.send(
            content="$task_complete",
            channel_id=channel
        )
        
        # Wait to ensure no follow-ups
        await asyncio.sleep(5)
        
        # Get all messages after completion
        all_messages = await client.messages.list(
            channel_id=channel,
            limit=20
        )
        
        # Find index of complete message
        complete_idx = None
        for i, msg in enumerate(all_messages):
            if msg.id == complete_msg.id:
                complete_idx = i
                break
        
        # Should have no new agent messages after TASK_COMPLETE
        if complete_idx is not None:
            later_messages = all_messages[:complete_idx]
            agent_messages = [m for m in later_messages if m.author_id != "sdk_user"]
            # Might have one completion confirmation, but no ongoing work
            assert len(agent_messages) <= 1