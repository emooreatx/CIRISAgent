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

# Check docker-compose version and warn if old
DOCKER_COMPOSE_VERSION=$(docker-compose version 2>/dev/null | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" | head -1 || echo "unknown")
if [[ "$DOCKER_COMPOSE_VERSION" =~ ^v1\. ]]; then
    warn "Detected old docker-compose version: $DOCKER_COMPOSE_VERSION"
    warn "Some operations may fail. The CD pipeline should update this."
fi

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
    
    # Try docker-compose, but handle potential failures
    if ! docker-compose -f "$DOCKER_COMPOSE_FILE" up -d 2>&1 | tee /tmp/compose.log; then
        if grep -q "ContainerConfig" /tmp/compose.log; then
            warn "docker-compose failed due to version incompatibility. Using fallback deployment..."
            
            # Start agent container
            docker run -d --name "$AGENT_CONTAINER" \
                --network deployment_ciris-network \
                -p 127.0.0.1:8080:8080 \
                -e CIRIS_AGENT_NAME=Datum \
                -e CIRIS_AGENT_ID=agent-datum \
                -e CIRIS_PORT=8080 \
                -e CIRIS_ADAPTER=api \
                -e CIRIS_ADAPTER_DISCORD=discord \
                -e CIRIS_MOCK_LLM=true \
                -e CIRIS_API_HOST=0.0.0.0 \
                -e CIRIS_API_PORT=8080 \
                -v deployment_datum_data:/app/data \
                -v deployment_datum_logs:/app/logs \
                -v /home/ciris/CIRISAgent/.env.datum:/app/.env:ro \
                -v /home/ciris/shared/oauth:/home/ciris/.ciris:ro \
                --restart unless-stopped \
                ciris-agent:latest python main.py --adapter api --adapter discord --mock-llm
            
            # Start GUI container
            docker run -d --name "$GUI_CONTAINER" \
                --network deployment_ciris-network \
                -p 127.0.0.1:3000:3000 \
                -e NODE_ENV=production \
                -e NEXT_PUBLIC_CIRIS_API_URL=https://agents.ciris.ai \
                --restart unless-stopped \
                ciris-gui:latest
            
            # Start Nginx container
            docker run -d --name "$NGINX_CONTAINER" \
                --network host \
                -v /etc/letsencrypt:/etc/letsencrypt:ro \
                -v /home/ciris/CIRISAgent/deployment/nginx/logs:/var/log/nginx \
                --restart unless-stopped \
                ciris-nginx:latest
        fi
    fi
    rm -f /tmp/compose.log
    
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
    # Try docker-compose first, fall back to docker run if it fails
    if ! docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$GUI_SERVICE" 2>/dev/null; then
        warn "docker-compose failed, using docker run for GUI..."
        docker stop "$GUI_CONTAINER" || true
        docker rm "$GUI_CONTAINER" || true
        docker run -d --name "$GUI_CONTAINER" \
            --network deployment_ciris-network \
            -p 127.0.0.1:3000:3000 \
            -e NODE_ENV=production \
            -e NEXT_PUBLIC_CIRIS_API_URL=https://agents.ciris.ai \
            --restart unless-stopped \
            ciris-gui:latest
    fi
else
    log "Starting GUI container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$GUI_SERVICE"
fi

# Update Nginx
if is_running "$NGINX_CONTAINER"; then
    log "Recreating Nginx container..."
    # Try docker-compose first, fall back to docker run if it fails
    if ! docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$NGINX_SERVICE" 2>/dev/null; then
        warn "docker-compose failed, using docker run for Nginx..."
        docker stop "$NGINX_CONTAINER" || true
        docker rm "$NGINX_CONTAINER" || true
        docker run -d --name "$NGINX_CONTAINER" \
            --network host \
            -v /etc/letsencrypt:/etc/letsencrypt:ro \
            -v /home/ciris/CIRISAgent/deployment/nginx/logs:/var/log/nginx \
            --restart unless-stopped \
            ciris-nginx:latest
    fi
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
    
    # Use docker-compose to create the new container but not start it
    # First, we need to stop the service without removing the container
    docker stop "$AGENT_CONTAINER" 2>/dev/null || true
    
    # Create new container using docker-compose (which preserves all settings)
    # Note: docker-compose v2.20.0 doesn't support --no-start flag
    # We'll use run with --no-deps and --detach, then immediately stop it
    log "Creating staged container..."
    
    # First, remove any existing staged container
    docker rm -f "${AGENT_CONTAINER}-staged" 2>/dev/null || true
    
    # Create and immediately stop the new container
    # Use run with --name to control the container name
    if docker-compose -f "$DOCKER_COMPOSE_FILE" run -d --no-deps --name "${AGENT_CONTAINER}-staged" "$AGENT_SERVICE"; then
        # Immediately stop the staged container
        docker stop "${AGENT_CONTAINER}-staged" 2>/dev/null || true
        log "Staged container created successfully"
    else
        error "Failed to create staged container"
        # Restart the old container
        docker start "$AGENT_CONTAINER"
        exit 1
    fi
    
    # Start the old container again
    docker start "$AGENT_CONTAINER"
    
    log "Staged container created. Monitoring current agent for graceful exit..."
    
    # Step 4.5: Trigger graceful shutdown if graceful-shutdown.py exists
    if [ -f "deployment/graceful-shutdown.py" ]; then
        log "Triggering graceful shutdown..."
        # Use localhost since we're on the same server
        python3 deployment/graceful-shutdown.py \
            --agent-url "http://localhost:8080" \
            --message "Updated container staged for deployment! Shutdown to upgrade immediately, defer if needed." || {
            warn "Failed to trigger graceful shutdown. Agent must be shut down manually."
        }
    else
        warn "Graceful shutdown script not found. Agent must be shut down manually."
    fi
    
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