# Deployment Migration Guide

## Overview

This guide documents the migration from complex staged deployments to a clean, direct approach using Docker Compose.

## Current Deployment Strategy

### Simple and Direct
- Use `docker-compose up -d` for all deployments
- Agents handle their own lifecycle gracefully
- No staging containers or complex orchestration
- Restart policy: `unless-stopped` for production stability

## Key Principles

1. **Simplicity**: Direct container management with Docker Compose
2. **Agent Autonomy**: Agents manage their own shutdown/restart cycles
3. **Zero Downtime**: Graceful shutdown ensures clean handoffs
4. **No Manual Intervention**: Automatic restart on clean exit

## Deployment Process

### 1. Update Images
```bash
# Pull latest images
docker-compose -f deployment/docker-compose.dev-prod.yml pull
```

### 2. Graceful Shutdown (Optional)
```bash
# Request graceful shutdown
./deployment/graceful-shutdown.py --message "Updating to new version"
```

### 3. Deploy
```bash
# Start/update containers
docker-compose -f deployment/docker-compose.dev-prod.yml up -d
```

## Container Restart Policies

- **unless-stopped**: Production agents (keeps running unless explicitly stopped)
- **on-failure**: Development/testing (restarts only on crashes)

## Migration from Old Approaches

### Removed Components
- Staged deployment scripts
- Complex container renaming logic
- Manager-based orchestration
- Dynamic agent discovery

### New Approach
- Static agent configuration
- Direct Docker Compose management
- Agent-controlled lifecycles
- Simplified deployment scripts

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs ciris-agent-datum

# Check status
docker ps -a | grep ciris
```

### Clean Restart
```bash
# Stop everything
docker-compose -f deployment/docker-compose.dev-prod.yml down

# Start fresh
docker-compose -f deployment/docker-compose.dev-prod.yml up -d
```

## Best Practices

1. Always use docker-compose files (never raw docker commands)
2. Let agents shutdown gracefully (don't force stop)
3. Monitor logs during deployment
4. Keep deployment scripts simple and readable