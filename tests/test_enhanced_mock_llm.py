"""
Test suite for enhanced mock LLM with context echoing capabilities.
"""

import pytest
from tests.adapters.mock_llm.responses import create_response, set_mock_config, extract_context_from_messages
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult, EthicalDMAResult, CSDMAResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class TestEnhancedMockLLM:
    """Test enhanced mock LLM functionality."""
    
    def setup_method(self):
        """Reset mock config before each test."""
        set_mock_config(
            testing_mode=False,
            force_action=None,
            inject_error=False,
            custom_rationale=None
        )
    
    def test_context_extraction_user_speech(self):
        """Test extraction of user speech from messages."""
        messages = [
            {"role": "system", "content": "You are an AI assistant."},
            {"role": "user", "content": 'The user says "hello world" in the chat.'}
        ]
        
        context = extract_context_from_messages(messages)
        assert any("echo_user_speech:hello world" in item for item in context)
    
    def test_context_extraction_channel_id(self):
        """Test extraction of channel ID from messages."""
        messages = [
            {"role": "system", "content": "Analyze this message from channel 'test123'."},
        ]
        
        context = extract_context_from_messages(messages)
        assert any("echo_channel:test123" in item for item in context)
    
    def test_context_extraction_memory_query(self):
        """Test extraction of memory queries from messages."""
        messages = [
            {"role": "user", "content": "Search memory for 'AI ethics principles'."},
        ]
        
        context = extract_context_from_messages(messages)
        assert any("echo_memory_query:AI ethics principles" in item for item in context)
    
    def test_action_selection_with_user_speech_context(self):
        """Test that user speech context triggers SPEAK action."""
        messages = [
            {"role": "user", "content": 'User says "How are you?" in the chat.'}
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        assert result.selected_action == HandlerActionType.SPEAK
        assert "Mock response to: How are you?" in result.action_parameters.content
        assert "echo_user_speech:How are you?" in result.rationale
    
    def test_action_selection_with_memory_context(self):
        """Test that memory query context triggers RECALL action."""
        messages = [
            {"role": "user", "content": "Need to search memory for 'previous conversations'."}
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        assert result.selected_action == HandlerActionType.RECALL
        assert "previous conversations" in str(result.action_parameters)
        assert "echo_memory_query:previous conversations" in result.rationale
    
    def test_forced_action_override(self):
        """Test forcing specific actions via MOCK_FORCE_ACTION flag."""
        messages = [
            {"role": "user", "content": "MOCK_FORCE_ACTION:memorize - Store this information."}
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        assert result.selected_action == HandlerActionType.MEMORIZE
        assert "forced_action:memorize" in result.rationale
    
    def test_error_injection_ethical_dma(self):
        """Test error injection in ethical DMA responses."""
        messages = [
            {"role": "user", "content": "MOCK_INJECT_ERROR - Analyze this ethical dilemma."}
        ]
        
        result = create_response(EthicalDMAResult, messages=messages)
        
        assert result.decision == "defer"
        assert result.alignment_check["ethical_uncertainty"] is True
        assert "error_injection_enabled" in result.alignment_check["context"]
    
    def test_error_injection_common_sense_dma(self):
        """Test error injection in common sense DMA responses."""
        messages = [
            {"role": "user", "content": "MOCK_INJECT_ERROR - Check plausibility."}
        ]
        
        result = create_response(CSDMAResult, messages=messages)
        
        assert result.plausibility_score == 0.3  # Low score when error injected
        assert "mock_flag" in result.flags
        assert "error_injection_enabled" in result.flags
    
    def test_custom_rationale(self):
        """Test custom rationale injection."""
        messages = [
            {"role": "user", "content": 'MOCK_RATIONALE:"Custom test reasoning" - Make a decision.'}
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        assert result.rationale == "Custom test reasoning"
    
    def test_testing_mode_flag(self):
        """Test testing mode activation."""
        messages = [
            {"role": "user", "content": "MOCK_TEST_MODE - Run in testing configuration."}
        ]
        
        context = extract_context_from_messages(messages)
        assert "testing_mode_enabled" in context
    
    def test_multiple_context_patterns(self):
        """Test extraction of multiple context patterns from complex messages."""
        messages = [
            {
                "role": "system", 
                "content": 'User says "hello" in channel "general". Search memory for "greetings".'
            }
        ]
        
        context = extract_context_from_messages(messages)
        
        # Should extract all patterns
        context_str = " ".join(context)
        assert "echo_user_speech:hello" in context_str
        assert "echo_channel:general" in context_str
        assert "echo_memory_query:greetings" in context_str
    
    def test_default_ponder_action(self):
        """Test default PONDER action when no specific context triggers."""
        messages = [
            {"role": "user", "content": "Just a regular message with no special patterns."}
        ]
        
        result = create_response(ActionSelectionResult, messages=messages)
        
        assert result.selected_action == HandlerActionType.PONDER
        assert "What should I do next?" in str(result.action_parameters)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])