#!/bin/bash
# Production troubleshooting script for CIRISManager and agent deployment

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

# Step 4: Check CIRISManager installation
log "\nStep 4: Checking CIRISManager installation..."
if command -v ciris-manager >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓ CIRISManager is installed${NC}"
    echo "  Location: $(which ciris-manager)"
else
    error "  ✗ CIRISManager not found in PATH"
    # Check if it's installed but not in PATH
    if [ -f "/usr/local/bin/ciris-manager" ]; then
        warn "  Found at /usr/local/bin/ciris-manager but not in PATH"
    fi
fi

# Step 5: Check CIRISManager service
log "\nStep 5: Checking CIRISManager systemd service..."
if systemctl list-unit-files | grep -q "ciris-manager.service"; then
    echo -e "  ${GREEN}✓ Service is installed${NC}"
    STATUS=$(systemctl is-active ciris-manager.service || echo "inactive")
    ENABLED=$(systemctl is-enabled ciris-manager.service || echo "disabled")
    echo "  Status: $STATUS"
    echo "  Enabled: $ENABLED"
    
    if [[ "$STATUS" != "active" ]]; then
        warn "  Service is not active!"
        echo "  Last 10 journal entries:"
        journalctl -u ciris-manager.service -n 10 --no-pager | sed 's/^/    /'
    fi
else
    error "  ✗ ciris-manager.service not found"
fi

# Step 6: Check CIRISManager config
log "\nStep 6: Checking CIRISManager configuration..."
if [ -f "/etc/ciris-manager/config.yml" ]; then
    echo -e "  ${GREEN}✓ Config file exists${NC}"
    echo "  Compose file path:"
    grep "compose_file:" /etc/ciris-manager/config.yml | sed 's/^/    /'
    
    # Verify compose file exists
    COMPOSE_FILE=$(grep "compose_file:" /etc/ciris-manager/config.yml | awk '{print $2}' | tr -d '"')
    if [ -f "$COMPOSE_FILE" ]; then
        echo -e "  ${GREEN}✓ Compose file exists${NC}"
    else
        error "  ✗ Compose file not found: $COMPOSE_FILE"
    fi
else
    error "  ✗ Config file not found at /etc/ciris-manager/config.yml"
fi

# Step 7: Check Docker permissions
log "\nStep 7: Checking Docker permissions..."
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

# Check if CIRISManager needs installation
if ! command -v ciris-manager >/dev/null 2>&1; then
    ((ISSUES++))
    echo "$ISSUES. CIRISManager needs to be installed:"
    echo "   cd /home/ciris/CIRISAgent"
    echo "   pip3 install -e ."
    echo ""
fi

# Check if service needs to be started
if systemctl list-unit-files | grep -q "ciris-manager.service"; then
    if [[ "$(systemctl is-active ciris-manager.service)" != "active" ]]; then
        ((ISSUES++))
        echo "$ISSUES. CIRISManager service needs to be started:"
        echo "   systemctl start ciris-manager"
        echo "   systemctl enable ciris-manager"
        echo ""
    fi
else
    ((ISSUES++))
    echo "$ISSUES. CIRISManager service needs to be installed:"
    echo "   cp /home/ciris/CIRISAgent/deployment/ciris-manager.service /etc/systemd/system/"
    echo "   systemctl daemon-reload"
    echo "   systemctl enable ciris-manager"
    echo "   systemctl start ciris-manager"
    echo ""
fi

# Check if config needs to be created
if [ ! -f "/etc/ciris-manager/config.yml" ]; then
    ((ISSUES++))
    echo "$ISSUES. CIRISManager config needs to be created:"
    echo "   mkdir -p /etc/ciris-manager"
    echo "   ciris-manager --generate-config --config /etc/ciris-manager/config.yml"
    echo "   # Then update the compose_file path to:"
    echo "   # /home/ciris/CIRISAgent/deployment/docker-compose.dev-prod.yml"
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
echo "docker-compose -f deployment/docker-compose.dev-prod.yml up -d && \\"
echo "pip3 install -e . && \\"
echo "mkdir -p /etc/ciris-manager && \\"
echo "ciris-manager --generate-config --config /etc/ciris-manager/config.yml && \\"
echo "sed -i 's|docker-compose.yml|docker-compose.dev-prod.yml|' /etc/ciris-manager/config.yml && \\"
echo "cp deployment/ciris-manager.service /etc/systemd/system/ && \\"
echo "systemctl daemon-reload && \\"
echo "systemctl enable ciris-manager && \\"
echo "systemctl start ciris-manager"