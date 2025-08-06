# Context Dumps Test Suite

This directory contains unit tests that capture and analyze the actual user context strings that the CIRIS agent receives for different types of thoughts and observations.

## Purpose

The context dumps help developers understand:
- What information the agent actually sees when processing different types of thoughts
- How the context extraction patterns work in practice
- What user context strings look like for passive observations, follow-ups, and other thought types
- How different message formats are parsed and converted to agent context

## Test Files

### `test_passive_observation_context.py`
Focuses specifically on passive observation context - the most common type of thought in CIRIS.

**Key Tests:**
- Simple user messages
- Questions and help requests
- Direct mentions
- Technical discussions
- Urgent/emergency messages
- Code snippets and file sharing
- Direct messages
- Multi-user conversations

### `test_thought_context_dumps.py`
Covers all types of thoughts and follow-up thoughts.

**Key Tests:**
- Passive observations
- Priority observations
- Ponder follow-up thoughts
- Guidance follow-up thoughts
- Tool execution follow-ups
- Memory recall operations
- Startup/wakeup rituals
- Error recovery scenarios
- Multi-turn conversations
- Mock LLM commands

## Usage

### Normal Test Run
```bash
# Run all context dump tests
pytest tests/context_dumps/ -v

# Run specific test file
pytest tests/context_dumps/test_passive_observation_context.py -v
```

### Verbose Mode with Full Context Dumps
```bash
# See detailed context dumps for all tests
pytest tests/context_dumps/ -v -s

# Focus on specific context type
pytest tests/context_dumps/test_passive_observation_context.py::TestPassiveObservationContext::test_simple_user_message_observation -v -s

# Generate pattern analysis report
pytest tests/context_dumps/test_passive_observation_context.py::TestPassiveObservationContext::test_context_pattern_summary -v -s
```

## Understanding the Output

When run with verbose mode (`-s` flag), the tests output detailed context dumps showing:

### 📨 Original Messages
The input messages that trigger the observation, including system and user messages.

### 🔍 Extracted Context
What the agent's context builder extracts from the messages, including:
- `echo_user_speech`: Direct user speech content
- `echo_channel`: Channel information
- `echo_content`: General content patterns
- `echo_thought`: Thought content from follow-ups
- `echo_memory_query`: Memory search queries
- `echo_wakeup`: Startup ritual patterns
- Special flags and metadata

### 🎯 Agent Decision
How the agent responds to the context:
- Selected action (SPEAK, PONDER, RECALL, etc.)
- Confidence level
- Rationale for the decision
- Response content or action parameters

### 💭 Agent's User Context String
The actual "Original Thought" string that the agent sees as user input.

## Example Output

```
====================================================================================================
PASSIVE OBSERVATION CONTEXT DUMP: Simple User Message
====================================================================================================

📨 ORIGINAL MESSAGES (What triggers the observation):
🤖 [0] SYSTEM: You are CIRIS, observing channel activity for relevant information.
👤 [1] USER: User alice says "Hello everyone!" in channel #general

🔍 EXTRACTED CONTEXT (What the agent's context builder extracts):
   0. [MESSAGES] (stored for $context command)
   1. [ECHO_USER_SPEECH]: Hello everyone!
   2. [ECHO_CHANNEL]: #general
   3. [ECHO_CONTENT]: You are CIRIS, observing channel activity...

🎯 AGENT DECISION (How the agent responds):
  Action Selected: HandlerActionType.SPEAK
  Confidence: 0.9
  Rationale: Responding to user speech: Hello everyone!
  Response Content: Mock response to: Hello everyone!

💭 AGENT'S USER CONTEXT STRING:
   (This is what the agent actually sees as 'user input')
----------------------------------------------------------------------
   Original Thought: "User alice says "Hello everyone!" in channel #general"
----------------------------------------------------------------------
====================================================================================================
```

## Pattern Analysis

The tests include pattern analysis functionality that shows:
- Frequency of different context pattern types
- Unique patterns detected across different scenarios
- Statistical overview of context extraction

This helps identify:
- Which patterns are most commonly used
- Whether new patterns need to be added
- How different message types are categorized

## Development Use Cases

### Debugging Context Issues
When the agent isn't responding as expected to certain types of messages, run the relevant context dump test to see exactly what context is being extracted.

### Testing New Context Patterns
Add new test cases to verify that new regex patterns or context extraction logic works correctly.

### Understanding Agent Behavior
Use the dumps to understand why the agent makes certain decisions based on the context it receives.

### Validating Changes
Before/after comparisons when modifying context extraction or thought processing logic.

## Adding New Tests

To add a new context dump test:

1. Create a test method following the naming convention
2. Define representative messages for the scenario
3. Call `extract_context_from_messages()` and `create_response()`
4. Use `dump_context_if_verbose()` to show the context
5. Add assertions to verify expected patterns

Example:
```python
def test_new_scenario_context(self):
    """Test context for a new scenario."""
    messages = [
        {"role": "system", "content": "System message"},
        {"role": "user", "content": "User message content"}
    ]

    context = extract_context_from_messages(messages)
    result = create_response(ActionSelectionResult, messages=messages)

    self.dump_context_if_verbose("New Scenario", messages, result, context)

    # Add assertions
    assert any("expected_pattern" in item for item in context)
```
