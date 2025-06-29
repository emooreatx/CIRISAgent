"""
Unit tests for ActionInstructionGenerator numeric ID guidance.
Tests that the generator properly instructs the agent to use numeric Discord IDs.
"""
import pytest
from unittest.mock import Mock

from ciris_engine.logic.dma.action_selection.action_instruction_generator import ActionInstructionGenerator
from ciris_engine.schemas.runtime.enums import HandlerActionType


class TestActionInstructionNumericIds:
    """Test action instruction generator provides proper numeric ID guidance."""

    @pytest.fixture
    def generator(self):
        """Create action instruction generator."""
        return ActionInstructionGenerator()

    def test_memorize_instruction_includes_numeric_id_guidance(self, generator):
        """Test MEMORIZE action includes guidance about numeric Discord IDs."""
        schema = generator._generate_schema_for_action(HandlerActionType.MEMORIZE)

        # Check that the schema includes numeric ID guidance
        assert "numeric Discord IDs" in schema
        assert "user/537080239679864862" in schema
        assert "primary identifier" in schema
        assert "Usernames can change" in schema
        assert "numeric IDs are permanent" in schema

    def test_recall_instruction_includes_numeric_id_guidance(self, generator):
        """Test RECALL action includes guidance about using numeric IDs."""
        schema = generator._generate_schema_for_action(HandlerActionType.RECALL)

        # Check that the schema includes numeric ID guidance
        assert "numeric Discord IDs" in schema
        assert "user/537080239679864862" in schema
        assert "node_id" in schema
        assert "If you only have a username" in schema

    def test_forget_instruction_includes_numeric_id_guidance(self, generator):
        """Test FORGET action includes guidance about numeric IDs."""
        schema = generator._generate_schema_for_action(HandlerActionType.FORGET)

        # Check that the schema includes numeric ID guidance
        assert "numeric Discord IDs" in schema
        assert "user/537080239679864862" in schema

    def test_full_action_instructions_include_memory_guidance(self, generator):
        """Test that full action instructions include all memory-related guidance."""
        # Generate instructions for memory-related actions
        instructions = generator.generate_action_instructions([
            HandlerActionType.MEMORIZE,
            HandlerActionType.RECALL,
            HandlerActionType.FORGET
        ])

        # Verify all memory actions have numeric ID guidance
        assert instructions.count("numeric Discord IDs") >= 3
        assert instructions.count("user/537080239679864862") >= 3

    def test_memorize_schema_format(self, generator):
        """Test that MEMORIZE schema is properly formatted."""
        schema = generator._format_memory_action_schema("MEMORIZE")

        # Check basic structure
        assert "MEMORIZE:" in schema
        assert "node" in schema
        assert "id: string (unique identifier)" in schema
        assert 'type: "agent"|"user"|"channel"|"concept"' in schema
        assert 'scope: "local"|"identity"|"environment"' in schema

        # Check guidance sections
        assert "For type:" in schema
        assert "For scope:" in schema
        assert "IMPORTANT for user nodes:" in schema

    def test_recall_schema_format(self, generator):
        """Test that RECALL schema is properly formatted."""
        schema = generator._format_memory_action_schema("RECALL")

        # Check basic structure
        assert "RECALL:" in schema
        assert "query" in schema
        assert "node_type" in schema
        assert "node_id" in schema
        assert "scope" in schema
        assert "limit" in schema

        # Check guidance
        assert "For user lookups:" in schema
        assert "Use numeric Discord IDs" in schema
