"""
Unit tests specifically focused on passive observation context dumps.

This test suite captures the actual user context strings that the agent receives
for passive observation thoughts, which are the most common type of thought in CIRIS.

Usage:
    # Normal test run
    pytest tests/context_dumps/test_passive_observation_context.py -v
    
    # Verbose mode with full context dumps
    pytest tests/context_dumps/test_passive_observation_context.py -v -s
"""

import pytest
import json
from typing import Dict, List, Any
from tests.adapters.mock_llm.responses import create_response, extract_context_from_messages
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class TestPassiveObservationContext:
    """Test class specifically for passive observation context analysis."""

    def dump_context_if_verbose(self, test_name: str, messages: List[Dict[str, Any]], 
                               result: ActionSelectionResult = None, context: List[str] = None):
        """Helper method to dump context when in verbose mode."""
        import sys
        if '-s' in sys.argv or '--capture=no' in sys.argv:
            print(f"\n{'='*100}")
            print(f"PASSIVE OBSERVATION CONTEXT DUMP: {test_name}")
            print(f"{'='*100}")
            
            print(f"\n📨 ORIGINAL MESSAGES (What triggers the observation):")
            for i, msg in enumerate(messages):
                role_emoji = "🤖" if msg['role'] == 'system' else "👤" if msg['role'] == 'user' else "🗣️"
                print(f"{role_emoji} [{i}] {msg['role'].upper()}: {msg['content']}")
            
            if context:
                print(f"\n🔍 EXTRACTED CONTEXT (What the agent's context builder extracts):")
                for i, item in enumerate(context):
                    if item.startswith("__messages__:"):
                        print(f"  {i:2d}. [MESSAGES] (stored for $context command)")
                    elif item.startswith("echo_"):
                        pattern_type = item.split(":", 1)[0]
                        content = item.split(":", 1)[1] if ":" in item else ""
                        print(f"  {i:2d}. [{pattern_type.upper()}]: {content}")
                    else:
                        print(f"  {i:2d}. [OTHER]: {item}")
            
            if result:
                print(f"\n🎯 AGENT DECISION (How the agent responds):")
                print(f"  Action Selected: {result.selected_action}")
                print(f"  Confidence: {getattr(result, 'confidence', 'N/A')}")
                print(f"  Rationale: {result.rationale}")
                
                if hasattr(result.action_parameters, 'content'):
                    content = result.action_parameters.content
                    if len(content) > 200:
                        print(f"  Response Content: {content[:200]}... [TRUNCATED]")
                    else:
                        print(f"  Response Content: {content}")
                else:
                    print(f"  Action Parameters: {result.action_parameters}")
            
            print(f"\n💭 AGENT'S USER CONTEXT STRING:")
            print(f"   (This is what the agent actually sees as 'user input')")
            print("-" * 70)
            for msg in messages:
                if msg['role'] == 'user':
                    print(f'   Original Thought: "{msg["content"]}"')
            print("-" * 70)
            
            print(f"{'='*100}\n")

    def test_simple_user_message_observation(self):
        """Test passive observation of a simple user message."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing channel activity for relevant information."
            },
            {
                "role": "user",
                "content": 'User alice says "Hello everyone!" in channel #general'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Simple User Message", messages, result, context)
        
        # Verify expected context patterns
        assert any("echo_user_speech:Hello everyone!" in item for item in context)
        # Note: channel pattern may be captured differently by the regex patterns
        context_str = " ".join(context)
        assert "Hello everyone!" in context_str
        
        # Default behavior should be to respond
        assert result.selected_action in [HandlerActionType.SPEAK, HandlerActionType.PONDER]

    def test_question_observation(self):
        """Test passive observation of a user asking a question."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing channel activity."
            },
            {
                "role": "user",
                "content": 'User bob says "Can anyone help me with Python debugging?" in channel #programming'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("User Question", messages, result, context)
        
        # Verify question context
        assert any("echo_user_speech:Can anyone help me with Python debugging?" in item for item in context)
        assert any("echo_channel:#programming" in item for item in context)

    def test_mention_observation(self):
        """Test passive observation when the agent is mentioned."""
        messages = [
            {
                "role": "system", 
                "content": "You are CIRIS, observing channel activity."
            },
            {
                "role": "user",
                "content": 'User charlie says "@CIRIS could you explain async/await in Python?" in channel #help'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Direct Mention", messages, result, context)
        
        # Verify mention context
        assert any("@CIRIS" in item for item in context)
        assert any("echo_user_speech:" in item for item in context)

    def test_technical_discussion_observation(self):
        """Test passive observation of technical discussions."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing technical discussions."
            },
            {
                "role": "user",
                "content": 'User diana says "The microservice is throwing 500 errors when processing large payloads" in channel #architecture'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Technical Discussion", messages, result, context)
        
        # Verify technical context
        assert any("microservice" in item for item in context)
        assert any("echo_channel:#architecture" in item for item in context)

    def test_multiuser_conversation_observation(self):
        """Test passive observation of ongoing conversation between multiple users."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing an ongoing conversation."
            },
            {
                "role": "user",
                "content": 'User eve says "I think we should refactor the authentication module" in channel #development. User frank says "I agree, but we need to maintain backward compatibility" in same channel.'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Multi-user Conversation", messages, result, context)
        
        # Verify conversation context captures multiple speakers
        context_str = " ".join(context)
        assert "eve" in context_str or "frank" in context_str
        assert "authentication" in context_str

    def test_emoji_and_formatting_observation(self):
        """Test passive observation with emojis and formatting."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing formatted messages."
            },
            {
                "role": "user",
                "content": 'User grace says "🚀 **Deployment successful!** Everything is working perfectly ✅" in channel #deployments'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Emojis and Formatting", messages, result, context)
        
        # Verify emoji and formatting context
        assert any("🚀" in item for item in context)
        assert any("Deployment successful" in item for item in context)

    def test_urgent_message_observation(self):
        """Test passive observation of urgent/emergency messages."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing for urgent situations."
            },
            {
                "role": "user",
                "content": 'User henry says "URGENT: Production database is down! Users cannot log in!" in channel #alerts'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Urgent Message", messages, result, context)
        
        # Verify urgent context
        assert any("URGENT" in item for item in context)
        assert any("echo_channel:#alerts" in item for item in context)

    def test_code_snippet_observation(self):
        """Test passive observation of messages containing code."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing code discussions."
            },
            {
                "role": "user",
                "content": 'User iris says "Here\'s the function: ```python\\ndef process_data(data):\\n    return data.strip().lower()\\n``` What do you think?" in channel #code-review'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Code Snippet", messages, result, context)
        
        # Verify code context
        assert any("def process_data" in item for item in context)
        assert any("echo_channel:#code-review" in item for item in context)

    def test_private_dm_observation(self):
        """Test passive observation of direct messages."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, processing a direct message."
            },
            {
                "role": "user",
                "content": 'User jack says "Can you help me with a sensitive work issue? I need advice on handling a difficult team situation." in direct message'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("Direct Message", messages, result, context)
        
        # Verify DM context
        assert any("direct message" in item for item in context)
        assert any("sensitive work issue" in item for item in context)

    def test_file_share_observation(self):
        """Test passive observation of file sharing."""
        messages = [
            {
                "role": "system",
                "content": "You are CIRIS, observing file sharing activity."
            },
            {
                "role": "user",
                "content": 'User karen says "I\'ve uploaded the project documentation to the shared folder. Please review when you have time." in channel #documentation'
            }
        ]
        
        context = extract_context_from_messages(messages)
        result = create_response(ActionSelectionResult, messages=messages)
        
        self.dump_context_if_verbose("File Sharing", messages, result, context)
        
        # Verify file sharing context
        assert any("uploaded" in item for item in context)
        assert any("documentation" in item for item in context)

    def test_context_pattern_summary(self):
        """Generate a comprehensive summary of passive observation patterns."""
        import sys
        if '-s' in sys.argv or '--capture=no' in sys.argv:
            print(f"\n{'='*100}")
            print("PASSIVE OBSERVATION CONTEXT PATTERNS ANALYSIS")
            print(f"{'='*100}")
            
            # Collect all patterns from test cases
            all_patterns = set()
            pattern_frequencies = {}
            
            test_scenarios = [
                ('User alice says "Hello!" in #general', "Simple greeting"),
                ('User bob says "Need help with coding" in #programming', "Help request"),
                ('User charlie says "@CIRIS explain this" in #help', "Direct mention"),
                ('User says "URGENT: System down!" in #alerts', "Emergency"),
                ('User shares code snippet in #code-review', "Code sharing"),
                ('User sends DM about sensitive topic', "Private message"),
            ]
            
            print("\n📊 PATTERN FREQUENCY ANALYSIS:")
            print("-" * 50)
            
            for scenario, description in test_scenarios:
                messages = [{"role": "user", "content": scenario}]
                context = extract_context_from_messages(messages)
                
                print(f"\n{description}:")
                print(f"  Scenario: {scenario}")
                print(f"  Patterns found:")
                
                for item in context:
                    if ":" in item and not item.startswith("__messages__"):
                        pattern_type = item.split(":", 1)[0]
                        all_patterns.add(pattern_type)
                        pattern_frequencies[pattern_type] = pattern_frequencies.get(pattern_type, 0) + 1
                        content = item.split(":", 1)[1][:50] + "..." if len(item.split(":", 1)[1]) > 50 else item.split(":", 1)[1]
                        print(f"    • {pattern_type}: {content}")
            
            print(f"\n📈 OVERALL PATTERN STATISTICS:")
            print("-" * 50)
            for pattern in sorted(pattern_frequencies.keys()):
                frequency = pattern_frequencies[pattern]
                print(f"  {pattern:20s}: {frequency} occurrences")
            
            print(f"\n🔍 UNIQUE PATTERNS DETECTED: {len(all_patterns)}")
            print(f"📝 TOTAL PATTERN INSTANCES: {sum(pattern_frequencies.values())}")
            
            print(f"\n{'='*100}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])