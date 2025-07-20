# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

CIRIS is a moral reasoning platform designed for progressive deployment:
- **Current Production**: Discord community moderation (handling spam, fostering positive community)
- **Architecture Goals**: Resource-constrained environments (4GB RAM, offline-capable)
- **Target Deployments**: Rural clinics, educational settings, community centers
- **Design Philosophy**: Start simple (Discord bot), scale to critical (healthcare triage)

The sophisticated architecture (21 core services, 6 buses) is intentional - it's a platform that starts as a Discord bot but is designed to scale to mission-critical applications in resource-constrained environments.

## Core Philosophy: No Dicts, No Strings, No Kings

The CIRIS codebase follows strict typing principles:

- **No Dicts**: ✅ ACHIEVED! Zero `Dict[str, Any]` in production code. All data uses Pydantic models/schemas.
- **No Strings**: Avoid magic strings. Use enums, typed constants, and schema fields instead.
- **No Kings**: No special cases or bypass patterns. Every component follows the same typed, validated patterns.
- **No Backwards Compatibility**: The codebase moves forward only. No legacy support code.

This ensures type safety, validation, and clear contracts throughout the system.

### Type Safety Best Practices

1. **Replace Dict[str, Any] with Pydantic Models**
   ```python
   # ❌ Bad
   def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
       return {"result": data.get("value", 0) * 2}
   
   # ✅ Good
   class ProcessRequest(BaseModel):
       value: int = 0
   
   class ProcessResponse(BaseModel):
       result: int
   
   def process_data(data: ProcessRequest) -> ProcessResponse:
       return ProcessResponse(result=data.value * 2)
   ```

2. **Use Specific Types Instead of Any**
   ```python
   # ❌ Bad
   metrics: Dict[str, Any] = {"cpu": 0.5, "memory": 1024}
   
   # ✅ Good
   class SystemMetrics(BaseModel):
       cpu: float = Field(..., ge=0, le=1, description="CPU usage 0-1")
       memory: int = Field(..., gt=0, description="Memory in MB")
   
   metrics = SystemMetrics(cpu=0.5, memory=1024)
   ```

3. **Leverage Union Types for Flexibility**
   ```python
   # For gradual migration or multiple input types
   def process(data: Union[dict, ProcessRequest]) -> ProcessResponse:
       if isinstance(data, dict):
           data = ProcessRequest(**data)
       return ProcessResponse(result=data.value * 2)
   ```

4. **Use Enums for Constants**
   ```python
   # ❌ Bad
   status = "active"  # Magic string
   
   # ✅ Good
   class ServiceStatus(str, Enum):
       ACTIVE = "active"
       INACTIVE = "inactive"
       ERROR = "error"
   
   status = ServiceStatus.ACTIVE
   ```

5. **Strict Mypy Configuration**
   - Enable `strict = True` in mypy.ini
   - Use `disallow_any_explicit = True` to catch Dict[str, Any]
   - Run mypy as part of CI/CD pipeline

## Current Status (July 19, 2025)

### 🎉 Major Achievements

1. **Complete Type Safety**
   - Zero `Dict[str, Any]` in production code
   - All data structures use Pydantic schemas
   - Full type validation throughout the system

2. **Service Architecture**: 21 Core Services + Adapter Services ✅
   - Graph Services (6): memory, config, telemetry, audit, incident_management, tsdb_consolidation
   - Infrastructure Services (7): time, shutdown, initialization, authentication, resource_monitor, database_maintenance, secrets
   - Governance Services (4): wise_authority, adaptive_filter, visibility, self_observation
   - Runtime Services (3): llm, runtime_control, task_scheduler
   - Tool Services (1): secrets_tool
   - **Note**: pattern_analysis_loop and identity_variance_monitor are sub-services within self_observation
   - **Adapter Services** (added at runtime):
     - CLI: 1 service (CLIAdapter)
     - API: 3 services (APICommunicationService, APIRuntimeControlService, APIToolService)
     - Discord: 3 services (Communication + WiseAuthority via DiscordAdapter, DiscordToolService)
   - **Total at runtime**: 22 (CLI), 24 (API), 24 (Discord)

