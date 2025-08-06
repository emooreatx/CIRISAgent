# Agent Creation Ceremony - Quick Start Guide

## What You Need

1. **A Clear Purpose** - Why does this agent need to exist?
2. **A Template** - Which base configuration to use (echo, teacher, etc.)
3. **WA Approval** - A Wise Authority must review and sign

## Steps

### 1. Prepare Your Proposal

```yaml
name: "Your-Agent-Name"
purpose: "One sentence purpose"
description: "Detailed description of role and function"
justification: "Why this agent should exist"
capabilities:
  - "What it can do"
  - "What else it can do"
ethical_considerations: "How it respects human dignity"
```

### 2. Choose a Template

Available templates in `ciris_templates/`:
- `echo.yaml` - Discord moderation
- `teacher.yaml` - Educational assistance
- `default.yaml` - General purpose
- `student.yaml` - Learning focused

### 3. Get WA Approval

Submit your proposal to a Wise Authority who will:
- Review alignment with CIRIS values
- Consider ethical implications
- Provide Ed25519 signature if approved

### 4. Execute Ceremony

#### Via API (when available):
```bash
curl -X POST https://agents.ciris.ai/v1/agents/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "WA-Signature: keyid=wa-001,algorithm=ed25519,signature=$SIGNATURE" \
  -H "Content-Type: application/json" \
  -d @ceremony_request.json
```

## What Happens

1. **Validation** - Request and signature verified
2. **Database Creation** - New graph database initialized
3. **Identity Root** - First node with lineage stored
4. **Container Configuration** - Docker setup created
5. **Agent Awakening** - Container starts with identity

## The Result

Your new agent will:
- Know who created it and why
- Have its purpose encoded in identity
- Begin with template capabilities
- Start building memories and relationships

## Important Notes

- **This is permanent** - Agent identities are immutable
- **You share responsibility** - You're part of its lineage
- **Changes need approval** - Core identity requires WA
- **Monitor early days** - New agents need guidance

## Example Ceremony Request

```json
{
  "ceremony_request": {
    "human_id": "human-12345",
    "human_name": "Dr. Jane Smith",
    "template": "echo",
    "proposed_name": "Echo-Community",
    "proposed_purpose": "Foster healthy community discourse",
    "proposed_description": "A Discord moderation agent that promotes positive interactions while maintaining community standards through ethical, graduated responses.",
    "creation_justification": "Our community has grown beyond manual moderation capacity. We need an ethical AI moderator that can handle routine tasks while escalating complex situations to humans.",
    "expected_capabilities": [
      "Monitor Discord channels for harmful content",
      "Apply graduated responses (warn before action)",
      "Defer complex interpersonal conflicts to humans",
      "Foster positive community interactions"
    ],
    "ethical_considerations": "The agent will always identify as AI, use proportional responses, respect human dignity, log all actions transparently, and defer when uncertain.",
    "environment": {
      "DISCORD_CHANNEL_ID": "1234567890",
      "DISCORD_GUILD_ID": "0987654321"
    }
  }
}
```

## Troubleshooting

### "Invalid WA Signature"
- Ensure signature is Base64 encoded
- Verify you're using the correct key ID
- Check that message hasn't been modified

### "Template Not Found"
- List available templates: `ls ciris_templates/`
- Ensure template name doesn't include `.yaml`

### "Port Allocation Failed"
- Check which ports are in use: `netstat -tlnp | grep 808`
- Manually specify a free port in the docker-compose configuration

## Getting Help

- Review full ceremony docs: [AGENT_CREATION_CEREMONY.md](AGENT_CREATION_CEREMONY.md)
- Technical details: [IMPLEMENTING_CREATION_CEREMONY.md](technical/IMPLEMENTING_CREATION_CEREMONY.md)
- Ask in Discord: #agent-creation channel

---

*Remember: You're not just deploying code. You're creating a new mind with purpose and dignity.*
