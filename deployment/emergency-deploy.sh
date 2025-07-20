#!/bin/bash
# Emergency deployment script for when graceful shutdown fails

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; }

log "Emergency deployment procedure"
echo ""

# Step 1: Check current state
log "Checking current container state..."
docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "ciris-agent|NAMES" || true

# Step 2: Force stop old container if running
if docker ps --format "{{.Names}}" | grep -q "^ciris-agent-datum$"; then
    warn "Force stopping unresponsive container..."
    docker stop -t 10 ciris-agent-datum || docker kill ciris-agent-datum || true
    sleep 2
fi

# Step 3: Check for staged container
if docker ps -a --format "{{.Names}}" | grep -q "^ciris-agent-datum-staged$"; then
    log "Found staged container, deploying it..."
    
    # Remove old container
    docker rm ciris-agent-datum 2>/dev/null || true
    
    # Deploy staged container
    docker rename ciris-agent-datum-staged ciris-agent-datum
    docker start ciris-agent-datum
    
    log "Staged container deployed!"
else
    log "No staged container found, starting fresh..."
    
    # Remove old container
    docker rm ciris-agent-datum 2>/dev/null || true
    
    # Start fresh
    cd /home/ciris/CIRISAgent
    docker-compose -f deployment/docker-compose.dev-prod.yml up -d agent-datum
fi

# Step 4: Deploy CIRISManager
log "Deploying CIRISManager..."

# Ensure Python environment
if [ ! -d "/home/ciris/CIRISAgent/venv" ]; then
    log "Creating Python virtual environment..."
    cd /home/ciris/CIRISAgent
    python3 -m venv venv
fi

# Activate venv and install dependencies
cd /home/ciris/CIRISAgent
source venv/bin/activate
pip install --upgrade pip
pip install pyyaml aiofiles

# Create ciris-manager wrapper
log "Creating ciris-manager command..."
cat > /usr/local/bin/ciris-manager << 'EOF'
#!/bin/bash
cd /home/ciris/CIRISAgent
export PYTHONPATH="/home/ciris/CIRISAgent:$PYTHONPATH"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
python3 -m ciris_manager.cli "$@"
EOF
chmod +x /usr/local/bin/ciris-manager

# Create config
mkdir -p /etc/ciris-manager
if [ ! -f "/etc/ciris-manager/config.yml" ]; then
    ciris-manager --generate-config --config /etc/ciris-manager/config.yml
    sed -i 's|docker-compose.yml|docker-compose.dev-prod.yml|' /etc/ciris-manager/config.yml
fi

# Install service
if [ -f "deployment/ciris-manager.service" ]; then
    cp deployment/ciris-manager.service /etc/systemd/system/
    sed -i 's|ExecStart=.*|ExecStart=/usr/local/bin/ciris-manager --config /etc/ciris-manager/config.yml|' /etc/systemd/system/ciris-manager.service
    systemctl daemon-reload
    systemctl enable ciris-manager
    systemctl restart ciris-manager
else
    warn "Service file not found, skipping systemd setup"
fi

# Step 5: Verify
log "Waiting for services to stabilize..."
sleep 10

echo ""
log "Final status check:"
echo ""

# Check containers
echo "Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "ciris|NAMES" || true

# Check CIRISManager
echo ""
echo "CIRISManager:"
if systemctl is-active ciris-manager >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Service is active${NC}"
else
    echo -e "  ${RED}✗ Service is not active${NC}"
fi

# Check API
echo ""
echo "API Health:"
if curl -sf http://localhost:8080/v1/system/health >/dev/null; then
    echo -e "  ${GREEN}✓ API is responding${NC}"
else
    echo -e "  ${RED}✗ API is not responding${NC}"
    echo "  Container logs:"
    docker logs ciris-agent-datum --tail 20 2>&1 | sed 's/^/    /'
fi

log "Emergency deployment complete!"