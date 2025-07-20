# CIRISManager - Functional Specification Document

## Executive Summary

CIRISManager is a lightweight agent lifecycle management service that provides centralized discovery, creation, and lifecycle management for CIRIS agents on a server. It solves the current deployment challenges by monitoring containers for crash loops, notifying agents of updates, and ensuring containers restart with the latest images after any exit.

## Problem Statement

### Current Challenges

1. **No Dynamic Agent Discovery**: The GUI has a hardcoded list of agents, requiring code changes to add new agents
2. **Manual Update Process**: Updates require manual intervention or complex staging scripts
3. **Crash Loop Risk**: No protection against agents that crash repeatedly  
4. **No Central Creation**: Creating new agents requires manual docker-compose editing
5. **Deployment Complexity**: Current staging approach stops containers, breaking graceful shutdown

### Why Periodic `docker-compose up -d`?

The key insight is that `docker-compose up -d` with `restart: unless-stopped` creates a natural update mechanism:

1. **Container stops** (for any reason - graceful shutdown, crash, manual stop)
2. **Docker's restart policy**: 
   - Exit code 0 → Container stays stopped (unless-stopped policy)
   - Non-zero exit → Docker tries to restart
3. **CIRISManager runs `docker-compose up -d`**:
   - Stopped containers start with the **latest image**
   - Running containers are **not affected**
   - No complex staging needed

This approach leverages Docker's natural behavior instead of fighting it.

## Solution Design

### Core Components

```
┌─────────────────────────────────────────────────────┐
│                   CIRISManager                      │
├─────────────────────────────────────────────────────┤
│  API Layer                                          │
│  ┌─────────────────┬───────────────┬─────────────┐ │
│  │ Agent Discovery │ Agent Creation │  Lifecycle  │ │
│  │   GET /agents   │ POST /agents   │ Mgmt (bg)   │ │
│  └─────────────────┴───────────────┴─────────────┘ │
├─────────────────────────────────────────────────────┤
│  Core Services                                      │
│  ┌──────────────┬────────────┬──────────────────┐  │
│  │   Watchdog   │  Notifier  │ Container Mgr    │  │
│  │ (crash loop) │ (updates)  │ (docker-compose) │  │
│  └──────────────┴────────────┴──────────────────┘  │
├─────────────────────────────────────────────────────┤
│  Security Layer                                     │
│  ┌──────────────────────┬──────────────────────┐   │
│  │ WA Signature Verify  │  Local Auth Socket   │   │
│  └──────────────────────┴──────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### API Endpoints

#### 1. Agent Discovery
```yaml
GET /agents
Response:
  agents:
    - id: "agent-datum"
      name: "Datum"
      status: "running"  # running, stopped, crashed
      container: "ciris-agent-datum"
      port: 8080
      health_url: "http://localhost:8080/v1/system/health"
      uptime_seconds: 3600
      version: "sha256:abc123..."  # image hash
      crash_count: 0
    - id: "agent-sage"
      name: "Sage"
      status: "stopped"
      container: "ciris-agent-sage"
      port: 8081
      health_url: "http://localhost:8081/v1/system/health"
      stopped_at: "2025-01-20T12:00:00Z"
      exit_code: 0
```

#### 2. Agent Creation
```yaml
POST /agents
Headers:
  Authorization: "WA-Signature ..."  # Ed25519 signature
Body:
  template: "echo"  # Template name from ciris_templates/
  name: "Echo-Community"  # Instance name
  port: 8085
  environment:
    DISCORD_CHANNEL_ID: "123456"
    # Other env vars
Response:
  agent_id: "agent-echo-community"
  container: "ciris-agent-echo-community"
  status: "starting"
```

### How It Works

#### 1. Startup Flow
```python
# CIRISManager starts
1. Load configuration (docker-compose file location, etc)
2. Discover existing agents from docker-compose.yml
3. Start background tasks:
   - Watchdog (monitor containers every 30s)
   - Update checker (check for new images every 5m)
   - Container manager (run docker-compose up -d every 60s)
4. Start API server on local socket/port
```

#### 2. Container Management Loop
```python
# Every 60 seconds:
async def container_management_loop():
    while True:
        # Pull latest images
        await run_command("docker-compose pull")
        
        # Start any stopped containers with latest image
        # This is idempotent - running containers unaffected
        await run_command("docker-compose up -d")
        
        # Check for agents that need update notification
        for agent in get_running_agents():
            current_image = get_container_image(agent.container)
            latest_image = get_latest_image(agent.service)
            
            if current_image != latest_image:
                await notify_agent_update_available(agent)
        
        await asyncio.sleep(60)
