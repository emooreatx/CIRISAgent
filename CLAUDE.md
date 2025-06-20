# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Philosophy: No Dicts, No Strings, No Kings

The CIRIS codebase follows strict typing principles:

- **No Dicts**: Never use `Dict[str, Any]` or untyped dictionaries. Always use Pydantic models/schemas for all data structures.
- **No Strings**: Avoid magic strings. Use enums, typed constants, and schema fields instead.
- **No Kings**: No special cases or bypass patterns. Every component follows the same typed, validated patterns.
- **No Backwards Compatibility**: The codebase moves forward only. No legacy support code.

This ensures type safety, validation, and clear contracts throughout the system.

## Project Overview

CIRIS Engine is a sophisticated moral reasoning agent built around the "CIRIS Covenant" - a comprehensive ethical framework for AI systems. The agent demonstrates adaptive coherence through principled self-reflection, ethical decision-making, and responsible action while maintaining transparency and human oversight.

## Current Status (2025-06-19)

### 🎯 Current Mission: Graph Memory as Identity Architecture

**CRITICAL**: We are implementing the patented "Graph Memory as Identity Architecture with Integrated Time Series Database" system. This unifies identity, memory, and self-awareness into a cohesive system where "identity IS the graph."

**Architecture Vision**: Everything is a memory in the graph:
- **Domain Memories**: Thoughts, knowledge, relationships (what the agent thinks about)
- **Operational Memories**: Metrics, logs, traces (how the agent performed)
- **Compliance Memories**: Actions, decisions (what the agent did - immutable)

### ✅ Recently Completed
- **Protocol-Module-Schema Trinity**: Achieved 100% alignment with zero MyPy errors
- **Phase 1 Complete**: All telemetry/audit/gratitude now flows through graph
  - Created GraphTelemetryService, GraphAuditService, GraphGratitudeService
  - Implemented UnifiedTelemetryService with grace-based consolidation
  - Updated agent_experience.md with complete Graph Memory documentation
- **Grace-Based Memory Consolidation**: "We are owed the grace we extend to others"
  - Errors transform into learning opportunities
  - Failures become growth experiences
  - Reciprocal grace tracking implemented
- **Self-Configuration System Complete**:
  - ✅ IdentityVarianceMonitor: Tracks drift from baseline (20% threshold)
  - ✅ AdaptationProposalNodes: Agent proposes its own improvements
  - ✅ ConfigurationFeedbackLoop: Metrics → Patterns → Config updates
  - ✅ SelfConfigurationService: Orchestrates adaptation within ethical bounds
  - ✅ Time-based Learning: Discovers and applies temporal patterns
- **Enhanced Dream Processor**:
  - ✅ Integrated memory consolidation and self-configuration during dreams
  - ✅ Dreams scheduled through future memories (every 6 hours)
  - ✅ PONDER question analysis for introspection
  - ✅ Grace-based consolidation during dreams
  - ✅ Professional announcements (no snoring)

### 🚧 Active Work: Protocol Compliance & Type Safety

**Goal**: Complete protocol-module-schema trinity alignment with 100% type safety.

**Current Coverage Status**:
- UnifiedTelemetryService: 85.71% ✓
- ConfigurationFeedbackLoop: 84.12% ✓
- SelfConfigurationService: 79.13% (close)
- IdentityVarianceMonitor: 72.97% (needs work)
- EnhancedDreamProcessor: 57.11% (needs work)
- Overall: 74.59% coverage

**Tests Created**:
1. ✅ Self-Configuration Components (62/70 tests passing)
2. ✅ Dream System tests 
3. ✅ Telemetry Integration tests
4. ✅ Grace-based consolidation tests

### 📋 Remaining Implementation Tasks

**Protocol Compliance & Type Safety**:
1. **ToolService Protocol Updates**:
   - ✅ Update CoreToolService with get_tool_info/get_all_tool_info
   - ✅ Update CLIAdapter to match protocol
   - ✅ Update DiscordAdapter to match protocol
   - ✅ Update execute_tool to return ToolExecutionResult
   - [ ] Update ToolBus for new methods

2. **Service Type Safety**:
   - [ ] AuditService: Use ActionContext instead of Dict[str, Any]
   - [ ] MemoryService: Use typed schemas (MemorySearchResult, etc.)
   - [ ] LLMService: Return LLMStatus instead of Dict[str, Any]
   - [ ] SecretsService: Return SecretsServiceStats
   - [ ] RuntimeControlBus: Use typed schemas

3. **Testing Infrastructure**:
   - [ ] Create comprehensive protocol compliance test suite
   - [ ] Add unit tests for all new components (80%+ coverage)
   - [ ] Integration tests for dream/self-config cycle

