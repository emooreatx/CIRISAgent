# CIRIS MyPy Toolkit 🛠️

A mission-critical toolkit for agents and developers to drive the CIRIS codebase to zero mypy errors, strict protocol adherence, and schema compliance. This toolkit is designed for agent-in-the-loop workflows, ensuring all type safety and compliance is enforced at the protocol and schema level—never via comments or dead code.

## 🎯 Mission

The CIRIS MyPy Toolkit ensures that all code in the CIRIS ecosystem:
- Uses only v1 schemas and protocol interfaces (never raw dicts or internal implementations)
- Maintains strict, module-level type safety with zero mypy errors
- Avoids dead code, code in comments, or ambiguous/partial fixes
- Empowers agents to review and approve all automated fixes before execution

## 👩‍💻 Agent-Driven Workflow

**The toolkit is designed for agent-in-the-loop operation:**

1. **Analyze**: Collect and categorize all mypy, protocol, and schema errors.
2. **Review**: Propose fixes and present them for agent/human review. No changes are made until explicitly approved.
3. **Execute**: Apply only agent-approved fixes, then re-analyze to ensure compliance.

This workflow guarantees:
- No code is left in comments or as dead code
- All type annotations and fixes are protocol/schema-bound
- Every change is reviewable and auditable by an agent

## ✨ Features

### 🔍 Advanced Analysis
- **Schema Validator**: Detects dict usage that should be proper schema classes
- **Protocol Analyzer**: Finds direct internal method calls that should use protocol interfaces
- **Unused Code Detector**: Identifies uncalled functions, unused imports, and dead code

### 🔧 Automated Fixing
- **Type Annotation Fixer**: Adds missing return types, variable annotations, Optional types, always using protocol/schema types
- **Protocol Compliance Fixer**: Refactors internal calls to use service registry and protocols
- **Schema Alignment Fixer**: Updates legacy imports to v1 schemas and adds schema TODOs

### 📊 Comprehensive Reporting
- Full compliance analysis across the codebase
- Adapter-specific validation for new components
- Progress tracking and success metrics

## 🚀 Quick Start

### Command Line Usage

```bash
# 1. Analyze (collect errors)
python -m ciris_mypy_toolkit.cli analyze

# 2. Propose fixes for review (do not apply yet)
python -m ciris_mypy_toolkit.cli propose --categories type_annotations schema_alignment protocol_compliance

# 3. Review the generated proposal file (e.g., proposed_fixes.json)
#    Approve or edit as needed.

# 4. Execute only approved fixes
python -m ciris_mypy_toolkit.cli execute proposed_fixes.json --approved

# 5. Re-analyze to confirm zero errors
python -m ciris_mypy_toolkit.cli analyze
```

### Python API Usage

```python
from ciris_mypy_toolkit import CIRISMypyToolkit

# Initialize toolkit
toolkit = CIRISMypyToolkit("ciris_engine", "ciris_engine/schemas")

# Analyze compliance
analysis = toolkit.analyze_compliance()
print(f"MyPy errors: {analysis['total_mypy_errors']}")

# Propose fixes for agent review
proposal = toolkit.propose_fixes(["type_annotations", "schema_alignment", "protocol_compliance"])
print(f"Proposal file: {proposal}")

# After review, execute approved fixes
results = toolkit.execute_approved_fixes(proposal)
print(f"Applied {results['total_errors_eliminated']} fixes")
```

## 🏗️ Architecture

The toolkit follows a modular architecture with clear separation of concerns:

```
ciris_mypy_toolkit/
├── core.py                    # Main orchestrator
├── analyzers/                 # Code analysis modules
│   ├── schema_validator.py    # Schema compliance checking
│   ├── protocol_analyzer.py   # Protocol usage analysis  
│   └── unused_code_detector.py # Dead code detection
├── error_fixers/              # Automated fixing modules
│   ├── type_annotation_fixer.py    # Type safety fixes (protocol/schema only)
│   ├── protocol_compliance_fixer.py # Protocol compliance
│   └── schema_alignment_fixer.py    # Schema alignment
└── cli.py                     # Command-line interface
```

## 🦾 Agent Usage Philosophy

- **No code in comments**: All dead code and commented-out code is purged, never left for review.
- **Protocol/Schema Only**: All type annotations and fixes use only types from `protocols/` and `schemas/`.
- **Review Required**: No fix is applied without explicit agent/human review and approval.
- **Zero Tolerance**: The goal is zero mypy errors, zero protocol violations, and zero schema drift.

## 🛡️ Safety Features

- **Conservative Fixing**: Only applies safe, well-tested transformations
- **Verification**: Validates fixes don't break functionality  
- **Rollback Support**: Git integration for easy rollback if needed
- **Progress Tracking**: Clear metrics on what was changed

## 🔄 Integration with Existing Tools

Works seamlessly with:
- **MyPy**: Uses mypy output for error detection and fixing
- **Pytest**: Validates fixes don't break tests
- **Git**: Tracks changes and enables rollback
- **CI/CD**: Can be integrated into automated pipelines

## 📈 Continuous Improvement

The toolkit learns from the codebase and can:
- **Detect Patterns**: Identifies recurring issues across modules
- **Suggest Improvements**: Recommends better architectural patterns
- **Track Progress**: Monitors compliance over time
- **Adapt Rules**: Updates validation rules as schemas evolve

## 🤝 Contributing

To extend the toolkit:

1. **Add New Analyzers**: Implement the analyzer interface for new checks
2. **Create Fixers**: Build automated fixes for detected patterns  
3. **Extend CLI**: Add new commands for specific use cases
4. **Update Patterns**: Keep schema and protocol patterns current

## 📚 Related Documentation

- [CIRIS Schemas](../ciris_engine/schemas/README.md) - v1 schema documentation
- [Protocol Interfaces](../ciris_engine/protocols/README.md) - Service protocols
- [Adapter Guidelines](../CONTRIBUTING.md) - Best practices for adapters

---

*Built for the CIRIS Agent ecosystem. Ensuring type safety, schema compliance, and maintainable code for all.*