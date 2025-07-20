# Manual CIRISManager Deployment Guide

Since the automated deployment is having issues with the unresponsive agent, here's how to manually deploy CIRISManager:

## Quick Deploy (SSH Commands)

```bash
# 1. SSH to server
ssh -i ~/.ssh/ciris_deploy root@108.61.119.117

# 2. Navigate to repository
cd /home/ciris/CIRISAgent
git pull origin main

# 3. Check current state
docker ps -a | grep ciris

# 4. Handle any staged container (if exists)
if docker ps -a | grep -q "ciris-agent-datum-staged"; then
    echo "Found staged container"
    # Check if old container is running
    if docker ps | grep -q "ciris-agent-datum"; then
        echo "Stopping old container..."
        docker stop ciris-agent-datum || true
        sleep 5
    fi
    # Deploy staged
    docker rm ciris-agent-datum 2>/dev/null || true
    docker rename ciris-agent-datum-staged ciris-agent-datum
    docker start ciris-agent-datum
else
    echo "No staged container, ensuring agent is running..."
    docker-compose -f deployment/docker-compose.dev-prod.yml up -d
fi

# 5. Install CIRISManager
cd /home/ciris/CIRISAgent

# Create Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install pyyaml aiofiles docker fastapi uvicorn pydantic

# Create ciris-manager command
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

# 6. Configure CIRISManager
mkdir -p /etc/ciris-manager
ciris-manager --generate-config --config /etc/ciris-manager/config.yml

# Update compose file path
sed -i 's|docker-compose.yml|docker-compose.dev-prod.yml|' /etc/ciris-manager/config.yml

# 7. Install systemd service
cp deployment/ciris-manager.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ciris-manager
systemctl start ciris-manager

# 8. Verify everything
systemctl status ciris-manager
docker ps
curl http://localhost:8080/v1/system/health

# 9. Test CIRISManager API
curl http://localhost:8888/manager/v1/health
curl http://localhost:8888/manager/v1/agents
```

## Expected Results

After successful deployment:
1. ✅ Agent container running (ciris-agent-datum)
2. ✅ CIRISManager service active
3. ✅ API responding at port 8080
4. ✅ CIRISManager API at port 8888
5. ✅ Periodic container management active

## Troubleshooting

If agent is unresponsive:
```bash
# Check logs
docker logs ciris-agent-datum --tail 100

# Check incidents
docker exec ciris-agent-datum tail -n 50 /app/logs/incidents_latest.log

# Restart if needed (respecting consent philosophy)
docker restart ciris-agent-datum
```

If CIRISManager fails:
```bash
# Check service logs
journalctl -u ciris-manager -n 50

# Check Python path issues
cd /home/ciris/CIRISAgent
source venv/bin/activate
python3 -c "import ciris_manager; print('Import successful')"

# Restart service
systemctl restart ciris-manager
```

## Consent-Based Updates

For future updates:
1. Use `./deployment/consent-based-deploy.sh`
2. If agent doesn't consent, use `./deployment/negotiate-deployment.sh`
3. Never force without consent - this is core to our philosophy

Remember: "We are a model of consent, in all directions."