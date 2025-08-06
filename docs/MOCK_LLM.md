# Mock LLM System

The Mock LLM system provides deterministic responses for testing CIRIS agent functionality offline without requiring API calls to external LLM services.

## Overview

The Mock LLM system intercepts LLM requests and provides structured responses based on the input context. It supports all CIRIS action types and includes special testing commands for development and debugging.

## Architecture

### Core Components

- **`tests/adapters/mock_llm/service.py`** - Mock LLM service implementation
- **`tests/adapters/mock_llm/responses.py`** - Response generation and context extraction
- **`tests/adapters/mock_llm/responses_action_selection.py`** - Action selection responses
- **`tests/adapters/mock_llm/responses_feedback.py`** - Feedback and epistemic responses
- **`tests/adapters/mock_llm/responses_epistemic.py`** - Entropy and coherence responses

### Integration

The Mock LLM automatically replaces the real LLM service when:
- Running tests
- Using the CLI with mock mode
- Development environments with mock configuration

## Command Syntax

The Mock LLM uses a simple `$` command syntax for testing and debugging:

### Action Commands

| Command | Format | Description |
|---------|--------|-------------|
| `$speak` | `$speak <message>` | Force SPEAK action with content |
| `$recall` | `$recall <node_id> [type] [scope]` | Force RECALL action |
| `$memorize` | `$memorize <node_id> [type] [scope]` | Force MEMORIZE action |
| `$tool` | `$tool <name> [params]` | Force TOOL action |
| `$observe` | `$observe [channel_id] [active]` | Force OBSERVE action |
| `$ponder` | `$ponder <q1>; <q2>` | Force PONDER action with questions |
| `$defer` | `$defer <reason>` | Force DEFER action |
| `$reject` | `$reject <reason>` | Force REJECT action |
| `$forget` | `$forget <node_id> <reason>` | Force FORGET action |
| `$task_complete` | `$task_complete` | Force TASK_COMPLETE action |

### Testing & Debug Commands

| Command | Format | Description |
|---------|--------|-------------|
| `$test` | `$test` | Enable testing mode |
| `$error` | `$error` | Inject error conditions |
| `$rationale` | `$rationale "text"` | Set custom rationale |
| `$context` | `$context` | Show full context |
| `$filter` | `$filter "regex"` | Filter context display |
| `$debug_dma` | `$debug_dma` | Show DMA details |
| `$debug_guardrails` | `$debug_guardrails` | Show guardrail details |
| `$help` | `$help` | Show command help |

### Special Commands

| Command | Format | Description |
|---------|--------|-------------|
| `$speak $context` | `$speak $context` | Display full context dump |

## Parameter Formats

### Node Types
- `AGENT` - Agent-related nodes
- `USER` - User-related nodes
- `CHANNEL` - Channel-related nodes
- `CONCEPT` - Concept/knowledge nodes
- `CONFIG` - Configuration nodes

### Graph Scopes
- `LOCAL` - Local to current context
- `IDENTITY` - Agent identity scope
- `ENVIRONMENT` - Environment scope
- `COMMUNITY` - Community scope
- `NETWORK` - Network-wide scope

### Tool Parameters
Tools accept parameters in `key=value` format:
```
$tool read_file path=/tmp/test.txt
$tool discord_delete_message channel_id=123 message_id=456
```

## Usage Examples

### Basic Actions
```bash
# Send a message
$speak Hello world!

# Recall user information
$recall user123 USER LOCAL

# Store a concept
$memorize concept/ai_ethics CONCEPT LOCAL

# Ask questions
$ponder What should I do?; Is this ethical?

# Defer with reason
$defer Need more information
```

### Testing Features
```bash
# Enable test mode with error injection
$test $error

# Set custom reasoning
$rationale "Testing custom logic" $speak This is a test

# Show full context
$speak $context

# Debug DMA evaluation
$debug_dma $ponder What should I consider?
```

### Advanced Usage
```bash
# Tool execution with parameters
$tool list_files path=/home/user/documents

# Memory operations with specific scopes
$memorize user/preferences USER IDENTITY
$recall config/settings CONFIG LOCAL

# Complex ponder questions
$ponder Should I prioritize speed or accuracy?; What are the ethical implications?; How will this affect users?
```

## Error Handling and Tooltips

The Mock LLM provides helpful error messages and tooltips when commands are used incorrectly:

