# CIRIS Agent Auto-Healing Setup

## Overview

The CIRIS Agent now includes enhanced health checking that monitors the processor thread. If the processor thread dies, the health check will report the container as unhealthy, allowing Docker to automatically restart it.

## Health Check Implementation

The health check endpoint (`/v1/system/health`) now verifies:
1. All services are healthy
2. The processor thread is alive and responding
3. The runtime control service can access the processor queue

If the processor thread dies, the health status becomes "critical".

## Running with Auto-Healing

### Option 1: Using Docker Autoheal (Recommended)

```bash
docker-compose -f docker-compose-api-discord-mock-autoheal.yml up -d
```

This starts:
- The CIRIS Agent container with health checks
- The autoheal container that monitors and restarts unhealthy containers

### Option 2: Manual Monitoring

```bash
docker-compose -f docker-compose-api-discord-mock.yml up -d
```

The container will have health checks but won't automatically restart when unhealthy.

## Health Check Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/v1/system/health"]
  interval: 30s      # Check every 30 seconds
  timeout: 10s       # Timeout after 10 seconds
  retries: 3         # Mark unhealthy after 3 failed checks
  start_period: 40s  # Wait 40s before first check
```

## Monitoring Health Status

Check container health:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Check detailed health status:
```bash
curl http://localhost:8080/v1/system/health | jq .
```

## Troubleshooting

If the container keeps restarting:
1. Check the incidents log: `docker exec <container> tail /app/logs/incidents_latest.log`
2. Check container logs: `docker logs <container> --tail 100`
3. Verify the processor is starting correctly during initialization

## Technical Details

The health check verifies processor health by:
1. Calling `runtime_control_service.get_processor_queue_status()`
2. Checking if the processor name is not "unknown"
3. Verifying `runtime_status.is_running` is true

If any of these checks fail, the container is marked as unhealthy.