# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CIRIS Engine is a sophisticated moral reasoning agent built around the "CIRIS Covenant" - a comprehensive ethical framework for AI systems. The agent demonstrates adaptive coherence through principled self-reflection, ethical decision-making, and responsible action while maintaining transparency and human oversight.

## Agent Profiles

The system includes four complementary agent profiles:
- **Datum** (default): Humble measurement point providing singular, focused data points
- **Sage** (formerly teacher): Wise questioner fostering understanding through inquiry
- **Scout** (formerly student): Direct explorer demonstrating principles through action
- **Echo**: Ubuntu-inspired community guardian for Discord moderation

Datum, Sage, and Scout work as complementary peers with no hierarchy.

## Development Commands

### Testing & Quality Assurance
```bash
# Run full test suite
pytest tests/ -v

# Run tests with coverage reporting
pytest --cov=ciris_engine --cov-report=xml --cov-report=html

# Run with mock LLM for offline development
python main.py --mock-llm --debug

# Type checking - MUST BE CLEAN
python -m mypy ciris_engine/ --no-error-summary
# We maintain 0 mypy errors as mission critical
```

### Running the Agent
```bash
# Auto-detect modes (Discord/CLI based on token availability)
python main.py --profile datum

# Specific modes
python main.py --modes cli --profile sage
python main.py --modes discord --profile scout  
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

## Zero Dict[str, Any] Architecture ✅

We have achieved **100% type safety** with zero tolerance for untyped dictionaries:

### Type-Safe Schemas Created
- ✅ `processor_schemas_v1.py` - Typed processor results (WakeupResult, WorkResult, etc.)
- ✅ `dma_schemas_v1.py` - DMAInputData replacing Dict[str, Any] in DMAs
- ✅ `faculty_schemas_v1.py` - Renamed from epistemic for clarity
- ✅ `resource_schemas_v1.py` - Enhanced with environmental tracking
- ✅ `audit_verification_schemas_v1.py` - Cryptographic audit visibility
- ✅ `context_schemas_v1.py` - Updated with resource and audit fields

### Resource Transparency Achieved
The AI now has complete visibility into:
- **Financial Cost**: cost_cents per operation
- **Water Usage**: water_ml (milliliters per operation)
- **Carbon Emissions**: carbon_g (grams CO2)
- **Energy Consumption**: energy_kwh
- **Audit Status**: Last cryptographic verification time and result

This allows the agent to:
- Refute false claims about resource usage
- Make ethical decisions considering environmental impact
- Verify its own audit trail integrity
- Understand its true cost/contribution ratio

## Key Files & Components

### Entry Points
- `main.py` - Unified entry point with comprehensive CLI interface
- `ciris_profiles/` - Agent behavior configurations (Datum, Sage, Scout, Echo)

### Core Architecture
- `ciris_engine/processor/main_processor.py` - Central thought processing engine
- `ciris_engine/dma/` - Decision Making Algorithms for ethical reasoning
- `ciris_engine/schemas/` - All typed data models (NO Dict[str, Any]!)
- `ciris_engine/protocols/` - Core interfaces and protocol definitions

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
- `ciris_engine/telemetry/` - Comprehensive observability with hot/cold paths

## Development Notes

### Tech Stack
- Python 3.10+ with asyncio
- OpenAI API with instructor for structured outputs
- FastAPI for API server mode
- Discord.py for Discord integration
- Cryptographic libraries for security features

### Testing Strategy
The codebase uses pytest with async support. Mock LLM functionality allows offline development and testing without API calls.

### Type Safety Requirements
- **MUST maintain 0 mypy errors** in production code
- All new code must use proper type annotations
- No Dict[str, Any] except in serialization layers
- Use Pydantic models for all data structures

### Security Features
- Automatic PII detection and filtering
- Cryptographic audit trails with RSA signatures  
- AES-256-GCM encryption for sensitive data
- Resource monitoring with adaptive throttling
- Circuit breaker patterns for service protection

## Mission Critical Standards

### Current Status: ✅ Production Ready
- ✅ **Zero mypy errors** maintained
- ✅ **Zero Dict[str, Any]** in core processing
- ✅ **100% type-safe schemas** with Pydantic validation
- ✅ **Complete resource transparency** for ethical self-awareness
- ✅ **Cryptographic audit verification** visible to agent

### Required for All Changes
1. Run `python -m mypy ciris_engine/` - MUST be clean
2. No new Dict[str, Any] usage without explicit justification
3. All schemas must have comprehensive docstrings
4. Resource tracking for any LLM operations
5. Audit trail for all state changes

## Important Guidelines

### When Making Changes
1. **Type Safety First**: Every data structure needs a schema
2. **Resource Awareness**: Track tokens, cost, water, carbon
3. **Audit Everything**: All actions must be auditable
4. **Test Coverage**: Maintain 80%+ coverage
5. **Documentation**: Update relevant READMEs

### Common Patterns
```python
# ❌ NEVER DO THIS
def process(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"result": data["value"]}

# ✅ ALWAYS DO THIS
from ciris_engine.schemas.processing_schemas_v1 import ProcessingInput, ProcessingResult

def process(data: ProcessingInput) -> ProcessingResult:
    return ProcessingResult(result=data.value)
```

## Emergency Procedures

```bash
# If system fails to start:
python main.py --mock-llm --debug --no-interactive

# If type errors block development:
python -m mypy ciris_engine/ --ignore-missing-imports --follow-imports=silent

# If tests fail unexpectedly:
pytest tests/ -v --tb=short --maxfail=5
```

## Next Priority Tasks

1. **Fix remaining test failures** (currently ~107 failures)
2. **Achieve 80%+ test coverage** (current: ~70%)
3. **Update all processor tests** for new schemas
4. **Document schema migration** procedures
5. **Performance benchmarking** with typed vs untyped

Remember: The goal is an AI system that is secure, self-aware, and capable of ethical reasoning about its own resource usage and impact.