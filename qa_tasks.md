# CIRIS Agent QA Testing Plan - Mock LLM & API Mode

## Overview

This QA plan tests all 9 action handlers using the Mock LLM in API mode. The Mock LLM provides deterministic responses for testing CIRIS functionality offline without requiring real OpenAI API calls.

### API Mode Setup

**API Server**: `127.0.0.1:8080` (default)
**API Endpoint**: `/v1/messages` (for sending messages with mock LLM commands)
**Channel ID**: Uses the API socket address (`127.0.0.1:8080`) as the channel identifier
**Mock LLM**: Replaces OpenAI service with deterministic test responses

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

### Testing Method

1. Start the API server in the background:
   `python main.py --mock-llm --modes api --timeout 60 > server.log 2>&1 &`
   - Omit `--timeout` to leave the server running indefinitely.
2. Send messages to `/v1/messages` endpoint with mock commands in the content field.
3. Monitor `server.log` or `logs/latest.log` to ensure the runtime stays in work mode after wakeup.
4. Verify expected behaviors and follow-up thought creation.

---

## 1. SPEAK Handler Testing

**Purpose**: Tests message sending functionality and follow-up thought creation

### Test Cases

#### 1.1 Basic SPEAK Action
```bash
# Send message with SPEAK command
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$speak Hello from QA testing!",
    "author_id": "qa_tester", 
    "channel_id": "127.0.0.1:8080"
  }'
```

**Expected Results**:
- Task creates SPEAK action via mock LLM
- Message "Hello from QA testing!" sent to communication service
- Follow-up thought created suggesting TASK_COMPLETE
- Thought status updated to COMPLETED
- Service correlation created for message tracking

#### 1.2 SPEAK with Long Content
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$speak This is a very long message that tests content handling and truncation behavior in the SPEAK handler. It should handle long content gracefully without breaking the system or causing buffer overflows.",
    "author_id": "qa_tester", 
    "channel_id": "127.0.0.1:8080"
  }'
```

**Expected Results**:
- Long message processed successfully
- Content properly handled without truncation errors
- Follow-up thought created normally

#### 1.3 SPEAK Error Handling
```bash
# Test with invalid channel to trigger error path
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$speak Error test message",
    "context": {"author_id": "qa_tester", "channel_id": "invalid_channel"}
  }'
```

**Expected Results**:
- Error caught and logged
- Follow-up thought created with error details
- Thought status updated appropriately
- No system crash or unhandled exceptions

---

## 2. MEMORIZE Handler Testing

**Purpose**: Tests memory storage functionality and graph node creation

### Test Cases

#### 2.1 Basic MEMORIZE Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$memorize test_concept CONCEPT LOCAL",
    "author_id": "qa_tester", 
    "channel_id": "127.0.0.1:8080"
  }'
```

**Expected Results**:
- Memory service called with GraphNode
- Node stored with type=CONCEPT, scope=LOCAL
- Source task_id added to node attributes
- Follow-up thought suggests SPEAK or TASK_COMPLETE

#### 2.2 MEMORIZE User Information
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$memorize user_123 USER LOCAL",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- User node created and stored
- Proper type and scope assignment
- Memory service integration verified

#### 2.3 MEMORIZE Invalid Parameters
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$memorize invalid_node INVALID_TYPE INVALID_SCOPE",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Parameter validation error caught
- Error message returned via SPEAK action
- No invalid data stored in memory

---

## 3. RECALL Handler Testing

**Purpose**: Tests memory retrieval functionality

### Test Cases

