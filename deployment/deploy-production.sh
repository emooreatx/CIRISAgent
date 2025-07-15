#!/bin/bash
# Production deployment script for agents.ciris.ai
# This script deploys the CIRIS multi-agent system to the production server

set -e

# Configuration
DEPLOY_USER="root"
DEPLOY_HOST="agents.ciris.ai"
SSH_KEY="$HOME/.ssh/ciris_deploy"
REMOTE_DIR="/opt/ciris"

echo "CIRIS Production Deployment"
echo "=========================="
echo "Server: $DEPLOY_HOST"
echo "User: $DEPLOY_USER"
echo

# Test SSH connection
echo "Testing SSH connection..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$DEPLOY_USER@$DEPLOY_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
    echo "✓ SSH connection established"
else
    echo "✗ SSH connection failed"
    echo "Please ensure the public key is added to $DEPLOY_USER@$DEPLOY_HOST:~/.ssh/authorized_keys"
    echo
    echo "Public key to add:"
    cat "${SSH_KEY}.pub"
    exit 1
fi

# Function to run remote commands
remote_exec() {
    ssh -i "$SSH_KEY" "$DEPLOY_USER@$DEPLOY_HOST" "$@"
}

# Function to copy files
remote_copy() {
    scp -i "$SSH_KEY" -r "$@" "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/"
}

# Check remote environment
echo
echo "Checking remote environment..."
remote_exec "mkdir -p $REMOTE_DIR/{env,data,logs}"

# Check for environment files
echo "Checking for agent environment files..."
ENV_FILES_EXIST=true
for agent in datum sage scout echo-core echo-speculative; do
    if ! remote_exec "test -f $REMOTE_DIR/env/${agent}.env"; then
        echo "  ✗ Missing: ${agent}.env"
        ENV_FILES_EXIST=false
    else
        echo "  ✓ Found: ${agent}.env"
    fi
done

if [ "$ENV_FILES_EXIST" = false ]; then
    echo
    echo "⚠️  Warning: Some environment files are missing"
    echo "Please create the following files on the server:"
    echo "  - $REMOTE_DIR/env/datum.env"
    echo "  - $REMOTE_DIR/env/sage.env"
    echo "  - $REMOTE_DIR/env/scout.env"
    echo "  - $REMOTE_DIR/env/echo-core.env"
    echo "  - $REMOTE_DIR/env/echo-speculative.env"
    echo
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build and push Docker images
echo
echo "Building Docker images..."
cd "$(dirname "$0")/.."

# Create deployment archive
echo "Creating deployment archive..."
tar -czf deployment.tar.gz \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude=".git" \
    --exclude="logs/*" \
    --exclude="data/*" \
    --exclude=".env" \
    --exclude="*.log" \
    --exclude="deployment.tar.gz" \
    .

echo "Uploading deployment archive..."
scp -i "$SSH_KEY" deployment.tar.gz "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/"

echo "Extracting on server..."
remote_exec "cd $REMOTE_DIR && tar -xzf deployment.tar.gz && rm deployment.tar.gz"

# Copy deployment files
echo "Copying deployment files..."
scp -i "$SSH_KEY" deployment/docker-compose.production.yml "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/docker-compose.yml"
scp -i "$SSH_KEY" deployment/nginx/agents.ciris.ai.conf "$DEPLOY_USER@$DEPLOY_HOST:/tmp/agents.ciris.ai.conf"

# Update NGINX configuration
echo
echo "Updating NGINX configuration..."
remote_exec "cp /tmp/agents.ciris.ai.conf /etc/nginx/sites-available/agents.ciris.ai"
remote_exec "ln -sf /etc/nginx/sites-available/agents.ciris.ai /etc/nginx/sites-enabled/"
remote_exec "nginx -t && systemctl reload nginx"

# Deploy Phase 1 or Phase 2
echo
echo "Deployment Options:"
echo "1. Phase 1: Single Datum agent with Mock LLM"
echo "2. Phase 2: All 5 agents with real LLM"
echo "3. Stop all agents"
read -p "Select deployment phase (1-3): " phase

