# CIRIS Agent Implementation Task List

## Document Status
**Version**: 1.1.0
**Status**: ✅ COMPLETE
**Last Updated**: 2025-06-11

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

## 🎯 HISTORICAL TASK SUMMARY

All pre-beta implementation tasks have been completed. Key areas covered:

- **Audit System Integration** – signed hash chain, migration 003, and full test suite
- **Telemetry System** – real-time metrics with security filtering and snapshot integration
- **Network & Community Schemas** – optimized structures for local and network presence
- **Secrets Service** – memory integration and auto-forget logic

These historical tasks remain for reference but require no further action.

## 🔧 CURRENT PRIORITY TASKS

### Task Group QA: Mock LLM Expansion
**Goal**: Extend and test the mock LLM using `qa_tasks.md` for robust API validation.

1. **Implement deterministic command coverage** – ensure `$speak`, `$memorize`, `$recall`, `$ponder`, `$observe`, `$tool`, `$defer`, `$reject`, `$forget`, and `$task_complete` are parsed correctly.
2. **Add integration tests** verifying each command triggers the proper action handler in API mode (`tests/adapters/mock_llm`).
3. **Run QA checklist** from `qa_tasks.md` against the API server in mock mode. Start the server with `python main.py --mock-llm --modes api --timeout 60 > server.log 2>&1 &` (omit the timeout for long sessions) and review `server.log` or `logs/latest.log` for handler output.
4. **Document** new mock LLM capabilities and update examples in `README.md`.

*Status Update (QA Session)*: Verified SPEAK and MEMORIZE handlers via `/v1/messages` using mock LLM.

Progress is tracked in this document under *Task Group QA* until complete.

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
- **Task Group A**: ✅ COMPLETE
- **Task Group B**: ✅ COMPLETE
- **Task Group C**: ✅ COMPLETE
- **Task Group D**: ✅ COMPLETE

**Estimated Total Time**: 0 days
**Current Completion**: 100%
**Next Action**: None

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

