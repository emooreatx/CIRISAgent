# CIRIS Deployment Guide

This guide covers deployment of CIRIS agents using the clean CD orchestration model.

## Quick Links
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Architecture](#architecture)

## Local Development

### Quick Start

```bash
# 1. Start CIRIS Agent with Mock LLM
docker-compose -f deployment/docker-compose-api-mock.yml up -d

# 2. Start GUI (optional)
cd CIRISGUI/apps/agui && npm run dev
```

Access at:
- GUI: http://localhost:3000
- Agent API: http://localhost:8080/docs
- Health: http://localhost:8080/v1/system/health

### With Discord

```bash
# Add Discord token to .env.datum
echo "DISCORD_TOKEN=your-bot-token" > .env.datum

# Start with Discord adapter
docker-compose -f deployment/docker-compose-api-discord-mock.yml up -d
```

## Production Deployment

### Clean CD Model

CIRIS uses a clean, agent-respecting deployment model:

1. **GitHub Actions builds and notifies** - One API call to CIRISManager
2. **CIRISManager orchestrates** - Handles canary deployment, respects agent autonomy
3. **Agents decide** - Each agent can accept, defer, or reject updates
4. **Docker handles the swap** - `restart: unless-stopped` enables clean container replacement

### Deployment Flow

```yaml
# What happens on merge to main:
1. Tests run in Docker
2. Images built and pushed to ghcr.io
3. CD notifies CIRISManager with rich context:
   - Changelog (commit message)
   - Risk level (auto-assessed)
   - Version (short SHA)
   - Peer results
4. CIRISManager orchestrates based on strategy
5. Agents make informed decisions
```

### Agent Update Protocol

When notified of an update, agents receive:
```json
{
  "version": "abc123f",
  "changelog": "Fix memory leak in telemetry service",
  "risk_level": "low",
  "peer_results": "3/3 explorers updated successfully"
}
```

Agents can respond:
- **TASK_COMPLETE**: Accept update now (graceful exit → Docker restart)
- **DEFER**: Reschedule for later (e.g., "ask again at 3am")
- **REJECT**: Decline the update

### Manual Deployment

If needed, trigger manually:
```bash
# From CIRISManager
curl -X POST https://agents.ciris.ai/manager/v1/updates/notify \
  -H "Authorization: Bearer $DEPLOY_TOKEN" \
  -d '{
    "agent_image": "ghcr.io/cirisai/ciris-agent:latest",
    "strategy": "immediate",
    "changelog": "Emergency security fix",
    "risk_level": "high"
  }'
```

## Architecture

### Deployment Components

```
[GitHub Actions] --notify--> [CIRISManager] --orchestrate--> [Agents]
                                    |
                                    └── Tracks deployment status
                                    └── Respects agent decisions
                                    └── Manages canary rollout
```

### Container Management

- **Restart Policy**: Always `restart: unless-stopped`
- **No Staged Containers**: Docker handles the swap automatically
- **Graceful Shutdown**: Agents process shutdown as a cognitive task
- **Clean Exit**: Exit code 0 triggers container replacement

### Multi-Agent Deployment

CIRISManager handles different deployment strategies:
- **Canary**: 10% explorers → 20% early adopters → 70% general population
- **Immediate**: All agents at once (for emergencies)
- **Manual**: Agents update on their own schedule

## Configuration

### Required Environment Variables

```bash
# API Adapter
CIRIS_API_HOST=0.0.0.0    # Bind to all interfaces
CIRIS_API_PORT=8080       # API port

# Deployment Token
DEPLOY_TOKEN=<secure-token>  # For CD authentication

# Mock LLM (development)
CIRIS_MOCK_LLM=true       # Enable mock LLM
```

### CIRISManager Setup

CIRISManager runs separately and handles:
- Nginx routing configuration
- Agent discovery and registration
- Deployment orchestration
- OAuth shared configuration

## Monitoring

### Check Deployment Status

```bash
# View current deployment
curl https://agents.ciris.ai/manager/v1/updates/status \
  -H "Authorization: Bearer $DEPLOY_TOKEN"

# Check agent health
curl http://localhost:8080/v1/system/health

# View incidents (always check first!)
docker exec ciris-agent-datum tail -n 100 /app/logs/incidents_latest.log
```

### Graceful Shutdown

For manual updates or maintenance:
```bash
# Standard graceful shutdown
./deployment/graceful-shutdown.py

# With custom message
./deployment/graceful-shutdown.py --message "Scheduled maintenance"
```

## Key Principles

1. **Agent Autonomy**: Agents decide when to update based on their state and users
2. **Informed Consent**: Rich context (changelog, risk, peer results) enables good decisions
3. **Clean Orchestration**: One API call triggers everything - no SSH scripts or manual steps
4. **Forward Only**: No backwards compatibility, no legacy support

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Graceful Shutdown FSD](../FSD/GRACEFUL_SHUTDOWN.md)
- [CIRISManager Documentation](https://github.com/CIRISAI/CIRISManager)
