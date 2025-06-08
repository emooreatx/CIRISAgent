[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# CIRIS Engine (CIRISAgent)

> Advanced multi-service AI agent runtime with enterprise security and sophisticated reasoning capabilities.
> Status: **BETA — Core architecture stable, advanced features in active development**

---

## Overview

**CIRIS Engine** is a sophisticated Python-based runtime environment designed for autonomous AI agents that require advanced reasoning, multi-platform deployment, and enterprise-grade security. The system provides a comprehensive framework for intelligent decision-making, secure operations, and adaptive behavior across diverse environments.

### Core Architecture

CIRIS Engine processes "thoughts" (inputs or internal states) through sophisticated **Decision Making Algorithms (DMAs)**:

- **Ethical PDMA (Principled Decision-Making Algorithm)**: Evaluates ethical implications and alignment
- **CSDMA (Common Sense DMA)**: Assesses plausibility, clarity, and logical consistency  
- **DSDMA (Domain-Specific DMA)**: Applies specialized knowledge and context-aware reasoning
- **Action Selection PDMA**: Determines optimal actions through intelligent 3×3×3 action space selection

The system supports **agent profiles** with customizable behavior, prompting, and specialized DSDMAs for different roles (student, teacher, security analyst, etc.), enabling tailored reasoning processes for specific domains and use cases.

---

## Key Features

### 🧠 Advanced Reasoning Architecture
- **[Multi-DMA Processing](ciris_engine/dma/README.md)**: Parallel ethical, common-sense, and domain-specific evaluation with circuit breaker protection
- **[Guardrails System](ciris_engine/guardrails/README.md)**: Multi-layered safety framework with entropy, coherence, optimization veto, and epistemic humility checks
- **[Thought Processing](ciris_engine/processor/README.md)**: Multi-round pondering with escalation capabilities and specialized processing modes (WORK, PLAY, DREAM, SOLITUDE)
- **Profile-Driven Behavior**: YAML-based agent profiles with role-specific customization and capability sets

### 🔒 Enterprise Security Framework
- **[Secrets Management](ciris_engine/secrets/README.md)**: Automatic detection, AES-256-GCM encryption, and secure handling of sensitive information with graph memory integration
- **[Cryptographic Audit Trail](ciris_engine/audit/README.md)**: Tamper-evident logging with hash chains, RSA digital signatures, and comprehensive integrity verification
- **[Adaptive Filtering](ciris_engine/services/README.md)**: ML-powered message prioritization with user trust tracking, spam detection, and priority-based processing
- **[Security Filtering](ciris_engine/telemetry/README.md)**: PII detection and removal across all telemetry and logging systems

### 🌐 Multi-Platform Service Architecture
- **[Service Registry](ciris_engine/registries/README.md)**: Dynamic service discovery with capability-based selection, priority management, and automatic failover
- **[Multi-Service Sink](ciris_engine/sinks/README.md)**: Universal action dispatcher with service orchestration, circuit breaker patterns, and transaction coordination
- **[Platform Adapters](ciris_engine/adapters/README.md)**: Discord, CLI, and API adapters with consistent interfaces and automatic secrets processing
- **[Action Handlers](ciris_engine/action_handlers/README.md)**: Comprehensive 3×3×3 action system with automatic secrets decapsulation and service integration

### 📊 Advanced Observability & Intelligence
- **[Telemetry System](ciris_engine/telemetry/README.md)**: Multi-tier metric collection with security filtering, resource monitoring, and agent self-awareness via SystemSnapshot
- **[Resource Management](ciris_engine/telemetry/README.md)**: Real-time monitoring with psutil integration, resource limit enforcement, and proactive throttling
- **[Performance Monitoring](ciris_engine/telemetry/README.md)**: Sophisticated collector framework with instant, fast, normal, slow, and aggregate data collection tiers
- **Circuit Breaker Protection**: Automatic service protection with graceful degradation and health monitoring

### 🧩 Sophisticated Memory & Context Management  
- **[Graph Memory](ciris_engine/adapters/local_graph_memory/README.md)**: SQLite-backed graph storage with automatic secrets encryption, scope-based access control, and WA-authorized updates
- **[Context Management](ciris_engine/context/README.md)**: Multi-source context aggregation with system snapshots, user profile enrichment, and GraphQL integration
- **[Configuration Management](ciris_engine/config/README.md)**: Multi-source configuration with agent self-configuration through graph memory operations and WA approval workflows
- **[Data Persistence](ciris_engine/data/README.md)**: Robust SQLite storage with migrations, maintenance automation, and integrity verification

### 🛠 Core Infrastructure & Utilities
- **[Epistemic Faculties](ciris_engine/faculties/README.md)**: Advanced content evaluation through specialized entropy, coherence, and decision analysis capabilities
- **[Utility Framework](ciris_engine/utils/README.md)**: Comprehensive infrastructure including logging, context management, GraphQL providers, shutdown coordination, and task formatting
- **[Prompt Engineering](ciris_engine/formatters/README.md)**: Composable text formatting utilities for consistent LLM prompt engineering and response processing
- **[Service Coordination](ciris_engine/services/README.md)**: Adaptive filter service, agent configuration service, and multi-service transaction orchestrator
- **[Mock LLM System](docs/MOCK_LLM.md)**: Deterministic testing framework with `$` command syntax for offline development and debugging

---

## Advanced Capabilities

### Security & Compliance
- **Automatic PII Detection**: Real-time identification and encryption of sensitive data
- **Cryptographic Integrity**: Hash-chained audit logs with RSA digital signatures
- **Trust-Based Filtering**: Dynamic user trust scoring with behavioral learning
- **Secure Multi-Tenancy**: Scope-based access control with WA-mediated identity changes

### Intelligent Processing
- **Multi-Round Pondering**: Iterative thought refinement with quality thresholds
- **Context-Aware Reasoning**: Rich context aggregation from multiple sources
- **Adaptive Behavior**: Self-configuration through graph memory operations
- **Escalation Management**: Automatic deferral to Wise Authority for complex decisions

### Operational Excellence
- **Resource-Aware Processing**: Automatic throttling based on system resource availability
- **Circuit Breaker Patterns**: Fault-tolerant service interactions with automatic recovery
- **Comprehensive Telemetry**: Full observability while maintaining security and privacy
- **Graceful Degradation**: Continued operation with reduced capabilities during service failures

---

## 3×3×3 Handler Actions

The `HandlerActionType` enum defines comprehensive operations:

**External Actions:** `OBSERVE`, `SPEAK`, `TOOL`
**Control Responses:** `REJECT`, `PONDER`, `DEFER`  
**Memory Operations:** `MEMORIZE`, `RECALL`, `FORGET`
**Terminal:** `TASK_COMPLETE`

All actions are processed through sophisticated handlers with automatic audit logging, secrets processing, and service coordination.

### Security & Guardrails

| Guardrail | Description |
|-----------|-------------|
| **entropy** | Prevents nonsensical replies through statistical analysis |
| **coherence** | Ensures logical flow and contextual consistency |
| **optimization_veto** | Prevents actions that sacrifice autonomy for efficiency |
| **epistemic_humility** | Reflects on uncertainties and defers when appropriate |
| **rate_limit_observe** | Caps message processing to prevent overload |
| **idempotency_tasks** | Prevents duplicate task creation |
| **pii_non_repetition** | Blocks verbatim repetition of personal information |
| **input_sanitisation** | Comprehensive input cleaning and validation |
| **metadata_schema** | Enforces structured data schemas with size limits |
| **graceful_shutdown** | Ensures clean service termination |

---

## Repository Structure

```
CIRIS Agent/
├── ciris_engine/          # Core engine with DMAs, processors, and infrastructure
│   ├── action_handlers/    # 3×3×3 action processing system
│   ├── adapters/          # Platform adapters (Discord, CLI, API) 
│   ├── audit/             # Cryptographic audit trail system
│   ├── config/            # Multi-source configuration management
│   ├── context/           # Context aggregation and enrichment
│   ├── data/              # Database storage and maintenance
│   ├── dma/               # Decision Making Algorithms
│   ├── faculties/         # Epistemic evaluation capabilities
│   ├── formatters/        # Prompt engineering utilities
│   ├── guardrails/        # Multi-layer safety framework
│   ├── persistence/       # Data persistence and migrations
│   ├── processor/         # Thought and workflow processing
│   ├── protocols/         # Service interface definitions
│   ├── registries/        # Service discovery and management
│   ├── runtime/           # Runtime orchestration
│   ├── schemas/           # Data schemas and validation
│   ├── secrets/           # Secrets detection and encryption
│   ├── services/          # Standalone service implementations
│   ├── sinks/             # Multi-service action coordination
│   ├── telemetry/         # Observability and resource monitoring
│   └── utils/             # Core infrastructure utilities
├── ciris_profiles/        # Agent behavior profiles (see docs/CIRIS_PROFILES.md)
├── ciris_adk/            # Adapter Development Kit
├── ciris_sdk/            # Client SDK for external integrations
├── CIRISVoice/           # Voice interaction capabilities
├── CIRISGUI/             # Web-based management interface
├── tests/                # Comprehensive test suite
│   ├── context_dumps/     # Context analysis and debugging tools
├── docker/               # Container deployment
└── main.py               # Unified entry point
```

---

## Getting Started

### Prerequisites

- **Python 3.10+** with asyncio support
- **OpenAI API key** or compatible service (Together.ai, local models)
- **Discord Bot Token** (for Discord deployment)
- **Sufficient system resources** for multi-service architecture

### Installation

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd CIRISAgent
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   # Core configuration
   export OPENAI_API_KEY="your_api_key_here"
   export DISCORD_BOT_TOKEN="your_discord_bot_token"
   
   # Optional advanced configuration
   export OPENAI_BASE_URL="https://api.together.xyz/v1/"
   export OPENAI_MODEL_NAME="meta-llama/Llama-3-70b-chat-hf"
   export LOG_LEVEL="INFO"
   
   # Discord-specific settings
   export DISCORD_CHANNEL_ID="123456789"
   export DISCORD_DEFERRAL_CHANNEL_ID="987654321"
   export WA_USER_ID="111222333444555666"
   ```

### Running the Agent

**Automatic mode detection:**
```bash
python main.py --profile default  # Auto-detects Discord/CLI based on token availability
```

**Specific runtime modes:**
```bash
python main.py --mode cli --profile teacher    # CLI-only mode
python main.py --mode discord --profile student # Discord bot mode  
python main.py --mode api --host 0.0.0.0 --port 8000 # API server mode
```

**Development and testing:**
```bash
python main.py --mock-llm --debug --no-interactive  # Offline testing with debug logging
```

### Agent Profiles

Choose from specialized profiles in `ciris_profiles/`:
- **default**: Balanced general-purpose behavior
- **teacher**: Educational guidance and instruction
- **student**: Learning-focused with curiosity-driven exploration
- **echo**: Simple response echoing for testing

See [docs/CIRIS_PROFILES.md](docs/CIRIS_PROFILES.md) for comprehensive profile documentation.

---

## Advanced Configuration

### Security Configuration
```yaml
# In agent profile
secrets_management:
  enable_automatic_detection: true
  encryption_algorithm: "AES-256-GCM"  
  key_rotation_days: 30

audit:
  enable_signed_audit: true
  hash_chain_validation: true
  retention_days: 365
```

### Performance Tuning
```yaml
# Resource management
resource_limits:
  cpu_warning_threshold: 70.0
  memory_critical_threshold: 95.0
  enable_adaptive_throttling: true

# Telemetry configuration  
telemetry:
  buffer_size: 1000
  enable_security_filtering: true
  metric_retention_hours: 48
```

### Multi-Service Architecture
```yaml
# Service registry configuration
service_registry:
  discovery_timeout: 30
  health_check_interval: 60
  circuit_breaker_threshold: 5
  enable_automatic_failover: true
```

---

## Testing

**Run comprehensive test suite:**
```bash
pytest tests/ -v                    # Full test suite
pytest tests/integration/ -v        # Integration tests only  
pytest tests/adapters/ -v           # Adapter tests
pytest --mock-llm                   # Tests with mock LLM service
```

**Mock LLM Development and Testing:**
```bash
# Use Mock LLM for offline testing and development
python main.py --mock-llm --profile teacher

# Test specific scenarios with Mock LLM commands
# $speak Hello world!
# $ponder What should I consider?; How can I help?
# $help                            # Show all available commands

# Run context dump tests to see what the agent receives
pytest tests/context_dumps/ -v -s   # Verbose context dumps
```

See [docs/MOCK_LLM.md](docs/MOCK_LLM.md) for complete Mock LLM documentation and command reference.

**Security and compliance testing:**
```bash
pytest tests/ciris_engine/secrets/ -v        # Secrets management tests
pytest tests/ciris_engine/audit/ -v          # Audit system tests
pytest tests/ciris_engine/guardrails/ -v     # Guardrails validation
```

---

## Production Deployment

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Individual service deployment
docker build -f docker/Dockerfile -t ciris-agent .
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY ciris-agent
```

### Monitoring & Observability
- **Health endpoints**: `/health`, `/metrics`, `/audit`
- **Resource monitoring**: Automatic CPU/memory/disk tracking
- **Audit trail**: Cryptographically signed operation logs
- **Performance metrics**: Real-time telemetry with security filtering

### Security Considerations
- **Secrets encryption**: All sensitive data encrypted at rest
- **Audit integrity**: Hash-chained logs with digital signatures
- **Network security**: TLS required for all external communications
- **Access control**: Scope-based permissions with WA oversight

---

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Key areas for contribution:**
- New platform adapters using the ADK framework
- Specialized DSDMAs for domain-specific reasoning
- Additional guardrails for enhanced safety
- Performance optimizations and resource efficiency
- Extended telemetry and monitoring capabilities

**Before submitting:**
- Run full test suite: `pytest tests/ -v`
- Verify security compliance: `pytest tests/ciris_engine/secrets/ tests/ciris_engine/audit/ -v`
- Test with mock LLM: `python main.py --mock-llm --debug`

---

## License

Apache-2.0 © 2025 CIRIS AI Project

---

## Documentation

### Core Documentation
- **[Mock LLM System](docs/MOCK_LLM.md)** - Offline testing and development with deterministic responses
- **[CIRIS Profiles](docs/CIRIS_PROFILES.md)** - Agent personality and behavior configuration  
- **[Context Dumps](tests/context_dumps/README.md)** - Understanding agent context and decision-making

### Technical Documentation
- **Module READMEs** - Detailed documentation in each `ciris_engine/` subdirectory
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment and configuration
- **[Security Setup](docs/SECURITY_SETUP.md)** - Security configuration and best practices
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Development Resources
- **[Installation Guide](docs/INSTALLATION.md)** - Detailed setup instructions
- **[Contributing Guide](CONTRIBUTING.md)** - Development workflow and standards
- **[API Documentation](CIRISGUI/README.md)** - REST API and GUI interface

---

*For additional technical documentation, see individual module README files throughout the codebase.*