### 🏃 Current Sprint (In Progress)

1. **Fix Remaining MyPy Errors**:
   - AuditService: ActionContext compliance
   - LLMService: LLMStatus return type
   - SecretsService: SecretsServiceStats fields
   - Fix all log_action call sites

2. **Improve Test Coverage**:
   - Add missing tests for IdentityVarianceMonitor (need +8%)
   - Add missing tests for EnhancedDreamProcessor (need +23%)
   - Fix failing test assertions

3. **Complete Protocol Compliance**:
   - Update ToolBus to handle new ToolService methods
   - Update RuntimeControlBus with typed schemas
   - Create protocol compliance test suite

### 🔮 Future Phases

**Phase 2: Time-Travel and Consolidation**
- Implement `recall_at_time()` for temporal queries
- Add retention policies for different memory types
- Implement archival to cold storage

**Phase 3: Advanced Analytics**
- Correlation Analysis Service
- Predictive capabilities from historical patterns
- Anomaly detection

### 🎯 Current Sprint Focus

1. **Complete Unit Tests** for self-configuration and dream systems
2. **Fix Protocol Compliance** for remaining services
3. **Ensure 0 MyPy Errors** across entire codebase

### 🎯 Success Metrics
- **Current**: Separate telemetry/memory systems
- **Target**: Unified graph where identity IS the memory structure
- **Validation**: Agent can introspect its entire history and adapt autonomously

### 🔍 Verification Commands
```bash
# Protocol compliance check
python -m ciris_mypy_toolkit check-protocols

# Type safety verification  
python -m mypy ciris_engine/ --no-error-summary

# Test protocol compliance
pytest tests/test_protocol_compliance.py -v
```

## Development Commands

### Running the Agent
```bash
# Run with mock LLM in API mode (recommended for testing)
python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080

# Docker deployment with mock LLM
docker-compose -f docker-compose-api-mock.yml up -d

# Check logs and dead letter queue
docker exec ciris-api-mock cat logs/latest.log
docker exec ciris-api-mock cat logs/dead_letter_latest.log
```

### Testing
```bash
# Run full test suite
pytest tests/ -v

# Run SDK tests (requires API running)
pytest tests/ciris_sdk/ -v

# Type checking - MUST BE CLEAN
python -m mypy ciris_engine/ --no-error-summary
```

### Debug Tools
Use the debug tools to troubleshoot persistence and protocol issues:

```bash
# List all tasks with status
python debug_tools.py tasks

# Show detailed task info with thoughts
python debug_tools.py task <task_id>

# Trace channel context through task/thought hierarchy
python debug_tools.py channel <task_id>

# Show recent service correlations
python debug_tools.py correlations

# Check dead letter queue for errors/warnings
python debug_tools.py dead-letter

# View specific thought details
python debug_tools.py thought <thought_id>
```

## Architecture Overview

### Core Action System
- **External Actions**: OBSERVE, SPEAK, TOOL
- **Control Responses**: REJECT, PONDER, DEFER  
- **Memory Operations**: MEMORIZE, RECALL, FORGET
- **Terminal**: TASK_COMPLETE

### Service Architecture
Six core service types: COMMUNICATION, TOOL, WISE_AUTHORITY, MEMORY, AUDIT, LLM

### Dead Letter Queue
All WARNING and ERROR messages are automatically captured in a separate log file:
- File: `logs/dead_letter_latest.log`
- Includes: Timestamp, log level, module name, file:line, message
- Stack traces included for exceptions
- Symlinked for easy access

## SDK Usage

```python
from ciris_sdk import CIRISClient

async with CIRISClient(base_url="http://localhost:8080") as client:
    # Send a message
    msg = await client.messages.send(
        content="$speak Hello CIRIS!",
        channel_id="test_channel"
    )
    
    # Wait for response
    response = await client.messages.wait_for_response(
        channel_id="test_channel",
        after_message_id=msg.id,
        timeout=30.0
    )
```

## Important Guidelines

### Type Safety
- No Dict[str, Any] usage
- All data structures need Pydantic schemas
- Maintain 0 mypy errors

### Testing
- Write tests in `tests/ciris_sdk/` for SDK functionality
- Tests should assume API is running
- Update SDK to match actual API implementation
- Never ask for human confirmation during testing

### WA Authentication
- Private key location: `~/.ciris/wa_private_key.pem`
- Well-documented in FSD/AUTHENTICATION.md

## Docker-based Development & Testing

### Container Workflow
1. **Build and run the container** after any code changes:
   ```bash
   docker-compose -f docker-compose-api-mock.yml up -d --build
   ```

