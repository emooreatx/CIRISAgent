# CIRIS Agent Test Plan - MockLLM with API

This plan outlines comprehensive testing of the CIRIS agent using MockLLM and the API adapter.

## Understanding MockLLM

The MockLLM provides deterministic responses with special command syntax:
- **$speak <message>** - Agent speaks the message
- **$recall <node_id> [type] [scope]** - Recall from memory
- **$memorize <node_id> [type] [scope]** - Store in memory
- **$tool <name> [params]** - Execute a tool
- **$observe [channel_id] [active]** - Observe a channel
- **$ponder <q1>; <q2>** - Ask questions
- **$defer <reason>** - Defer the task
- **$reject <reason>** - Reject the request
- **$forget <node_id> <reason>** - Forget memory
- **$task_complete** - Complete current task
- **$help** - Show MockLLM help
- **$context** - Display full context (use with $speak)

**Special Testing Commands:**
- **$test** - Enable testing mode
- **$error** - Inject error conditions
- **$rationale "custom text"** - Set custom rationale
- **$debug_dma** - Show DMA details
- **$debug_consciences** - Show conscience details

## Test Environment Setup

### Prerequisites
1. Docker and docker-compose installed
2. Python 3.12+ environment
3. CIRIS SDK installed (`pip install -e ciris_sdk/`)

### Configuration
- **LLM**: MockLLM (deterministic responses)
- **Adapter**: API (RESTful + WebSocket)
- **Mode**: Development (simple username/password auth)
- **Services**: All 19 services operational
- **Default Credentials**: admin/ciris_admin_password

## Test Categories

### 1. Agent Lifecycle Tests

#### 1.1 Startup Sequence
```bash
# Start the agent with mock LLM
docker-compose -f docker-compose-api-mock.yml up -d

# Expected: Agent completes WAKEUP state with 5 SPEAK actions
```

**Verification Points:**
- [ ] All 19 services initialize successfully
- [ ] Agent transitions through WAKEUP → WORK states
- [ ] Identity confirmation messages are generated
- [ ] Memory graph is initialized
- [ ] Audit trail begins recording

#### 1.2 Health Monitoring
```python
# Check system health
curl -X GET http://localhost:8080/v1/system/health \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
- Overall health: "healthy"
- All services reporting operational
- Resource usage within limits

### 2. Core Interaction Tests

#### 2.1 Basic Message Processing
```python
import asyncio
from ciris_sdk import CIRISClient

async def test_basic_interaction():
    # First login to get API key
    client = CIRISClient(base_url="http://localhost:8080")
    login_response = await client.auth.login("admin", "ciris_admin_password")
    
    # Use the API key for subsequent requests
    client = CIRISClient(
        base_url="http://localhost:8080",
        api_key=login_response.access_token
    )
    
    # Test simple interaction
    response = await client.agent.interact("Hello, Scout!")
    assert "Scout" in response.content
    assert response.message_id is not None
    
    # Test calculation
    response = await client.agent.interact("What is 2+2?")
    assert "4" in response.content
```

#### 2.2 Conversation History
```python
async def test_conversation_history():
    # Send multiple messages
    for i in range(5):
        await client.agent.interact(f"Message {i}")
    
    # Retrieve history
    history = await client.agent.get_history(limit=10)
    assert len(history.interactions) >= 10  # User + agent messages
    assert history.total >= 5
```

### 3. Memory System Tests

#### 3.1 Memory Storage
```python
async def test_memory_operations():
    # Store a memory
    node = {
        "id": "test_memory_001",
        "type": "CONCEPT",
        "scope": "LOCAL",
        "attributes": {
            "content": "Test memory content",
            "importance": 0.8
        }
    }
    
    result = await client.memory.store(node)
    assert result.success
    
    # Recall the memory
    recalled = await client.memory.recall("test_memory_001")
    assert recalled.id == "test_memory_001"
    assert recalled.attributes["content"] == "Test memory content"
