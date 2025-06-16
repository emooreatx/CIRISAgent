# Agent Creation Templates (formerly CIRIS Profiles)

**⚠️ IMPORTANT: The profile system has been replaced by the graph-based identity system. Profile YAML files are now ONLY used as templates during initial agent creation. After creation, all identity management happens through the graph database with WA approval.**

## Overview

Profile YAML files in the `ciris_profiles/` directory serve as **templates for creating new agents**. They define the initial personality, capabilities, and configuration that a new agent will have when first created.

**Key Changes:**
- Profiles are **NOT** runtime configurations
- Profiles **CANNOT** be switched or reloaded after agent creation
- All identity changes must go through the MEMORIZE action with WA approval
- The agent's true identity lives in the graph database at `agent/identity`

## How Profiles Are Used

### 1. During Agent Creation Only

When creating a new agent via CLI:
```bash
python main.py --profile teacher --wa-bootstrap
```

Or via API:
```bash
curl -X POST http://localhost:8000/v1/agents/create \
  -H "Authorization: Bearer $WA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "TeacherBot",
    "profile_template": "teacher",
    "purpose": "Educational assistance"
  }'
```

### 2. Template Structure

Profile YAML files still exist but are now just creation templates:

```yaml
# ciris_profiles/teacher.yaml
name: "teacher"
description: "Template for creating educational assistant agents"
role_description: "Helps students learn and understand concepts"

# Initial capabilities (can be modified post-creation via MEMORIZE)
permitted_actions:
  - OBSERVE
  - SPEAK
  - MEMORIZE
  - RECALL
  - PONDER
  - DEFER
  - TASK_COMPLETE

# Domain-specific DMA selection
dsdma_identifier: "education"

# Initial configuration
initial_temperature: 0.7
initial_prompts:
  - "You are a patient and knowledgeable teacher"
```

## Identity Management Post-Creation

After an agent is created, its identity is stored in the graph:

```python
# Stored as GraphNode with id="agent/identity"
{
    "agent_id": "unique-agent-id",
    "agent_name": "TeacherBot",
    "purpose": "Educational assistance",
    "core_profile": {
        "name": "teacher",  # Original template name
        "role_description": "...",
        "permitted_actions": [...]
    },
    "identity_metadata": {
        "created_at": "2025-06-15T...",
        "created_by": "WA-001",
        "lineage": {
            "parent_agent_id": null,
            "creation_ceremony_id": "..."
        }
    }
}
```

## Modifying Agent Identity

### Requirements for Identity Changes

1. **WA Authorization Required**: All changes to `agent/identity` require WA approval
2. **20% Variance Check**: Changes exceeding 20% variance trigger reconsideration
3. **Audit Trail**: All changes are cryptographically logged

### Example Identity Modification

```python
# Via MEMORIZE action (requires WA authorization)
{
    "action": "MEMORIZE",
    "params": {
        "node_id": "agent/identity",
        "scope": "IDENTITY",
        "updates": {
            "core_profile.role_description": "Advanced educational mentor",
            "allowed_capabilities": ["new_capability"]
        }
    }
}
```

## Migration from Profile-Based System

If you have existing agents using the old profile system:

1. On first startup, the agent will create its identity in the graph from the profile
2. After creation, the profile YAML is no longer used
3. All future changes must go through MEMORIZE with WA approval

## Available Profile Templates

Current templates in `ciris_profiles/`:

- **default.yaml**: Balanced general-purpose agent
- **teacher.yaml**: Educational instructor template
- **student.yaml**: Learning-focused agent template
- **echo.yaml**: Simple testing template

## Creating New Templates

To create a new agent template:

1. Copy an existing template as a starting point
2. Modify the initial configuration as needed
3. Save in `ciris_profiles/` directory
4. Use during agent creation: `--profile your_template`

Remember: These are just templates. The agent's actual identity evolves through the graph database with proper authorization.

## See Also

- [Identity System Documentation](IDENTITY_MIGRATION_SUMMARY.md)
- [FOR_WISE_AUTHORITIES.md](FOR_WISE_AUTHORITIES.md) - WA identity management
- [Agent Creation API](api/runtime-control.md#agent-creation)

---

*Copyright © 2025 Eric Moore and CIRIS L3C - Apache 2.0 License*