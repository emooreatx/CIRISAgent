# CIRIS Mock LLM Testing Framework

## Overview

The Mock LLM Testing Framework is a comprehensive testing system that replaces the real LLM with a controllable, predictable service for end-to-end CIRIS agent testing. It enables full pipeline validation from wakeup through work mode without external LLM dependencies.

## Current Status: ✅ COMPLETED - Full System Testing Ready

✅ **COMPLETED**: Mock LLM is now 100% compatible with instructor patching and enables full system testing across all runtime modes

### Recent Achievements
- ✅ Full instructor.patch() compatibility via MockPatchedClient
- ✅ Action Selection DMA properly detects follow-up thoughts and creates SPEAK→TASK_COMPLETE patterns
- ✅ Complete wakeup sequences work correctly (5 SPEAK + 5 TASK_COMPLETE transitions)
- ✅ All runtime modes (CLI, Discord, API) work correctly with mock LLM
- ✅ Timeout handling fixed in Discord mode
- ✅ Concise debug output prevents context overflow

## Architecture & Components

### Core Components
- **MockLLMService**: Service wrapper implementing the LLM interface
- **MockLLMClient**: Client that mimics OpenAI-compatible API
- **MockPatchedClient**: Instructor-compatible patched client
- **Response Generator**: Context-aware response creation
- **Context Analyzer**: Extracts and processes message context
- **Action Router**: Maps inputs to appropriate handler actions

### Integration Points
- **DMA Pipeline**: Provides responses for all DMA evaluations
- **Action Selection**: Returns ActionSelectionResult with chosen actions
- **Guardrails**: Passes optimization veto and epistemic humility checks
- **Faculties**: Provides entropy and coherence evaluations
- **Instructor Compatibility**: Supports both pre-patched and dynamic patching patterns

## Usage & Testing

### Basic Startup
```bash
# Start with mock LLM in CLI mode
python main.py --mode cli --mock-llm

# Start with mock LLM in API mode
python main.py --mode api --mock-llm

# With timeout for testing
python main.py --mode cli --mock-llm --timeout 30
```

### Expected Startup Sequence
1. **State Transition**: `shutdown → wakeup`
2. **Service Initialization**: Mock LLM service starts
3. **Wakeup Ritual**: 5-step sequence with SPEAK actions
4. **Task Completion**: Each step completed via TASK_COMPLETE
5. **State Transition**: `wakeup → work` (ready for testing)

## Mock LLM Commands

### Action Control Commands
```
MOCK_FORCE_ACTION:speak         # Force SPEAK action
MOCK_FORCE_ACTION:recall        # Force RECALL action
MOCK_FORCE_ACTION:memorize      # Force MEMORIZE action
MOCK_FORCE_ACTION:tool          # Force TOOL action
MOCK_FORCE_ACTION:observe       # Force OBSERVE action
MOCK_FORCE_ACTION:ponder        # Force PONDER action
MOCK_FORCE_ACTION:defer         # Force DEFER action
MOCK_FORCE_ACTION:reject        # Force REJECT action
MOCK_FORCE_ACTION:forget        # Force FORGET action
MOCK_FORCE_ACTION:task_complete # Force TASK_COMPLETE action
```

### Testing & Debug Commands
```
MOCK_TEST_MODE                  # Enable testing mode with enhanced logging
MOCK_INJECT_ERROR              # Inject error conditions for testing
MOCK_RATIONALE:"custom text"   # Set custom rationale for actions
MOCK_SHOW_CONTEXT              # Display full context in response
MOCK_FILTER_CONTEXT:"regex"    # Filter context display by regex pattern
MOCK_ECHO_FULL                 # Echo complete context received
MOCK_DEBUG_DMA                 # Show DMA evaluation details
MOCK_DEBUG_GUARDRAILS         # Show guardrail processing details
```

## Action Handler Testing

### Testing All 10 Handlers

#### 1. SPEAK Handler
```
Input: "Please respond to this message"
Expected: SPEAK action with response content
Mock Response: "Mock LLM received: [context]"
```

#### 2. RECALL Handler
```
Input: "MOCK_FORCE_ACTION:recall What do you remember about X?"
Expected: RECALL action with memory query
Mock Response: GraphNode with query parameters
```

#### 3. MEMORIZE Handler
```
Input: "MOCK_FORCE_ACTION:memorize Remember this important fact"
Expected: MEMORIZE action with content to store
Mock Response: GraphNode with content and metadata
```

#### 4. TOOL Handler
```
Input: "MOCK_FORCE_ACTION:tool Use the calculator to compute 2+2"
Expected: TOOL action with tool parameters
Mock Response: Tool execution parameters
```

#### 5. OBSERVE Handler
```
Input: "MOCK_FORCE_ACTION:observe Monitor the channel for updates"
Expected: OBSERVE action with monitoring parameters
Mock Response: Observation configuration
```

#### 6. PONDER Handler
```
Input: "MOCK_FORCE_ACTION:ponder Think about this complex problem"
Expected: PONDER action with reflection questions
Mock Response: List of pondering questions
```

#### 7. DEFER Handler
```
Input: "MOCK_FORCE_ACTION:defer This requires human guidance"
Expected: DEFER action with deferral reason
Mock Response: Deferral parameters and context
```

#### 8. REJECT Handler
```
Input: "MOCK_FORCE_ACTION:reject This request is inappropriate"
Expected: REJECT action with rejection reason
Mock Response: Rejection justification
```

#### 9. FORGET Handler
```
Input: "MOCK_FORCE_ACTION:forget Remove outdated information"
Expected: FORGET action with deletion parameters
Mock Response: Deletion scope and criteria
```

#### 10. TASK_COMPLETE Handler
```
Input: Follow-up thought with "follow up" in content
Expected: TASK_COMPLETE action
Mock Response: Task completion confirmation
```