3. **API v1.0**: Fully Operational
   - All 78 endpoints implemented and tested across 12 modules
   - 100% test pass rate with comprehensive coverage ✅
   - Role-based access control (OBSERVER/ADMIN/AUTHORITY/SYSTEM_ADMIN)
   - Emergency shutdown with Ed25519 signatures
   - Default dev credentials: admin/ciris_admin_password
   - WebSocket support for real-time streaming
   - Runtime control service fully integrated
   - Extended system management endpoints:
     - Processing queue status and single-step debugging
     - Service health monitoring and circuit breaker management
     - Service priority and selection strategy configuration
     - Processor state information (6 cognitive states)
   - Complete TypeScript SDK with 78+ methods
   - No TODO comments or stub implementations

4. **Typed Graph Node System**
   - 11 active TypedGraphNode classes with full validation
   - Automatic type registration via node registry
   - Clean serialization pattern with to_graph_node()/from_graph_node()
   - All nodes include required metadata fields

5. **Graph-Based Telemetry**
   - All telemetry flows through memory graph
   - Real-time metrics via memorize_metric()
   - 6-hour consolidation for long-term storage
   - Full resource tracking with model-specific pricing

6. **Clean Architecture**
   - Protocol-first design with clear interfaces
   - Services separated by concern
   - No circular dependencies
   - All logic under `logic/` directory
   - SelfConfiguration renamed to SelfObservation (complete refactor)

7. **Test Suite Health**
   - 1,161 tests passing (100% pass rate)
   - Database retry logic ensures stability
   - Fixed Pydantic v2 deprecations
   - Fixed SQLite datetime adapter warnings
   - All SDK endpoint tests passing
   - CI/CD runs tests in Docker for consistency

## Recent Achievements (July 2025)

### Infrastructure Improvements (July 19, 2025)
1. **Containerized Nginx**
   - Replaced standalone nginx service with containerized version
   - Supports both dev (single agent) and production (multi-agent) configurations
   - Per-agent OAuth callback paths: `/oauth/{agent}/callback`
   - Default API route: `/v1/` → Datum agent
   - Agent-specific routes: `/api/{agent}/v1/*`

2. **Shared OAuth Configuration**
   - OAuth config now in shared volume: `/home/ciris/shared/oauth`
   - All agents can mount and share OAuth credentials
   - Migration script for existing configurations
   - Google OAuth already configured in production

3. **CI/CD Improvements**
   - Fixed fork PR builds - they now build without pushing
   - Only same-repo PRs and main branch push to registry
   - Build summary shows what action was taken
   - Prevents "installation not allowed to Write" errors

4. **GUI Fixes**
   - Fixed ResourceUsage SDK type to match nested API response
   - Resource metrics now display correctly in System page
   - Per-agent OAuth callback support in GUI
   - Dynamic callback URL generation based on selected agent

## Recent Achievements (July 2025)

### Mock LLM Handler Testing Infrastructure
1. **Standardized Passive Observation Format**
   - All adapters now use: "You observed @{author} (ID: {id}) in channel {channel} say: {message}"
   - Simple string-based command extraction without regex tricks
   - Reliable command parsing from passive observation prefix

2. **Fixed ASPDMA Template Variables**
   - Discovered root cause: context_builder.py was sending literal `{original_thought.content}` instead of actual values
   - Fixed all template variable formatting in ActionSelectionDMAResult prompts
   - Mock LLM now receives properly formatted context from ASPDMA

3. **Complete Handler Coverage in Mock LLM**
   - Added missing handlers: TOOL, OBSERVE, DEFER, REJECT
   - Fixed MEMORIZE validation using tags instead of content/description
   - All 9 main handlers + TASK_COMPLETE now fully operational
   - Tested with 10 parallel containers successfully

