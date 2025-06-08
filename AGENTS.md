# CIRIS Agent Implementation Task List

## Document Status
**Version**: 1.0.0  
**Status**: ACTIVE WORK PLAN  
**Last Updated**: 2025-06-05

## Overview

This document provides a comprehensive, prioritized task list for completing the CIRIS Agent pre-beta implementation. Tasks are organized by component and include clear success criteria, testing requirements, and integration points.

## ⚡️ AGENT-IN-THE-LOOP TYPE SAFETY & COMPLIANCE

CIRIS Agents are responsible for:
- Enforcing strict type safety and protocol/schema compliance across the codebase
- Using the CIRIS MyPy Toolkit to analyze, review, and execute type and protocol/schema fixes
- Ensuring no code is left in comments, no dead code remains, and all type annotations are protocol/schema-bound
- Reviewing all proposed fixes before execution (no auto-application without agent approval)
- Driving the codebase to zero mypy errors and full compliance

### CIRIS MyPy Toolkit Agent Workflow
1. **Analyze**: Run the toolkit to collect and categorize all mypy, protocol, and schema errors.
2. **Review**: Review the proposed fixes (in JSON or report form) and approve or edit as needed.
3. **Execute**: Apply only the approved fixes, then re-analyze to confirm compliance.

**Key Principles:**
- Only types from `protocols/` and `schemas/` are allowed in type annotations.
- All dead code and commented code is purged automatically.
- No ambiguous or partial fixes are allowed—every change must be protocol/schema-compliant.
- All changes are reviewable and auditable by agents.

## ⚠️ WORKING PRINCIPLES

1. **Test-Driven Development**: Write unit tests BEFORE implementing features
2. **Type Safety**: All code must be properly typed with comprehensive error handling
3. **Security First**: Assume hostile environment, implement defense-in-depth
4. **Fail Secure**: Any failure must default to safe operation
5. **Humble Assessment**: Only mark tasks complete when fully tested and integrated

## 🎯 HIGH PRIORITY TASKS (Blockers for Beta)

### Task Group A: Audit System Integration
**Est: 3-5 days | Priority: CRITICAL | Dependencies: None**

#### A1: Create Audit System Tests
**File**: `tests/ciris_engine/audit/test_audit_integration.py`
**Status**: ✅ COMPLETE

```python
# Required test coverage:
# - Hash chain integrity verification
# - RSA signature generation and verification  
# - Database migration 003 application
# - Integration with existing audit service
# - Performance impact validation
# - Error handling and recovery
# - Key rotation procedures
```

**Success Criteria**:
- [ ] All crypto components have 100% test coverage
- [ ] Performance overhead < 5% of normal operation
- [ ] Migration applies successfully on existing databases
- [ ] Audit service uses signed trail without breaking existing functionality

#### A2: Integrate Signed Audit Trail with LocalAuditLog
**File**: `ciris_engine/adapters/local_audit_log.py`
**Status**: ❌ NOT STARTED

```python
# Integration requirements:
# - Modify existing audit service to use AuditHashChain
# - Add signature verification to audit reads
# - Implement graceful fallback if signing fails
# - Add configuration options for enabling/disabling
# - Maintain backwards compatibility
```

**Success Criteria**:
- [ ] Existing audit functionality unchanged
- [ ] New entries are hash-chained and signed
- [ ] Verification occurs on audit read operations
- [ ] Configuration controls feature activation

#### A3: Apply Database Migration 003 Safely
**File**: `ciris_engine/persistence/migration_runner.py`
**Status**: ❌ NEEDS CREATION

```python
# Migration runner requirements:
# - Safe application of migration 003
# - Rollback procedures if migration fails
# - Backup creation before migration
# - Validation of migration success
# - No data loss during upgrade
```

**Success Criteria**:
- [ ] Migration applies without data loss
- [ ] Rollback works correctly
- [ ] Existing audit logs remain intact
- [ ] New schema validates correctly

### Task Group B: Telemetry System Implementation  
**Est: 2-3 days | Priority: HIGH | Dependencies: A2**

#### B1: Implement Core Telemetry Service
**File**: `ciris_engine/telemetry/core.py`
**Status**: ❌ NEEDS CREATION

```python
# Core service requirements:
# - Metric collection with security filtering
# - Integration with SystemSnapshot
# - Memory-efficient buffering
# - Tiered collection intervals (50ms, 250ms, 1s, 5s, 30s)
# - Thread-safe operations
```

**Success Criteria**:
- [ ] SystemSnapshot contains real-time telemetry data
- [ ] Memory usage < 10MB for telemetry system
- [ ] No PII or sensitive data in metrics
- [ ] Performance impact < 1% of normal operation

