# Adapters

The adapters module provides platform-specific implementations and service interfaces for the CIRIS engine. Adapters allow CIRIS to operate across different environments (CLI, Discord, API) and integrate with various external services.

## Core Components

### Platform Adapters
- **CLI Adapter** (`cli/`): Command-line interface for direct user interaction
- **Discord Adapter** (`discord/`): Discord bot integration for community interaction  
- **API Adapter** (`api/`): RESTful API for web service integration

### Service Adapters
- **Local Graph Memory** (`local_graph_memory/`): Local graph-based memory implementation
- **OpenAI Compatible LLM** (`openai_compatible_llm.py`): LLM service adapter for OpenAI-compatible APIs
- **Local Audit Log** (`local_audit_log.py`): File-based audit logging service
- **Tool Registry** (`tool_registry.py`): Central registry for external tools and services

### Base Classes
- **Base Adapter** (`base.py`): Abstract base class for all adapters
- **CIRISNode Client** (`cirisnode_client.py`): Client for connecting to CIRISNode services

## Key Features

- **Service Registry Integration**: All adapters register with the service registry for dependency injection
- **Runtime Agnostic**: Handlers work across all adapters without modification
- **Circuit Breaker Support**: Built-in reliability patterns for external service integration
- **Type Safety**: Full Pydantic model validation for all adapter interfaces

## Usage

Adapters are automatically loaded based on runtime mode:

```python
# CLI mode
python main.py --mode cli

# Discord mode  
python main.py --mode discord

# API mode
python main.py --mode api
```

Each adapter provides the same core services (communication, tools, memory, audit) but with platform-specific implementations.