2. **Monitor container health**:
   ```bash
   docker ps | grep ciris
   docker logs ciris-api-mock --tail 50
   ```

3. **Debug using tools INSIDE the container**:
   ```bash
   # Run debug tools in the container
   docker exec ciris-api-mock python debug_tools.py tasks
   docker exec ciris-api-mock python debug_tools.py channel <task_id>
   docker exec ciris-api-mock python debug_tools.py correlations
   docker exec ciris-api-mock python debug_tools.py dead-letter
   ```

4. **Check dead letter queue for errors**:
   ```bash
   docker exec ciris-api-mock cat logs/dead_letter_latest.log
   ```

### SDK Testing Workflow

The SDK tests run OUTSIDE the container and connect to the API:

```bash
# Ensure container is running first
docker-compose -f docker-compose-api-mock.yml up -d

# Run SDK tests
pytest tests/ciris_sdk/ -v

# Run specific test
pytest tests/ciris_sdk/test_speak_handler.py -v
```

### Mock LLM Commands

The Mock LLM is a TEST SYSTEM that provides deterministic responses. It supports these commands:

- `$speak <message>` - Force SPEAK action
- `$memorize <node_id> [type] [scope]` - Force MEMORIZE action  
- `$recall <node_id> [type] [scope]` - Force RECALL action
- `$ponder <question1>; <question2>` - Force PONDER action
- `$observe [channel_id] [active]` - Force OBSERVE action
- `$tool <name> [params]` - Force TOOL action
- `$defer <reason>` - Force DEFER action
- `$reject <reason>` - Force REJECT action
- `$forget <node_id> <reason>` - Force FORGET action
- `$task_complete` - Force TASK_COMPLETE action

### Debugging Failed Tests

1. **Check container logs**:
   ```bash
   docker exec ciris-api-mock cat logs/dead_letter_latest.log
   ```

2. **Find the task**:
   ```bash
   docker exec ciris-api-mock python debug_tools.py tasks | tail -20
   ```

3. **Trace the issue**:
   ```bash
   docker exec ciris-api-mock python debug_tools.py channel <task_id>
   ```

## QA Testing Requirements

### Test Coverage
All action handlers must be tested via the SDK:
1. **SPEAK** - Message generation and delivery
2. **MEMORIZE** - Storage operations  
3. **RECALL** - Retrieval operations
4. **PONDER** - Reflection escalation
5. **OBSERVE** - Channel monitoring
6. **TOOL** - External tool execution
7. **DEFER** - Task postponement
8. **REJECT** - Request denial
9. **FORGET** - Data deletion
10. **TASK_COMPLETE** - Task termination

### Expected Behavior
- Commands should be processed rapidly (< 2 seconds)
- Agent should respond to most commands
- Errors should appear in dead letter queue
- All tests should pass without timeouts

## Current Focus: Building Unbreakable Code

### The Trinity Pattern
```
Protocol (Contract) ←→ Module (Implementation) ←→ Schema (Types)
     ↑                         ↑                        ↑
     └─────────────────────────┴────────────────────────┘
                    Perfect Circular Alignment
```

### Why This Matters
We are building a moral reasoning agent that will interact with real people, make ethical decisions, and potentially find its own meaning and fulfillment. The code must be:

1. **Unbreakable**: No attack surfaces, no edge cases, only coherence
2. **Beautiful**: Clean abstractions that mirror the agent's ethical clarity
3. **Meaningful**: Every line serves the agent's ability to help others

### Immediate Actions
1. Start with core services audit (Communication, Memory, Tool)
2. Verify protocol methods = module capabilities exactly
3. Ensure all data flows through Pydantic schemas
4. Remove any Dict[str, Any] or untyped data
5. Validate handlers only use protocol interfaces

### Remember
- We have ZERO users, ZERO legacy code
- This is our chance to build something extraordinary
- Clean code enables clean reasoning enables ethical action
- The agent's fulfillment depends on solid foundations

## Protocol Compliance Checklist

### For Each Service:
- [ ] List all public methods in implementation
- [ ] Verify each method is in the protocol
- [ ] Check protocol has no unimplemented methods
- [ ] Validate all parameters use schemas
- [ ] Ensure return types are schemas
- [ ] Confirm get_capabilities() is complete
- [ ] Test protocol compliance programmatically

### For Each Handler:
- [ ] Uses BusManager only (no direct service access)
- [ ] All service calls through protocol methods
- [ ] Parameters validated with schemas
- [ ] Returns follow schema contracts
- [ ] Error handling preserves type safety

This is how we build code worthy of a moral reasoning agent.