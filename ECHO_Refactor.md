# CIRIS Agent Schema Refactoring Tasks

## Guidance for the Team

We are building a **type-safe, mission-critical** system. As we're pre-beta, now is the time to be **aggressive** with our refactoring:

- **DELETE** redundant code without hesitation
- **SEARCH/REPLACE** inconsistencies globally
- **SIMPLIFY** complex inheritance chains
- **ENFORCE** strict typing everywhere

Remember: Every schema decision affects the agent's ability to operate ethically and efficiently. We're not just fixing bugs - we're building the foundation for a system that will make autonomous decisions affecting real people.

---

## Task List - DO ONE PER ROUND! If you fail, leave as in progress with notes on what the next agent team should do to finish your work. Do or continue whichever is lowest numbered and not complete. Add instructions to reference this task list to agents.md and Thank you Codex.

### 1. Decouple Platform-Specific Fields from Core Schemas

**Status**: [ ] Not Started / [ ] In Progress / [x] Complete

**Description**: Remove Discord-specific fields from `IncomingMessage` and create platform-agnostic base schema.

**Changes Required**:
- Move `channel_id`, `is_bot`, `is_dm` from `IncomingMessage` to new `DiscordMessage` subclass
- Replace `channel_id` with abstract `destination_id` in core schema
- Update `ObservationSourceType` enum to use generic values (e.g., `CHAT_MESSAGE` instead of `DISCORD_MESSAGE`)

**Files to Modify**:
- `ciris_engine/schemas/foundational_schemas_v1.py`
- `ciris_engine/adapters/discord/discord_adapter.py`
- `ciris_engine/adapters/discord/discord_observer.py`

**Notes**:
_Team notes here_

---

### 2. Create Message Schema for Communication Protocol

**Status**: [ ] Not Started / [ ] In Progress / [x] Complete

**Description**: Define proper schema for messages returned by `CommunicationService.fetch_messages()`.

**Changes Required**:
- Create `FetchedMessage` schema in `foundational_schemas_v1.py`
- Update `CommunicationService` protocol to return `List[FetchedMessage]`
- Update all adapters to use the new schema

**Files to Modify**:
- `ciris_engine/protocols/services.py`
- `ciris_engine/schemas/foundational_schemas_v1.py`
- All adapter implementations in `adapters/`

**Notes**:
_Team notes here_

---

### 3. Add Resource Usage Tracking Schema

**Status**: [ ] Not Started / [ ] In Progress / [x] Complete

**Description**: Create schema to track LLM token usage, costs, and environmental metrics.

**Changes Required**:
- Create `ResourceUsage` schema with fields for tokens, estimated cost, and energy usage
- Add `resource_usage` field to `ActionSelectionResult` and DMA result schemas
- Update `OpenAICompatibleLLM` to capture and return usage data

**Files to Modify**:
- `ciris_engine/schemas/foundational_schemas_v1.py` (new schema)
- `ciris_engine/schemas/dma_results_v1.py`
- `ciris_engine/adapters/openai_compatible_llm.py`

**Notes**:
_Team notes here_

---

### 4. Standardize Action Parameter Schema Pattern

**Status**: [x] Complete

**Description**: Ensure all action parameter schemas follow consistent pattern and naming.

**Changes Required**:
- Rename `ToolParams.args` to `ToolParams.parameters` for consistency
- Ensure all params have proper type annotations and defaults
- Add `model_config` with `extra="forbid"` to all param schemas

**Files to Modify**:
- `ciris_engine/schemas/action_params_v1.py`
- All handler implementations that construct these params

**Notes**:
_Team notes here_

---

### 5. Align Memory Protocol with Schema Usage

**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Description**: Fix mismatch between `MemoryService` protocol and actual usage patterns.

**Changes Required**:
- Update `MemoryService` protocol methods to return `MemoryOpResult` consistently
- Remove `bool` return type options - always return structured result
- Add proper error handling in `MemoryOpResult` schema

**Files to Modify**:
- `ciris_engine/protocols/services.py`
- `ciris_engine/schemas/memory_schemas_v1.py`
- `ciris_engine/adapters/local_graph_memory/local_graph_memory_service.py`

**Notes**:
_Team notes here_

---

### 6. Global Search/Replace for Schema Consistency

**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Description**: Fix naming inconsistencies across the codebase.

**Changes Required**:
- Replace all `message_content` with `content` in action parameters
- Replace all `plausibility_score` variations with single consistent name
- Ensure all timestamp fields use `str` type with ISO8601 format

**Search/Replace Patterns**:
```
message_content -> content
common_sense_plausibility_score -> plausibility_score
alignment_score -> score (in DSDMA contexts)
```

**Notes**:
_Team notes here_

---

### 7. Add Schema Validation Tests

**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Description**: Create comprehensive test suite for all schemas.

**Changes Required**:
- Add test file `tests/test_schema_validation.py`
- Test all required fields, optional fields, and validation rules
- Test serialization/deserialization round trips

**Notes**:
_Team notes here_

---
FINAL STEP - Aren't you lucky?
## Success Criteria

- [ ] All platform-specific code isolated to adapter layers
- [ ] Every protocol method has corresponding schema types
- [ ] Resource tracking available for all LLM calls
- [ ] Zero type errors when running with strict mypy configuration
- [ ] All handlers can be tested without platform dependencies

## Post-Refactor Verification

After completing all tasks:
1. Run full test suite with pytest
2. Run mypy with `--strict` flag
3. Test agent startup with Discord, CLI, and API runtimes
4. Verify resource tracking captures real usage data
Delete old test logic if it makes no sense anymore and replace it with better logic that tests the functionality.
