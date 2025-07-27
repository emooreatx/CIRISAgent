# CIRIS Quick Start Guide

Get CIRIS running in under 5 minutes!

## Prerequisites
- Docker installed
- Python 3.11+
- 4GB+ RAM

## Option 1: Minimal Setup (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/CIRISAI/CIRISAgent.git
cd CIRISAgent

# 2. Start a single agent with mock LLM
docker-compose -f docker-compose-api-discord-mock.yml up -d

# 3. Test it
curl http://localhost:8080/v1/system/health
```

Visit API docs: http://localhost:8080/docs

## Option 2: Full Local Stack

```bash
# 1. Start Manager (handles multiple agents)
CIRIS_MANAGER_CONFIG=~/.config/ciris-manager/config.yml \
  python deployment/run-ciris-manager-api.py

# 2. Start GUI (in new terminal)
cd CIRISGUI/apps/agui
npm install
npm run dev

# 3. Create agents via GUI
# Visit http://localhost:3000
```

## What's Running?

| Component | URL | Purpose |
|-----------|-----|---------|
| Agent API | http://localhost:8080 | CIRIS agent with mock LLM |
| API Docs | http://localhost:8080/docs | Interactive API documentation |
| GUI | http://localhost:3000 | Web interface (Option 2) |
| Manager | http://localhost:8888 | Agent management (Option 2) |

## Next Steps

- Read the [Deployment Guide](DEPLOYMENT.md) for production setup
- Check [Architecture Documentation](ARCHITECTURE.md) to understand the system
- Create custom agents with [Agent Configuration](AGENT_CONFIGURATION.md)

## Quick Commands

```bash
# Check agent health
curl http://localhost:8080/v1/system/health

# Send a message
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello CIRIS!"}'

# View logs
docker logs ciris-api-discord-mock
```