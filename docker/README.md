# CIRIS Agent Docker Deployment

## Port Assignments

Each CIRIS agent runs on a unique API port to allow simultaneous deployment:

| Agent | Container Name | API Port | Profile |
|-------|---------------|----------|---------|
| Default/Teacher | cirisagent/teacher | 8000/8001 | teacher |
| Student | student | 8002 | student |
| Echo Core | echo-core | 8003 | echo-core |
| Echo Speculative | echo-speculative | 8004 | echo-speculative |

## Usage

### Run a Single Agent

```bash
# Teacher agent
docker-compose -f docker-compose-teacher.yml up -d

# Student agent
docker-compose -f docker-compose-student.yml up -d

# Echo Core agent
docker-compose -f docker-compose-echo-core.yml up -d

# Echo Speculative agent
docker-compose -f docker-compose-echo-spec.yml up -d
```

### Run All Agents Simultaneously

```bash
# Start all 4 agents
docker-compose -f docker-compose-all.yml up -d

# View logs for all agents
docker-compose -f docker-compose-all.yml logs -f

# Stop all agents
docker-compose -f docker-compose-all.yml down
```

### Environment Files

Each agent requires its own `.env` file:
- `.env` or `.env.teacher` - Teacher agent configuration
- `.env.student` - Student agent configuration
- `.env.echo-core` - Echo Core agent configuration
- `.env.echo-spec` - Echo Speculative agent configuration

Each env file should contain:
```env
OPENAI_API_KEY=your_openai_key
DISCORD_BOT_TOKEN=your_discord_token_for_this_agent
# Other agent-specific configuration
```

### API Access

Once running, each agent's API is accessible at:
- Teacher: http://localhost:8001
- Student: http://localhost:8002
- Echo Core: http://localhost:8003
- Echo Speculative: http://localhost:8004

### Health Check

```bash
# Check teacher agent
curl http://localhost:8001/api/v1/health

# Check all agents
for port in 8001 8002 8003 8004; do
  echo "Agent on port $port:"
  curl -s http://localhost:$port/api/v1/health | jq .
done
```

### OAuth Endpoints

Each agent exposes OAuth endpoints:
- `GET /v1/auth/oauth/{provider}/start` - Start OAuth flow
- `GET /v1/auth/oauth/{provider}/callback` - Handle OAuth callback

Example:
```bash
# Start Google OAuth for teacher agent
curl http://localhost:8001/v1/auth/oauth/google/start
```