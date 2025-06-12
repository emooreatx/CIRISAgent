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