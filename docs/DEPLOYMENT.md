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
- Ports available: 80, 3000, 8080-8199, 8888

### Quick Start (3 Steps)

```bash
# 1. Start CIRISManager (no agents needed)
GOOGLE_CLIENT_ID=your-client-id GOOGLE_CLIENT_SECRET=your-secret \
  CIRIS_MANAGER_CONFIG=~/.config/ciris-manager/config.yml \
  python deployment/run-ciris-manager-api.py

# 2. Start GUI
cd CIRISGUI/apps/agui && npm run dev

# 3. Start nginx (optional, for unified routing)
docker-compose -f docker-compose-nginx.yml up -d
```

Access at:
- GUI: http://localhost:3000 (direct) or http://localhost (via nginx)
- Manager API: http://localhost:8888/manager/v1/agents
- Agent APIs: http://localhost:808X/docs (when agents are created)

### Creating Agents

Via GUI:
1. Navigate to http://localhost:3000/manager
2. Click "Create Agent"
3. Select template and configure
4. **Important**: Set `CIRIS_ADAPTER=api` or agent will exit

Via API:
```bash
curl -X POST http://localhost:8888/manager/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "template": "scout",
    "name": "My Scout",
    "environment": {"CIRIS_ADAPTER": "api"}
  }'
```

## Production Deployment

### Current Setup (agents.ciris.ai)

Production uses:
- CIRISManager as systemd service (API-only mode)
- Multiple agent containers (managed by Docker)
- nginx for routing
- Google OAuth for authentication

### Deployment Flow

1. **Code Changes**
   - Push to main branch
   - GitHub Actions builds and pushes Docker images
   - CIRISManager detects new images (checks every 60s)
   - Automatic rolling updates for agents

2. **Manager Updates**
   - SSH to server required
   - `git pull origin main`
   - `sudo systemctl restart ciris-manager-api`

### Environment Variables

Required for production:
```bash
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=yyy
CIRIS_MANAGER_CONFIG=/path/to/config.yml
```

## Architecture Overview

```
[Browser] → [nginx:80/443] → ├─ [GUI:3000] → [Manager:8888] → [Docker API]
                              ├─ [Manager:8888]              ↘
                              └─ [/api/<agent>/*] ← ← ← ← ← ← [Agents:808X]
```

### Components

1. **CIRISManager** - Agent lifecycle management
   - Discovers agents via Docker API
   - Updates nginx configuration
   - Handles OAuth authentication
   - Port allocation (8080-8199)

2. **nginx** - Reverse proxy
   - Routes to GUI, Manager, and Agents
   - SSL termination (production)
   - Health checks

3. **GUI** - Web interface
   - Agent management
   - Real-time status
   - OAuth integration

4. **Agents** - CIRIS instances
   - API adapter for web access
   - Discord adapter for chat
   - Health monitoring

## Configuration

### Manager Config (config.yml)
```yaml
manager:
  agents_directory: ~/.config/ciris-manager/agents
  manifest_path: ~/.config/ciris-manager/pre-approved-templates.json
  templates_directory: ./ciris_templates
nginx:
  config_dir: /home/ciris/nginx
  container_name: ciris-nginx
ports:
  start: 8080
  end: 8199
  reserved: [8888, 3000, 80, 443]
```

### Docker Networks

- `ciris-network` - Used by most compose files
- Created automatically by docker-compose

### Critical Settings

- **CIRIS_ADAPTER=api** - Required for agents to serve HTTP
- **OAuth** - Required for create/delete operations
- **Port Range** - 8080-8199 reserved for agents

## Troubleshooting

### Common Issues

**"Pre-approved manifest not found"**
```bash
cp pre-approved-templates.json ~/.config/ciris-manager/
```

**401 Unauthorized on agent creation**
- Ensure OAuth environment variables are set
- Check Manager logs: `tail -f /tmp/ciris-manager.log`

**Agent exits immediately**
- Set `CIRIS_ADAPTER=api` in environment
- Check logs: `docker logs ciris-<agent-id>`

**nginx routing issues**
- Verify network: `docker network ls | grep ciris`
- Check config: `cat /home/ciris/nginx/nginx.conf`
- Reload: `docker exec ciris-nginx nginx -s reload`

### Logs

- Manager: `/tmp/ciris-manager.log` or `journalctl -u ciris-manager-api`
- Agents: `docker logs ciris-<agent-id>`
- nginx: `docker logs ciris-nginx`
- GUI: Browser console

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Architecture Pattern](ARCHITECTURE_PATTERN.md)
- [Agent Configuration](AGENT_CONFIGURATION.md)
- [Security Documentation](SECURITY_AGENT_IDS.md)