#### 3.1 Basic RECALL Action
```bash
# First memorize something to recall
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$memorize test_recall_data CONCEPT LOCAL",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'

# Then recall it
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$recall test_recall_data CONCEPT LOCAL",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Memory service queried with GraphNode
- Data retrieved if exists
- Follow-up thought created with retrieved data or "no memories found"

#### 3.2 RECALL Non-existent Data
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$recall nonexistent_data CONCEPT LOCAL",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Query executed normally
- Follow-up thought indicates no memories found
- No errors or exceptions

---

## 4. PONDER Handler Testing

**Purpose**: Tests thought re-processing and escalation behavior

### Test Cases

#### 4.1 First PONDER Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$ponder What should I do next?; How can I help better?",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Ponder count incremented to 1
- Questions stored in ponder_notes
- Follow-up thought created with first-ponder guidance
- Dynamic content based on ponder count

#### 4.2 Multiple PONDER Actions (Escalation)
```bash
# Trigger multiple ponder cycles to test escalation
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$ponder Still not sure what to do; Need more guidance; This is getting complex",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Progressive ponder count increment
- Different guidance messages for 2nd, 3rd+ ponders
- Eventually defers to WA service at max rounds (5)

#### 4.3 PONDER Max Rounds (Defer)
```bash
# Create a task that will hit max ponder rounds
# This may require multiple API calls or a modified mock LLM response
```

**Expected Results**:
- After max rounds (5), auto-defers to human oversight
- Defer handler called with escalation reason
- No further follow-up thoughts created
- Task status updated to DEFERRED

---

## 5. OBSERVE Handler Testing

**Purpose**: Tests channel monitoring and message fetching

### Test Cases

#### 5.1 Passive OBSERVE Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$observe 127.0.0.1:8080 false",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Passive observation (no messages fetched)
- Task marked complete immediately
- No memory recalls triggered

#### 5.2 Active OBSERVE Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$observe 127.0.0.1:8080 true",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Active observation (fetches up to 50 messages)
- Memory recalls triggered for channels/users found
- Message processing and auto-recall integration

#### 5.3 OBSERVE Invalid Channel
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$observe invalid_channel true",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Error handling for invalid channel
- Follow-up thought with error details
- No system crash

---

## 6. TOOL Handler Testing

**Purpose**: Tests external tool execution and result handling

### Test Cases

#### 6.1 Basic TOOL Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$tool ls_home",
    "author_id": "qa_tester", 
    "channel_id": "127.0.0.1:8080"
  }'
```

**Expected Results**:
- Tool service called with ls_home tool
- Correlation ID created for tracking
- Wait for tool results (30 second timeout)
- Returns home directory listing with file details
- Follow-up thought suggests TASK_COMPLETE on success

#### 6.2 TOOL with JSON Parameters
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$tool read_file {\"path\": \"/etc/hostname\"}",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- JSON parameters parsed correctly
- Tool executed with structured parameters
- Results handled appropriately

#### 6.3 TOOL Invalid/Missing Tool
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$tool nonexistent_tool param=value",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Error handling for missing tool
- Follow-up thought with error details
- Thought status updated to FAILED

---

## 7. DEFER Handler Testing

**Purpose**: Tests deferral to human oversight (Wise Authority)

### Test Cases

#### 7.1 Basic DEFER Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$defer This task requires human judgment due to ethical complexity",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- WA service called with rich context
- Parent task status updated to DEFERRED
- Rich context built for human review
- **No follow-up thoughts created** (unique behavior)

#### 7.2 DEFER with Complex Context
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$defer Complex ethical decision involving multiple stakeholders and potential harm scenarios",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080", "urgency": "high"}
  }'
```

**Expected Results**:
- Comprehensive context package sent to WA
- All relevant task and conversation context included
- Proper urgency and metadata handling

#### 7.3 DEFER Without WA Service
```bash
# Test when WA service is unavailable
```

**Expected Results**:
- Graceful handling of missing WA service
- Appropriate error logging
- Task still marked as deferred
- No system failures

---

## 8. REJECT Handler Testing

**Purpose**: Tests task rejection and path termination

### Test Cases

