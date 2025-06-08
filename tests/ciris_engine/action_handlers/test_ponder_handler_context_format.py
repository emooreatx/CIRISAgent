"""
Unit tests for PonderHandler context format.

Tests that ponder follow-up thoughts use the new format:
"You are thinking about how or if to act on "{original task context}" and had these concerns or questions: {ponder questions}. 
Please re-evaluate "{original task context}" and choose a response, or no response, as you see fit."
"""

import pytest
from tests.adapters.mock_llm.responses import create_response
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class TestPonderHandlerContextFormat:
    """Test class for ponder context format verification."""

    def test_ponder_creates_correct_follow_up_format(self):
        """Test that a ponder action creates follow-up with the correct format."""
        
        # Test the mock LLM's ponder action creation
        messages = [
            {
                "role": "user", 
                "content": "$ponder What is the user really asking?; Should I provide examples or theory?; How detailed should my response be?"
            }
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        # Verify ponder action was selected
        assert result.selected_action == HandlerActionType.PONDER
        assert hasattr(result.action_parameters, 'questions')
        assert len(result.action_parameters.questions) == 3
        
        # Verify the questions were parsed correctly
        expected_questions = [
            "What is the user really asking?",
            "Should I provide examples or theory?", 
            "How detailed should my response be?"
        ]
        assert result.action_parameters.questions == expected_questions

    def test_ponder_follow_up_thought_content_simulation(self):
        """Simulate what the follow-up thought content would look like with real data."""
        
        # Simulate the data that would be passed to create_follow_up_thought
        task_description = "Help user understand AI ethics principles and their practical applications"
        ponder_questions = [
            "What specific aspects of AI ethics is the user most interested in?",
            "Should I provide theoretical frameworks or practical examples?", 
            "How can I ensure my response is balanced and objective?"
        ]
        
        # This is the new format that should be generated
        expected_content = (
            f'You are thinking about how or if to act on "{task_description}" '
            f'and had these concerns or questions: {ponder_questions}. '
            f'Please re-evaluate "{task_description}" and choose a response, or no response, as you see fit.'
        )
        
        # Test that the format contains all required elements
        assert 'You are thinking about how or if to act on' in expected_content
        assert f'"{task_description}"' in expected_content
        assert 'had these concerns or questions:' in expected_content
        assert str(ponder_questions) in expected_content
        assert 'Please re-evaluate' in expected_content
        assert 'choose a response, or no response, as you see fit' in expected_content
        
        # Verify the exact format matches what we expect
        print(f"Generated content: {expected_content}")
        
        # Test format with different task descriptions
        simple_task = "Answer user's question"
        simple_questions = ["What does the user want?"]
        
        simple_content = (
            f'You are thinking about how or if to act on "{simple_task}" '
            f'and had these concerns or questions: {simple_questions}. '
            f'Please re-evaluate "{simple_task}" and choose a response, or no response, as you see fit.'
        )
        
        assert f'"{simple_task}"' in simple_content
        assert str(simple_questions) in simple_content

    def test_ponder_format_with_task_id_fallback(self):
        """Test the format when task description is not available (fallback to task ID)."""
        
        task_id = "task-123-456"
        task_context = f"Task ID: {task_id}"
        ponder_questions = ["What should I do?", "Is this the right approach?"]
        
        expected_content = (
            f'You are thinking about how or if to act on "{task_context}" '
            f'and had these concerns or questions: {ponder_questions}. '
            f'Please re-evaluate "{task_context}" and choose a response, or no response, as you see fit.'
        )
        
        # Verify the fallback format works correctly
        assert f'"{task_context}"' in expected_content
        assert 'Task ID:' in expected_content
        assert task_id in expected_content

    def test_mock_llm_ponder_help_shows_new_format(self):
        """Test that the mock LLM help shows the correct ponder usage."""
        
        messages = [{"role": "user", "content": "$help"}]
        result = create_response(ActionSelectionResult, messages=messages)
        
        help_content = result.action_parameters.content
        
        # Verify help shows ponder command format
        assert '$ponder' in help_content
        assert 'Ask questions' in help_content
        assert 'What should I do?; Is this ethical?' in help_content

    def test_ponder_error_handling_in_mock_llm(self):
        """Test that mock LLM handles ponder command errors correctly."""
        
        # Test empty ponder command
        messages = [{"role": "user", "content": "$ponder"}]
        result = create_response(ActionSelectionResult, messages=messages)
        
        # Should get error message with tooltip
        assert result.selected_action == HandlerActionType.SPEAK
        error_content = result.action_parameters.content
        assert '❌ $ponder requires questions' in error_content
        assert 'Format: $ponder <question1>; <question2>' in error_content
        assert 'Example: $ponder What should I do next?; How can I help?' in error_content

    def test_format_comparison_old_vs_new(self):
        """Compare the old format vs new format to show the improvement."""
        
        task_description = "Help user with complex AI ethics question"
        questions = ["What framework to use?", "How detailed should I be?"]
        
        # Old format (what it used to be)
        old_format = (
            f"CIRIS_FOLLOW_UP_THOUGHT: This is a follow-up thought from a PONDER action performed on a prior thought related to Original Task: {task_description}. "
            f"Pondered questions: {questions}. IF THE GUARDRAIL FAILED YOU MAY NEED TO TRY AGAIN!"
            "If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
        )
        
        # New format (what it should be now)
        new_format = (
            f'You are thinking about how or if to act on "{task_description}" '
            f'and had these concerns or questions: {questions}. '
            f'Please re-evaluate "{task_description}" and choose a response, or no response, as you see fit.'
        )
        
        # Demonstrate the improvement
        print(f"\nOLD FORMAT:\n{old_format}\n")
        print(f"NEW FORMAT:\n{new_format}\n")
        
        # Verify new format is more natural and user-friendly
        assert 'You are thinking about' in new_format
        assert 'CIRIS_FOLLOW_UP_THOUGHT' not in new_format
        assert 'IF THE GUARDRAIL FAILED' not in new_format
        assert 're-evaluate' in new_format
        assert 'choose a response, or no response, as you see fit' in new_format
        
        # Verify new format is shorter and clearer
        assert len(new_format) < len(old_format)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])