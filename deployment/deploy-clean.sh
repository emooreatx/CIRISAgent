#!/bin/bash
# CIRIS Clean Deployment Script
# Simple deployment with graceful shutdown

set -e

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-deployment/docker-compose.dev-prod.yml}"
GRACEFUL_SHUTDOWN_TIMEOUT="${GRACEFUL_SHUTDOWN_TIMEOUT:-300}"  # 5 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Main deployment process
main() {
    log "Starting CIRIS clean deployment process..."
    
    # Step 1: Pull latest images
    log "Pulling latest Docker images..."
    if ! docker-compose -f "$DOCKER_COMPOSE_FILE" pull; then
        error "Failed to pull Docker images"
        exit 1
    fi
    
    # Step 2: Find all running CIRIS agents
    log "Finding running CIRIS agents..."
    RUNNING_AGENTS=$(docker ps --format "{{.Names}}" | grep -E "^ciris-agent-" || true)
    
    if [ -z "$RUNNING_AGENTS" ]; then
        log "No running agents found. Starting fresh..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
        log "Deployment complete!"
        exit 0
    fi
    
    # Step 3: Notify agents about pending update
    log "Notifying agents about pending update..."
    for agent in $RUNNING_AGENTS; do
        log "Notifying $agent..."
        
        # Check if agent is healthy first
        if docker exec "$agent" curl -s http://localhost:8080/v1/system/health > /dev/null 2>&1; then
            # Try to use the graceful shutdown script if available
            if docker exec "$agent" test -f /app/deployment/graceful-shutdown.py 2>/dev/null; then
                docker exec "$agent" python /app/deployment/graceful-shutdown.py \
                    --message "Deployment update - please shutdown gracefully" \
                    2>/dev/null || warn "Could not notify $agent (may not support graceful shutdown)"
            else
                # Fallback: Try to login and send shutdown signal with auth
                TOKEN=$(docker exec "$agent" curl -s -X POST \
                    http://localhost:8080/v1/auth/login \
                    -H "Content-Type: application/json" \
                    -d '{"username":"admin","password":"ciris_admin_password"}' \
                    2>/dev/null | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
                
                if [ -n "$TOKEN" ]; then
                    docker exec "$agent" curl -X POST \
                        http://localhost:8080/v1/system/shutdown \
                        -H "Authorization: Bearer $TOKEN" \
                        -H "Content-Type: application/json" \
                        -d '{"reason": "Deployment update - please shutdown gracefully", "confirm": true}' \
                        2>/dev/null || warn "Could not notify $agent (may not support graceful shutdown)"
                else
                    warn "Could not authenticate with $agent for graceful shutdown"
                fi
            fi
        else
            warn "$agent is not healthy, will be restarted"
        fi
    done
    
    # Step 4: Wait for agents to shutdown gracefully
    log "Waiting up to ${GRACEFUL_SHUTDOWN_TIMEOUT}s for agents to shutdown gracefully..."
    
    WAIT_START=$(date +%s)
    while [ -n "$(docker ps --format '{{.Names}}' | grep -E '^ciris-agent-' || true)" ]; do
        ELAPSED=$(($(date +%s) - WAIT_START))
        
        if [ $ELAPSED -gt $GRACEFUL_SHUTDOWN_TIMEOUT ]; then
            warn "Timeout waiting for graceful shutdown"
            break
        fi
        
        # Show remaining agents
        REMAINING=$(docker ps --format "{{.Names}}" | grep -E "^ciris-agent-" | wc -l || echo "0")
        if [ "$REMAINING" -gt 0 ]; then
            echo -ne "\r${YELLOW}Waiting...${NC} $REMAINING agents still running (${ELAPSED}s elapsed)"
        fi
        
        sleep 2
    done
    echo # New line after progress
    
    # Step 5: Restart containers with new images
    log "Agents have stopped. Starting containers with new images..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    # Step 6: Verify deployment
    log "Waiting for services to be healthy..."
    sleep 10
    
    # Check health of known agents
    for port in 8080 8081 8082 8083 8084; do
        if curl -s "http://localhost:$port/v1/system/health" > /dev/null 2>&1; then
            log "Agent on port $port is healthy ✓"
        fi
    done
    
    log "Deployment complete!"
}

# Run main function
main "$@"