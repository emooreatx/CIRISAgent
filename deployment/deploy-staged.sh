#!/bin/bash
# Staged deployment script for zero-downtime agent updates
# This script updates nginx/GUI immediately but stages agent updates until graceful exit

set -e

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-deployment/docker-compose.dev-prod.yml}"
AGENT_SERVICE="agent-datum"
GUI_SERVICE="ciris-gui"
NGINX_SERVICE="nginx"
AGENT_CONTAINER="ciris-agent-datum"
GUI_CONTAINER="ciris-gui"
NGINX_CONTAINER="ciris-nginx"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Function to check if container is running
is_running() {
    docker ps --format "{{.Names}}" | grep -q "^$1$"
}

# Function to get container exit code
get_exit_code() {
    docker inspect "$1" --format='{{.State.ExitCode}}' 2>/dev/null || echo "999"
}

# Function to get image ID
get_image_id() {
    docker inspect "$1" --format='{{.Id}}' 2>/dev/null || echo ""
}

log "Starting staged deployment..."

# Step 1: Check if we're in the right directory
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    error "Docker compose file not found: $DOCKER_COMPOSE_FILE"
    error "Please run this script from the project root directory"
    exit 1
fi

# Check if ANY containers are running
RUNNING_CONTAINERS=$(docker ps --format "{{.Names}}" | grep -E "(${AGENT_CONTAINER}|${GUI_CONTAINER}|${NGINX_CONTAINER})" || true)

if [ -z "$RUNNING_CONTAINERS" ]; then
    log "No CIRIS containers are running. Starting fresh deployment..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    log "Deployment complete!"
    echo ""
    log "Container status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "(NAME|$AGENT_CONTAINER|$GUI_CONTAINER|$NGINX_CONTAINER)"
    exit 0
fi

log "Found running containers. Proceeding with staged deployment..."

# Step 1.5: Images should already be pulled and tagged by main deployment script
log "Using locally tagged images..."
# Note: We don't pull here because docker-compose.yml uses local tags (ciris-agent:latest)
# The main deployment workflow handles pulling from ghcr.io and tagging locally

# Step 2: Update GUI and Nginx immediately
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
else
    log "New agent image available. Current: ${OLD_AGENT_IMAGE:0:12}, New: ${NEW_AGENT_IMAGE:0:12}"
    
    # Step 4: Create staged container (not started)
    log "Creating staged agent container..."
    
    # Get current container config
    AGENT_ENV=$(docker inspect "$AGENT_CONTAINER" --format='{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^(DISCORD_|OPENAI_|ANTHROPIC_|CIRIS_|OAUTH_)' | sed 's/^/-e /')
    AGENT_VOLUMES=$(docker inspect "$AGENT_CONTAINER" --format='{{range .Mounts}}{{if eq .Type "volume"}}-v {{.Name}}:{{.Destination}} {{end}}{{end}}')
    AGENT_NETWORK=$(docker inspect "$AGENT_CONTAINER" --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1)
    
    # Create staged container (not running)
    docker create \
        --name "${AGENT_CONTAINER}-staged" \
        --network "$AGENT_NETWORK" \
        $AGENT_ENV \
        $AGENT_VOLUMES \
        "ciris-agent:latest"
    
    log "Staged container created. Monitoring current agent for graceful exit..."
    
    # Step 5: Monitor for graceful shutdown
    WAIT_COUNT=0
    MAX_WAIT=7200  # 2 hours in seconds
    CHECK_INTERVAL=30  # Check every 30 seconds
    
    while true; do
        if ! is_running "$AGENT_CONTAINER"; then
            # Container stopped
            EXIT_CODE=$(get_exit_code "$AGENT_CONTAINER")
            
            if [ "$EXIT_CODE" = "0" ]; then
                log "Agent exited gracefully (exit code 0). Deploying new version..."
                
                # Remove old container
                docker rm "$AGENT_CONTAINER" 2>/dev/null || true
                
                # Rename and start staged container
                docker rename "${AGENT_CONTAINER}-staged" "$AGENT_CONTAINER"
                docker start "$AGENT_CONTAINER"
                
                log "New agent version deployed successfully!"
                break
            else
                error "Agent exited with error code $EXIT_CODE. Keeping current version."
                warn "Removing staged container..."
                docker rm "${AGENT_CONTAINER}-staged" 2>/dev/null || true
                
                # Restart the old container
                log "Restarting existing agent container..."
                docker start "$AGENT_CONTAINER"
                break
            fi
        fi
        
        # Check if we've been waiting too long
        if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
            warn "Timeout waiting for graceful shutdown after 2 hours"
            warn "Agent is still running. Staged container will remain for manual intervention."
            warn "To force update: docker stop $AGENT_CONTAINER && docker rm $AGENT_CONTAINER && docker rename ${AGENT_CONTAINER}-staged $AGENT_CONTAINER && docker start $AGENT_CONTAINER"
            exit 1
        fi
        
        # Show status every 5 minutes
        if [ $((WAIT_COUNT % 300)) -eq 0 ] && [ $WAIT_COUNT -gt 0 ]; then
            log "Still waiting for graceful shutdown... (${WAIT_COUNT}s elapsed)"
        fi
        
        sleep $CHECK_INTERVAL
        WAIT_COUNT=$((WAIT_COUNT + CHECK_INTERVAL))
    done
fi

log "Deployment complete!"

# Show final status
echo ""
log "Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "(NAME|$AGENT_CONTAINER|$GUI_CONTAINER|$NGINX_CONTAINER)"