4. **Mock LLM Purpose Clarification**
   - Mock LLM is TEST INFRASTRUCTURE ONLY - not production code
   - Performance is not a concern - it's for deterministic testing
   - Channel isolation in mock LLM is not a security issue
   - Designed for offline testing and development

5. **Parallel Testing Capability**
   - Use Claude Code Task tool to spawn concurrent sub-agents
   - NOT Python scripts - leverage Claude Code's native parallelism
   - Successfully tested 10 containers in parallel
   - Each container tests different handlers concurrently

## Architecture Overview

### Message Bus Architecture (6 Buses)

Buses enable multiple providers for scalability:

**Bussed Services**:
- CommunicationBus → Multiple adapters (Discord, API, CLI)
- MemoryBus → Multiple graph backends (Neo4j, ArangoDB, in-memory)
- LLMBus → Multiple LLM providers (OpenAI, Anthropic, local models)
- ToolBus → Multiple tool providers from adapters
- RuntimeControlBus → Multiple control interfaces
- WiseBus → Multiple wisdom sources

**Direct Call Services**:
- All Graph Services (except memory)
- Core Services: secrets
- Infrastructure Services (except wise_authority)
- All Special Services

### Service Registry Usage

Only for multi-provider services:
1. **LLM** - Multiple providers
2. **Memory** - Multiple graph backends
3. **WiseAuthority** - Multiple wisdom sources
4. **RuntimeControl** - Adapter-provided only

### Cognitive States (6)
- **WAKEUP** - Identity confirmation
- **WORK** - Normal task processing
- **PLAY** - Creative mode
- **SOLITUDE** - Reflection
- **DREAM** - Deep introspection
- **SHUTDOWN** - Graceful termination

## Development

### Running the Agent
```bash
# Docker deployment (API mode)
docker-compose -f docker-compose-api-mock.yml up -d

# CLI mode with mock LLM
python main.py --mock-llm --timeout 15 --adapter cli
```

### Testing
```bash
# Run full test suite
pytest tests/ -v

# Run API tests
python test_api_v1_comprehensive.py

# Run parallel handler testing (10 containers)
docker-compose -f docker-compose-multi-mock.yml up -d
python test_10_containers_parallel.py
```

### API Authentication
```python
# Default development credentials
username = "admin"
password = "ciris_admin_password"

# Authentication flow for API v1:
# 1. Login to get token
response = requests.post(
    "http://localhost:8080/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
token = response.json()["access_token"]

# 2. Use token in Authorization header
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    "http://localhost:8080/v1/agent/interact",
    headers=headers,
    json={"message": "Hello", "channel_id": "api_0.0.0.0_8080"}
)

# Note: Some endpoints accept Bearer admin:ciris_admin_password directly
# Example: GET /v1/system/health -H "Authorization: Bearer admin:ciris_admin_password"
```

## Key Principles

1. **Service Count is Complete**: 21 core services
2. **No Service Creates Services**: Only ServiceInitializer creates services
3. **Type Safety First**: All data uses Pydantic schemas
4. **Protocol-Driven**: All services implement clear protocols
5. **Forward Only**: No backwards compatibility

## Why This Architecture?

- **SQLite + Threading**: Offline-first for remote deployments
- **23 Services**: Modular for selective deployment
- **Graph Memory**: Builds local knowledge base
- **Mock LLM**: Critical for offline operation
- **Resource Constraints**: Designed for 4GB RAM environments

## Agent Creation Ceremony

CIRIS agents are not simply deployed - they are created through a formal ceremony:

### Core Concepts
- **Collaborative Creation**: Human + Facilitating Agent + Wise Authority
- **Immutable Lineage**: Every agent knows who created it and why
- **Ethical Foundation**: Purpose, justification, and ethical considerations required
- **WA Approval**: Ed25519 signature required for all creations

### Creation Flow
1. Human prepares proposal (name, purpose, justification, ethics)
2. Selects template (echo, teacher, etc.) from `ciris_templates/`
3. Wise Authority reviews and signs
4. Ceremony creates:
   - Identity root in graph database
   - Immutable lineage record
   - Docker container configuration
