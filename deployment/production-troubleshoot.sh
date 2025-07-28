#!/bin/bash
# Production troubleshooting script for CIRIS agent deployment

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

echo -e "${BLUE}=== CIRIS Production Troubleshooting ===${NC}"
echo ""

# Step 1: Check current container state
log "Step 1: Checking container state..."
echo -e "\nAll containers:"
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "ciris|NAMES" || true

# Check for staged containers
if docker ps -a --format "{{.Names}}" | grep -q "staged"; then
    warn "Found staged containers - deployment may be incomplete"
fi

# Step 2: Check container health
log "\nStep 2: Checking container health..."
for container in ciris-agent-datum ciris-gui ciris-nginx; do
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        STATUS=$(docker inspect "$container" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
        HEALTH=$(docker inspect "$container" --format='{{.State.Health.Status}}' 2>/dev/null || echo "no healthcheck")
        echo -e "  ${container}: Status=${STATUS}, Health=${HEALTH}"
        
        if [[ "$HEALTH" == "unhealthy" ]]; then
            warn "Container $container is unhealthy!"
            echo "    Last 5 log lines:"
            docker logs "$container" --tail 5 2>&1 | sed 's/^/    /'
        fi
    else
        error "  ${container}: NOT RUNNING"
    fi
done

# Step 3: Check API health
log "\nStep 3: Checking API health..."
if curl -sf http://localhost:8080/v1/system/health > /tmp/health.json 2>/dev/null; then
    echo -e "  ${GREEN}✓ API is responding${NC}"
    if command -v jq >/dev/null 2>&1; then
        echo "  Status: $(jq -r '.status' /tmp/health.json 2>/dev/null || echo 'parse error')"
        echo "  Uptime: $(jq -r '.uptime' /tmp/health.json 2>/dev/null || echo 'parse error')"
    fi
else
    error "  ✗ API health check failed"
    echo "  Checking if port 8080 is listening..."
    netstat -tlnp | grep :8080 || echo "  Port 8080 not listening"
fi

# Step 4: Check Docker permissions
log "\nStep 4: Checking Docker permissions..."
if docker ps >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Docker accessible${NC}"
else
    error "  ✗ Cannot access Docker - permission issue?"
fi

# Step 8: Provide recommendations
echo ""
echo -e "${BLUE}=== Recommendations ===${NC}"
echo ""

ISSUES=0

# Check if containers need to be started
if ! docker ps --format "{{.Names}}" | grep -q "ciris-agent-datum"; then
    ((ISSUES++))
    echo "$ISSUES. Agent container is not running. Start it with:"
    echo "   docker-compose -f /home/ciris/CIRISAgent/deployment/docker-compose.dev-prod.yml up -d"
    echo ""
fi


if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}No issues found! Everything appears to be configured correctly.${NC}"
else
    echo -e "${YELLOW}Found $ISSUES issue(s) that need attention.${NC}"
fi

echo ""
echo -e "${BLUE}=== Quick Fix Script ===${NC}"
echo ""
echo "Run this to fix common issues:"
echo ""
echo "cd /home/ciris/CIRISAgent && \\"
echo "docker-compose -f deployment/docker-compose.dev-prod.yml up -d"