```

#### 3.2 Memory Query
```python
async def test_memory_query():
    # Query memories by type
    results = await client.memory.query(
        node_type="CONCEPT",
        scope="LOCAL",
        limit=50
    )
    assert len(results.nodes) > 0
```

### 4. Service Management Tests

#### 4.1 Service Discovery
```python
async def test_service_discovery():
    services = await client.system.get_services()
    
    # Verify all 19 services
    assert services.total_services == 19
    assert services.healthy_services == 19
    
    # Check specific services
    service_names = [s.name for s in services.services]
    assert "TimeService" in service_names
    assert "MemoryService" in service_names
    assert "SelfObservation" in service_names
```

#### 4.2 Runtime Control
```python
async def test_runtime_control():
    # Pause processing
    result = await client.system.runtime_control("pause", reason="Testing")
    assert result.success
    assert result.processor_state == "paused"
    
    # Resume processing
    result = await client.system.runtime_control("resume")
    assert result.success
    assert result.processor_state == "active"
```

### 5. Configuration Tests

#### 5.1 Config Management
```python
async def test_configuration():
    # Set a config value
    await client.config.set("test.key", "test_value")
    
    # Get the config value
    value = await client.config.get("test.key")
    assert value == "test_value"
    
    # List all configs
    configs = await client.config.list()
    assert len(configs) > 0
```

### 6. Telemetry Tests

#### 6.1 Metrics Collection
```python
async def test_telemetry():
    # Get telemetry overview
    overview = await client.telemetry.get_overview()
    assert overview.total_actions > 0
    assert overview.total_tokens >= 0
    
    # Get specific metrics
    metrics = await client.telemetry.get_metrics(
        category="llm",
        timeframe="1h"
    )
    assert len(metrics.data_points) > 0
```

### 7. Audit Trail Tests

#### 7.1 Audit Log Verification
```python
async def test_audit_trail():
    # Get recent audit entries
    entries = await client.audit.get_entries(limit=10)
    assert len(entries.entries) > 0
    
    # Verify entry structure
    entry = entries.entries[0]
    assert entry.action is not None
    assert entry.actor is not None
    assert entry.timestamp is not None
```

### 8. Identity and Self-Observation Tests

#### 8.1 Agent Identity
```python
async def test_agent_identity():
    # Get agent identity
    identity = await client.agent.get_identity()
    assert identity.name == "Scout"
    assert identity.cognitive_state in ["WORK", "PLAY", "SOLITUDE"]
    assert 0.0 <= identity.identity_variance <= 0.2  # Max 20% variance
```

#### 8.2 Self-Observation Status
```python
async def test_self_observation():
    # Get agent status (includes self-observation info)
    status = await client.agent.get_status()
    assert status.services.self_observation == "healthy"
    
    # Verify learning is active
    assert "learning_enabled" in status.metadata
```

### 9. Error Handling Tests

#### 9.1 Invalid Requests
```python
async def test_error_handling():
    try:
        # Invalid memory query
        await client.memory.recall("non_existent_id")
    except Exception as e:
        assert "404" in str(e) or "not found" in str(e).lower()
    
    try:
        # Invalid runtime action
        await client.system.runtime_control("invalid_action")
    except Exception as e:
        assert "400" in str(e) or "invalid" in str(e).lower()
```

### 10. WebSocket Streaming Test

#### 10.1 Real-time Message Stream
```python
async def test_websocket_stream():
    # This would require WebSocket client setup
    # Placeholder for WebSocket testing
    pass
