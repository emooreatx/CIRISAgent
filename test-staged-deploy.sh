#!/bin/bash
set -e

echo "=== Testing Staged Deployment Locally ==="

# Test configuration
COMPOSE_FILE="docker-compose-api-discord-mock.yml"
CONTAINER_NAME="ciris-api-discord-mock"
API_URL="http://localhost:8080"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }

# Step 1: Ensure container is running
log "Checking if container is running..."
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    log "Starting container..."
    docker-compose -f "$COMPOSE_FILE" up -d
    sleep 5
fi

# Step 2: Test the --no-start option
log "Testing docker-compose up --no-start..."
if docker-compose -f "$COMPOSE_FILE" up --no-start 2>&1 | grep -q "unknown flag: --no-start"; then
    error "The --no-start flag is not recognized!"
    
    # Test alternative: create with different project name
    log "Testing alternative: using different project name..."
    docker-compose -p staged -f "$COMPOSE_FILE" up -d --no-deps ciris-local
    docker-compose -p staged -f "$COMPOSE_FILE" stop ciris-local
    
    if docker ps -a | grep -q "staged"; then
        log "Created staged container with project name 'staged'"
        docker ps -a | grep staged
    fi
else
    log "The --no-start flag works! Creating staged container..."
    # This should create containers without starting them
    docker-compose -f "$COMPOSE_FILE" up --no-start
fi

# Step 3: Test graceful shutdown
log "Testing graceful shutdown script..."
if [ -f "deployment/graceful-shutdown.py" ]; then
    log "Checking agent health..."
    if curl -s "$API_URL/v1/system/health" > /dev/null; then
        log "Agent is healthy. Attempting graceful shutdown..."
        python3 deployment/graceful-shutdown.py \
            --agent-url "$API_URL" \
            --message "Test staged deployment shutdown" || {
            warn "Graceful shutdown failed"
        }
    else
        error "Agent is not responding at $API_URL"
    fi
else
    error "graceful-shutdown.py not found"
fi

# Step 4: Monitor container exit
log "Monitoring container for exit..."
WAIT_COUNT=0
MAX_WAIT=60  # 1 minute for test

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        # Container stopped
        EXIT_CODE=$(docker inspect "$CONTAINER_NAME" --format='{{.State.ExitCode}}' 2>/dev/null || echo "unknown")
        log "Container exited with code: $EXIT_CODE"
        
        if [ "$EXIT_CODE" = "0" ]; then
            log "✅ Graceful shutdown successful (exit code 0)"
        else
            error "❌ Container exited with non-zero code: $EXIT_CODE"
        fi
        break
    fi
    
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
    
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        log "Still waiting for shutdown... (${WAIT_COUNT}s elapsed)"
    fi
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    warn "Timeout waiting for shutdown"
fi

# Step 5: Clean up
log "Cleaning up test containers..."
docker-compose -p staged down 2>/dev/null || true

log "Test complete!"