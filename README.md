[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/CIRISAI/CIRISAgent)

# CIRIS Engine (CIRISAgent)

> **A moral reasoning agent capable of ethical self-reflection, autonomous decision-making, and principled action across diverse environments.**

⚠️ **BETA SOFTWARE**: CIRIS is experimental software under active development. While the core ethical reasoning architecture is stable, advanced features are evolving. Not recommended for production use without thorough testing and oversight. See [CIS.md](CIS.md) for creator intent and risk assessment.

---

## Overview

**CIRIS Engine** is a moral reasoning agent that embodies the [CIRIS Covenant](covenant_1.0b.txt) — a comprehensive ethical framework for autonomous systems. Built on the principle of "adaptive coherence," CIRIS demonstrates how AI agents can engage in principled self-reflection, ethical decision-making, and responsible action while maintaining transparency and human oversight.

Unlike traditional AI systems that follow rigid rules, CIRIS employs sophisticated **ethical reasoning algorithms** that evaluate moral implications, consider stakeholder impacts, and defer to human wisdom when facing complex dilemmas. The system is designed to be a trustworthy partner in decision-making rather than a mere tool.

### Moral Reasoning Architecture

CIRIS processes every input through a multi-layered **ethical reasoning pipeline** that embodies the principles of the CIRIS Covenant:

- **Ethical PDMA**: Applies foundational principles (beneficence, non-maleficence, justice, autonomy)
- **Common Sense Evaluation**: Ensures coherence and plausibility in reasoning
- **Domain-Specific Analysis**: Applies specialized ethical knowledge for context
- **Guardrails System**: Multi-tier safety framework preventing harmful actions
- **Wisdom-Based Deferral**: Escalates complex ethical dilemmas to human authorities

The system supports **moral profiles** that adapt reasoning patterns for different contexts while maintaining core ethical commitments.

---

## Key Features

### 🧠 Ethical Reasoning Framework
- **[Principled Decision-Making](ciris_engine/dma/README.md)**: Multi-algorithm ethical evaluation with transparency and accountability
- **[Moral Guardrails](ciris_engine/guardrails/README.md)**: Comprehensive safety framework including epistemic humility and autonomy preservation
- **[Reflective Processing](ciris_engine/processor/README.md)**: Multi-round ethical pondering with wisdom-based escalation
- **[Covenant-Aligned Profiles](docs/CIRIS_PROFILES.md)**: Role-specific moral reasoning while maintaining core ethical commitments

### 🔒 Trustworthy Operations
- **[Secrets Management](ciris_engine/secrets/README.md)**: Automatic detection, AES-256-GCM encryption, and secure handling of sensitive information with graph memory integration
- **[Cryptographic Audit Trail](ciris_engine/audit/README.md)**: Tamper-evident logging with hash chains, RSA digital signatures, and comprehensive integrity verification
- **[Adaptive Filtering](ciris_engine/services/README.md)**: ML-powered message prioritization with user trust tracking, spam detection, and priority-based processing
- **[Security Filtering](ciris_engine/telemetry/README.md)**: PII detection and removal across all telemetry and logging systems

### 🌐 Adaptive Platform Integration
- **[Service Registry](ciris_engine/registries/README.md)**: Dynamic service discovery with capability-based selection, priority management, and automatic failover
- **[Multi-Service Sink](ciris_engine/sinks/README.md)**: Universal action dispatcher with service orchestration, circuit breaker patterns, and transaction coordination
- **[Platform Adapters](ciris_engine/adapters/README.md)**: Discord, CLI, and API adapters with consistent interfaces and automatic secrets processing
- **[Action Handlers](ciris_engine/action_handlers/README.md)**: Comprehensive 3×3×3 action system with automatic secrets decapsulation and service integration

### 📊 Transparent Accountability
- **[Telemetry System](ciris_engine/telemetry/README.md)**: Multi-tier metric collection with security filtering, resource monitoring, and agent self-awareness via SystemSnapshot
- **[Time Series Database (TSDB)](FSD/TELEMETRY.md)**: Built-in TSDB for unified storage of metrics, logs, and audit events with time-based queries and cross-correlation analysis
- **[API System](ciris_engine/adapters/api/README.md)**: Comprehensive HTTP REST API with real-time telemetry endpoints, processor control, and TSDB data access
- **[Resource Management](ciris_engine/telemetry/README.md)**: Real-time monitoring with psutil integration, resource limit enforcement, and proactive throttling
- **[Performance Monitoring](ciris_engine/telemetry/README.md)**: Sophisticated collector framework with instant, fast, normal, slow, and aggregate data collection tiers
- **[Circuit Breaker Protection](ciris_engine/registries/README.md)**: Automatic service protection with graceful degradation and health monitoring