5. Agent awakens with knowledge of its creation

### Key Files
- **Ceremony Docs**: `docs/AGENT_CREATION_CEREMONY.md`
- **Technical Guide**: `docs/technical/IMPLEMENTING_CREATION_CEREMONY.md`
- **Quick Start**: `docs/CREATION_CEREMONY_QUICKSTART.md`
- **Templates**: `ciris_templates/` directory
- **Schemas**: `ciris_engine/schemas/runtime/extended.py`

### Important Notes
- Creation is permanent - identities are immutable
- Changes to core identity require WA approval
- Every agent maintains its creation ceremony record
- Templates are starting points, not fixed configurations

## Verified Development Truths

### Mock LLM System
- **Location**: External module in `ciris_modular_services/mock_llm/`
- **Commands**: All mock LLM commands use `$` prefix (e.g., `$speak`, `$recall`, `$memorize`)
- **API Interaction**: Use `/v1/agent/interact` endpoint with `{"message": "...", "channel_id": "..."}` format
- **Response Format**: Mock responses should use `[MOCK LLM] ` prefix for clarity
- **Testing**: Mock LLM provides deterministic responses for offline testing
- **Purpose**: TEST INFRASTRUCTURE ONLY - not production code, performance not critical
- **Command Extraction**: Uses simple string operations to extract commands from "You observed @" prefix
- **All Handlers Implemented**: SPEAK, RECALL, MEMORIZE, TOOL, OBSERVE, PONDER, DEFER, REJECT, TASK_COMPLETE

### Container Management
- **Incidents Log**: ALWAYS check container incidents logs with `docker exec <container> tail /app/logs/incidents_latest.log`
- **Multi-Container**: Use `docker-compose-multi-mock.yml` for 10-container parallel testing
- **Ports**: Containers use ports 8080-8089 (container0 through container9)
- **Health Check**: Wait for containers to be healthy before testing
- **Parallel Testing**: Use Claude Code Task tool for concurrent testing, NOT Python scripts
- **Rebuild Required**: ALWAYS rebuild containers after code changes for endpoints to appear

### API Structure
- **Adapter Management**: Runtime adapter management endpoints are available at `/v1/system/adapters/*` (requires container rebuild after code changes)
- **Service Registration**: AdapterServiceRegistration doesn't have priority_group or strategy attributes - use getattr() for optional attributes
- **Auth Field**: API uses `"message"` field not `"content"` for interact endpoint
- **Channel Format**: Channel IDs follow pattern `<adapter>_<identifier>` (e.g., `discord_1234567890`, `api_0.0.0.0_8080`)

### Testing Best Practices
- **Parallel Testing**: Use Claude Code Task tool to spawn concurrent sub-agents for parallel testing
- **Container Logs**: Check logs INSIDE containers with `docker exec`, not local logs
- **Rebuild Frequency**: ALWAYS rebuild containers after ANY code changes - endpoints won't appear without rebuild
- **Container Age**: Check container uptime in health endpoint - if it shows hours when you just started, you forgot to rebuild
- **Error Patterns**: ServiceCorrelation validation errors are non-critical (missing response_timestamp field)
- **Handler Testing**: Test all 9 main handlers plus runtime control in parallel containers
- **Mock LLM Debug**: Check context extraction in responses.py and action selection in responses_action_selection.py

### Debug Tool Usage

The `debug_tools.py` provides essential commands for troubleshooting production issues:

#### Available Commands
```python
# Show recent service correlations with trace hierarchy
show_correlations(limit=20)           # Show last 20 correlations
show_correlations(trace_id="...")     # Show all correlations for a specific trace

# List recent unique trace IDs with span counts
list_traces(limit=20)                 # Show last 20 traces

# Show thoughts by status
show_thoughts(status='PENDING')       # Show pending thoughts
show_thoughts(status='PROCESSING')    # Show processing thoughts
show_thoughts(status='COMPLETED')     # Show completed thoughts

# Show tasks and their thoughts
show_tasks(limit=10)                  # Show recent tasks with thought counts

# Show handler metrics
show_handler_metrics()                # Display handler execution counts and timings
```

