# CIRISManager Deployment Guide

## Overview

CIRISManager is a lightweight systemd service that manages CIRIS agent containers by:
- Running `docker-compose up -d` every 60 seconds to ensure stopped containers restart with latest images
- Detecting and preventing crash loops (3 crashes in 5 minutes)
- Providing agent discovery API for the GUI (future)
- Enabling graceful, zero-downtime deployments

## How It Works

The key insight: Docker's `restart: unless-stopped` policy + periodic `docker-compose up -d` = natural update mechanism

1. **Container exits** (graceful shutdown, crash, or manual stop)
2. **Docker's restart policy**:
   - Exit code 0 → Container stays stopped
   - Non-zero exit → Docker attempts restart
3. **CIRISManager runs `docker-compose up -d` every 60 seconds**:
   - Stopped containers start with **latest image**
   - Running containers are **unaffected**

## Installation

### Quick Install (Recommended)

```bash
# Run as root/sudo
sudo ./deployment/install-ciris-manager.sh
```

This script will:
- Check dependencies (Python 3.8+, Docker, docker-compose)
- Install the CIRISManager Python package
- Create default configuration at `/etc/ciris-manager/config.yml`
- Install and start the systemd service

### Manual Installation

```bash
# 1. Install Python package
cd /home/ciris/CIRISAgent
pip install -e . -f setup_manager.py

# 2. Create config directory
sudo mkdir -p /etc/ciris-manager

# 3. Generate configuration
ciris-manager --generate-config --config /etc/ciris-manager/config.yml

# 4. Edit configuration as needed
sudo nano /etc/ciris-manager/config.yml

# 5. Install systemd service
sudo cp deployment/ciris-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ciris-manager
sudo systemctl start ciris-manager
```

## Configuration

Default configuration at `/etc/ciris-manager/config.yml`:

```yaml
manager:
  port: 9999              # Future API port
  host: 127.0.0.1

docker:
  compose_file: /home/ciris/CIRISAgent/deployment/docker-compose.yml

watchdog:
  check_interval: 30      # Check every 30 seconds
  crash_threshold: 3      # Stop after 3 crashes
  crash_window: 300       # Within 5 minutes

container_management:
  interval: 60            # Run docker-compose up -d every 60 seconds
  pull_images: true       # Pull latest images
```

## Deployment Workflow

### With CIRISManager Running

Use the new deployment script:

```bash
./deployment/deploy-with-manager.sh
```

This script:
1. Pulls latest images
2. Updates GUI/Nginx immediately (can restart anytime)
3. Triggers graceful shutdown for agents
4. CIRISManager handles the rest automatically

### Without CIRISManager

Use the original staged deployment:

```bash
./deployment/deploy-staged.sh
```

## Monitoring

### CIRISManager Status

```bash
# Service status
sudo systemctl status ciris-manager

# Live logs
sudo journalctl -u ciris-manager -f

# Container status
docker ps
```

### What to Look For

1. **Normal Operation**:
   ```
   Container manager started with 60s interval
   Crash loop watchdog started - threshold: 3 crashes in 300s
   ```

2. **Update Detected**:
   ```
   Update available for agent-datum - notification pending
   ```

3. **Crash Loop Detected**:
   ```
   Crash loop detected for ciris-agent-datum: 3 crashes in 300s
   Stopped container ciris-agent-datum
   ALERT: Agent ciris-agent-datum stopped due to crash loop
   ```

## Troubleshooting

### CIRISManager Won't Start

Check logs:
```bash
sudo journalctl -u ciris-manager -n 50
```

Common issues:
- Docker socket permissions: Ensure user is in docker group
- Compose file not found: Check path in config
- Python dependencies: Reinstall with `pip install -e .`

### Containers Not Updating

1. Check if CIRISManager is running:
   ```bash
   sudo systemctl status ciris-manager
   ```

2. Verify graceful shutdown triggered:
   ```bash
   docker logs ciris-agent-datum | tail -20
   ```

3. Check container restart policy:
   ```bash
   docker inspect ciris-agent-datum | grep -A5 RestartPolicy
   ```
   Should show `unless-stopped`

### Crash Loops

If an agent is crash-looping:

1. Check why it's crashing:
   ```bash
   docker logs ciris-agent-datum
   ```

2. Fix the issue (config, dependencies, etc.)

3. Manually start the container:
   ```bash
   docker start ciris-agent-datum
   ```

## Best Practices

1. **Always use `restart: unless-stopped`** in docker-compose.yml
2. **Test locally first** with `docker-compose up` before deploying
3. **Monitor logs** during deployments
4. **Use graceful shutdown** to control update timing
5. **Let CIRISManager handle restarts** - don't manually restart containers

## Integration with CI/CD

The GitHub Actions workflow can trigger deployments:

1. Push to main branch
2. CI/CD builds and pushes images
3. Runs `deploy-with-manager.sh` on server
4. CIRISManager handles container lifecycle

## Security Considerations

- CIRISManager runs as root (needs Docker access)
- Config file should be readable only by root
- Future API will use local socket for agent communication
- WA signatures will be required for agent creation

## Future Enhancements

- **Phase 2**: REST API for agent discovery
- **Phase 3**: Agent creation with WA signatures
- **Phase 4**: GUI integration for dynamic agent lists
- **Phase 5**: Local auth for update notifications

## Summary

CIRISManager simplifies deployments by leveraging Docker's natural behavior. Instead of complex staging scripts, we use a simple, reliable pattern: periodic `docker-compose up -d` that respects container state and restart policies.

This approach is:
- **Simple**: One command, predictable behavior
- **Reliable**: No race conditions or complex state management
- **Flexible**: Agents control when they update
- **Safe**: Crash loop protection prevents infinite restarts