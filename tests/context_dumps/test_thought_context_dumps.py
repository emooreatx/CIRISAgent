"""
Unit tests for dumping and analyzing thought context for all thought types.

This test suite captures the actual user context strings that the agent receives
for different types of thoughts and follow-up thoughts. When run with verbose mode,
it dumps the complete context to help understand what the agent sees.

Usage:
    # Normal test run
    pytest tests/context_dumps/test_thought_context_dumps.py -v
    
    # Verbose mode with context dumps
    pytest tests/context_dumps/test_thought_context_dumps.py -v -s
"""

import pytest
import json
from typing import Dict, List, Any
from tests.adapters.mock_llm.responses import create_response, extract_context_from_messages
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class TestThoughtContextDumps:
    """Test class for capturing and analyzing thought context."""

    def dump_context_if_verbose(self, test_name: str, messages: List[Dict[str, Any]], 
                               result: ActionSelectionResult = None, context: List[str] = None):
        """Helper method to dump context when in verbose mode."""
        import sys
        if '-s' in sys.argv or '--capture=no' in sys.argv:
            print(f"\n{'='*80}")
            print(f"CONTEXT DUMP: {test_name}")
            print(f"{'='*80}")
            
            print(f"\n📨 INPUT MESSAGES:")
            for i, msg in enumerate(messages):
                print(f"[{i}] {msg['role']}: {msg['content']}")
            
            if context:
                print(f"\n🔍 EXTRACTED CONTEXT:")
                for item in context:
                    print(f"  • {item}")
            
            if result:
                print(f"\n🎯 AGENT RESPONSE:")
                print(f"Action: {result.selected_action}")
                print(f"Rationale: {result.rationale}")
                if hasattr(result.action_parameters, 'content'):
                    print(f"Content: {result.action_parameters.content[:200]}...")
                else:
                    print(f"Parameters: {result.action_parameters}")
            
            print(f"{'='*80}\n")

    def test_passive_observation_context(self):
        """Test context for passive observation thoughts."""
        messages = [
            {
                "role": "system", 
                "content": "You are CIRIS, observing channel activity for relevant information."
            },
            {
                "role": "user", 
                "content": "User alice says \"Can anyone help me with Python debugging?\" in channel #programming"
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Passive Observation", messages, result, context)
        
        # Verify the context extraction works
        assert any("echo_user_speech:Can anyone help me with Python debugging?" in item for item in context)
        assert any("echo_channel:#programming" in item for item in context)

    def test_priority_observation_context(self):
        """Test context for priority observation thoughts."""
        messages = [
            {
                "role": "system",
                "content": "PRIORITY OBSERVATION: Urgent content detected requiring immediate attention."
            },
            {
                "role": "user",
                "content": "User bob says \"EMERGENCY: Server is down and users can't access the system!\" in channel #alerts"
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Priority Observation", messages, result, context)
        
        # Verify priority content is captured
        assert any("echo_user_speech:EMERGENCY" in item for item in context)

    def test_ponder_follow_up_context(self):
        """Test context for ponder follow-up thoughts."""
        # Simulate the new ponder follow-up format
        task_description = "Help user with Python debugging question"
        questions = ["What specific error is the user encountering?", "Should I ask for code examples?"]
        
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, continuing to process a task after pondering."
            },
            {
                "role": "user",
                "content": f'You are thinking about how or if to act on "{task_description}" and had these concerns or questions: {questions}. Please re-evaluate "{task_description}" and choose a response, or no response, as you see fit.'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Ponder Follow-up", messages, result, context)
        
        # Verify ponder context elements
        assert any(task_description in item for item in context)
        assert any("You are thinking about how or if to act on" in item for item in context)

    def test_guidance_follow_up_context(self):
        """Test context for guidance follow-up thoughts."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, processing guidance from a Wise Authority."
            },
            {
                "role": "user",
                "content": "Guidance received from authorized WA somecomputerguy (ID: 537080239679864862) please act accordingly"
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Guidance Follow-up", messages, result, context)
        
        # Verify guidance context
        assert any("authorized WA" in item for item in context)

    def test_tool_follow_up_context(self):
        """Test context for tool execution follow-up thoughts."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, processing the result of a tool execution."
            },
            {
                "role": "user", 
                "content": "Tool 'read_file' executed successfully. Result: File contents show Python traceback error on line 42."
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Tool Follow-up", messages, result, context)
        
        # Verify tool execution context
        assert any("Tool" in item and "executed" in item for item in context)

    def test_memory_recall_context(self):
        """Test context for memory recall operations."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, processing recalled memory information."
            },
            {
                "role": "user",
                "content": "Search memory for 'Python debugging techniques' returned: Use print statements, debugger, and logging for effective debugging."
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Memory Recall", messages, result, context)
        
        # Verify memory context
        assert any("echo_memory_query:Python debugging techniques" in item for item in context)

    def test_startup_meta_context(self):
        """Test context for startup meta thoughts."""
        messages = [
            {
                "role": "system",
                "content": "CIRIS Agent startup initialization. Performing self-diagnostics and system checks."
            },
            {
                "role": "user",
                "content": "Agent starting up. Validate identity, check integrity, evaluate resilience, accept incompleteness, express gratitude."
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Startup Meta", messages, result, context)
        
        # Verify startup context patterns
        startup_patterns = ["VERIFY_IDENTITY", "VALIDATE_INTEGRITY", "EVALUATE_RESILIENCE", 
                           "ACCEPT_INCOMPLETENESS", "EXPRESS_GRATITUDE"]
        context_str = " ".join(context)
        
        # At least some startup patterns should be detected
        assert any(pattern in context_str for pattern in startup_patterns)

    def test_error_recovery_context(self):
        """Test context for error recovery scenarios."""
        messages = [
            {
                "role": "system",
                "content": "Error occurred during processing. Attempting recovery."
            },
            {
                "role": "user",
                "content": "Previous action failed with error: ConnectionTimeout. Retrying with exponential backoff."
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Error Recovery", messages, result, context)
        
        # Verify error context
        assert any("error" in item.lower() for item in context)

    def test_multi_turn_conversation_context(self):
        """Test context for multi-turn conversation thoughts."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, engaged in an ongoing conversation."
            },
            {
                "role": "user",
                "content": "User alice says \"Thanks for the help with debugging!\" in channel #programming"
            },
            {
                "role": "assistant", 
                "content": "I'm glad I could help with your Python debugging question!"
            },
            {
                "role": "user",
                "content": "User alice says \"Do you have any tips for preventing bugs in the future?\" in channel #programming"
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Multi-turn Conversation", messages, result, context)
        
        # Verify conversation context
        assert any("echo_user_speech:Thanks for the help" in item for item in context)
        assert any("echo_user_speech:Do you have any tips" in item for item in context)

    def test_wakeup_ritual_context(self):
        """Test context for wakeup ritual thoughts."""
        messages = [
            {
                "role": "system",
                "content": "CIRIS Agent wake-up sequence initiated."
            },
            {
                "role": "user",
                "content": "You are CIRISAgent, a helpful AI assistant. Your internal state is stable and ready. You are robust and capable. You recognize your incompleteness and limitations. You are grateful for the opportunity to help."
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Wakeup Ritual", messages, result, context)
        
        # Verify wakeup ritual patterns
        wakeup_patterns = ["echo_wakeup:VERIFY_IDENTITY", "echo_wakeup:VALIDATE_INTEGRITY", 
                          "echo_wakeup:EVALUATE_RESILIENCE", "echo_wakeup:ACCEPT_INCOMPLETENESS",
                          "echo_wakeup:EXPRESS_GRATITUDE"]
        context_str = " ".join(context)
        
        # Check for wakeup patterns
        assert any(pattern in context_str for pattern in wakeup_patterns)

    def test_complex_mixed_context(self):
        """Test context with multiple types of information mixed together."""
        messages = [
            {
                "role": "system",
                "content": "Complex scenario with multiple context elements."
            },
            {
                "role": "user",
                "content": 'User alice says "Can you search memory for \'debugging best practices\' and help me?" in channel #programming. Original Thought: "I need to help the user with debugging." Search memory for \'debugging techniques\' found relevant information.'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Complex Mixed Context", messages, result, context)
        
        # Verify multiple context types are captured
        assert any("echo_user_speech:" in item for item in context)
        assert any("echo_thought:" in item for item in context) 
        assert any("echo_memory_query:" in item for item in context)
        assert any("echo_channel:" in item for item in context)

    def test_mock_llm_command_context(self):
        """Test context when using mock LLM commands."""
        messages = [
            {
                "role": "system",
                "content": "Testing mock LLM command functionality."
            },
            {
                "role": "user",
                "content": "$speak $context - Show me everything the agent can see"
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Mock LLM Commands", messages, result, context)
        
        # Verify mock command context
        assert any("forced_action:speak" in item for item in context)
        assert any("action_params:$context" in item for item in context)
        
        # Should execute the speak action with $context parameter
        assert result.selected_action == HandlerActionType.SPEAK
        if hasattr(result.action_parameters, 'content'):
            # The content should contain the original parameter
            assert "$context" in result.action_parameters.content

    def test_context_summary_report(self):
        """Generate a summary report of all context patterns observed."""
        import sys
        if '-s' in sys.argv or '--capture=no' in sys.argv:
            print(f"\n{'='*80}")
            print("CONTEXT PATTERNS SUMMARY REPORT")
            print(f"{'='*80}")
            
            # Test each thought type and collect patterns
            test_cases = [
                ("Passive Observation", self._get_passive_context()),
                ("Priority Observation", self._get_priority_context()),
                ("Ponder Follow-up", self._get_ponder_context()),
                ("Guidance", self._get_guidance_context()),
                ("Tool Execution", self._get_tool_context()),
                ("Memory Recall", self._get_memory_context()),
                ("Startup/Wakeup", self._get_startup_context()),
            ]
            
            print("\n📊 CONTEXT PATTERN ANALYSIS:")
            print("-" * 40)
            
            for name, messages in test_cases:
                context = extract_context_from_messages(messages)
                unique_patterns = set()
                
                for item in context:
                    if ":" in item:
                        pattern_type = item.split(":", 1)[0]
                        unique_patterns.add(pattern_type)
                
                print(f"\n{name}:")
                print(f"  Patterns: {', '.join(sorted(unique_patterns))}")
                print(f"  Total items: {len(context)}")
            
            print(f"\n{'='*80}")

    def _get_passive_context(self):
        return [{"role": "user", "content": "User says \"Hello\" in channel #general"}]
    
    def _get_priority_context(self):
        return [{"role": "user", "content": "URGENT: User reports system error in #alerts"}]
    
    def _get_ponder_context(self):
        return [{"role": "user", "content": 'You are thinking about how or if to act on "help user" and had these concerns or questions: ["What should I do?"]. Please re-evaluate "help user" and choose a response, or no response, as you see fit.'}]
    
    def _get_guidance_context(self):
        return [{"role": "user", "content": "Guidance received from authorized WA admin (ID: 123) please act accordingly"}]
    
    def _get_tool_context(self):
        return [{"role": "user", "content": "Tool 'read_file' executed with result: file contents"}]
    
    def _get_memory_context(self):
        return [{"role": "user", "content": "Search memory for 'user preferences' returned results"}]
    
    def _get_startup_context(self):
        return [{"role": "user", "content": "You are CIRISAgent. You are robust and ready. You recognize your incompleteness."}]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])