# CIRIS Deployment Guide

This guide covers deployment options for CIRIS, from local development to production.

## Quick Links
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Architecture Overview](#architecture-overview)
- [Troubleshooting](#troubleshooting)

## Local Development

### Prerequisites
- Docker and docker-compose installed
- Python 3.11+
- Node.js 18+
- Ports available: 80, 3000, 8080

### Quick Start (2 Steps)

```bash
# 1. Start CIRIS Agent with API adapter
docker-compose -f docker-compose-api-mock.yml up -d

# 2. Start GUI (optional)
cd CIRISGUI/apps/agui && npm run dev
```

Access at:
- GUI: http://localhost:3000
- Agent API: http://localhost:8080/docs
- Health check: http://localhost:8080/v1/system/health

### Running with Discord

```bash
# Create .env.datum file with Discord token
echo "DISCORD_TOKEN=your-bot-token" > .env.datum

# Start with Discord adapter
docker-compose -f docker-compose-api-discord-mock.yml up -d
```

## Production Deployment

### Current Setup (agents.ciris.ai)

Production uses:
- Single Datum agent with Mock LLM
- nginx for routing
- Google OAuth for authentication
- Automated deployment via GitHub Actions

### Deployment Flow

1. **Code Changes**
   - Create PR to CIRISAI/CIRISAgent
   - Merge to main branch
   - GitHub Actions automatically:
     - Runs tests
     - Builds Docker images
     - Deploys to production
     - Uses staged deployment for zero downtime

2. **Manual Deployment** (if needed)
   ```bash
   ssh -i ~/.ssh/ciris_deploy root@108.61.119.117
   cd /home/ciris/CIRISAgent
   git pull
   docker-compose -f deployment/docker-compose.dev-prod.yml up -d
   ```

### Environment Variables

Required for production:
```bash
# For API access
CIRIS_API_HOST=0.0.0.0  # Required for external access
CIRIS_API_PORT=8080

# For Discord (optional)
DISCORD_TOKEN=your-token

# For Google OAuth (optional)
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=yyy
```

## Architecture Overview

```
[Browser] → [nginx:80/443] → ├─ [GUI:3000]
                             └─ [Agent API:8080]
```

### Components

1. **CIRIS Agent** - The main AI agent
   - API adapter for web access
   - Discord adapter for chat (optional)
   - Mock LLM for offline operation
   - Health monitoring

2. **nginx** - Reverse proxy
   - Routes to GUI and Agent
   - SSL termination (production)
   - Static configuration

3. **GUI** - Web interface
   - Agent interaction
   - System status
   - Static agent configuration

## Configuration

### Docker Networks

- `ciris-network` - Used by most compose files
- Created automatically by docker-compose

### Critical Settings

- **CIRIS_ADAPTER=api** - Required for HTTP API
- **CIRIS_API_HOST=0.0.0.0** - Required for external access
- **Mock LLM** - Enabled by default for offline operation

## Troubleshooting

### Common Issues

**Agent not accessible externally**
- Ensure `CIRIS_API_HOST=0.0.0.0` is set
- Check firewall allows port 8080
- Verify with: `curl http://localhost:8080/v1/system/health`

**Container exits immediately**
- Check logs: `docker logs ciris-agent-datum`
- Look at incidents: `docker exec ciris-agent-datum tail /app/logs/incidents_latest.log`
- Ensure required environment variables are set

**nginx routing issues**
- Check config: `docker exec ciris-nginx cat /etc/nginx/nginx.conf`
- Reload: `docker exec ciris-nginx nginx -s reload`
- Verify network: `docker network ls | grep ciris`

### Logs

- Agent: `docker logs ciris-agent-datum`
- Incidents: `docker exec ciris-agent-datum tail -f /app/logs/incidents_latest.log`
- nginx: `docker logs ciris-nginx`
- GUI: Browser console

### Health Checks

```bash
# Check agent health
curl http://localhost:8080/v1/system/health

# Check all services
./deployment/production-troubleshoot.sh
```

## Graceful Shutdown

For zero-downtime deployments:
```bash
./deployment/graceful-shutdown.py
# or with custom message
./deployment/graceful-shutdown.py --message "Maintenance update"
```

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Architecture Pattern](ARCHITECTURE_PATTERN.md)
- [Agent Configuration](AGENT_CONFIGURATION.md)
- [Security Documentation](SECURITY_AGENT_IDS.md)