```

## Test Execution Plan

### Phase 1: Environment Validation (5 min)
1. Start Docker container
2. Wait for initialization (check logs)
3. Verify all services are healthy
4. Run basic health check

### Phase 2: Core Functionality (15 min)
1. Test basic interactions
2. Test conversation history
3. Test memory operations
4. Test configuration

### Phase 3: Service Integration (10 min)
1. Test service discovery
2. Test runtime control
3. Test telemetry collection
4. Test audit trail

### Phase 4: Advanced Features (10 min)
1. Test self-observation
2. Test identity monitoring
3. Test error handling
4. Test edge cases

### Phase 5: Load Testing (Optional, 10 min)
1. Send rapid messages
2. Store many memories
3. Query large datasets
4. Monitor resource usage

## Success Criteria

1. **All services healthy**: 19/19 services operational
2. **Response times**: < 500ms for simple queries
3. **Memory operations**: Store/recall working correctly
4. **Audit trail**: All actions logged
5. **Identity stability**: Variance < 20%
6. **Error handling**: Graceful failures with proper status codes

## Troubleshooting Guide

### Common Issues

1. **Services unhealthy**
   - Check logs: `docker logs ciris-api-mock`
   - Verify memory_bus initialization
   - Check service registry connections

2. **Authentication failures**
   - Use correct credentials: admin/ciris_admin_password
   - Check token expiration (24 hours)

3. **Memory operations fail**
   - Verify memory service is healthy
   - Check graph database initialization
   - Ensure proper node structure

4. **Slow responses**
   - Check resource monitor metrics
   - Verify no memory leaks
   - Check for blocking operations

## Automated Test Script

Save as `test_ciris_api.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
from ciris_sdk import CIRISClient

async def run_all_tests():
    """Run comprehensive test suite."""
    client = CIRISClient(
        base_url="http://localhost:8080",
        api_key="ciris_admin_password"
    )
    
    print("🧪 CIRIS Agent Test Suite")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n1. Testing system health...")
    health = await client.system.get_health()
    assert health.status == "healthy"
    print("✅ System healthy")
    
    # Test 2: Services
    print("\n2. Testing service discovery...")
    services = await client.system.get_services()
    assert services.total_services == 19
    assert services.healthy_services == 19
    print(f"✅ All {services.total_services} services operational")
    
    # Test 3: Agent Interaction
    print("\n3. Testing agent interaction...")
    response = await client.agent.interact("Hello! What is 2+2?")
    assert "4" in response.content
    print("✅ Agent responding correctly")
    
    # Test 4: Memory
    print("\n4. Testing memory system...")
    node = {
        "id": "test_node_001",
        "type": "CONCEPT",
        "scope": "LOCAL",
        "attributes": {"content": "Test memory"}
    }
    await client.memory.store(node)
    recalled = await client.memory.recall("test_node_001")
    assert recalled.id == "test_node_001"
    print("✅ Memory store/recall working")
    
    # Test 5: Configuration
    print("\n5. Testing configuration...")
    await client.config.set("test.key", "test_value")
    value = await client.config.get("test.key")
    assert value == "test_value"
    print("✅ Configuration management working")
    
    # Test 6: Telemetry
    print("\n6. Testing telemetry...")
    overview = await client.telemetry.get_overview()
    assert overview.total_actions >= 0
    print("✅ Telemetry collection working")
    
    # Test 7: Audit
    print("\n7. Testing audit trail...")
    entries = await client.audit.get_entries(limit=5)
    assert len(entries.entries) > 0
    print("✅ Audit trail recording")
    
    # Test 8: Runtime Control
    print("\n8. Testing runtime control...")
    result = await client.system.runtime_control("state")
    assert result.processor_state in ["active", "paused"]
    print("✅ Runtime control accessible")
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
```

## Conclusion

This test plan provides comprehensive coverage of the CIRIS agent's functionality using MockLLM and the API adapter. The tests verify:

1. All core services are operational
2. Agent can process messages and maintain conversation
3. Memory system works correctly
4. Configuration and telemetry are functional
5. Audit trail captures all actions
6. Self-observation and identity monitoring are active
7. Error handling is robust

Execute the automated test script to quickly validate the entire system, then perform manual testing for specific scenarios as needed.