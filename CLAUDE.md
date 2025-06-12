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

### Docker Deployment
```bash
docker-compose up -d
# or
docker build -f docker/Dockerfile -t ciris-agent .
```

## Architecture Overview

### Core 3×3×3 Action System
The agent operates on a sophisticated action model with three categories:
- **External Actions**: OBSERVE, SPEAK, TOOL
- **Control Responses**: REJECT, PONDER, DEFER  
- **Memory Operations**: MEMORIZE, RECALL, FORGET
- **Terminal**: TASK_COMPLETE

### Ethical Reasoning Pipeline
Multi-layered moral decision-making system:
- **Ethical PDMA**: Applies foundational principles (beneficence, non-maleficence, justice, autonomy)
- **Common Sense Evaluation**: Ensures coherence and plausibility
- **Domain-Specific Analysis**: Specialized ethical knowledge
- **Guardrails System**: Multi-tier safety framework
- **Wisdom-Based Deferral**: Escalates complex dilemmas to humans

### Service-Oriented Architecture
Six core service types: COMMUNICATION, TOOL, WISE_AUTHORITY, MEMORY, AUDIT, LLM

## Key Files & Components

### Entry Points
- `main.py` - Unified entry point with comprehensive CLI interface
- `ciris_profiles/` - Agent behavior configurations and personality settings

### Core Architecture
- `ciris_engine/processor/main_processor.py` - Central thought processing engine
- `ciris_engine/dma/` - Decision Making Algorithms for ethical reasoning
- `ciris_engine/schemas/` and `ciris_engine/protocols/` - Core data models, interfaces, and protocol definitions

### Ethical Framework
- `covenant_1.0b.txt` - Complete ethical framework and principles
- `CIS.md` - Creator Intent Statement defining design philosophy
- `ciris_engine/guardrails/` - Multi-layer safety and ethical constraint system

### Platform Interfaces
- `ciris_engine/adapters/` - Platform-specific interfaces (Discord, CLI, API)
- `ciris_engine/action_handlers/` - Implementation of the 3×3×3 action system

### Security & Audit
- `ciris_engine/audit/` - Cryptographic audit trails with tamper-evident logging
- `ciris_engine/secrets/` - Automatic secrets detection and AES-256-GCM encryption
- `ciris_engine/telemetry/` - Comprehensive observability and monitoring

## Development Notes

### Tech Stack
- Python 3.10+ with asyncio
- OpenAI API with instructor for structured outputs
- FastAPI for API server mode
- Discord.py for Discord integration
- Cryptographic libraries for security features

### Testing Strategy
The codebase uses pytest with async support. Mock LLM functionality allows offline development and testing without API calls.

### Security Features
- Automatic PII detection and filtering
- Cryptographic audit trails with RSA signatures  
- AES-256-GCM encryption for sensitive data
- Resource monitoring with adaptive throttling
- Circuit breaker patterns for service protection

### Resource Considerations
Designed to run on modest hardware without requiring internet connectivity for core functionality.

## Mission Critical Readiness Status

### Current Achievement: 70% Mission Critical Ready ✅

**COMPLETED - MISSION READY:**
- ✅ **Service Management System**: 100% API/SDK/GUI coverage with enterprise-grade features
- ✅ **Audit & Security**: Cryptographic audit trails with tamper-evident logging (31/31 tests passing)
- ✅ **Multi-Service Transaction Manager**: Service-level priority management with FALLBACK/ROUND_ROBIN strategies
- ✅ **Circuit Breaker Fault Tolerance**: Automatic fault recovery and health monitoring
- ✅ **Communication Safety Guards**: Prevention of adapter isolation (cannot remove last communication adapter)
- ✅ **Real-time Service Diagnostics**: Complete health monitoring and issue detection in GUI/API/SDK

### Critical Tasks for 100% Mission Critical Status 🎯

#### Phase 1: Critical Type Safety Fixes (IMMEDIATE)
```bash
# 1. Fix Runtime Configuration Service Type Issues
# File: ciris_engine/runtime/config_manager_service.py
# Issues: Missing return type annotations, incompatible type assignments, union type handling
python -m mypy ciris_engine/runtime/config_manager_service.py --show-error-codes

# 2. Fix Protocol Interface Contract Violations  
# File: ciris_engine/protocols/dma_interface.py, ciris_engine/adapters/openai_compatible_llm.py
# Issues: Signature incompatibilities, method parameter mismatches
python -m mypy ciris_engine/protocols/ ciris_engine/adapters/openai_compatible_llm.py

# 3. Fix Main Processor Type Conflicts
# File: ciris_engine/processor/main_processor.py
# Issues: Dict assignment to float|str types, union attribute access
python -m mypy ciris_engine/processor/main_processor.py
```

