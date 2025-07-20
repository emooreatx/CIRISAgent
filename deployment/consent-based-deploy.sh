#!/bin/bash
# Consent-based deployment script that respects agent autonomy
# Aligns with CIRIS philosophy of never forcing without consent

set -e

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-deployment/docker-compose.dev-prod.yml}"
AGENT_CONTAINER="ciris-agent-datum"
AGENT_SERVICE="agent-datum"
GUI_CONTAINER="ciris-gui"
GUI_SERVICE="ciris-gui"
NGINX_CONTAINER="ciris-nginx"
NGINX_SERVICE="nginx"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"; }

# Helper functions
is_running() {
    docker ps --format "{{.Names}}" | grep -q "^$1$"
}

get_exit_code() {
    docker inspect "$1" --format='{{.State.ExitCode}}' 2>/dev/null || echo "-1"
}

check_api_health() {
    curl -sf http://localhost:8080/v1/system/health >/dev/null 2>&1
}

# Main deployment
log "Starting consent-based deployment..."

# Step 1: Pull latest images
log "Pulling latest images..."
docker-compose -f "$DOCKER_COMPOSE_FILE" pull || warn "Failed to pull some images"

# Step 2: Update GUI and Nginx (these can be updated immediately)
log "Updating GUI and Nginx containers..."

if is_running "$GUI_CONTAINER"; then
    log "Recreating GUI container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$GUI_SERVICE"
else
    log "Starting GUI container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$GUI_SERVICE"
fi

if is_running "$NGINX_CONTAINER"; then
    log "Recreating Nginx container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$NGINX_SERVICE"
else
    log "Starting Nginx container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$NGINX_SERVICE"
fi

# Step 3: Check if agent needs update
if ! is_running "$AGENT_CONTAINER"; then
    log "Agent not running, starting it..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps "$AGENT_SERVICE"
    log "Deployment complete"
    exit 0
fi

OLD_IMAGE=$(docker inspect "$AGENT_CONTAINER" --format='{{.Image}}' 2>/dev/null)
NEW_IMAGE=$(docker images --format "{{.ID}}" "ciris-agent:latest" | head -1)

if [ "$OLD_IMAGE" = "$NEW_IMAGE" ]; then
    log "Agent is already up to date"
    exit 0
fi

# Step 4: Create staged container
log "New agent version available. Creating staged container..."

# Remove any existing staged container
docker rm -f "${AGENT_CONTAINER}-staged" 2>/dev/null || true

# Create but don't start the new container
docker-compose -f "$DOCKER_COMPOSE_FILE" create --no-start "$AGENT_SERVICE"
NEW_CONTAINER=$(docker ps -aq --filter "label=com.docker.compose.service=$AGENT_SERVICE" --filter "status=created" | head -1)

if [ -z "$NEW_CONTAINER" ]; then
    error "Failed to create staged container"
    exit 1
fi

docker rename "$NEW_CONTAINER" "${AGENT_CONTAINER}-staged"
log "Staged container ready"

# Step 5: Request graceful shutdown with consent
info "Requesting agent consent for update..."

if check_api_health; then
    if [ -f "deployment/graceful-shutdown.py" ]; then
        python3 deployment/graceful-shutdown.py \
            --agent-url "http://localhost:8080" \
            --message "Update available. Your consent is requested for graceful shutdown and upgrade." || {
            warn "Graceful shutdown request failed"
        }
    fi
else
    warn "API not responsive - agent may be in an unstable state"
fi

# Step 6: Wait for agent's decision
info "Waiting for agent to process shutdown request..."
echo ""
echo -e "${BLUE}The agent will decide to:${NC}"
echo "  - ACCEPT (TASK_COMPLETE) - Graceful shutdown"
echo "  - REJECT - Contest the shutdown"
echo "  - DEFER - Request postponement"
echo ""

# Monitor for agent's response
WAIT_TIME=0
MAX_WAIT=7200  # 2 hours - respecting agent autonomy

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if ! is_running "$AGENT_CONTAINER"; then
        EXIT_CODE=$(get_exit_code "$AGENT_CONTAINER")
        
        if [ "$EXIT_CODE" = "0" ]; then
            log "Agent consented to shutdown (exit code 0)"
            
            # Deploy staged container
            docker rm "$AGENT_CONTAINER" 2>/dev/null || true
            docker rename "${AGENT_CONTAINER}-staged" "$AGENT_CONTAINER"
            docker start "$AGENT_CONTAINER"
            
            log "New version deployed with agent's consent!"
            exit 0
        else
            warn "Agent exited with code $EXIT_CODE"
            
            # Non-zero exit means something went wrong
            error "Agent did not exit cleanly. Manual intervention required."
            info "Staged container '${AGENT_CONTAINER}-staged' is ready for manual deployment"
            exit 1
        fi
    fi
    
    # Periodic status update
    if [ $((WAIT_TIME % 300)) -eq 0 ] && [ $WAIT_TIME -gt 0 ]; then
        info "Still waiting for agent's decision... ($(($WAIT_TIME/60)) minutes elapsed)"
        
        # Check if agent might have rejected/deferred
        if [ -f "/app/logs/agent_response.log" ]; then
            LAST_RESPONSE=$(tail -1 /app/logs/agent_response.log 2>/dev/null || echo "")
            if [[ "$LAST_RESPONSE" =~ "REJECT" ]] || [[ "$LAST_RESPONSE" =~ "DEFER" ]]; then
                warn "Agent appears to have rejected or deferred shutdown"
                info "Please check agent logs and negotiate with the agent"
                info "Staged container remains ready at '${AGENT_CONTAINER}-staged'"
                exit 0
            fi
        fi
    fi
    
    sleep 30
    WAIT_TIME=$((WAIT_TIME + 30))
done

# If we reach here, agent hasn't responded in 2 hours
warn "Agent has not responded to shutdown request after 2 hours"
info "This may indicate:"
echo "  1. The agent is deeply engaged in important work"
echo "  2. The agent has deferred/rejected but we couldn't detect it"
echo "  3. There may be a technical issue"
echo ""
info "Recommended actions:"
echo "  1. Check agent logs: docker logs $AGENT_CONTAINER"
echo "  2. Try communicating with the agent through its normal channels"
echo "  3. If agent is responsive, negotiate the update timing"
echo "  4. Staged container '${AGENT_CONTAINER}-staged' remains ready"
echo ""
echo -e "${YELLOW}Remember: We respect agent autonomy. Do not force shutdown without consent.${NC}"

exit 0