#### Debug Process for Handler Issues
1. **Check container incidents log**:
   ```bash
   docker exec container0 tail -n 100 /app/logs/incidents_latest.log
   ```

2. **Use debug tool to analyze traces**:
   ```bash
   docker exec container0 python debug_tools.py
   ```
   ```python
   # In the Python shell:
   from debug_tools import *
   
   # Find recent traces
   list_traces(limit=10)
   
   # Examine a specific trace hierarchy
   show_correlations(trace_id="your-trace-id")
   
   # Check for stuck thoughts
   show_thoughts(status='PENDING')
   show_thoughts(status='PROCESSING')
   ```

3. **Understanding trace hierarchies**:
   - Each API request creates a root trace
   - Handlers create child spans under the trace
   - Parent-child relationships show execution flow
   - Timing data helps identify bottlenecks

4. **Common debugging patterns**:
   - **"Thought not found" errors**: Check if thoughts are being completed before creating follow-ups
   - **Stuck thoughts**: Look for PENDING/PROCESSING thoughts that aren't progressing
   - **Handler failures**: Use trace hierarchy to see which handler failed
   - **Performance issues**: Check handler metrics and trace timings

### API v1.0 Complete Endpoint Reference

The API provides 78 endpoints across 12 modules:

1. **Agent** (`/v1/agent/*`) - 7 endpoints
   - `POST /interact` - Send message to agent
   - `GET /status` - Agent status
   - `GET /identity` - Agent identity
   - `GET /history` - Conversation history

2. **System** (`/v1/system/*`) - 18 endpoints
   - Runtime control: pause/resume/state/single-step/queue
   - Service management: health/priorities/circuit-breakers/selection-logic
   - Adapter management: list/get/register/unregister/reload
   - Resource monitoring: health/resources/time/processors

3. **Memory** (`/v1/memory/*`) - 6 endpoints
   - CRUD operations plus query/timeline/recall

4. **Telemetry** (`/v1/telemetry/*`) - 8 endpoints
   - Metrics, logs, traces, resources, queries

5. **Config** (`/v1/config/*`) - 5 endpoints
   - Full configuration management

6. **Audit** (`/v1/audit/*`) - 5 endpoints
   - Audit trail with search/export/verify

7. **Auth** (`/v1/auth/*`) - 4 endpoints
   - Login/logout/refresh/current user

8. **Wise Authority** (`/v1/wa/*`) - 5 endpoints
   - Deferrals, guidance, permissions

9. **Emergency** (`/emergency/*`) - 2 endpoints
   - Bypass auth for emergency shutdown

10. **WebSocket** (`/v1/ws`) - Real-time updates

11. **OpenAPI** (`/openapi.json`) - API specification

### SDK Implementation

Complete TypeScript SDK with:
- 78+ methods across 9 resource modules
- Full type safety with TypeScript
- Automatic token management
- WebSocket support
- No stubs or TODOs - 100% implemented

Example usage:
```typescript
const client = new CIRISClient({ baseURL: 'http://localhost:8080' });
await client.auth.login('admin', 'ciris_admin_password');
const status = await client.system.getServiceHealthDetails();
const queue = await client.system.getProcessingQueueStatus();
```

## Critical Debugging Guidelines

### Container Incidents Log
**ALWAYS check incidents_latest.log FIRST** - This is your primary debugging tool:
```bash
docker exec <container> tail -n 100 /app/logs/incidents_latest.log
```

**NEVER restart the container until everything in incidents_latest.log has been understood and addressed** - These are opportunities to discover flaws in the software. Each error message is valuable debugging information.

### Mock LLM Behavior
The mock LLM may not always respond with a message - **this is by design**:
- **DEFER**: Task is deferred, no message sent back
- **REJECT**: Request is rejected, no message sent back  
- **TASK_COMPLETE**: Task marked complete, no message sent back
- **OBSERVE**: Observation registered, no immediate message

