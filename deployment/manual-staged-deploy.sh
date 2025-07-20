#!/bin/bash
# Manual intervention script for failed staged deployment

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; }

# Check current state
log "Checking current deployment state..."

# List all containers
echo -e "\nCurrent containers:"
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "ciris|NAMES" || true

# Check for staged container
if docker ps -a --format "{{.Names}}" | grep -q "ciris-agent-datum-staged"; then
    log "Found staged container waiting for deployment"
    
    # Check if old container is still running
    if docker ps --format "{{.Names}}" | grep -q "ciris-agent-datum"; then
        warn "Old container is still running"
        
        # Ask for confirmation
        echo -e "\n${YELLOW}Manual intervention required:${NC}"
        echo "1. Stop the old container and deploy staged version"
        echo "2. Remove staged container and keep current version"
        echo "3. Exit without changes"
        
        read -p "Choose option (1-3): " choice
        
        case $choice in
            1)
                log "Stopping old container and deploying staged version..."
                docker stop ciris-agent-datum || true
                docker rm ciris-agent-datum || true
                docker rename ciris-agent-datum-staged ciris-agent-datum
                docker start ciris-agent-datum
                log "Staged container deployed successfully!"
                ;;
            2)
                log "Removing staged container..."
                docker rm ciris-agent-datum-staged || true
                log "Staged container removed. Current version kept."
                ;;
            3)
                log "Exiting without changes."
                exit 0
                ;;
            *)
                error "Invalid option"
                exit 1
                ;;
        esac
    else
        log "Old container is not running. Deploying staged version..."
        docker rm ciris-agent-datum || true
        docker rename ciris-agent-datum-staged ciris-agent-datum
        docker start ciris-agent-datum
        log "Staged container deployed successfully!"
    fi
else
    log "No staged container found"
    
    # Check if deployment needs to be rerun
    if ! docker ps --format "{{.Names}}" | grep -q "ciris-agent-datum"; then
        warn "Agent container is not running!"
        echo -e "\n${YELLOW}Would you like to start the containers?${NC}"
        read -p "Start containers? (y/n): " start_choice
        
        if [[ "$start_choice" == "y" ]]; then
            log "Starting containers..."
            cd /home/ciris/CIRISAgent
            docker-compose -f deployment/docker-compose.dev-prod.yml up -d
            log "Containers started"
        fi
    fi
fi

# Show final state
echo -e "\n${GREEN}Final container state:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "ciris|NAMES" || true

# Check health
echo -e "\n${GREEN}Checking API health:${NC}"
if curl -f http://localhost:8080/v1/system/health 2>/dev/null; then
    echo -e "\n${GREEN}✓ API is healthy${NC}"
else
    echo -e "\n${RED}✗ API health check failed${NC}"
fi