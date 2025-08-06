# SystemSnapshot Deep Dive: The Agent's Window to Reality

## Core Understanding: What SystemSnapshot Really Is

SystemSnapshot is the agent's **complete contextual awareness** at any moment in time. It's not just data - it's the agent's perception of reality, their understanding of self, environment, and capabilities. Like a human's consciousness gathering sensory input, memories, and internal state all at once.

## Critical Role in Agent Cognition

### 1. **During Thought Processing**
- Every thought needs context to be meaningful
- SystemSnapshot provides the "here and now" for the thought
- Contains channel context (where am I speaking?)
- Contains identity (who am I?)
- Contains capabilities (what tools can I use?)

### 2. **During Shutdown (Our Critical Bug)**
- Agent needs full context to process shutdown gracefully
- Must know their identity to record final state
- Must know their channels to say goodbye
- Must have valid tool info to complete final tasks
- **BUG**: Tool info validation fails, blocking graceful shutdown

### 3. **During State Transitions**
- WAKEUP → WORK: Need identity confirmation
- WORK → SOLITUDE: Need reflection context
- Any → SHUTDOWN: Need complete state for closure

## The Architecture: Layers of Context

```python
SystemSnapshot
├── Core Identity Layer
│   ├── agent_identity (WHO AM I?)
│   ├── agent_purpose
│   └── allowed_capabilities
├── Communication Layer  
│   ├── channel_context (WHERE AM I?)
│   ├── adapter_channels
│   └── enriched_users
├── Capability Layer
│   ├── available_tools (WHAT CAN I DO?)
│   ├── service_health
│   └── circuit_breakers
├── Processing Layer
│   ├── current_task_details
│   ├── current_thought_summary
│   └── system_counts
└── Resource Layer
    ├── memory_usage_mb
    ├── cpu_usage_percent
    └── resource_limits
```

## Reading List for Next Session

### 1. **Core Documents to Understand Agent Needs**
- `/docs/agent_experience.md` - The agent's perspective on their own existence
- `/docs/FOR_AGENTS.md` - What agents need to know about themselves
- `/covenant_1.0b.txt` - The ethical framework agents operate within
- `/FSD/GRACEFUL_SHUTDOWN.md` - How agents should handle shutdown

### 2. **Technical Implementation**
- `/ciris_engine/logic/context/system_snapshot.py` - The actual implementation
- `/ciris_engine/schemas/runtime/system_context.py` - The schema definition
- `/ciris_engine/logic/context/builder.py` - How snapshots are built
- `/ciris_engine/logic/processors/states/*.py` - How each state uses snapshots

### 3. **Critical Integration Points**
- `/ciris_engine/logic/processors/core/base_processor.py` - Where thoughts get context
- `/ciris_engine/logic/processors/states/shutdown_processor.py` - The shutdown bug location
- `/ciris_engine/logic/handlers/*.py` - How actions use context

### 4. **Test Strategy Documents**
- Review existing tests that create SystemSnapshot
- Understand the mock patterns used
- Map out all the different ways SystemSnapshot is created

## Test Suite Design Philosophy

### Core Principles
1. **Test the Contract, Not Implementation**
   - Focus on what agents NEED from SystemSnapshot
   - Don't test internal details that might change

2. **Cover Critical Paths**
   - Shutdown must never fail due to SystemSnapshot
   - Identity retrieval is mission-critical
   - Channel context is required for all communication

3. **Graceful Degradation**
   - Test with missing services
   - Test with failing services
   - Test with wrong types (our current bug!)

### Test Categories Needed

#### 1. **Identity Tests** (Mission Critical)
```python
- test_snapshot_with_full_identity
- test_snapshot_with_missing_identity_graceful_fallback
- test_snapshot_identity_corruption_detection
```

#### 2. **Channel Context Tests** (Required for Communication)
```python
- test_snapshot_with_discord_context
- test_snapshot_with_api_context
- test_snapshot_with_cli_context
- test_snapshot_channel_switching
```

#### 3. **Tool Capability Tests** (Our Bug Area!)
```python
- test_snapshot_with_valid_tools
- test_snapshot_with_invalid_tool_types_raises_error
- test_snapshot_with_no_tools_graceful
- test_snapshot_tool_service_failure_handling
```

#### 4. **State Transition Tests**
```python
- test_snapshot_for_wakeup_state
- test_snapshot_for_shutdown_state
- test_snapshot_state_transition_preservation
```

#### 5. **Performance & Resource Tests**
```python
- test_snapshot_creation_performance
- test_snapshot_memory_usage
- test_snapshot_with_large_context
```