```

#### 3. Crash Loop Detection
```python
# Watchdog monitors container restarts
async def watchdog_loop():
    crash_trackers = {}  # container -> crash events
    
    while True:
        for agent in get_all_agents():
            if not is_running(agent.container):
                exit_code = get_exit_code(agent.container)
                
                if exit_code != 0:
                    # Track crash
                    if agent.container not in crash_trackers:
                        crash_trackers[agent.container] = []
                    
                    crash_trackers[agent.container].append(time.now())
                    
                    # Remove old crashes (> 5 minutes)
                    crash_trackers[agent.container] = [
                        t for t in crash_trackers[agent.container]
                        if time.now() - t < 300
                    ]
                    
                    # Check for crash loop (3 crashes in 5 minutes)
                    if len(crash_trackers[agent.container]) >= 3:
                        logger.error(f"Crash loop detected: {agent.container}")
                        await stop_container(agent.container)
                        await send_alert(f"Agent {agent.name} in crash loop")
        
        await asyncio.sleep(30)
```

#### 4. Update Notification
```python
# Notify agents of available updates via local auth
async def notify_agent_update_available(agent):
    # Use local socket or internal endpoint
    async with LocalAuthClient(agent.health_url) as client:
        await client.post("/internal/update-available", {
            "current_image": agent.current_image,
            "new_image": agent.latest_image,
            "message": "New version available. Shutdown when ready to update."
        })
```

#### 5. Agent Creation Flow
```python
async def create_agent(request, wa_signature):
    # 1. Verify WA signature
    if not verify_wa_signature(request, wa_signature):
        raise Unauthorized("Invalid WA signature")
    
    # 2. Load template
    template = load_template(f"ciris_templates/{request.template}.yaml")
    
    # 3. Generate container config
    agent_config = {
        "name": request.name,
        "container_name": f"ciris-agent-{request.name.lower()}",
        "image": "ciris-agent:latest",
        "port": request.port,
        "environment": merge_env(template.env, request.environment),
        "command": ["python", "main.py", "--adapter", "api"]
    }
    
    # 4. Update docker-compose.yml
    compose_data = load_docker_compose()
    compose_data["services"][agent_config["name"]] = agent_config
    save_docker_compose(compose_data)
    
    # 5. Update nginx routing
    add_nginx_route(agent_config["name"], agent_config["port"])
    
    # 6. Start the agent
    await run_command(f"docker-compose up -d {agent_config['name']}")
    
    return {"agent_id": agent_config["name"], "status": "starting"}
```

### Security

#### 1. WA Signature Verification
```python
# Agent creation requires valid WA signature
def verify_wa_signature(request, signature_header):
    # Parse signature header: "WA-Signature keyid=...,signature=..."
    keyid, signature = parse_signature_header(signature_header)
    
    # Get WA public key from database or config
    wa_public_key = get_wa_public_key(keyid)
    
    # Verify signature over request body
    return ed25519_verify(
        public_key=wa_public_key,
        message=json.dumps(request, sort_keys=True),
        signature=signature
    )
```

#### 2. Local Authentication
```python
# Manager uses local-only auth for agent communication
class LocalAuthClient:
    def __init__(self, agent_url):
        # Use Unix socket or local-only token
        self.socket_path = f"/var/run/ciris/{agent_id}.sock"
        # Or use predefined local token
        self.local_token = generate_local_token()
```

### GUI Integration

The GUI can dynamically discover agents:

```typescript
// In AgentContext
async function discoverAgents() {
  const response = await fetch('http://localhost:9999/agents');
  const data = await response.json();
  
  // Transform to GUI format
  return data.agents.map(agent => ({
    id: agent.id,
    name: agent.name,
    apiUrl: `https://agents.ciris.ai/api/${agent.id}`,
    port: agent.port,
    status: agent.status,
    health: agent.status === 'running' ? 'online' : 'offline'
  }));
}

// Periodic refresh
useEffect(() => {
  const interval = setInterval(discoverAgents, 30000);
  return () => clearInterval(interval);
}, []);
```

### Configuration

```yaml
# /etc/ciris-manager/config.yml
manager:
  port: 9999
  socket: /var/run/ciris-manager.sock

docker:
  compose_file: /home/ciris/CIRISAgent/deployment/docker-compose.yml
  
watchdog:
  check_interval: 30  # seconds
  crash_threshold: 3  # crashes
  crash_window: 300   # seconds (5 minutes)

updates:
  check_interval: 300  # seconds (5 minutes)
  auto_notify: true

container_management:
  interval: 60  # seconds
  pull_images: true
```

### Benefits

1. **Zero-Downtime Updates**: Agents control when to shutdown, new version starts automatically
2. **Crash Protection**: Prevents infinite restart loops
3. **Dynamic Discovery**: GUI no longer needs hardcoded agent list
4. **Secure Creation**: WA signature required for new agents
5. **Simple Implementation**: Leverages Docker's natural behavior
6. **Agent Autonomy**: Agents decide when to update, manager just notifies

### Implementation Phases

1. **Phase 1**: Core watchdog and container management
2. **Phase 2**: API endpoints for discovery
3. **Phase 3**: Agent creation with WA signatures
4. **Phase 4**: GUI integration
5. **Phase 5**: Update notifications via local auth

This design provides a simple, robust solution that respects agent autonomy while solving real deployment challenges.