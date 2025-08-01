# CIRIS Deployment

This directory contains deployment configurations for CIRIS agents.

## Clean CD Model

CIRIS uses a clean deployment model that respects agent autonomy:

1. **GitHub Actions** builds images and notifies CIRISManager
2. **CIRISManager** orchestrates deployment based on strategy (canary/immediate)
3. **Agents** receive update notifications with context and decide: accept/defer/reject
4. **Docker** handles container swaps with `restart: unless-stopped`

## Docker Compose Files

### Development
- `docker-compose-api-mock.yml` - API with Mock LLM
- `docker-compose-api-discord-mock.yml` - API + Discord with Mock LLM

### Production
- `docker-compose.dev-prod.yml` - Single agent using pre-built images
- `docker-compose.multi-agent.yml` - Multi-agent deployment

## Key Configuration

All containers use:
- `restart: unless-stopped` - Enables clean container swaps
- Network: `ciris-network` - Shared network for all services
- Volumes: Persistent data/logs/audit trails

## Environment Variables

```bash
# Required for API
CIRIS_API_HOST=0.0.0.0
CIRIS_API_PORT=8080

# For Mock LLM
CIRIS_MOCK_LLM=true

# For Discord (optional)
DISCORD_BOT_TOKEN=your-token
```

## Scripts

- `graceful-shutdown.py` - Request agent shutdown (respects agent decision)
- `create-ciris-user.sh` - Create system user for running services

## No Legacy

This deployment follows the "forward only" principle:
- No staged containers
- No complex deployment scripts  
- No backwards compatibility
- Just clean, simple, agent-respecting deployment