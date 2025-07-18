# CIRIS Deployment

This directory contains the deployment configuration for the CIRIS system.

## Deployment Environments

### Development (Mock LLM)
- Single Datum agent with mock LLM for testing
- No external API dependencies
- Ideal for development and testing

### Production (Multi-Agent)
- 5 specialized CIRIS agents working in concert
- Real LLM integration (OpenAI, Anthropic, etc.)
- Full Discord and API capabilities

## Production Architecture

The production system consists of 5 CIRIS agents, each with a specific role:

1. **Datum** (port 8080) - Primary decision-making agent
2. **Sage** (port 8081) - Wisdom and deep analysis
3. **Scout** (port 8082) - Information gathering and reconnaissance  
4. **Echo-Core** (port 8083) - Core reasoning and consistency
5. **Echo-Speculative** (port 8084) - Speculative reasoning and possibilities

## Production Environment Files

On the production server, each agent has its own `.env` file:
- `/path/to/datum.env`
- `/path/to/sage.env`
- `/path/to/scout.env`
- `/path/to/echo-core.env`
- `/path/to/echo-speculative.env`

Each `.env` file should contain:
```bash
# LLM Configuration
OPENAI_API_KEY=...
OPENAI_API_BASE=...
OPENAI_MODEL_NAME=...

# Discord Configuration (if different per agent)
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...
DISCORD_DEFERRAL_CHANNEL_ID=...
WA_USER_ID=...
SNORE_CHANNEL_ID=...

# Agent-specific settings
CIRIS_AGENT_NAME=Datum  # Or Sage, Scout, etc.
```

## Deployment Commands

### Development Environment
```bash
# Deploy single agent with mock LLM
docker-compose -f docker-compose.dev.yml up -d
```

### Production Environment
```bash
# Deploy all 5 agents with real LLM
docker-compose -f docker-compose.production.yml up -d
```

## Automated CI/CD

Production deployment is fully automated via GitHub Actions:
1. Push to main branch triggers the pipeline
2. Tests run in Docker containers
3. Docker images built and pushed to ghcr.io
4. Automatic deployment to production server
5. Health checks verify successful deployment

## Adapter Priority Configuration

The adapters are configured with the following priorities:
- **API Adapter**: Priority.CRITICAL (highest)
- **Discord Adapter**: Priority.NORMAL (medium)
- **CLI Adapter**: Priority.LOW (lowest)

This ensures that API requests take precedence, followed by Discord, then CLI.

## NGINX Configuration

The production NGINX configuration (`nginx/agents.ciris.ai.conf`) routes:
- `/` → GUI on port 3000
- `/api/datum/*` → Datum agent on port 8080
- `/api/sage/*` → Sage agent on port 8081
- `/api/scout/*` → Scout agent on port 8082
- `/api/echo-core/*` → Echo-Core agent on port 8083
- `/api/echo-speculative/*` → Echo-Speculative agent on port 8084

## Local Development

For local development and testing:

```bash
# Run with mock LLM
python main.py --adapter api --adapter discord --mock-llm --timeout 60

# Or use Docker
docker-compose -f docker-compose.dev.yml up -d
```

## Monitoring

Check agent health:
```bash
# Individual agents
curl http://localhost:8080/v1/system/health  # Datum
curl http://localhost:8081/v1/system/health  # Sage
# etc...

# Through NGINX
curl https://agents.ciris.ai/api/datum/system/health
```

View logs:
```bash
docker logs ciris-agent-datum
docker logs ciris-agent-sage
# etc...
```