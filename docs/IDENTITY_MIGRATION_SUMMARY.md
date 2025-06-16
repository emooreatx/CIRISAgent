# Identity System Migration Summary

## Overview

The CIRIS Agent system has been migrated from a profile-based identity system to a graph-based identity system where "identity IS the graph."

## Key Changes

### 1. Profile System (OLD)
- Profiles stored as YAML files
- Runtime could switch between profiles
- Identity was mutable during runtime
- No approval required for changes

### 2. Identity System (NEW)
- Identity stored as graph node "agent/identity"
- Identity is immutable except through MEMORIZE with WA approval
- 20% variance threshold triggers reconsideration
- Profile YAML only used as template during initial creation

## Technical Implementation

### Identity Storage
```python
# Stored in graph_nodes table
GraphNode(
    id="agent/identity",
    type=NodeType.AGENT,
    scope=GraphScope.IDENTITY,  # WA approval required
    attributes={"identity": AgentIdentityRoot(...)}
)
```

### Persistence Model
- Created: `/ciris_engine/persistence/models/identity.py`
- Functions:
  - `store_agent_identity()` - Initial storage
  - `retrieve_agent_identity()` - Get from graph
  - `update_agent_identity()` - WA-approved updates
  - `get_identity_for_context()` - For DMAs/processors

### Updated Components

#### Removed/Modified
- ✅ Removed profile switching from RuntimeControlInterface
- ✅ Removed profile management from API endpoints
- ✅ Removed backward compatibility shims
- ✅ Updated wakeup processor to use identity
- ✅ Updated DMA orchestrator to use identity
- ✅ Updated action selection to use identity

#### Enhanced Security
- ✅ WA approval enforced for identity changes
- ✅ Comprehensive audit logging for all identity operations
- ✅ Identity change attempts without WA approval are logged and denied
- ✅ Variance calculation prevents drastic identity shifts

### Agent Creation

#### API Endpoints (NEW)
- `POST /v1/agents/create` - Create new agent (WA required)
- `POST /v1/agents/{agent_id}/initialize` - Initialize agent

#### Creation Flow
1. WA authenticates with token
2. Provides profile template and agent details
3. System creates identity root
4. Stores metadata for first-run initialization
5. Agent creates graph identity on first startup

## Migration Path

For existing systems:
1. Agents will load identity from graph if it exists
2. On first run, identity is created from profile YAML
3. After creation, profile YAML is ignored
4. All identity changes must go through MEMORIZE action

## Breaking Changes

1. `create_profile()` method removed
2. `reload_profile()` method removed
3. Profile switching no longer supported
4. `agent_profile` parameter removed from processors
5. DMAs now receive `agent_identity` instead of `agent_profile`

## Documentation Created

1. **FOR_HUMANS.md** - Simple guide for end users
2. **FOR_WISE_AUTHORITIES.md** - WA responsibilities and powers
3. **FOR_AGENTS.md** - Self-reference for agents
4. **FOR_NERDS.md** - Technical deep dive

All documentation includes:
- Beta software disclaimers
- Copyright notices (Eric Moore and CIRIS L3C)
- Patent pending notices
- Apache 2.0 license references

## Legal Compliance

- Created NOTICE file with disclaimers
- Updated README with prominent warnings
- Added copyright headers to all docs
- Included liability disclaimers
- Patent pending notices added

---

**Remember**: This is BETA software. Use at your own risk!