#### B2: Create Security Filter Implementation
**File**: `ciris_engine/telemetry/security.py`
**Status**: ❌ NEEDS CREATION

```python
# Security filter requirements:
# - PII detection and removal
# - Metric bounds validation
# - Rate limiting per metric type
# - Sanitization of error messages
# - Audit trail for filtered metrics
```

**Success Criteria**:
- [ ] No PII leaks through telemetry
- [ ] All metrics are bounds-checked
- [ ] Rate limiting prevents DoS
- [ ] Security tests pass 100%

#### B3: Update SystemSnapshot Integration
**File**: `ciris_engine/schemas/context_schemas_v1.py`
**Status**: ❌ NEEDS MODIFICATION

```python
# Integration requirements:
# - Add TelemetrySnapshot to SystemSnapshot
# - Ensure real-time updates from TelemetryService
# - Maintain backwards compatibility
# - Add validation for telemetry data
```

**Success Criteria**:
- [ ] Agent can access its own metrics via SystemSnapshot
- [ ] Telemetry updates in real-time
- [ ] No breaking changes to existing code
- [ ] Validation prevents invalid telemetry data

### Task Group C: Network Schema Implementation
**Est: 2-3 days | Priority: HIGH | Dependencies: None**

#### C1: Create Network Schema Files
**File**: `ciris_engine/schemas/network_schemas_v1.py`
**Status**: ❌ NEEDS CREATION

```python
# From NETWORK_SCHEMAS.md specifications:
# - NetworkType enum (LOCAL, CIRISNODE, DISCORD)
# - AgentIdentity with minimal memory footprint
# - NetworkPresence for discovery
# - Memory optimization (integers vs floats, epochs vs ISO8601)
```

**Success Criteria**:
- [ ] All schemas serialize to < 1KB each
- [ ] Memory usage tested on Raspberry Pi
- [ ] Type validation works correctly
- [ ] Integration with existing schemas

#### C2: Create Community Schema Files
**File**: `ciris_engine/schemas/community_schemas_v1.py`
**Status**: ❌ NEEDS CREATION

```python
# Community awareness requirements:
# - CommunityHealth with 0-100 integer metrics
# - MinimalCommunityContext for resource constraints
# - Single community tracking to save memory
```

**Success Criteria**:
- [ ] Single community context < 4KB memory
- [ ] Health metrics use single bytes
- [ ] Integration with graph memory

#### C3: Create Wisdom Schema Files
**File**: `ciris_engine/schemas/wisdom_schemas_v1.py`
**Status**: ❌ NEEDS CREATION

```python
# Wisdom-seeking requirements:
# - WisdomRequest for isolation scenarios
# - UniversalGuidanceProtocol as last resort
# - Clear activation criteria (72+ hours isolation)
# - Integration with deferral system
```

**Success Criteria**:
- [ ] UGP only activates after proper escalation
- [ ] Integration with existing WA deferral
- [ ] Clear audit trail for UGP activation
- [ ] Prevents bypass of normal deferral

#### C4: Update Schema Registry and Exports
**Files**: `ciris_engine/schemas/__init__.py`, `ciris_engine/schemas/schema_registry.py`
**Status**: ❌ NEEDS MODIFICATION

```python
# Registry requirements:
# - Add all new schemas to registry
# - Update exports in __init__.py
# - Maintain backwards compatibility
# - Add version tracking
```

**Success Criteria**:
- [ ] All new schemas accessible via imports
- [ ] Schema registry contains all schemas
- [ ] No breaking changes to existing imports
- [ ] Version tracking works correctly

## 🔧 MEDIUM PRIORITY TASKS (Quality & Robustness)

### Task Group D: Secrets System Enhancement
**Est: 1-2 days | Priority: MEDIUM | Dependencies: None**

#### D1: Complete Secrets Service Implementation
**Files**: `ciris_engine/secrets/filter.py`, `ciris_engine/secrets/store.py`, `ciris_engine/secrets/service.py`, `ciris_engine/secrets/tools.py`
**Status**: ❌ PARTIALLY IMPLEMENTED

```python
# Secrets system completion:
# - Implement missing components referenced in __init__.py
# - Integration with graph memory for RECALL/MEMORIZE/FORGET
# - Auto-FORGET behavior after task completion
# - Agent tools for secrets management
```

**Success Criteria**:
- [ ] All imports in secrets/__init__.py work
- [ ] RECALL/MEMORIZE/FORGET work with secrets
- [ ] Auto-FORGET prevents secret accumulation
- [ ] Agent can manage detection patterns

