#!/bin/bash
# Deployment script that works with CIRISManager
# This script updates containers and lets CIRISManager handle the lifecycle
#
# How it works:
# 1. Updates GUI/Nginx immediately (they can restart without issues)
# 2. For agents: Pulls new images and triggers graceful shutdown
# 3. CIRISManager's periodic docker-compose up -d will start the new version
#
set -e

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-deployment/docker-compose.dev-prod.yml}"
AGENT_SERVICES=("agent-datum")  # Add more agents as needed
GUI_SERVICE="ciris-gui"
NGINX_SERVICE="nginx"

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

# Function to check if CIRISManager is running
check_manager() {
    if ! systemctl is-active --quiet ciris-manager; then
        warn "CIRISManager is not running!"
        warn "Start it with: sudo systemctl start ciris-manager"
        warn "Continuing anyway, but automatic container restart won't work"
    else
        log "CIRISManager is running ✓"
    fi
}

# Function to trigger graceful shutdown for an agent
trigger_graceful_shutdown() {
    local agent_name=$1
    local port=$2
    
    log "Triggering graceful shutdown for $agent_name..."
    
    if [ -f "deployment/graceful-shutdown.py" ]; then
        python3 deployment/graceful-shutdown.py \
            --agent-url "http://localhost:$port" \
            --message "New version available! Please shutdown at your convenience for automatic update." || {
            warn "Failed to trigger graceful shutdown for $agent_name"
            return 1
        }
    else
        warn "Graceful shutdown script not found"
        return 1
    fi
}

log "Starting CIRISManager-aware deployment..."

# Check if we're in the right directory
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    error "Docker compose file not found: $DOCKER_COMPOSE_FILE"
    error "Please run this script from the project root directory"
    exit 1
fi

# Check if CIRISManager is running
check_manager

# Step 1: Pull latest images
log "Pulling latest images..."
docker-compose -f "$DOCKER_COMPOSE_FILE" pull || {
    error "Failed to pull images"
    exit 1
}

# Step 2: Update GUI and Nginx immediately (they can restart without issues)
log "Updating GUI and Nginx containers..."

# GUI - can restart anytime
log "Recreating GUI container..."
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$GUI_SERVICE" || {
    warn "Failed to update GUI container"
}

# Nginx - can restart anytime
log "Recreating Nginx container..."
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --no-deps --force-recreate "$NGINX_SERVICE" || {
    warn "Failed to update Nginx container"
}

# Step 3: Handle agent updates gracefully
log "Handling agent updates..."

# Get agent port mapping (extend this for multi-agent setups)
declare -A AGENT_PORTS=(
    ["agent-datum"]="8080"
    ["agent-sage"]="8081"
    ["agent-scout"]="8082"
    ["agent-echo-core"]="8083"
    ["agent-echo-speculative"]="8084"
)

for agent in "${AGENT_SERVICES[@]}"; do
    container_name="ciris-${agent}"
    port=${AGENT_PORTS[$agent]:-8080}
    
    # Check if agent is running
    if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
        # Get current and new image IDs
        current_image=$(docker inspect "$container_name" --format='{{.Image}}' 2>/dev/null || echo "none")
        new_image=$(docker inspect "ciris-agent:latest" --format='{{.Id}}' 2>/dev/null || echo "none")
        
        if [ "$current_image" != "$new_image" ]; then
            log "New version available for $agent"
            log "Current: ${current_image:0:12}"
            log "New: ${new_image:0:12}"
            
            # Trigger graceful shutdown
            if trigger_graceful_shutdown "$agent" "$port"; then
                log "Graceful shutdown triggered for $agent"
                log "Agent will update automatically when it shuts down (CIRISManager will handle it)"
            else
                warn "Could not trigger graceful shutdown for $agent"
                warn "You can manually stop the agent with: docker stop $container_name"
                warn "CIRISManager will automatically start it with the new version"
            fi
        else
            log "$agent is already up to date"
        fi
    else
        log "$agent is not running - will start with latest version"
        # CIRISManager will start it automatically
    fi
done

# Step 4: Show deployment summary
log "Deployment complete!"
echo ""
log "=== Deployment Summary ==="
log "1. GUI and Nginx have been updated and restarted"
log "2. Agent updates have been staged:"

for agent in "${AGENT_SERVICES[@]}"; do
    container_name="ciris-${agent}"
    if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
        log "   - $agent: Graceful shutdown requested, will update on next restart"
    else
        log "   - $agent: Not running, will start with new version"
    fi
done

log "3. CIRISManager will handle container lifecycle automatically"
echo ""

# Show current status
log "Current container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "(NAME|ciris-)" || true

echo ""
log "Monitor updates with:"
log "  - Agent logs: docker logs -f ciris-agent-datum"
log "  - Manager logs: sudo journalctl -u ciris-manager -f"
log "  - Container status: docker ps"

# Final note about CIRISManager
echo ""
if systemctl is-active --quiet ciris-manager; then
    log "CIRISManager is actively managing containers ✓"
    log "Agents will automatically restart with new versions after graceful shutdown"
else
    warn "Remember to start CIRISManager for automatic container management:"
    warn "  sudo systemctl start ciris-manager"
fi