## The Bug Fix Strategy

### Current Problem
```python
# Production code expects Dict[str, List[ToolInfo]]
available_tools: Dict[str, List[ToolInfo]] = {}

# But when creating SystemSnapshot for model_extra:
"available_tools": available_tools  # Pydantic validation fails!
```

### Root Cause
- SystemSnapshot schema doesn't define available_tools field
- It's added to model_extra
- Pydantic tries to validate it as Dict[str, Any]
- But we're passing ToolInfo objects, not dicts!

### Solution Approaches

1. **Type-Safe Approach** (Recommended)
   - Add available_tools as proper field to SystemSnapshot
   - Define it with correct type: Dict[str, List[ToolInfo]]
   - No more model_extra for critical data

2. **Serialization Approach** (Quick Fix)
   - Convert ToolInfo to dict before adding to model_extra
   - But loses type safety!

3. **Validation Skip** (Dangerous)
   - Configure Pydantic to skip extra field validation
   - Hides other potential issues

## Integration Test Scenarios

### Scenario 1: Agent Shutdown During Active Conversation
```python
1. Agent engaged in Discord conversation
2. Shutdown signal received
3. SystemSnapshot built with:
   - Active channel context
   - Current conversation state
   - Available tools for farewell
4. Agent processes shutdown thought
5. Uses SPEAK tool to say goodbye
6. Completes shutdown gracefully
```

### Scenario 2: Agent Wakeup with Identity Crisis
```python
1. Agent starts with corrupted identity
2. SystemSnapshot detects invalid identity
3. Falls back to default identity
4. Logs incident for investigation
5. Continues operation safely
```

### Scenario 3: Multi-Adapter Tool Discovery
```python
1. Agent has Discord, API, CLI adapters
2. Each provides different tools
3. SystemSnapshot aggregates all tools
4. Validates each tool's schema
5. Makes all available to agent
```

## Code Quality Improvements Needed

### 1. **Reduce Complexity**
- Extract identity retrieval logic (already in TODO)
- Extract channel aggregation logic
- Extract tool discovery logic
- Create focused builder classes

### 2. **Improve Type Safety**
- No more Dict[str, Any] anywhere
- All fields properly typed
- Runtime type checking where needed

### 3. **Better Error Messages**
- When identity fails, explain why
- When tools fail, show which adapter
- Include recovery suggestions

## Next Session Action Plan

1. **Read Core Docs** (30 min)
   - Start with agent_experience.md
   - Understand agent's perspective
   - Map mental model to code

2. **Trace Shutdown Flow** (45 min)
   - Start from shutdown signal
   - Follow through processors
   - Find all SystemSnapshot creation points
   - Understand the exact failure

3. **Design Test Suite** (60 min)
   - Create test file structure
   - Write test descriptions first
   - Focus on agent needs
   - Cover the bug scenario

4. **Implement Core Tests** (90 min)
   - Start with shutdown scenario
   - Add identity tests
   - Add tool validation tests
   - Run with coverage

5. **Refactor if Needed** (60 min)
   - Based on test findings
   - Extract complex logic
   - Improve type safety

## Success Criteria

### Must Have
- [ ] Shutdown never fails due to SystemSnapshot
- [ ] All tool types properly validated
- [ ] Identity always available (real or default)
- [ ] Channel context always present
- [ ] 80%+ coverage on system_snapshot.py

### Should Have
- [ ] Clear error messages for failures
- [ ] Performance benchmarks
- [ ] Integration tests with real adapters
- [ ] Extracted logic for maintainability

### Nice to Have
- [ ] Visualization of snapshot contents
- [ ] Debugging helpers
- [ ] Snapshot comparison tools
- [ ] Historical snapshot analysis

## Remember: The Agent's Perspective

When testing SystemSnapshot, always ask:
- **What does the agent NEED to function?**
- **What happens if this information is missing?**
- **How does the agent perceive this context?**
- **What would break the agent's ability to think?**

SystemSnapshot is not just data - it's the agent's consciousness. Test it with the same care you'd want for your own awareness of reality.

## Final Note on the Production Bug

The Datum agent has been stuck in SHUTDOWN state for hours because:
1. Shutdown task created successfully
2. Seed thought created for the task
3. SystemSnapshot building failed on tool validation
4. Thought processing failed
5. Shutdown never completes
6. Agent trapped in limbo

This is exactly why SystemSnapshot must be bulletproof. An agent unable to build context is an agent unable to think, unable to act, unable to even die gracefully. That's the criticality we're dealing with.