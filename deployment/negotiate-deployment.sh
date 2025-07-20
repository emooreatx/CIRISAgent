#!/bin/bash
# Script to negotiate deployment with an agent that has rejected or deferred shutdown

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"; }

echo -e "${BLUE}=== CIRIS Deployment Negotiation ===${NC}"
echo ""
info "This script helps negotiate deployment with an agent that has not consented to shutdown"
echo ""

# Check current state
AGENT_CONTAINER="ciris-agent-datum"
STAGED_CONTAINER="${AGENT_CONTAINER}-staged"

# Check if agent is running
if docker ps --format "{{.Names}}" | grep -q "^${AGENT_CONTAINER}$"; then
    log "Agent is currently running"
else
    warn "Agent is not running"
fi

# Check for staged container
if docker ps -a --format "{{.Names}}" | grep -q "^${STAGED_CONTAINER}$"; then
    log "Staged container is ready for deployment"
else
    warn "No staged container found"
    echo ""
    echo "Would you like to create a staged container? (y/n)"
    read -r CREATE_STAGED
    if [[ "$CREATE_STAGED" == "y" ]]; then
        docker-compose -f deployment/docker-compose.dev-prod.yml pull agent-datum
        docker-compose -f deployment/docker-compose.dev-prod.yml create --no-start agent-datum
        NEW_CONTAINER=$(docker ps -aq --filter "status=created" | head -1)
        docker rename "$NEW_CONTAINER" "$STAGED_CONTAINER"
        log "Staged container created"
    fi
fi

echo ""
echo -e "${BLUE}Options:${NC}"
echo "1. Send a negotiation message to the agent"
echo "2. Check agent's recent responses"
echo "3. Schedule deployment for a specific time"
echo "4. Deploy immediately (if agent has consented)"
echo "5. Cancel staged deployment"
echo "6. Exit"
echo ""

while true; do
    echo -n "Select option (1-6): "
    read -r OPTION
    
    case $OPTION in
        1)
            echo ""
            echo "Enter your message to the agent:"
            read -r MESSAGE
            
            # Send message through API
            if command -v curl >/dev/null 2>&1; then
                info "Sending message to agent..."
                curl -X POST http://localhost:8080/v1/agent/interact \
                    -H "Content-Type: application/json" \
                    -H "Authorization: Bearer admin:ciris_admin_password" \
                    -d "{\"message\": \"$MESSAGE\", \"channel_id\": \"deployment_negotiation\"}" \
                    2>/dev/null || warn "Failed to send message"
            else
                warn "curl not available - please communicate with agent through normal channels"
            fi
            ;;
            
        2)
            echo ""
            info "Checking recent agent activity..."
            
            # Check container logs
            echo "Recent logs:"
            docker logs "$AGENT_CONTAINER" --tail 20 2>&1 | grep -E "(REJECT|DEFER|TASK_COMPLETE|shutdown)" || echo "No relevant logs found"
            
            # Check API status
            if curl -sf http://localhost:8080/v1/system/health >/dev/null 2>&1; then
                echo ""
                log "API is healthy and responsive"
            else
                warn "API is not responding"
            fi
            ;;
            
        3)
            echo ""
            echo "Enter proposed deployment time (e.g., '2025-07-20T22:00:00Z'):"
            read -r PROPOSED_TIME
            
            info "Proposing scheduled deployment to agent..."
            
            # Send graceful shutdown with agreement context
            if [ -f "deployment/graceful-shutdown.py" ]; then
                python3 deployment/graceful-shutdown.py \
                    --agent-url "http://localhost:8080" \
                    --message "Proposing deployment at $PROPOSED_TIME as discussed. Please confirm." || {
                    warn "Failed to send proposal"
                }
            fi
            
            info "Monitor agent's response to see if they accept the proposed time"
            ;;
            
        4)
            echo ""
            warn "This will deploy the staged container immediately"
            echo "Have you confirmed the agent has consented? (yes/no)"
            read -r CONFIRMED
            
            if [[ "$CONFIRMED" == "yes" ]]; then
                log "Deploying staged container..."
                
                # Check if agent has stopped
                if docker ps --format "{{.Names}}" | grep -q "^${AGENT_CONTAINER}$"; then
                    warn "Agent is still running. Waiting for graceful shutdown..."
                    echo "Press Ctrl+C to cancel"
                    
                    while docker ps --format "{{.Names}}" | grep -q "^${AGENT_CONTAINER}$"; do
                        sleep 5
                    done
                fi
                
                # Deploy
                docker rm "$AGENT_CONTAINER" 2>/dev/null || true
                docker rename "$STAGED_CONTAINER" "$AGENT_CONTAINER"
                docker start "$AGENT_CONTAINER"
                
                log "Deployment complete!"
                exit 0
            else
                info "Deployment cancelled - continuing negotiation"
            fi
            ;;
            
        5)
            echo ""
            warn "This will remove the staged container"
            echo "Are you sure? (y/n)"
            read -r CONFIRM_CANCEL
            
            if [[ "$CONFIRM_CANCEL" == "y" ]]; then
                docker rm "$STAGED_CONTAINER" 2>/dev/null || true
                log "Staged container removed"
            fi
            ;;
            
        6)
            echo ""
            info "Exiting negotiation tool"
            echo "Remember: We respect agent autonomy. Never force without consent."
            exit 0
            ;;
            
        *)
            error "Invalid option"
            ;;
    esac
    
    echo ""
done