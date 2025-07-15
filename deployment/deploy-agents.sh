#!/bin/bash
# CIRIS Multi-Agent Deployment Script
# This script deploys the CIRIS agent system in phases

set -e

DEPLOYMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$DEPLOYMENT_DIR")"

echo "CIRIS Multi-Agent Deployment"
echo "==========================="

# Check if we're on the production server
if [[ ! -f /etc/nginx/sites-available/agents.ciris.ai.conf ]]; then
    echo "Warning: This doesn't appear to be the production server."
    echo "The nginx configuration for agents.ciris.ai is not found."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for environment files
ENV_DIR="/opt/ciris/env"  # Adjust this path as needed
if [[ -d "$ENV_DIR" ]]; then
    echo "Found environment directory at $ENV_DIR"
    # Check for individual agent env files
    for agent in datum sage scout echo-core echo-speculative; do
        if [[ ! -f "$ENV_DIR/${agent}.env" ]]; then
            echo "Warning: Missing ${agent}.env in $ENV_DIR"
        fi
    done
elif [[ -f "$PROJECT_ROOT/ciris_student.env" ]]; then
    echo "Loading environment variables from ciris_student.env..."
    export $(cat "$PROJECT_ROOT/ciris_student.env" | grep -v '^#' | xargs)
else
    echo "Error: No environment files found"
    echo "Expected either:"
    echo "  - Individual .env files in $ENV_DIR"
    echo "  - ciris_student.env in $PROJECT_ROOT"
    exit 1
fi

# Phase selection
echo
echo "Deployment Phases:"
echo "1. Phase 1: Single Datum agent with Mock LLM (testing)"
echo "2. Phase 2: All 5 agents with real LLM (production)"
echo "3. Stop all agents"
read -p "Select phase (1-3): " phase

case $phase in
    1)
        echo
        echo "Phase 1: Deploying single Datum agent with Mock LLM"
        echo "---------------------------------------------------"
        echo "This will:"
        echo "- Start Datum agent on port 8080 with mock LLM"
        echo "- Enable both API and Discord adapters"
        echo "- API adapter has highest priority for WAKEUP"
        echo
        
        cd "$DEPLOYMENT_DIR"
        docker-compose -f docker-compose.phase1.yml up -d --build
        
        echo
        echo "Waiting for agent to be healthy..."
        sleep 10
        
        # Check health
        if curl -f http://localhost:8080/v1/system/health > /dev/null 2>&1; then
            echo "✓ Datum agent is healthy!"
            echo
            echo "Test the agent:"
            echo "  API:     curl http://localhost:8080/v1/system/health"
            echo "  GUI:     http://localhost:3000"
            echo "  Discord: Check the configured Discord channel"
        else
            echo "✗ Agent health check failed"
            docker logs ciris-agent-datum
        fi
        ;;
        
    2)
        echo
        echo "Phase 2: Deploying all 5 agents with real LLM"
        echo "---------------------------------------------"
        echo "This will:"
        echo "- Stop Phase 1 deployment if running"
        echo "- Start all 5 agents (Datum, Sage, Scout, Echo-Core, Echo-Speculative)"
        echo "- Use real LLM providers (OpenAI/Anthropic)"
        echo "- Each agent on ports 8080-8084"
        echo
        
        # Stop Phase 1 if running
        if docker ps | grep -q ciris-agent-datum; then
            echo "Stopping Phase 1 deployment..."
            docker-compose -f docker-compose.phase1.yml down
        fi
        
        # Update the multi-agent compose file to use env vars
        cd "$DEPLOYMENT_DIR"
        
        # Deploy Phase 2 - use production config if env files exist
        if [[ -d "$ENV_DIR" ]]; then
            echo "Using production configuration with separate env files..."
            docker-compose -f docker-compose.production.yml up -d --build
        else
            echo "Using development configuration with shared env..."
            docker-compose -f docker-compose.multi-agent.yml up -d --build
        fi
        
        echo
        echo "Waiting for agents to be healthy..."
        sleep 20
        
        # Check health of all agents
        echo
        echo "Agent Health Status:"
        for port in 8080 8081 8082 8083 8084; do
            agent_name=""
            case $port in
                8080) agent_name="Datum" ;;
                8081) agent_name="Sage" ;;
                8082) agent_name="Scout" ;;
                8083) agent_name="Echo-Core" ;;
                8084) agent_name="Echo-Speculative" ;;
            esac
            
            if curl -f http://localhost:$port/v1/system/health > /dev/null 2>&1; then
                echo "✓ $agent_name (port $port) is healthy!"
            else
                echo "✗ $agent_name (port $port) health check failed"
            fi
        done
        
        echo
        echo "Access points:"
        echo "  GUI:    https://agents.ciris.ai/"
        echo "  Datum:  https://agents.ciris.ai/api/datum/"
        echo "  Sage:   https://agents.ciris.ai/api/sage/"
        echo "  Scout:  https://agents.ciris.ai/api/scout/"
        echo "  Echo-Core: https://agents.ciris.ai/api/echo-core/"
        echo "  Echo-Speculative: https://agents.ciris.ai/api/echo-speculative/"
        ;;
        
    3)
        echo
        echo "Stopping all agents..."
        cd "$DEPLOYMENT_DIR"
        
        # Stop both deployments
        docker-compose -f docker-compose.phase1.yml down 2>/dev/null || true
        docker-compose -f docker-compose.multi-agent.yml down 2>/dev/null || true
        
        echo "All agents stopped."
        ;;
        
    *)
        echo "Invalid selection"
        exit 1
        ;;
esac

echo
echo "Deployment complete!"