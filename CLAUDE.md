# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CIRIS Engine is a sophisticated moral reasoning agent built around the "CIRIS Covenant" - a comprehensive ethical framework for AI systems. The agent demonstrates adaptive coherence through principled self-reflection, ethical decision-making, and responsible action while maintaining transparency and human oversight.

## Development Commands

### Testing & Quality Assurance
```bash
# Run full test suite
pytest tests/ -v

# Run tests with coverage reporting
pytest --cov=ciris_engine --cov-report=xml --cov-report=html

# Run with mock LLM for offline development
python main.py --mock-llm --debug

# Type checking
python -m mypy ciris_engine/ --no-error-summary
```

### Running the Agent
```bash
# Auto-detect modes (Discord/CLI based on token availability)
python main.py --profile default

# Specific modes
python main.py --modes cli --profile teacher
python main.py --modes discord --profile student  
python main.py --modes api --host 0.0.0.0 --port 8000

# Development modes with debugging
python main.py --mock-llm --debug --no-interactive
```

## Current Priority Task List 🎯

### Phase 1: Schema Creation (Zero Dict[str, Any] Tolerance)

1. **Rename epistemic_schemas_v1.py → faculty_schemas_v1.py**
   - Make faculty evaluation results clearer and more accessible
   - Add timestamp and faculty_name to base FacultyResult

2. **Create processor_schemas_v1.py**
   - BaseProcessorResult with elegant inheritance
   - Processor-specific results (WakeupResult, WorkResult, etc.)
   - ProcessorMetrics for standardized metric tracking
   - ProcessorStatus for get_status() methods

3. **Create dma_schemas_v1.py**
   - DMAInputData to replace Dict[str, Any] in DMA evaluation
   - Include resource transparency (tokens, costs, water usage)
   - Faculty evaluations with proper typing

4. **Enhance resource_schemas_v1.py**
   - Add ResourceUsage with cost/environmental tracking
   - Extend ResourceSnapshot with round-specific usage
   - Track water_ml, carbon_g, cost_cents per operation

5. **Create audit_verification_schemas_v1.py**
   - AuditVerificationStatus for cryptographic verification
   - AuditSummary for system snapshot visibility
   - Last verification time and results

6. **Update context_schemas_v1.py**
   - Add audit_summary to SystemSnapshot
   - Add current_round_resources for real-time cost visibility
   - Add cost_per_message for refuting false claims

7. **Supporting Schemas**
   - QueueStatus, TaskOutcome, StateMetadata
   - CostSummary, CostComparison
   - MaintenanceResult, ReflectionResult

### Phase 2: Implementation
1. Update all processors to use new result schemas
2. Update DMAs to use DMAInputData
3. Update all Dict[str, Any] usage to proper schemas
4. Run mypy to ensure no regressions

### Phase 3: Testing
1. Update all unit tests for new schemas
2. Fix failing tests (102 failures)
3. Achieve 80%+ test coverage

### Why This Matters
- **Zero attack surface**: No Dict[str, Any] for injection attacks
- **Complete self-awareness**: AI knows its exact resource usage
- **Audit transparency**: AI can verify its own audit trail integrity
- **Cost refutation**: Can counter false claims with real data

### Success Metrics
- ✅ 0 mypy errors maintained
- ✅ 0 Dict[str, Any] usage (except minimal legacy)
- ✅ 80%+ test coverage
- ✅ All tests passing

## Project Architecture Notes

### Key Principles
- **Zero Dict[str, Any]**: Every data structure must have a proper schema for security and self-awareness
- **Resource Transparency**: AI must know its exact cost per operation for ethical self-reflection
- **Audit Integrity**: AI must be able to verify its own audit trail hasn't been tampered with

### Schema Organization
- `ciris_engine/schemas/` - All data models with v1 versioning
- `ciris_engine/protocols/` - Interface contracts and protocols
- New schemas should follow existing naming patterns (*_schemas_v1.py)

### Testing Requirements
- All schemas must have corresponding tests
- Integration tests for schema migrations
- Mock data factories for testing