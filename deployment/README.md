# CIRIS Multi-Agent Deployment

This directory contains the deployment configuration for the CIRIS multi-agent system.

## Architecture

The system consists of 5 CIRIS agents, each with a specific role:

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

## Deployment Phases

### Phase 1: Testing with Mock LLM
```bash
# Load the environment and deploy with mock LLM
docker-compose -f docker-compose.phase1.yml --env-file datum.env up -d
```

### Phase 2: Production with Real LLM
```bash
# Deploy all 5 agents with their respective env files
# Note: You'll need to modify docker-compose.multi-agent.yml to use
# separate env files per service, or load them manually
./deploy-agents.sh
```

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

## Testing Multi-Adapter Setup Locally

To test the multi-adapter configuration locally:

```bash
# Export environment variables from ciris_student.env
export $(cat ../ciris_student.env | grep -v '^#' | xargs)

# Run with mock LLM, API and Discord adapters
python main.py --adapter api --adapter discord --mock-llm --timeout 60
```

This will:
1. Start both API and Discord adapters
2. Use the mock LLM for testing
3. Send WAKEUP to API channel (due to higher priority)
4. Allow interaction via both API and Discord

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