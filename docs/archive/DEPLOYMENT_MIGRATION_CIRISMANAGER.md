# Deployment Migration Guide: From Staged to Clean

## Overview

We've migrated from a complex staged deployment process to a clean, simple approach that leverages Docker and CIRIS Manager's natural behavior.

## What Changed

### Old Approach (Staged Deployment)
- Used `docker-compose create --no-start` to create staged containers
- Complex renaming and orchestration logic
- Risk of containers getting stuck in staging
- Required manual intervention if agent didn't consent

### New Approach (Clean Deployment)
- Simple `docker-compose pull` to get latest images
- Graceful shutdown notification to running agents
- Agents exit with code 0 when ready
- CIRIS Manager or `docker-compose up -d` starts them with new image
- Uses `restart: unless-stopped` policy

## Key Benefits

1. **Simplicity**: No staging, no renaming, no complex state management
2. **Reliability**: Leverages Docker's built-in restart policies
3. **Safety**: Running containers are never forcefully stopped
4. **Automation**: CIRIS Manager handles restarts automatically

## Migration Steps

### 1. Update Docker Compose Files

Change restart policy from `on-failure` to `unless-stopped`:

```yaml
services:
  agent-datum:
    restart: unless-stopped  # Changed from on-failure
```

### 2. Remove Old Scripts

The following scripts are no longer needed:
- `deployment/deploy-staged.sh`
- `deployment/deploy-staged-v2.sh`
- `deployment/consent-based-deploy.sh`
- `deployment/negotiate-deployment.sh`

### 3. Use New Deployment Script

```bash
# Simple deployment
./deployment/deploy-clean.sh

# Or just use docker-compose directly
docker-compose pull
docker-compose up -d
```

### 4. Enable CIRIS Manager (Optional but Recommended)

CIRIS Manager will automatically:
- Run `docker-compose up -d` every 60 seconds
- Start stopped containers with latest images
- Monitor for crash loops
- Provide agent discovery API

```bash
# Start CIRIS Manager
systemctl start ciris-manager
systemctl enable ciris-manager
```

## How It Works

1. **Pull Latest Images**: `docker-compose pull`
2. **Notify Agents**: Send graceful shutdown request
3. **Wait for Exit**: Agents exit with code 0 when ready
4. **Automatic Restart**:
   - With CIRIS Manager: Happens within 60s automatically
   - Without: Run `docker-compose up -d`

## Important Notes

- **Exit Code 0**: Agents must exit with code 0 for `unless-stopped` to work
- **No Force Stops**: Never use `docker stop -f` or `docker-compose down`
- **Patience**: Give agents time to shutdown gracefully

## Troubleshooting

### Container Won't Restart
- Check exit code: `docker ps -a`
- Exit 0 = Won't auto-restart (correct for updates)
- Non-zero = Will auto-restart (for crashes)

### Stuck in Old State
- Remove any `-staged` containers: `docker rm ciris-agent-*-staged`
- Run `docker-compose up -d` to restore normal state

### CIRIS Manager Not Starting Containers
- Check if running: `systemctl status ciris-manager`
- Check logs: `journalctl -u ciris-manager -f`
- Manual fix: `docker-compose up -d`
