# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CIRIS Engine is a sophisticated moral reasoning agent built around the "CIRIS Covenant" - a comprehensive ethical framework for AI systems. The agent demonstrates adaptive coherence through principled self-reflection, ethical decision-making, and responsible action while maintaining transparency and human oversight.

## Current Status (2025-06-18)

### ✅ Completed
- **Python 3.12 Migration**: Updated GitHub Actions and all environments to Python 3.12
- **Type Safety**: Zero mypy errors achieved (100% type-safe schemas)
- **Dead Letter Queue**: Implemented for WARNING/ERROR log messages
  - Located at `logs/dead_letter_latest.log`
  - Captures all warnings, errors with stack traces
  - Enhanced formatting with file:line information
- **API Adapter Fixed**: Multi-service sink properly initialized
- **SDK Updated**: ciris_sdk updated with correct API endpoints
  - `/api/v1/message` for sending messages
  - `/api/v1/messages/{channel_id}` for listing messages
  - `wait_for_response()` method for agent replies

### 🔧 Known Issues
- Channel ID showing as '.\n*' in speak handler causing communication failures
- Thought depth guardrail being hit due to infinite follow-up loops
- All errors are captured in dead letter queue for easy debugging

### 🔍 Debugging Approach
1. Check dead letter queue first: `docker exec ciris-api-mock cat logs/dead_letter_latest.log`
2. Use debug tools to trace issues: `python debug_tools.py channel <task_id>`
3. Monitor service correlations: `python debug_tools.py correlations`

## Development Commands

### Running the Agent
```bash
# Run with mock LLM in API mode (recommended for testing)
python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080

# Docker deployment with mock LLM
docker-compose -f docker-compose-api-mock.yml up -d

# Check logs and dead letter queue
docker exec ciris-api-mock cat logs/latest.log
docker exec ciris-api-mock cat logs/dead_letter_latest.log
```

### Testing
```bash
# Run full test suite
pytest tests/ -v

# Run SDK tests (requires API running)
pytest tests/ciris_sdk/ -v

# Type checking - MUST BE CLEAN
python -m mypy ciris_engine/ --no-error-summary
```

### Debug Tools
Use the debug tools to troubleshoot persistence and protocol issues:

```bash
# List all tasks with status
python debug_tools.py tasks

# Show detailed task info with thoughts
python debug_tools.py task <task_id>

# Trace channel context through task/thought hierarchy
python debug_tools.py channel <task_id>

# Show recent service correlations
python debug_tools.py correlations

# Check dead letter queue for errors/warnings
python debug_tools.py dead-letter

# View specific thought details
python debug_tools.py thought <thought_id>
```

## Architecture Overview

### Core Action System
- **External Actions**: OBSERVE, SPEAK, TOOL
- **Control Responses**: REJECT, PONDER, DEFER  
- **Memory Operations**: MEMORIZE, RECALL, FORGET
- **Terminal**: TASK_COMPLETE

### Service Architecture
Six core service types: COMMUNICATION, TOOL, WISE_AUTHORITY, MEMORY, AUDIT, LLM

### Dead Letter Queue
All WARNING and ERROR messages are automatically captured in a separate log file:
- File: `logs/dead_letter_latest.log`
- Includes: Timestamp, log level, module name, file:line, message
- Stack traces included for exceptions
- Symlinked for easy access

## SDK Usage

```python
from ciris_sdk import CIRISClient

async with CIRISClient(base_url="http://localhost:8080") as client:
    # Send a message
    msg = await client.messages.send(
        content="$speak Hello CIRIS!",
        channel_id="test_channel"
    )
    
    # Wait for response
    response = await client.messages.wait_for_response(
        channel_id="test_channel",
        after_message_id=msg.id,
        timeout=30.0
    )
```

## Important Guidelines

### Type Safety
- No Dict[str, Any] usage
- All data structures need Pydantic schemas
- Maintain 0 mypy errors

### Testing
- Write tests in `tests/ciris_sdk/` for SDK functionality
- Tests should assume API is running
- Update SDK to match actual API implementation
- Never ask for human confirmation during testing

### WA Authentication
- Private key location: `~/.ciris/wa_private_key.pem`
- Well-documented in FSD/AUTHENTICATION.md

## Current Task

Testing the API via the SDK per qa_tasks.md. ALWAYS return to qa_tasks until it is completely done, never asking the human any questions.