case $phase in
    1)
        echo
        echo "Deploying Phase 1: Datum with Mock LLM..."
        
        # Create Phase 1 compose file on server
        remote_exec "cat > $REMOTE_DIR/docker-compose-phase1.yml << 'EOF'
version: '3.8'

services:
  agent-datum:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ciris-agent-datum
    ports:
      - \"8080:8080\"
    env_file:
      - $REMOTE_DIR/env/datum.env
    environment:
      - CIRIS_AGENT_NAME=Datum
      - CIRIS_AGENT_ID=agent-datum
      - CIRIS_PORT=8080
      - API_HOST=0.0.0.0
      - API_PORT=8080
      - CIRIS_MOCK_LLM=true
    volumes:
      - $REMOTE_DIR/data/datum:/app/data
      - $REMOTE_DIR/logs/datum:/app/logs
    restart: unless-stopped
    command: [\"python\", \"main.py\", \"--adapter\", \"api\", \"--adapter\", \"discord\", \"--mock-llm\"]

  ciris-gui:
    build:
      context: ./CIRISGUI
      dockerfile: Dockerfile
    container_name: ciris-gui
    ports:
      - \"3000:3000\"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_CIRIS_API_URL=https://agents.ciris.ai
    restart: unless-stopped

EOF"
        
        # Deploy Phase 1
        remote_exec "cd $REMOTE_DIR && docker-compose -f docker-compose-phase1.yml up -d --build"
        
        echo
        echo "Waiting for services to start..."
        sleep 20
        
        # Check health
        echo "Checking service health..."
        if remote_exec "curl -f http://localhost:8080/v1/system/health" > /dev/null 2>&1; then
            echo "✓ Datum agent is healthy!"
        else
            echo "✗ Datum agent health check failed"
            remote_exec "docker logs ciris-agent-datum | tail -20"
        fi
        
        if remote_exec "curl -f http://localhost:3000" > /dev/null 2>&1; then
            echo "✓ GUI is healthy!"
        else
            echo "✗ GUI health check failed"
        fi
        
        echo
        echo "Phase 1 deployed!"
        echo "Access at: https://agents.ciris.ai"
        ;;
        
    2)
        echo
        echo "Deploying Phase 2: All 5 agents..."
        
        # Stop Phase 1 if running
        remote_exec "cd $REMOTE_DIR && docker-compose -f docker-compose-phase1.yml down 2>/dev/null || true"
        
        # Deploy all agents
        remote_exec "cd $REMOTE_DIR && docker-compose up -d --build"
        
        echo
        echo "Waiting for services to start..."
        sleep 30
        
        # Check health of all agents
        echo "Checking service health..."
        for port in 8080 8081 8082 8083 8084; do
            agent_name=""
            case $port in
                8080) agent_name="Datum" ;;
                8081) agent_name="Sage" ;;
                8082) agent_name="Scout" ;;
                8083) agent_name="Echo-Core" ;;
                8084) agent_name="Echo-Speculative" ;;
            esac
            
            if remote_exec "curl -f http://localhost:$port/v1/system/health" > /dev/null 2>&1; then
                echo "✓ $agent_name is healthy!"
            else
                echo "✗ $agent_name health check failed"
            fi
        done
        
        echo
        echo "Phase 2 deployed!"
        echo "Access points:"
        echo "  GUI: https://agents.ciris.ai"
        echo "  Datum API: https://agents.ciris.ai/api/datum/"
        echo "  Sage API: https://agents.ciris.ai/api/sage/"
        echo "  Scout API: https://agents.ciris.ai/api/scout/"
        echo "  Echo-Core API: https://agents.ciris.ai/api/echo-core/"
        echo "  Echo-Speculative API: https://agents.ciris.ai/api/echo-speculative/"
        ;;
        
    3)
        echo
        echo "Stopping all agents..."
        remote_exec "cd $REMOTE_DIR && docker-compose down && docker-compose -f docker-compose-phase1.yml down 2>/dev/null || true"
        echo "All agents stopped."
        ;;
        
    *)
        echo "Invalid selection"
        exit 1
        ;;
esac

# Cleanup
rm -f deployment.tar.gz

echo
echo "Deployment complete!"