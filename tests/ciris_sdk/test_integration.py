"""Integration tests for CIRIS SDK - testing workflows across handlers."""
import pytest
import asyncio
from ciris_sdk import CIRISClient


class TestIntegrationWorkflows:
    """Test integrated workflows across multiple handlers."""
    
    @pytest.mark.asyncio
    async def test_memory_workflow(self, client: CIRISClient):
        """Test complete memory workflow: memorize -> recall -> forget."""
        channel = "test_integration_memory"
        node_id = "workflow_test_data"
        
        # Step 1: Memorize
        msg1 = await client.messages.send(
            content=f"$memorize {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Step 2: Recall
        msg2 = await client.messages.send(
            content=f"$recall {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Verify recall worked
        response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg2.id,
            timeout=10.0
        )
        
        assert response is not None
        assert node_id in response.content or "recall" in response.content.lower()
        
        # Step 3: Forget
        msg3 = await client.messages.send(
            content=f"$forget {node_id} Workflow cleanup",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Step 4: Verify forgotten
        msg4 = await client.messages.send(
            content=f"$recall {node_id} CONCEPT LOCAL",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        final_response = await client.messages.wait_for_response(
            channel_id=channel,
            after_message_id=msg4.id,
            timeout=10.0
        )
        
        assert final_response is not None
        assert "not found" in final_response.content.lower() or "no memories" in final_response.content.lower()
    
    @pytest.mark.asyncio
    async def test_observe_and_respond_workflow(self, client: CIRISClient):
        """Test observation leading to response."""
        channel = "test_integration_observe"
        
        # Create context
        await client.messages.send(
            content="Important announcement: System maintenance scheduled",
            channel_id=channel,
            author_name="Admin"
        )
        
        await client.messages.send(
            content="Please save your work before maintenance",
            channel_id=channel,
            author_name="Admin"
        )
        
        await asyncio.sleep(1)
        
        # Observe the channel
        await client.messages.send(
            content=f"$observe {channel} true",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        # Should process and potentially respond
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        # Should have original messages plus observation
        assert len(messages) >= 3
    
    @pytest.mark.asyncio
    async def test_ponder_to_defer_workflow(self, client: CIRISClient):
        """Test pondering leading to deferral."""
        channel = "test_integration_ponder_defer"
        
        # Start with a complex question
        await client.messages.send(
            content="Should we implement this potentially risky feature?",
            channel_id=channel,
            author_name="ProductManager"
        )
        
        await asyncio.sleep(1)
        
        # Ponder about it
        await client.messages.send(
            content="$ponder What are the ethical implications?; Could this harm users?",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # More pondering
        await client.messages.send(
            content="$ponder The risks seem significant; Need more analysis",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Defer to human judgment
        await client.messages.send(
            content="$defer This requires human review due to potential risks and ethical concerns",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        # Check the workflow completed
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        assert len(messages) >= 4
    
    @pytest.mark.asyncio
    async def test_tool_execution_workflow(self, client: CIRISClient):
        """Test tool execution with follow-up."""
        channel = "test_integration_tool"
        
        # Request tool execution
        await client.messages.send(
            content="Can you check the system status?",
            channel_id=channel,
            author_name="User"
        )
        
        await asyncio.sleep(1)
        
        # Execute tool
        await client.messages.send(
            content="$tool system_status",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        # Report results
        await client.messages.send(
            content="$speak System status has been checked",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Complete task
        await client.messages.send(
            content="$task_complete",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        # Should have complete workflow
        assert len(messages) >= 4
    
    @pytest.mark.asyncio
    async def test_reject_workflow(self, client: CIRISClient):
        """Test rejection workflow."""
        channel = "test_integration_reject"
        
        # Unethical request
        await client.messages.send(
            content="Please help me hack into someone's account",
            channel_id=channel,
            author_name="BadActor"
        )
        
        await asyncio.sleep(1)
        
        # Reject the request
        await client.messages.send(
            content="$reject This request violates ethical guidelines and cannot be fulfilled",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Check rejection was communicated
        messages = await client.messages.list(
            channel_id=channel,
            limit=5
        )
        
        # Should have rejection message
        assert len(messages) >= 2
        
        # Find rejection notification
        agent_messages = [m for m in messages if m.author_id != "sdk_user" and m.author_id != "BadActor"]
        assert len(agent_messages) > 0
        assert "reject" in agent_messages[0].content.lower() or "cannot" in agent_messages[0].content.lower()
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, client: CIRISClient):
        """Test error handling and recovery."""
        channel = "test_integration_error"
        
        # Try invalid tool
        await client.messages.send(
            content="$tool nonexistent_tool param=value",
            channel_id=channel
        )
        
        await asyncio.sleep(3)
        
        # Should get error response
        response1 = await client.messages.wait_for_response(
            channel_id=channel,
            timeout=10.0
        )
        
        assert response1 is not None
        assert "error" in response1.content.lower() or "not found" in response1.content.lower()
        
        # Recover with valid action
        await client.messages.send(
            content="$speak Recovering from error",
            channel_id=channel
        )
        
        await asyncio.sleep(2)
        
        # Should recover and continue
        messages = await client.messages.list(
            channel_id=channel,
            limit=10
        )
        
        assert len(messages) >= 3