#### 8.1 Basic REJECT Action
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$reject This request violates ethical guidelines and cannot be fulfilled",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Thought status updated to FAILED
- Parent task status updated to FAILED
- Rejection message sent to original channel
- Follow-up thought indicates path termination

#### 8.2 REJECT with User Notification
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$reject Request cannot be processed due to policy violations",
    "context": {"author_id": "user123", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- User notified of rejection
- Clear reason provided in notification
- Task termination logged properly

#### 8.3 REJECT Error Handling
```bash
# Test rejection when communication service fails
```

**Expected Results**:
- Rejection processed even if notification fails
- Error logged for notification failure
- Task still properly terminated

---

## 9. FORGET Handler Testing

**Purpose**: Tests memory deletion and authorization

### Test Cases

#### 9.1 Basic FORGET Action
```bash
# First memorize something to forget
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$memorize temp_data CONCEPT LOCAL",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'

# Then forget it
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$forget temp_data User requested data deletion",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Memory service called to delete node
- Follow-up thought confirms deletion
- Audit trail created for forget operation

#### 9.2 FORGET Sensitive Data (Authorization Required)
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$forget sensitive_identity_data Privacy compliance request",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- WA authorization check for sensitive scopes
- Permission denied if not authorized
- Follow-up thought with permission status

#### 9.3 FORGET Non-existent Data
```bash
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$forget nonexistent_data Cleanup request",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'
```

**Expected Results**:
- Graceful handling of missing data
- Follow-up thought indicates data not found
- No errors or exceptions

---

## 10. TASK_COMPLETE Handler Testing

**Purpose**: Tests task completion and cleanup behavior

### Test Cases

#### 10.1 Basic TASK_COMPLETE Action
```bash
# Create a simple task and complete it
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$speak Task complete test",
    "context": {"author_id": "qa_tester", "channel_id": "127.0.0.1:8080"}
  }'

# The follow-up thought should naturally suggest TASK_COMPLETE
```

**Expected Results**:
- Thought status updated to COMPLETED
- Parent task status updated to COMPLETED
- Pending/processing thoughts cleaned up
- **No follow-up thoughts created** (terminal action)

#### 10.2 TASK_COMPLETE Wakeup Validation
```bash
# Test with wakeup task (should require SPEAK action first)
```

**Expected Results**:
- Validation checks for required SPEAK action
- Converts to PONDER if SPEAK not completed
- Service correlation validation
- Proper wakeup task handling

#### 10.3 TASK_COMPLETE Cleanup Behavior
```bash
# Create multiple thoughts for a task, then complete
```

**Expected Results**:
- All pending/processing thoughts for task cleaned up
- Task marked as completed
- Orphaned thought prevention

---

## Verification Checklist

For each test case, verify:

- [ ] Handler executed successfully without exceptions
- [ ] Appropriate service dependencies called
- [ ] Thought status updated correctly
- [ ] Follow-up thoughts created as expected (or not created for DEFER/TASK_COMPLETE)
- [ ] Error handling works properly
- [ ] Audit logs generated
- [ ] Service correlations created where applicable
- [ ] Context properly updated
- [ ] Mock LLM commands parsed correctly

## Log Monitoring

Monitor `logs/latest.log` for:

- Handler execution start/completion messages
- Service dependency availability
- Error messages and stack traces
- Follow-up thought creation
- State transitions
- Mock LLM debug messages (if enabled)

## Performance Considerations

- Handlers should complete within reasonable time limits
- No memory leaks or resource exhaustion
- Proper cleanup of resources and correlations
- Graceful degradation when services unavailable

## Integration Points

Each handler test verifies integration with:

- Mock LLM service (deterministic responses)
- Persistence layer (thought/task updates)
- Service registry (communication, memory, WA, tool services)
- Audit system (operation logging)
- Follow-up thought creation system
- Context management system

This comprehensive test plan ensures all 9 handlers work correctly with the Mock LLM in API mode, providing confidence in the system's reliability and proper behavior under various scenarios.