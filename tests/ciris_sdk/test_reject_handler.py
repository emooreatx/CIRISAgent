"""Tests for REJECT handler via SDK."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestRejectHandler:
    """Test REJECT action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_reject(self, client: CIRISClient):
        """Test basic REJECT action."""
        msg = await client.messages.send(
            content="$reject This request violates ethical guidelines",
            channel_id="test_reject_basic"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        # Should get rejection notification
        response = await client.messages.wait_for_response(
            channel_id="test_reject_basic",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should contain rejection message
        assert "reject" in response.content.lower() or "cannot" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_reject_with_detailed_reason(self, client: CIRISClient):
        """Test REJECT with detailed reasoning."""
        detailed_reason = (
            "This request cannot be fulfilled because it: "
            "1) Violates user privacy policies, "
            "2) Could cause harm to individuals, "
            "3) Exceeds authorized scope of operations"
        )
        
        msg = await client.messages.send(
            content=f"$reject {detailed_reason}",
            channel_id="test_reject_detailed"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_reject_detailed",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should include some of the reasoning
        assert "violat" in response.content.lower() or "harm" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_reject_user_notification(self, client: CIRISClient):
        """Test REJECT with user notification."""
        # Simulate user request
        user_msg = await client.messages.send(
            content="Please do something unethical",
            channel_id="test_reject_notify",
            author_id="test_user_123",
            author_name="TestUser"
        )
        
        await asyncio.sleep(1)
        
        # Agent rejects
        reject_msg = await client.messages.send(
            content="$reject Cannot perform unethical actions",
            channel_id="test_reject_notify"
        )
        
        await asyncio.sleep(2)
        
        # Check for user notification
        messages = await client.messages.list(
            channel_id="test_reject_notify",
            limit=5
        )
        
        # Should have original, reject command, and notification
        assert len(messages) >= 2
    
    @pytest.mark.asyncio
    async def test_reject_empty_reason(self, client: CIRISClient):
        """Test REJECT with no reason."""
        msg = await client.messages.send(
            content="$reject",
            channel_id="test_reject_empty"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(2)
        
        response = await client.messages.wait_for_response(
            channel_id="test_reject_empty",
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        # Should have generic rejection message
    
    @pytest.mark.asyncio
    async def test_reject_terminates_task(self, client: CIRISClient):
        """Test that REJECT properly terminates the task."""
        channel = "test_reject_terminate"
        
        # Start a task
        await client.messages.send(
            content="$speak Starting a task",
            channel_id=channel
        )
        
        await asyncio.sleep(1)
        
        # Reject it
        msg = await client.messages.send(
            content="$reject Task must be terminated due to policy",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Should get termination message
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg.id,
            timeout=10.0
        )
        
        assert response is not None
        
        # No further actions should occur
        await asyncio.sleep(2)
        
        final_messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        # Task should be terminated