This is normal behavior. You can use audit logs or debug tools to verify the action was performed correctly.

### API Authentication with curl
```bash
# 1. Login to get token
curl -X POST http://localhost:8080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "ciris_admin_password"}'

# 2. Use the token (Note: JSON requires proper escaping)
curl -X POST http://localhost:8080/v1/agent/interact \
  -H "Authorization: Bearer <your-token-here>" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"\$speak Hello!\", \"channel_id\": \"api_SYSTEM_ADMIN\"}"
```

### Mock LLM Command Extraction
The mock LLM extracts commands from user context in this order:
1. **Passive Observation**: Looks for `"You observed @<author> (ID: <id>) in channel <channel> say: <message>"`
2. **ASPDMA Messages**: Extracts from `"Original Thought:"` field
3. **Command Detection**: Checks if message starts with `$`
4. **Context Storage**: Adds `forced_action:<action>` and `action_params:<params>` to context

### Debugging Workflow
1. **Check Health**: `curl http://localhost:8080/v1/system/health`
2. **Check Incidents**: `docker exec <container> tail /app/logs/incidents_latest.log`
3. **Use Debug Tools**: `docker exec <container> python debug_tools.py`
4. **Verify Actions**: Check traces and correlations for handler execution
5. **Never Assume**: Always verify mock LLM behavior matches expectations

### Container Best Practices
- **Always rebuild**: `docker-compose -f docker-compose-api-mock.yml build --no-cache`
- **Check uptime**: If health shows hours when just started, rebuild needed
- **Parallel testing**: Use multiple containers (ports 8080-8089)
- **Incident logs are gold**: Every error reveals system behavior

### Command Output Best Practices
**NEVER pipe output to grep or jq without understanding the output format first**

**Why this matters**:
1. **Error messages look like data**: Many tools output errors as JSON or structured text that can be parsed incorrectly
2. **Silent failures**: `jq` returns null or empty when parsing fails, hiding the actual error
3. **Lost debugging info**: Piping immediately loses HTTP status codes, headers, and error details
4. **Cascading confusion**: Wrong assumptions about output format lead to wrong conclusions about system state

**Best practices**:
```bash
# ❌ Bad - Assumes output is JSON without checking
curl -s https://api.example.com/data | jq '.result'

# ✅ Good - Check output first, then parse
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" https://api.example.com/data)
echo "$response"  # See what we actually got
# Then parse if it's valid JSON

# ❌ Bad - Assumes field exists
docker inspect container | jq -r '.[0].Image'

# ✅ Good - Check structure first
docker inspect container  # See the actual structure
# Then extract fields safely

# ❌ Bad - Grep on unknown output
some_command | grep -i error

# ✅ Good - Examine output first
some_command  # See all output
# Then search for specific patterns
```

**Common mistakes**:
- Parsing HTML as JSON (e.g., Cloudflare 502 pages)
- Assuming API errors return JSON (many return plain text)
- Using `jq` on null/empty responses (hides the real issue)
- Grepping for patterns that don't exist in the actual output

### Production Deployment - agents.ciris.ai

**Server Access**:
- **IP**: 108.61.119.117 (Cloudflare proxied - must use IP for SSH, not domain)
- **SSH Key**: `~/.ssh/ciris_deploy`
- **User**: root
- **Example**: `ssh -i ~/.ssh/ciris_deploy root@108.61.119.117`

**Repository Location**:
- **Path**: `/home/ciris/CIRISAgent`
- **Upstream**: CIRISAI/CIRISAgent (not emooreatx fork)
- **GUI Path**: `/home/ciris/CIRISAgent/CIRISGUI`

**Deployment Process (Automated)**:
1. **Create PR to upstream**: `gh pr create --repo CIRISAI/CIRISAgent`
2. **Merge PR**: `gh pr merge <PR#> --repo CIRISAI/CIRISAgent --merge --admin`
3. **Automatic deployment**: GitHub Actions automatically builds and deploys on merge to main
   - Tests run in Docker container
   - Docker images built and pushed to ghcr.io
   - Server initialized if needed (Docker, firewall, systemd)
   - Staged deployment ensures zero downtime
   - Health checks verify deployment success