#### D2: Create Secrets Integration Tests
**File**: `tests/ciris_engine/secrets/test_secrets_integration.py`
**Status**: ❌ NEEDS CREATION

```python
# Integration test requirements:
# - End-to-end secret detection and storage
# - Graph memory integration testing
# - Auto-FORGET behavior validation
# - Performance impact testing
```

**Success Criteria**:
- [ ] Secrets detected and stored correctly
- [ ] Graph memory operations work with secrets
- [ ] Auto-FORGET cleans up after tasks
- [ ] Performance overhead < 2%

## 📋 TASK EXECUTION INSTRUCTIONS

### Before Starting Any Task:
1. Read the FINAL_FEATURES.md status and limitations
2. Check if any dependencies are incomplete
3. Write comprehensive unit tests FIRST
4. Implement with proper error handling and type safety
5. Test integration with existing systems
6. Update documentation

### Task Completion Criteria:
- [ ] All unit tests pass (100% coverage for new code)
- [ ] Integration tests pass
- [ ] Performance benchmarks meet targets  
- [ ] Security tests pass
- [ ] Documentation updated
- [ ] Code review completed (self-review acceptable)

## 🚦 PROGRESS TRACKING

### Legend:
- ❌ NOT STARTED
- 🔄 IN PROGRESS  
- ⚠️ BLOCKED (waiting for dependency)
- ✅ COMPLETE
- 🧪 TESTING
- 📝 DOCUMENTATION

### Current Status:
- **Task Group A**: ❌ NOT STARTED
- **Task Group B**: ❌ NOT STARTED  
- **Task Group C**: ❌ NOT STARTED
- **Task Group D**: ❌ NOT STARTED

**Estimated Total Time**: 10-15 days
**Current Completion**: 0%
**Next Action**: Begin Task A1 (Create Audit System Tests)

---

## REPOSITORY GUIDELINES (Original Content)

- All unit tests are currently passing. Ensure they remain green by running
  `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.
- All handler logic now lives under `ciris_engine/action_handlers`. The old
  `memory/` and `ponder/` packages were removed. When adding new handlers use the
  service registry via `BaseActionHandler.get_*_service()` for communication,
  memory, and other services. See `registries/README.md` for details on the
  registry and fallback behavior.
- Ensure `OPENAI_API_KEY` is set (or a local equivalent) before running tests.

- Action handlers must follow the standard BaseActionHandler pattern. Each handler defines `action_type` and implements `handle(thought, params, dispatch_context) -> bool`.
- Replace any direct service usage (e.g. discord_service.send_message) with registry lookups like `get_communication_service()`.

- Validate handler parameters using Pydantic models. If `params` is a dict, cast it to the proper `*Params` model before using it.
- Do not compare action names with string literals. Use the `HandlerActionType` enums instead.

- Configure logging using `ciris_engine.utils.logging_config.setup_basic_logging`
  and access the application configuration with
  `ciris_engine.config.config_manager.get_config()`.

- After the setup script completes, the environment is locked down: only
  packages listed in `requirements.txt` are available. Add new dependencies to
  that file and move on if you face issues testing

- Each submodule under `ciris_engine/` should include a brief `README.md`
  describing its purpose and how to use it. Add one if it doesn't exist when
  modifying a module.

- Use `python main.py --help` to see the unified runtime options. The same flags
  map directly to runtime arguments (e.g., `--host`, `--port`, `--no-interactive`).
  For offline tests pass `--mock-llm` to avoid calling external APIs.

## NOTES FOR CLAUDE

When working through this task list:

1. **Always start with tests** - Write comprehensive unit tests before implementing features
2. **Be thorough** - Don't mark tasks complete until fully tested and integrated
3. **Update progress** - Keep this document updated with current status
4. **Security focus** - All security-critical components need extra testing
5. **Performance validation** - Measure impact of all changes
6. **Integration testing** - Ensure new features don't break existing functionality

Remember: This is mission-critical software. Quality and security are more important than speed.

## ADDITIONAL GUIDELINES

- All implementation details can be found in the top-level `README.md` and each module's `README.md`. Refer to those documents for background, usage, and architectural notes.
- The development environment has full internet access. Use online resources if needed.
- When running or testing the system, **always** use the mock LLM service (`--mock-llm`). Extend the mock implementation when debugging issues rather than calling external APIs.
- Every code change must be mission critical and completely typed. No legacy accommodation or backward compatibility should be introduced.
- Guardrails and sinks currently have less than 40% test coverage. Prioritize tests to bring these modules to acceptable levels.