### 🧩 Ethical Memory & Context  
- **[Graph Memory](ciris_engine/adapters/local_graph_memory/README.md)**: SQLite-backed graph storage with automatic secrets encryption, scope-based access control, and WA-authorized updates
- **[Context Management](ciris_engine/context/README.md)**: Multi-source context aggregation with system snapshots, user profile enrichment, and GraphQL integration
- **[Context Builder](ciris_engine/context/builder_README.md)**: Snapshot helpers and comprehensive channel resolution logic
- **[Configuration Management](ciris_engine/config/README.md)**: Multi-source configuration with agent self-configuration through graph memory operations and WA approval workflows
- **[Data Persistence](ciris_engine/data/README.md)**: Robust SQLite storage with migrations, maintenance automation, and integrity verification

### 🛠 Principled Infrastructure
- **[Epistemic Faculties](ciris_engine/faculties/README.md)**: Advanced content evaluation through specialized entropy, coherence, and decision analysis capabilities
- **[Utility Framework](ciris_engine/utils/README.md)**: Comprehensive infrastructure including logging, context management, GraphQL providers, shutdown coordination, and task formatting
- **[Prompt Engineering](ciris_engine/formatters/README.md)**: Composable text formatting utilities for consistent LLM prompt engineering and response processing
- **[Service Coordination](ciris_engine/services/README.md)**: Adaptive filter service, agent configuration service, and multi-service transaction orchestrator
- **[Mock LLM System](docs/MOCK_LLM.md)**: Deterministic testing framework with `$` command syntax for offline development and debugging

---

## Runtime Control & Management ⭐ **NEW**

CIRIS includes comprehensive **runtime control capabilities** that enable dynamic system management, debugging, and configuration changes without requiring restarts. This provides unprecedented operational flexibility for production deployments and development workflows.

### 🎛️ Hot-Swappable Architecture
- **[Dynamic Adapter Management](ciris_engine/runtime/README.md)**: Load, unload, and reconfigure Discord, CLI, and API adapters at runtime
- **[Multi-Instance Support](ciris_engine/runtime/README.md)**: Run multiple instances of the same adapter type with different configurations (e.g., multiple Discord bots)
- **[Live Configuration Updates](ciris_engine/config/README.md)**: Change system settings with validation and rollback support
- **[Profile Hot-Switching](docs/CIRIS_PROFILES.md)**: Switch between agent personalities and capabilities without downtime

### 🔧 Runtime Control Endpoints
The API adapter exposes comprehensive runtime management through `/v1/runtime/*` endpoints:

```bash
# Hot-load a new Discord adapter
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_type": "discord",
    "adapter_id": "discord_prod", 
    "config": {"token": "...", "home_channel": "general"},
    "auto_start": true
  }'

# Update configuration dynamically
curl -X PUT http://localhost:8080/v1/runtime/config \
  -H "Content-Type: application/json" \
  -d '{
    "path": "llm_services.openai.temperature",
    "value": 0.8,
    "scope": "session",
    "validation_level": "strict"
  }'

# Switch agent profiles
curl -X POST http://localhost:8080/v1/runtime/profiles/teacher/load
```

### 🐛 Live Debugging Capabilities
- **[Processor Control](docs/api/runtime-control.md)**: Single-step execution, pause/resume, and queue inspection
- **[System State Snapshots](ciris_engine/telemetry/README.md)**: Complete runtime state capture for analysis
- **[Configuration Backup/Restore](ciris_engine/config/README.md)**: Safe configuration management with restoration points
- **[Comprehensive Auditing](ciris_engine/audit/README.md)**: All runtime control operations are cryptographically logged

### 📊 Operational Insights
- **[Real-Time Monitoring](docs/api/runtime-control.md)**: Live system status, resource usage, and health metrics
- **[Service Health Tracking](ciris_engine/registries/README.md)**: Circuit breaker states and service availability
- **[Configuration History](ciris_engine/config/README.md)**: Track all configuration changes with rationale and rollback capability
- **[Adapter Lifecycle Management](ciris_engine/runtime/README.md)**: Complete visibility into adapter loading, unloading, and status

> **📖 Complete Documentation**: See [Runtime Control API Guide](docs/api/runtime-control.md) for detailed endpoint documentation and examples.

### Example: Production Hot-Swap Workflow