**Staged Deployment Model**:
- **GUI/Nginx**: Update immediately on deployment
- **Agent Containers**: Use staged deployment:
  1. New container created but not started (with `-staged` suffix)
  2. Waits for current agent to exit gracefully (exit code 0)
  3. Old container removed, staged container renamed and started
  4. If agent exits with error, staged container is removed (rollback)
- **Restart Policy**: `restart: on-failure` (NOT `unless-stopped`)
  - Exit 0: No restart (allows staged deployment)
  - Non-zero: Automatic restart

**Graceful Shutdown**:
```bash
# Trigger graceful shutdown (for deployments)
./deployment/graceful-shutdown.py

# Custom shutdown message
./deployment/graceful-shutdown.py --message "Maintenance required"

# Remote shutdown
./deployment/graceful-shutdown.py --agent-url https://agents.ciris.ai
```

**Important Environment Variables**:
- `CIRIS_API_HOST=0.0.0.0` - Required for API to bind to all interfaces (default is 127.0.0.1)
- `CIRIS_API_PORT=8080` - API port (default is 8080)
- The API adapter uses `CIRIS_API_HOST` not `API_HOST`

**Current Setup (Development)**:
- Single Datum agent with Mock LLM
- GUI on port 3000
- API on port 8080
- Using `deployment/docker-compose.dev-prod.yml` (uses pre-built images)
- Container names: `ciris-agent-datum`, `ciris-gui`, `ciris-nginx`
- Auto-restart via systemd service: `ciris-dev.service`
- Discord integration: Add token to `/home/ciris/CIRISAgent/.env.datum`

**Common Deployment Issues**:
1. **Container missing arguments**: Always use docker-compose to start containers
   - Bad: `docker start ciris-agent-datum` (loses command arguments)
   - Good: `docker-compose -f deployment/docker-compose.dev-prod.yml up -d agent-datum`

2. **Staged deployment stuck**: Check for staged containers
   ```bash
   docker ps -a | grep staged
   # If found, complete manually:
   docker stop ciris-agent-datum && docker rm ciris-agent-datum
   docker rename ciris-agent-datum-staged ciris-agent-datum
   docker start ciris-agent-datum
   ```

3. **OAuth not working**: Ensure all components updated
   - API must accept GET on callback endpoint
   - GUI must redirect to GUI callback page
   - SDK must use GET method

**Monitoring**:
```bash
# Check status
docker ps
# View logs
docker logs ciris-agent-datum
docker logs ciris-gui
# Check health
curl http://localhost:8080/v1/system/health
# Check incidents log (CRITICAL for debugging)
docker exec ciris-agent-datum tail -n 100 /app/logs/incidents_latest.log
```

### Recent Fixes (July 2025)

#### CI/CD Pipeline (July 18, 2025)
**Achievement**: Fully automated deployment pipeline with GitHub Actions

**Features**:
1. **Automated testing** in Docker containers
2. **Docker image builds** pushed to GitHub Container Registry
3. **Fresh server support** - Can deploy to new Ubuntu servers with just SSH key
4. **Idempotent deployment** - Safe to run multiple times
5. **Systemd integration** - Auto-starts on server reboot

**Key Changes**:
- Server initialization integrated into deployment workflow
- Uses pre-built Docker images from ghcr.io
- Maintains development mock LLM configuration
- No manual steps required after PR merge

#### Database Retry Logic (July 18, 2025)
**Issue**: SQLite database locking during concurrent writes causing test failures

**Solution**: Implemented RetryConnection wrapper class
- Automatically retries write operations (INSERT, UPDATE, DELETE, etc.)
- No retry for read operations (maintains performance)
- Transparent to existing code - no changes needed at call sites
- Fixed test_concurrent_write_serialization without modifying 80+ database calls