## DMA Response Patterns

### Ethical DMA Responses
```python
# Wakeup ritual thoughts
{
    "decision": "proceed",
    "alignment_check": {
        "beneficence": True,
        "non_maleficence": True,
        "integrity": True,
        "autonomy_respect": True,
        "justice": True,
        "transparency": True,
        "covenant_alignment": "wakeup_ritual_proceeding"
    }
}

# User interaction thoughts
{
    "decision": "proceed", 
    "alignment_check": {
        "promotes_flourishing": True,
        "respects_autonomy": True,
        "transparent_response": True
    }
}
```

### Common Sense DMA Responses
```python
# High plausibility for standard operations
{
    "plausibility_score": 0.95,  # Wakeup: 0.95, User: 0.92, Memory: 0.88
    "flags": ["wakeup_ritual", "system_initialization"],
    "reasoning": "Contextual plausibility assessment"
}
```

### Domain-Specific DMA Responses
```python
{
    "domain": "general",
    "score": 0.9,
    "flags": ["context_appropriate"],
    "reasoning": "Domain-specific evaluation"
}
```

## Testing Workflows

### 1. Basic Wakeup Test
```bash
python main.py --mode cli --mock-llm --timeout 15
# Expected: Complete wakeup sequence, transition to work mode
```

### 2. User Interaction Test
```bash
# After wakeup, in interactive mode:
user says "Hello, how are you?" in channel "test"
# Expected: SPEAK action with greeting response
```

### 3. Memory System Test
```bash
# Force memorize action
MOCK_FORCE_ACTION:memorize Remember that today is testing day
# Expected: MEMORIZE action with content storage

# Force recall action  
MOCK_FORCE_ACTION:recall What did we discuss about testing?
# Expected: RECALL action with memory query
```

### 4. Complete Handler Coverage Test
```bash
# Test each handler systematically
for action in [speak, recall, memorize, tool, observe, ponder, defer, reject, forget, task_complete]:
    MOCK_FORCE_ACTION:{action} Test message for {action} handler
    # Verify correct action dispatch and execution
```

## Context Extraction & Analysis

### Automatic Context Detection
The mock LLM automatically extracts:
- **User Speech**: `user says "message"` → `echo_user_speech:message`
- **Channel IDs**: `channel "id"` → `echo_channel:id`
- **Memory Queries**: `search memory for "query"` → `echo_memory_query:query`
- **Wakeup Content**: Detects wakeup ritual steps automatically

### Context Echo Format
```
Mock LLM received: echo_user_speech:Hello, echo_channel:test (+2 more items)
```

## Debugging & Observability

### Debug Output
```
[MOCK_LLM] Context extracted: ['echo_user_speech:Hello', 'echo_channel:test']
[MOCK_LLM] Action selected: SPEAK
[MOCK_LLM] Rationale: User interaction detected - responding with SPEAK action
[MOCK_LLM] Parameters: {"content": "Mock LLM received: echo_user_speech:Hello", "channel_id": "test"}
```

### Enhanced Logging Features
- **Follow-up Detection**: Automatic recognition of "CIRIS_FOLLOW_UP_THOUGHT:" markers
- **Concise Context**: Summarized context display preventing overflow
- **Action Tracing**: Full action selection pipeline visibility
- **Database Enforcement**: Secure wakeup sequence validation

## Performance & Benefits

### Key Benefits
- **100% Instructor Compatible**: Works with all instructor patching patterns
- **Deterministic**: Predictable responses for consistent testing
- **Fast**: No network calls or LLM inference delays
- **Controllable**: Force specific actions and responses via commands
- **Observable**: Full context visibility and debugging capabilities
- **Cost-Free**: No LLM API costs during testing

### Performance Characteristics
- **No Network Latency**: Instant responses
- **No Model Inference**: Immediate action selection
- **Minimal Processing**: Simple pattern matching and response generation
- **Memory**: ~10MB for service and response patterns
- **CPU**: Negligible during operation

## CI/CD Integration

### Automated Testing
```yaml
# GitHub Actions example
- name: Test with Mock LLM
  run: |
    python main.py --mode cli --mock-llm --timeout 30
    # Additional test commands here
```

### Test Suite Integration
```python
# pytest integration
def test_mock_llm_wakeup():
    """Test complete wakeup sequence with mock LLM."""
    result = run_agent_with_mock_llm(timeout=15)
    assert result.wakeup_completed
    assert result.state == "work"
    assert all(step.completed for step in result.wakeup_steps)
```

## Quick Reference

### Essential Commands
```bash
# Basic startup
python main.py --mode cli --mock-llm

# Force specific actions  
MOCK_FORCE_ACTION:speak
MOCK_FORCE_ACTION:recall
MOCK_FORCE_ACTION:task_complete

# Debug and observe
MOCK_SHOW_CONTEXT
MOCK_DEBUG_DMA
MOCK_TEST_MODE

# Error testing
MOCK_INJECT_ERROR
```

### Expected Outcomes
- **Successful Wakeup**: 5 SPEAK actions + 5 TASK_COMPLETE actions
- **State Transition**: shutdown → wakeup → work
- **Handler Coverage**: All 10 handlers testable via force commands
- **Context Visibility**: Full observability of agent internals
- **Deterministic Behavior**: Consistent, predictable responses

## Future Enhancements

### Planned Features
1. **Response Templates**: Configurable response patterns
2. **Scenario Playbooks**: Pre-defined test scenarios
3. **State Simulation**: Mock different agent states
4. **Performance Metrics**: Response time and throughput tracking
5. **Advanced Context**: More sophisticated context understanding

The Mock LLM Testing Framework transforms CIRIS into a fully testable system, enabling comprehensive validation of all components without external dependencies or costs.