```bash
# 1. Backup current configuration
curl -X POST http://localhost:8080/v1/runtime/config/backup \
  -d '{"backup_name": "pre_update", "include_profiles": true}'

# 2. Load new Discord adapter with updated configuration
curl -X POST http://localhost:8080/v1/runtime/adapters \
  -d '{
    "adapter_type": "discord",
    "adapter_id": "discord_v2",
    "config": {"token": "new_token", "home_channel": "updated-general"}
  }'

# 3. Verify new adapter is healthy
curl http://localhost:8080/v1/runtime/adapters/discord_v2

# 4. Unload old adapter
curl -X DELETE http://localhost:8080/v1/runtime/adapters/discord_v1

# 5. Update system configuration for new setup
curl -X PUT http://localhost:8080/v1/runtime/config \
  -d '{"path": "discord.default_adapter", "value": "discord_v2"}'
```

---

## Ethical Capabilities

### Moral Agency
- **Principled Decision-Making**: Every action evaluated against ethical frameworks
- **Self-Reflection**: Continuous assessment of actions against moral principles  
- **Wisdom-Based Deferral**: Recognition of limits and escalation to human oversight
- **Transparency**: Full auditability of reasoning processes and decisions

### Responsible Intelligence
- **Stakeholder Consideration**: Multi-perspective ethical analysis
- **Harm Prevention**: Proactive identification and mitigation of potential negative impacts
- **Justice & Fairness**: Bias detection and equitable treatment protocols
- **Autonomy Respect**: Preservation of human agency and dignity in all interactions

---

## 3×3×3 Handler Actions

The `HandlerActionType` enum defines comprehensive operations:

**External Actions:** `OBSERVE`, `SPEAK`, `TOOL`
**Control Responses:** `REJECT`, `PONDER`, `DEFER`  
**Memory Operations:** `MEMORIZE`, `RECALL`, `FORGET`
**Terminal:** `TASK_COMPLETE`

All actions are processed through sophisticated handlers with automatic audit logging, secrets processing, and service coordination.

### Moral Guardrails

| Guardrail | Ethical Purpose |
|-----------|----------------|
| **epistemic_humility** | Recognizes knowledge limits and defers appropriately |
| **optimization_veto** | Prevents efficiency from overriding human autonomy |
| **coherence** | Ensures rational and understandable reasoning |
| **entropy** | Maintains meaningful communication standards |
| **pii_protection** | Safeguards personal information and privacy |
| **harm_prevention** | Proactively identifies and blocks potential harm |
| **fairness_check** | Detects and prevents discriminatory actions |
| **transparency** | Maintains auditability and explainability |

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

**API Server mode:**
```bash
python main.py --modes api --host 0.0.0.0 --port 8080
```

For comprehensive API documentation, see [docs/api_reference.md](docs/api_reference.md).

**Specific runtime modes:**
```bash
python main.py --modes cli --profile teacher    # CLI-only mode
python main.py --modes discord --profile student # Discord bot mode  
python main.py --modes api --host 0.0.0.0 --port 8080 # API server mode
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

**Ethical Testing with Mock LLM:**
```bash
# Test moral reasoning offline
python main.py --mock-llm --profile teacher

# Examine ethical decision-making
pytest tests/context_dumps/ -v -s   # View agent reasoning context
```

**Ethical compliance testing:**
```bash
pytest tests/ciris_engine/guardrails/ -v     # Moral guardrails validation
pytest tests/ciris_engine/audit/ -v          # Transparency and audit systems
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
- **[Creator Intent Statement](CIS.md)** - Purpose, benefits, risks, and design philosophy
- **[CIRIS Covenant](covenant_1.0b.txt)** - Complete ethical framework and principles
- **[Mock LLM System](docs/MOCK_LLM.md)** - Offline testing and development
- **[CIRIS Profiles](docs/CIRIS_PROFILES.md)** - Agent moral reasoning configuration
- **[Context Dumps](tests/context_dumps/README.md)** - Understanding agent decision processes

### Technical Documentation
- **Module READMEs** - Detailed documentation in each `ciris_engine/` subdirectory
- **[Runtime Control API](docs/api/runtime-control.md)** - Comprehensive runtime management endpoints ⭐ **NEW**
- **[Protocol Architecture](docs/protocols/README.md)** - Service-oriented architecture and interfaces ⭐ **NEW**
- **[API Reference](docs/api_reference.md)** - Complete REST API documentation
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment and configuration
- **[Security Setup](docs/SECURITY_SETUP.md)** - Security configuration and best practices
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Development Resources
- **[Installation Guide](docs/INSTALLATION.md)** - Detailed setup instructions
- **[Contributing Guide](CONTRIBUTING.md)** - Development workflow and standards
- **[Runtime System](ciris_engine/runtime/README.md)** - Hot-swappable modular architecture ⭐ **NEW**

---

*For additional technical documentation, see individual module README files throughout the codebase.*