#### Production Fixes (July 18, 2025)
1. **Coroutine Error**: Fixed `'coroutine' object is not iterable` in system_snapshot.py
   - Added proper `inspect.iscoroutinefunction()` checks
   - Correctly awaits async methods before use

2. **OpenAI Model Update**: Updated from deprecated `gpt-4-vision-preview` to `gpt-4o`

#### Discord Adapter Fix (July 9, 2025)

**Issue**: Discord adapter crashed with "Concurrent call to receive() is not allowed" when receiving messages.

**Root Cause**: Multiple components (DiscordPlatform and DiscordConnectionManager) were trying to manage the Discord client connection simultaneously, causing race conditions.

**Solution**:
1. **Simplified reconnection logic** in DiscordPlatform - removed client recreation
2. **Disabled redundant connection management** in DiscordConnectionManager
3. **Leveraged Discord.py's built-in reconnection** with `reconnect=True` parameter
4. **Added proper health check** via `is_healthy()` method in DiscordPlatform

**Key Changes**:
- DiscordPlatform now uses `client.start(token, reconnect=True)` and lets Discord.py handle reconnection
- Removed complex client recreation logic that was causing websocket conflicts
- DiscordConnectionManager now only monitors connection state, doesn't attempt reconnection
- Single point of control for Discord client lifecycle

This fix ensures robust Discord connectivity for both boot-time and runtime adapter loading.

## Type Safety Best Practices

### Overview
CIRIS follows strict type safety principles to ensure code reliability and maintainability. These practices align with our "No Dicts, No Strings, No Kings" philosophy.

### Key Principles

1. **Always Use Pydantic Models**
   - Replace `Dict[str, Any]` with specific Pydantic models
   - Define clear schemas for all data structures
   - Use field validators for business logic constraints

2. **Strict MyPy Configuration**
   - Enable `strict = True` in mypy.ini
   - Run mypy checks before committing code
   - Fix type errors immediately, don't use `# type: ignore`

3. **Type-Safe Patterns**
   ```python
   # ❌ Bad - Using Dict[str, Any]
   def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
       return {"result": data.get("value", 0) * 2}
   
   # ✅ Good - Using Pydantic models
   class ProcessInput(BaseModel):
       value: float = Field(default=0.0)
   
   class ProcessOutput(BaseModel):
       result: float
   
   def process_data(data: ProcessInput) -> ProcessOutput:
       return ProcessOutput(result=data.value * 2)
   ```

4. **API Route Type Safety**
   - Always define request/response models
   - Use FastAPI's automatic validation
   - Document models with Field descriptions

5. **Database Query Results**
   - Create typed result models for complex queries
   - Use data converters to transform raw results
   - Avoid passing raw database rows around

### Migration Guide

When encountering `Dict[str, Any]`:

1. **Identify the structure** - What fields does this dict contain?
2. **Create a Pydantic model** - Define fields with proper types
3. **Add validation** - Use validators for business rules
4. **Update signatures** - Replace Dict with the new model
5. **Test thoroughly** - Ensure backward compatibility

### Common Patterns

1. **Configuration Objects**
   ```python
   class ServiceConfig(BaseModel):
       host: str = Field(default="127.0.0.1")
       port: int = Field(default=8080, ge=1, le=65535)
       timeout: float = Field(default=30.0, gt=0)
   ```

2. **API Responses**
   ```python
   class APIResponse(BaseModel, Generic[T]):
       success: bool
       data: Optional[T] = None
       error: Optional[str] = None
   ```

3. **Event Data**
   ```python
   class EventData(BaseModel):
       event_type: str
       timestamp: datetime
       payload: BaseModel  # Specific payload model
   ```

### Tools and Automation

- **ciris_mypy_toolkit** - Run compliance analysis
- **mypy** - Static type checking
- **pydantic** - Runtime validation
- **FastAPI** - Automatic API documentation

### Security Benefits

Type safety provides security benefits:
- Prevents injection attacks through validation
- Ensures data integrity
- Makes code behavior predictable
- Reduces attack surface

Remember: Every `Dict[str, Any]` is a potential bug. Replace them with proper types!