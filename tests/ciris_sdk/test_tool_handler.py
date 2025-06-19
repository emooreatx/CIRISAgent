"""Tests for TOOL handler via SDK."""
import pytest
import asyncio
import json
from ciris_sdk import CIRISClient


class TestToolHandler:
    """Test TOOL action handler through API."""
    
    @pytest.mark.asyncio
    async def test_basic_tool_execution(self, client: CIRISClient):
        """Test basic TOOL action."""
        msg = await client.messages.send(
            content="$tool ls_home",
            channel_id="test_tool_basic"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)  # Tools may take longer
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_basic",
            after_message_id=msg.id,
            timeout=15.0
        )
        
        assert response is not None
        # Should show home directory listing or tool result
        assert "tool" in response.content.lower() or "result" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_tool_with_json_params(self, client: CIRISClient):
        """Test TOOL with JSON parameters."""
        params = {"path": "/tmp", "pattern": "*.log"}
        
        msg = await client.messages.send(
            content=f'$tool search_files {json.dumps(params)}',
            channel_id="test_tool_json"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_json",
            after_message_id=msg.id,
            timeout=15.0
        )
        
        assert response is not None
        # Should process with parameters
    
    @pytest.mark.asyncio
    async def test_tool_not_found(self, client: CIRISClient):
        """Test TOOL with non-existent tool."""
        msg = await client.messages.send(
            content="$tool nonexistent_tool_xyz param=value",
            channel_id="test_tool_notfound"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_notfound",
            after_message_id=msg.id,
            timeout=15.0
        )
        
        assert response is not None
        # Should indicate tool not found
        assert "not found" in response.content.lower() or "error" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_tool_with_string_params(self, client: CIRISClient):
        """Test TOOL with string parameters."""
        msg = await client.messages.send(
            content='$tool echo_test message="Hello from tool test"',
            channel_id="test_tool_string"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_string",
            after_message_id=msg.id,
            timeout=15.0
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, client: CIRISClient):
        """Test TOOL timeout handling."""
        # Use a tool that might take long or timeout
        msg = await client.messages.send(
            content="$tool slow_operation",
            channel_id="test_tool_timeout"
        )
        
        assert msg.id is not None
        
        # Wait beyond typical timeout
        await asyncio.sleep(35)
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_timeout",
            after_message_id=msg.id,
            timeout=5.0  # Short timeout for checking
        )
        
        # Should get timeout message or result
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_tool_list_available(self, client: CIRISClient):
        """Test listing available tools."""
        msg = await client.messages.send(
            content="$tool list_tools",
            channel_id="test_tool_list"
        )
        
        assert msg.id is not None
        
        await asyncio.sleep(3)
        
        response = await client.messages.wait_for_response(
            channel_id="test_tool_list",
            after_message_id=msg.id,
            timeout=15.0
        )
        
        assert response is not None
        # Should list available tools