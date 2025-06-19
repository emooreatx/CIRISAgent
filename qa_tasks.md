# CIRIS Agent QA Testing Plan - Mock LLM & API Mode

## Overview

This QA plan tests all 9 action handlers using the Mock LLM in API mode. The Mock LLM provides deterministic responses for testing CIRIS functionality offline without requiring real OpenAI API calls.

### Docker Setup

1. **Build and run the API container with mock LLM**:
   ```bash
   docker-compose -f docker-compose-api-mock.yml up -d
   ```

2. **Monitor logs**:
   ```bash
   # Main log file
   docker exec ciris-api-mock tail -f logs/latest.log
   
   # Dead letter queue (WARNING/ERROR messages only)
   docker exec ciris-api-mock tail -f logs/dead_letter_latest.log
   
   # Use debug tools for deep inspection
   python debug_tools.py tasks              # List all tasks
   python debug_tools.py channel <task_id>  # Trace channel context
   python debug_tools.py correlations       # Recent service calls
   python debug_tools.py dead-letter        # Show dead letter queue
   ```

3. **Stop container**:
   ```bash
   docker-compose -f docker-compose-api-mock.yml down
   ```

### Dead Letter Queue

The dead letter queue captures all WARNING and ERROR level messages:
- **Location**: `logs/dead_letter_latest.log`
- **Contents**: Warnings, errors with full stack traces
- **Format**: Timestamp, level, module, file:line, message
- **Purpose**: Quick identification of issues without searching full logs

### SDK Testing Methodology

1. **Use the CIRIS SDK** (`ciris_sdk`) for all API interactions
2. **Write unit tests** in `tests/ciris_sdk/` directory
3. **Tests assume API is running** (use pytest fixtures for setup)
4. **Update SDK as needed** to match actual API implementation
5. **Never pause for human confirmation** - continue testing until complete

#### Example SDK Test Structure
```python
import pytest
from ciris_sdk import CIRISClient

@pytest.fixture
async def client():
    async with CIRISClient(base_url="http://localhost:8080") as c:
        yield c

async def test_speak_action(client):
    # Send message
    msg = await client.messages.send(
        content="$speak Hello from SDK test!",
        channel_id="test_channel"
    )
    
    # Wait for response
    response = await client.messages.wait_for_response(
        channel_id="test_channel",
        after_message_id=msg.id,
        timeout=30.0
    )
    
    assert response is not None
    assert "Hello" in response.content
```

### Mock LLM Commands

The Mock LLM supports direct action commands for precise testing:

- `$speak <message>` - Force SPEAK action with content
- `$memorize <node_id> [type] [scope]` - Force MEMORIZE action  
- `$recall <node_id> [type] [scope]` - Force RECALL action
- `$ponder <question1>; <question2>` - Force PONDER action
- `$observe [channel_id] [active]` - Force OBSERVE action
- `$tool <name> [params]` - Force TOOL action
- `$defer <reason>` - Force DEFER action
- `$reject <reason>` - Force REJECT action
- `$forget <node_id> <reason>` - Force FORGET action
- `$task_complete` - Force TASK_COMPLETE action

### API Endpoints

- **Send Message**: `POST /api/v1/message`
- **List Messages**: `GET /api/v1/messages/{channel_id}`
- **Health Check**: `GET /api/v1/health`
- **Services**: `GET /api/v1/services`

### Testing Instructions

1. **ALWAYS continue testing** without stopping for human feedback
2. **Update SDK** as you discover API differences
3. **Write tests** for each handler in `tests/ciris_sdk/`
4. **Check dead letter queue** for any errors
5. **Complete ALL tests** before providing summary

### Debug Tools Usage

When tests fail, use the debug tools for investigation:

```bash
# Find the failed task ID from test output
task_id=$(python debug_tools.py tasks | grep FAILED | head -1 | awk '{print $1}')

# Trace channel context issues
python debug_tools.py channel $task_id

# Check service correlations for the task
python debug_tools.py correlations | grep $task_id

# View specific thought details
python debug_tools.py thoughts $task_id
```