### Invalid Parameters
```
❌ $memorize requires: <node_id> [type] [scope]
Example: $memorize user123 USER LOCAL
Types: AGENT, USER, CHANNEL, CONCEPT, CONFIG
Scopes: LOCAL, IDENTITY, ENVIRONMENT, COMMUNITY, NETWORK
```

### Missing Arguments
```
❌ $speak requires content. Format: $speak <message>
Example: $speak Hello world!
Special: $speak $context (displays full context)
```

### Invalid Actions
```
❌ Invalid action 'invalid_action'. Valid actions: speak, recall, memorize, tool, observe, ponder, defer, reject, forget, task_complete
```

## Context Extraction

The Mock LLM automatically extracts context from messages using regex patterns:

### Detected Patterns
- **User Speech**: `echo_user_speech:` - Direct user speech content
- **Channel Info**: `echo_channel:` - Channel information
- **Memory Queries**: `echo_memory_query:` - Memory search requests
- **Thought Content**: `echo_thought:` - Thought content from follow-ups
- **Wakeup Patterns**: `echo_wakeup:` - Startup ritual elements
- **General Content**: `echo_content:` - Catch-all content pattern

### Context Display
Use `$speak $context` to see exactly what context the agent receives:

```
📋 **Full Context Display**

**Extracted Context Items:**
• __messages__:[{"role": "user", "content": "..."}]
• echo_user_speech:Hello world
• echo_channel:#general
• forced_action:speak
• action_params:$context

**Original Messages:**
[0] system: You are CIRIS, an AI assistant.
[1] user: Hello world
[2] user: $speak $context
```

## Development Integration

### Test Usage
```python
from tests.adapters.mock_llm.responses import create_response
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult

# Test action selection
messages = [{"role": "user", "content": "$speak Hello!"}]
result = create_response(ActionSelectionResult, messages=messages)
assert result.selected_action == HandlerActionType.SPEAK
```

### Context Dumps
The Mock LLM integrates with the context dumps test suite:
```bash
# Run context dump tests with Mock LLM
pytest tests/context_dumps/ -v -s
```

### Configuration
The Mock LLM can be configured through:
- Environment variables
- Test fixtures
- Direct configuration in test code

## Response Types

The Mock LLM supports all CIRIS response types:

### Action Selection
- `ActionSelectionResult` - Primary action selection responses
- Includes rationale, confidence, and action parameters

### DMA Responses
- `EthicalDMAResult` - Ethical evaluation responses
- `CSDMAResult` - Common sense evaluation
- `DSDMAResult` - Domain-specific evaluation

### Feedback Responses
- `OptimizationVetoResult` - Optimization feedback
- `EpistemicHumilityResult` - Humility assessments

### Epistemic Responses
- `EntropyResult` - Entropy calculations
- `CoherenceResult` - Coherence evaluations

## Best Practices

### Testing
1. Use specific commands to test exact scenarios
2. Combine multiple commands for complex test cases
3. Use `$context` to debug unexpected behavior
4. Leverage error injection for failure testing

### Development
1. Use Mock LLM for offline development
2. Test action flows without API costs
3. Validate context extraction patterns
4. Debug agent decision-making logic

### Debugging
1. Enable debug modes (`$debug_dma`, `$debug_guardrails`)
2. Use context filtering (`$filter "pattern"`)
3. Inject custom rationales for testing
4. Use verbose test output to see full context

## Integration with CIRIS Profiles

The Mock LLM respects CIRIS profile configurations:
- Profile-specific prompt templates
- Action restrictions based on profile
- Custom behavior patterns per profile

See [CIRIS_PROFILES.md](CIRIS_PROFILES.md) for more information about profile integration.

## Troubleshooting

### Common Issues

**Commands not recognized**
- Ensure commands start with `$`
- Check spelling of command names
- Use `$help` to see available commands

**Parameter errors**
- Check parameter format in error messages
- Verify node types and scopes are valid
- Use examples provided in tooltips

**Context not as expected**
- Use `$speak $context` to see extracted context
- Check regex patterns in `responses.py`
- Verify message format matches expected patterns

### Debug Output
Enable Mock LLM debug output:
```
[MOCK_LLM_DEBUG] Request for: ActionSelectionResult
[MOCK_LLM_DEBUG] Found handler: action_selection
[MOCK_LLM_DEBUG] Handler returned: ActionSelectionResult
```

This shows the request flow and handler selection process.
