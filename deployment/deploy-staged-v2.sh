#!/bin/bash
# Enhanced staged deployment with force-stop capability
# Handles unresponsive containers gracefully

set -e

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-deployment/docker-compose.dev-prod.yml}"
AGENT_CONTAINER="ciris-agent-datum"
AGENT_SERVICE="agent-datum"
GUI_CONTAINER="ciris-gui"
GUI_SERVICE="ciris-gui"
NGINX_CONTAINER="ciris-nginx"
NGINX_SERVICE="nginx"
MAX_GRACEFUL_WAIT=300  # 5 minutes for graceful shutdown
FORCE_STOP_TIMEOUT=30  # 30 seconds for force stop

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2; }

# Helper functions
is_running() {
    docker ps --format "{{.Names}}" | grep -q "^$1$"
}

get_exit_code() {
    docker inspect "$1" --format='{{.State.ExitCode}}' 2>/dev/null || echo "-1"
}

get_image_id() {
    docker images --format "{{.ID}}" "$1" 2>/dev/null | head -1
}

check_api_health() {
    curl -sf http://localhost:8080/v1/system/health >/dev/null 2>&1
}

# Main deployment logic
log "Starting staged deployment..."

# Step 1: Pull latest images
log "Pulling latest images..."
docker-compose -f "$DOCKER_COMPOSE_FILE" pull || warn "Failed to pull some images"

# Step 2: Update GUI and Nginx (these can be updated immediately)
log "Updating GUI and Nginx containers..."

# Update GUI
if is_running "$GUI_CONTAINER"; then
    log "Recreating GUI container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$GUI_SERVICE"
else
    log "Starting GUI container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$GUI_SERVICE"
fi

# Update Nginx
if is_running "$NGINX_CONTAINER"; then
    log "Recreating Nginx container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$NGINX_SERVICE"
else
    log "Starting Nginx container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$NGINX_SERVICE"
fi

# Step 3: Check if agent needs update
OLD_AGENT_IMAGE=$(docker inspect "$AGENT_CONTAINER" --format='{{.Image}}' 2>/dev/null || echo "none")
NEW_AGENT_IMAGE=$(get_image_id "ciris-agent:latest")

if [ "$OLD_AGENT_IMAGE" = "$NEW_AGENT_IMAGE" ] || [ "$OLD_AGENT_IMAGE" = "none" ]; then
    log "Agent is already up to date or not running"
    
    # If not running, start it
    if ! is_running "$AGENT_CONTAINER"; then
        log "Starting agent container..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$AGENT_SERVICE"
    fi
    
    log "Deployment complete - no agent update needed"
    exit 0
fi

# Step 4: Create staged container
log "Creating staged agent container..."

# Remove any existing staged container
docker rm -f "${AGENT_CONTAINER}-staged" 2>/dev/null || true

# Stop the current container to get its exact configuration
docker stop "$AGENT_CONTAINER" 2>/dev/null || true

# Create new container with same config but don't start it
log "Creating staged container..."
docker-compose -f "$DOCKER_COMPOSE_FILE" create --no-start "$AGENT_SERVICE"

# The new container will have a temporary name, find it and rename
NEW_CONTAINER=$(docker ps -aq --filter "label=com.docker.compose.service=$AGENT_SERVICE" --filter "status=created" | head -1)
if [ -z "$NEW_CONTAINER" ]; then
    error "Failed to create staged container"
    docker start "$AGENT_CONTAINER"
    exit 1
fi

# Rename to staged
docker rename "$NEW_CONTAINER" "${AGENT_CONTAINER}-staged"
log "Staged container created successfully"

# Start the old container again
docker start "$AGENT_CONTAINER"

# Step 5: Attempt graceful shutdown
log "Attempting graceful shutdown..."

# Check if API is responsive
if check_api_health; then
    # Try graceful shutdown
    if [ -f "deployment/graceful-shutdown.py" ]; then
        log "Triggering graceful shutdown..."
        python3 deployment/graceful-shutdown.py \
            --agent-url "http://localhost:8080" \
            --message "Updated container staged for deployment! Please shutdown to upgrade." || {
            warn "Graceful shutdown request failed"
        }
    fi
else
    warn "API is not responsive, will use force stop"
fi

# Step 6: Wait for shutdown with timeout
log "Waiting for container to stop (max ${MAX_GRACEFUL_WAIT}s)..."
ELAPSED=0

while [ $ELAPSED -lt $MAX_GRACEFUL_WAIT ]; do
    if ! is_running "$AGENT_CONTAINER"; then
        EXIT_CODE=$(get_exit_code "$AGENT_CONTAINER")
        
        if [ "$EXIT_CODE" = "0" ]; then
            log "Agent exited gracefully (exit code 0)"
            break
        else
            warn "Agent exited with code $EXIT_CODE"
            break
        fi
    fi
    
    # Show progress
    if [ $((ELAPSED % 60)) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
        log "Still waiting... (${ELAPSED}s elapsed)"
    fi
    
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

# Step 7: Force stop if still running
if is_running "$AGENT_CONTAINER"; then
    warn "Container did not stop gracefully, using force stop..."
    docker stop -t $FORCE_STOP_TIMEOUT "$AGENT_CONTAINER" || docker kill "$AGENT_CONTAINER"
    
    # Wait for it to actually stop
    sleep 2
    
    # Set exit code to non-zero to indicate forced stop
    EXIT_CODE=137
else
    EXIT_CODE=$(get_exit_code "$AGENT_CONTAINER")
fi

# Step 8: Deploy based on exit code
if [ "$EXIT_CODE" = "0" ] || [ "$EXIT_CODE" = "137" ]; then
    # Deploy new version (0 = graceful, 137 = forced stop)
    log "Deploying new version..."
    
    # Remove old container
    docker rm "$AGENT_CONTAINER" 2>/dev/null || true
    
    # Rename and start staged container
    docker rename "${AGENT_CONTAINER}-staged" "$AGENT_CONTAINER"
    docker start "$AGENT_CONTAINER"
    
    if [ "$EXIT_CODE" = "137" ]; then
        warn "Deployment completed (container was force-stopped)"
    else
        log "Deployment completed successfully!"
    fi
else
    # Rollback - remove staged and keep current
    error "Agent exited with error code $EXIT_CODE. Keeping current version."
    docker rm "${AGENT_CONTAINER}-staged" 2>/dev/null || true
    
    # Restart the current container
    docker start "$AGENT_CONTAINER" 2>/dev/null || true
    
    exit 1
fi

# Step 9: Verify deployment
log "Verifying deployment..."
sleep 10

if check_api_health; then
    log "✓ API is healthy"
else
    warn "API health check failed - container may still be starting"
fi

# Show final status
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "ciris|NAMES" || true

log "Staged deployment complete!"