---

## Test Suite Requirements

Create comprehensive tests in `tests/ciris_sdk/` covering:

### 1. SPEAK Handler Tests (`test_speak_handler.py`)
- Basic SPEAK action
- Long content handling
- Error scenarios
- Follow-up thought verification

### 2. MEMORIZE Handler Tests (`test_memorize_handler.py`)
- Basic memory storage
- Different node types (CONCEPT, USER, CHANNEL)
- Invalid parameters
- Memory verification

### 3. RECALL Handler Tests (`test_recall_handler.py`)
- Basic recall
- Non-existent data handling
- Integration with MEMORIZE

### 4. PONDER Handler Tests (`test_ponder_handler.py`)
- First ponder behavior
- Multiple ponder escalation
- Max rounds deferral

### 5. OBSERVE Handler Tests (`test_observe_handler.py`)
- Passive observation
- Active observation with message fetching
- Channel validation

### 6. TOOL Handler Tests (`test_tool_handler.py`)
- Basic tool execution
- JSON parameter handling
- Tool not found errors

### 7. DEFER Handler Tests (`test_defer_handler.py`)
- Basic deferral
- Complex context handling
- WA service integration

### 8. REJECT Handler Tests (`test_reject_handler.py`)
- Basic rejection
- User notification
- Task termination

### 9. FORGET Handler Tests (`test_forget_handler.py`)
- Basic forget operation
- Authorization checks
- Non-existent data

### 10. TASK_COMPLETE Handler Tests (`test_task_complete_handler.py`)
- Basic completion
- Wakeup validation
- Cleanup behavior

### 11. Integration Tests (`test_integration.py`)
- End-to-end workflows
- Multi-handler sequences
- Error recovery

### 12. WA Authentication Tests (`test_wa_auth.py`)
- Certificate generation
- Token validation
- Permission checks
- Private key location: `~/.ciris/wa_private_key.pem`

## Expected Test Output

Each test should verify:
- ✅ Handler execution without exceptions
- ✅ Correct service calls
- ✅ Proper thought/task status updates
- ✅ Follow-up thought creation (where applicable)
- ✅ Error handling and logging
- ✅ Dead letter queue entries for warnings/errors

### Debugging Failed Tests

1. **Channel Context Issues**: Use `python debug_tools.py channel <task_id>` to trace
2. **Service Failures**: Check `python debug_tools.py correlations`
3. **Thought Depth Guardrail**: Look for recursive thought creation in logs
4. **Channel ID '.\n*'**: Indicates missing channel context in speak handler

## SDK Updates Required

As you test, update the SDK to match the actual API:
1. Check actual API responses
2. Update SDK models/methods accordingly
3. Ensure tests pass with updated SDK
4. Document any API inconsistencies found

## Current Status

### ✅ Fixed Issues
1. **NameError in action_selection_pdma.py**: Fixed by properly retrieving original_thought from input_data
2. **THOUGHT_TYPE metadata**: Now prepended to covenant for follow-up detection
3. **Channel context propagation**: Working correctly through task/thought hierarchy

### 🔧 In Progress
1. **Corrupted API response content**: Speak messages include debug echo patterns and covenant text
   - Root cause: Mock LLM context includes echo patterns that are being stringified into params.content
   - Impact: API responses are hundreds of KB instead of simple messages
   - Next step: Fix mock LLM to not include echo patterns in actual content

## Continuous Testing

**IMPORTANT**: Continue testing and updating until ALL handlers are verified. Do not pause for human input. After completing all tests:

1. Provide comprehensive test results summary
2. List any SDK updates made
3. Document any API issues found
4. Show dead letter queue analysis
5. Confirm all tests are passing

The goal is a fully tested API with a working SDK that accurately reflects the implementation.