#### Phase 2: Enhanced Type Safety Validation (HIGH PRIORITY)
```bash
# 1. Add Protocol Compliance Tests
# Create comprehensive tests verifying all interface implementations
pytest tests/ciris_engine/protocols/ -v

# 2. Integration Type Safety Tests
# Add end-to-end type safety verification tests
pytest tests/integration/test_type_safety_integration.py -v

# 3. Security Module Type Audit
# Deep dive type safety review of security-critical modules
python -m mypy ciris_engine/secrets/ ciris_engine/guardrails/ --strict
```

#### Phase 3: Legacy Code Elimination (MEDIUM PRIORITY)
```bash
# 1. Remove Dead Code
python -m vulture ciris_engine/ --min-confidence 80

# 2. Remove Backwards Compatibility (Pre-Beta)
# Eliminate all legacy/deprecated code paths

# 3. Remove Unreachable Code
# Clean up unreachable statements identified by mypy
```

### Mission Critical Validation Commands

```bash
# Type Safety Validation
python -m mypy ciris_engine/ --no-error-summary | grep -c "error:"
# Target: 0 errors

# Test Coverage Validation  
pytest --cov=ciris_engine --cov-report=term-missing --cov-fail-under=90
# Target: >90% coverage on critical modules

# Critical Module Test Execution
pytest tests/ciris_engine/runtime/ tests/ciris_engine/processor/ tests/ciris_engine/protocols/ -v
# Target: All tests passing

# Security Module Verification
pytest tests/ciris_engine/audit/ tests/ciris_engine/secrets/ tests/ciris_engine/guardrails/ -v
# Target: All security tests passing

# Service Management Verification
pytest tests/ciris_engine/test_services_resource.py tests/ciris_engine/services/test_transaction_orchestrator.py -v
# Target: All service management tests passing
```

### Module Readiness Matrix

| Module | Type Safety | Test Coverage | Priority | Status |
|--------|-------------|---------------|----------|---------|
| **Audit** | ✅ CLEAN | ✅ 31/31 | CRITICAL | ✅ **READY** |
| **Services** | ✅ CLEAN | ✅ 11/11 | HIGH | ✅ **READY** |
| **Sinks** | ✅ CLEAN | ✅ 28/28 | HIGH | ✅ **READY** |
| **Runtime Control** | ⚠️ 17/30 | ✅ Tests exist | CRITICAL | 🔧 **NEEDS WORK** |
| **Config Manager** | ❌ Major issues | ✅ Tests exist | CRITICAL | 🔧 **NEEDS WORK** |
| **Main Processor** | ❌ Major issues | ✅ Tests exist | CRITICAL | 🔧 **NEEDS WORK** |
| **Protocols** | ❌ Contract violations | ⚠️ Limited | CRITICAL | 🔧 **NEEDS WORK** |
| **Secrets** | ⚠️ Moderate | ✅ 11/11 | HIGH | ⚠️ **REVIEW** |

### Success Criteria for Mission Critical

- **Type Safety**: Zero mypy errors in all critical modules
- **Test Coverage**: >90% line coverage for runtime, processor, protocols, audit, secrets
- **Integration**: All protocol contracts verified with integration tests
- **Security**: All security-critical modules pass comprehensive testing
- **Performance**: No performance regression in type-safe implementations
- **Documentation**: All mission-critical features documented in API/SDK/GUI

### Development Workflow for Mission Critical

1. **Before making changes**: Run full test suite and mypy validation
2. **After changes**: Verify no new type errors introduced  
3. **Critical modules**: Require peer review and comprehensive testing
4. **Security changes**: Mandatory security review and audit trail verification
5. **Performance**: Benchmark critical paths before/after changes

### Emergency Procedures

```bash
# If system fails to start:
python main.py --mock-llm --debug --no-interactive

# If type errors block development:
python -m mypy ciris_engine/ --ignore-missing-imports --follow-imports=silent

# If tests fail unexpectedly:
pytest tests/ -v --tb=short --maxfail=5

# If service management fails:
python main.py --modes cli --profile default
# Check: Service registry should show healthy services
```