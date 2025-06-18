"""
Unit tests for the ActionInstructionGenerator.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from typing import Dict, Any

from ciris_engine.dma.action_selection.action_instruction_generator import ActionInstructionGenerator
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.sinks import ListToolsAction


class TestActionInstructionGenerator:
    """Test cases for ActionInstructionGenerator."""
    
    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry."""
        return Mock()
    
    @pytest.fixture
    def generator(self, mock_service_registry):
        """Create an ActionInstructionGenerator instance."""
        return ActionInstructionGenerator(mock_service_registry)
    
    def test_init(self):
        """Test initialization."""
        generator = ActionInstructionGenerator()
        assert generator.service_registry is None
        assert generator._cached_instructions is None
        
        registry = Mock()
        generator = ActionInstructionGenerator(registry)
        assert generator.service_registry == registry
    
    def test_generate_speak_schema(self, generator):
        """Test SPEAK action schema generation."""
        schema = generator._generate_schema_for_action(HandlerActionType.SPEAK)
        assert "SPEAK:" in schema
        assert "content" in schema
        assert "string (required)" in schema
        assert "channel_id" in schema
    
    def test_generate_ponder_schema(self, generator):
        """Test PONDER action schema generation."""
        schema = generator._generate_schema_for_action(HandlerActionType.PONDER)
        assert "PONDER:" in schema
        assert "questions" in schema
        assert "[string]" in schema
        assert "2-3 questions" in schema
    
    def test_generate_reject_schema(self, generator):
        """Test REJECT action schema generation."""
        schema = generator._generate_schema_for_action(HandlerActionType.REJECT)
        assert "REJECT:" in schema
        assert "reason" in schema
        assert "create_filter" in schema
        assert "filter_pattern" in schema
        assert "filter_type" in schema
        assert "filter_priority" in schema
        assert "prevent similar future requests" in schema
    
    def test_generate_memorize_schema(self, generator):
        """Test MEMORIZE action schema generation."""
        schema = generator._generate_schema_for_action(HandlerActionType.MEMORIZE)
        assert "MEMORIZE:" in schema
        assert "node" in schema
        assert "id: string" in schema
        assert "type:" in schema
        assert "scope:" in schema
        assert "attributes" in schema
        assert "For type: use" in schema
        assert "For scope: use" in schema
    
    def test_generate_tool_schema_no_registry(self, generator):
        """Test TOOL schema generation without service registry."""
        generator.service_registry = None
        schema = generator._generate_tool_schema()
        assert "TOOL:" in schema
        assert "name" in schema
        assert "parameters" in schema
        # Should fall back to default tools
        assert "discord_delete_message" in schema
    
    @pytest.mark.asyncio
    async def test_generate_tool_schema_with_tools(self, generator, mock_service_registry):
        """Test TOOL schema generation with dynamic tool discovery."""
        # Mock the multi-service sink
        mock_sink = AsyncMock()
        mock_service_registry.multi_service_sink = mock_sink
        
        # Mock tool information
        mock_tools = {
            "test_tool": {
                "name": "test_tool",
                "service": "test_service",
                "description": "A test tool",
                "parameters": {"param1": "string", "param2": "integer"},
                "when_to_use": "When testing"
            },
            "another_tool": {
                "name": "another_tool",
                "service": "another_service",
                "description": "Another test tool",
                "parameters": {"data": "object"}
            }
        }
        
        mock_sink._handle_list_tools = AsyncMock(return_value=mock_tools)
        
        # Test schema generation - manually run the coroutine
        async def get_schema():
            # Temporarily replace the sync method with async call
            return await mock_sink._handle_list_tools(None, ListToolsAction(
                handler_name="action_instruction_generator",
                metadata={"purpose": "dynamic_instruction_generation"},
                include_schemas=True
            ))
        
        # Run the async function and get tools
        all_tools = await get_schema()
        
        # Now manually build the schema as the generator would
        # Create a mock tool service that returns the tools
        mock_tool_service = AsyncMock()
        mock_tool_service.get_available_tools = AsyncMock(return_value=mock_tools)
        mock_tool_service.adapter_name = "test_service"
        
        with patch.object(generator, 'service_registry') as patched_registry:
            patched_registry.get_services_by_type = Mock(return_value=[mock_tool_service])
            # Mock the asyncio handling to return our result directly
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.is_running = Mock(return_value=False)
                mock_loop.return_value.run_until_complete = Mock(return_value=mock_tools)
                schema = generator._generate_tool_schema()
        
        assert "TOOL:" in schema
        assert "Available tools and their parameters:" in schema
        assert "test_tool: A test tool" in schema
        assert "another_tool: Another test tool" in schema
        assert "When testing" in schema
        assert '"param1": "string"' in schema
        assert '"data": "object"' in schema
    
    def test_generate_action_instructions_all_actions(self, generator):
        """Test generating instructions for all action types."""
        instructions = generator.generate_action_instructions()
        
        # Check that all action types are included
        assert "SPEAK:" in instructions
        assert "PONDER:" in instructions
        assert "TOOL:" in instructions
        assert "OBSERVE:" in instructions
        assert "REJECT:" in instructions
        assert "DEFER:" in instructions
        assert "MEMORIZE:" in instructions
        assert "RECALL:" in instructions
        assert "FORGET:" in instructions
        assert "TASK_COMPLETE:" in instructions
    
    def test_generate_action_instructions_subset(self, generator):
        """Test generating instructions for a subset of actions."""
        permitted_actions = [
            HandlerActionType.SPEAK,
            HandlerActionType.PONDER,
            HandlerActionType.REJECT
        ]
        
        instructions = generator.generate_action_instructions(permitted_actions)
        
        # Check included actions
        assert "SPEAK:" in instructions
        assert "PONDER:" in instructions
        assert "REJECT:" in instructions
        
        # Check excluded actions
        assert "TOOL:" not in instructions
        assert "MEMORIZE:" not in instructions
        assert "DEFER:" not in instructions
    
    def test_get_action_guidance(self, generator):
        """Test getting action-specific guidance."""
        speak_guidance = generator.get_action_guidance(HandlerActionType.SPEAK)
        assert "action_parameters" in speak_guidance
        assert "content" in speak_guidance
        
        ponder_guidance = generator.get_action_guidance(HandlerActionType.PONDER)
        assert "2-3 distinct" in ponder_guidance
        
        reject_guidance = generator.get_action_guidance(HandlerActionType.REJECT)
        assert "unserviceable" in reject_guidance
        assert "create_filter=true" in reject_guidance
        
        # Test TASK_COMPLETE action
        task_complete_guidance = generator.get_action_guidance(HandlerActionType.TASK_COMPLETE)
        assert "TASK_COMPLETE" in task_complete_guidance
        assert "done, impossible, unnecessary" in task_complete_guidance
    
    def test_simplify_schema(self, generator):
        """Test schema simplification."""
        test_schema = {
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "integer", "default": 42},
                "field3": {"type": "boolean"}
            },
            "required": ["field1", "field3"]
        }
        
        simplified = generator._simplify_schema(test_schema)
        assert '"field1": string (required)' in simplified
        assert '"field2"?: integer (default: 42)' in simplified
        assert '"field3": boolean (required)' in simplified
    
    def test_format_memory_action_schema(self, generator):
        """Test memory action schema formatting."""
        memorize_schema = generator._format_memory_action_schema("MEMORIZE")
        assert "MEMORIZE:" in memorize_schema
        assert "attributes?: object (data to store)" in memorize_schema
        
        recall_schema = generator._format_memory_action_schema("RECALL")
        assert "RECALL:" in recall_schema
        assert "attributes?: object" not in recall_schema  # RECALL doesn't have attributes
    
    @pytest.mark.asyncio
    async def test_tool_schema_error_handling(self, generator, mock_service_registry):
        """Test error handling in tool schema generation."""
        # Mock sink that raises an error
        mock_sink = AsyncMock()
        mock_service_registry.multi_service_sink = mock_sink
        mock_sink._handle_list_tools = AsyncMock(side_effect=Exception("Test error"))
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete = lambda coro: asyncio.run(coro)
            schema = generator._generate_tool_schema()
        
        # Should fall back to default tools
        assert "TOOL:" in schema
        assert "discord_delete_message" in schema