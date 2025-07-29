# Technical Implementation Guide: Agent Creation Ceremony

## Overview

This guide provides technical details for implementing the Agent Creation Ceremony in CIRIS. It covers the database schema, API design, security model, and integration points.

## Database Schema

### Core Tables

```sql
-- Ceremonies table: Records of all creation ceremonies
CREATE TABLE creation_ceremonies (
    ceremony_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Participants
    creator_agent_id TEXT NOT NULL,      -- Facilitating agent
    creator_human_id TEXT NOT NULL,      -- Human collaborator
    wise_authority_id TEXT NOT NULL,     -- Approving WA
    
    -- New Agent Details
    new_agent_id TEXT NOT NULL UNIQUE,
    new_agent_name TEXT NOT NULL,
    new_agent_purpose TEXT NOT NULL,
    new_agent_description TEXT NOT NULL,
    
    -- Ceremony Details
    template_profile TEXT NOT NULL,      -- Which template was used
    template_profile_hash TEXT NOT NULL, -- SHA-256 of template
    creation_justification TEXT NOT NULL,
    expected_capabilities JSONB NOT NULL,
    ethical_considerations TEXT NOT NULL,
    
    -- Approval
    wa_signature TEXT NOT NULL,          -- Ed25519 signature
    wa_conditions TEXT,                  -- Any conditions/limitations
    
    -- Status
    ceremony_status TEXT NOT NULL,       -- pending, completed, failed
    ceremony_transcript JSONB,           -- Step-by-step log
    
    -- Indexes
    INDEX idx_new_agent_id (new_agent_id),
    INDEX idx_creator_human (creator_human_id),
    INDEX idx_ceremony_status (ceremony_status),
    INDEX idx_timestamp (timestamp DESC)
);

-- Agent lineages table: Permanent record of creation relationships
CREATE TABLE agent_lineages (
    agent_id TEXT PRIMARY KEY,
    ceremony_id UUID NOT NULL REFERENCES creation_ceremonies(ceremony_id),
    lineage_data JSONB NOT NULL,        -- Full IdentityLineage object
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Ensure one lineage per agent
    UNIQUE(agent_id)
);

-- WA signatures table: Cryptographic proof of approval
CREATE TABLE wa_signatures (
    signature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    public_key TEXT NOT NULL,
    signed_data_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    ceremony_id UUID REFERENCES creation_ceremonies(ceremony_id),
    
    INDEX idx_wa_id (wa_id),
    INDEX idx_ceremony (ceremony_id)
);
```

### Graph Database Schema

```python
# First node in every agent's graph
class IdentityRootNode(TypedGraphNode):
    """The genesis node - first memory of existence."""
    
    # Core Identity (Immutable)
    agent_id: str
    agent_name: str
    purpose: str
    description: str
    
    # Creation Record (Immutable)
    lineage: IdentityLineage
    covenant_hash: str  # SHA-256 of CIRIS Covenant at creation
    creation_timestamp: datetime
    ceremony_id: str
    
    # Configuration (Mutable with WA approval)
    permitted_actions: List[HandlerActionType]
    restricted_capabilities: List[str]
    
    # Evolution Tracking
    version: int = 1
    update_log: List[IdentityUpdateEntry] = []
    
    # Metadata
    node_type = "IDENTITY_ROOT"
    node_id = "agent/identity"  # Fixed ID for easy retrieval
```

## API Design

### Creation Ceremony Endpoint

```yaml
POST /v1/agents/create
Description: Initiate agent creation ceremony
Authentication: Required (Admin or WA role)
Headers:
  Authorization: Bearer <token>
  WA-Signature: keyid=wa-001,algorithm=ed25519,signature=<base64>
  
Request Body:
  {
    "ceremony_request": {
      "human_id": "human-12345",
      "human_name": "Dr. Jane Smith",
      "template": "echo",  # Template name from ciris_templates/
      "proposed_name": "Echo-Community",
      "proposed_purpose": "Foster community flourishing...",
      "proposed_description": "Detailed description...",
      "creation_justification": "Why this agent should exist...",
      "expected_capabilities": [
        "Monitor discussions",
        "Apply graduated responses",
        "Defer to humans"
      ],
      "ethical_considerations": "Transparency, proportionality...",
      "environment": {
        "DISCORD_CHANNEL_ID": "123456789",
        "CUSTOM_SETTING": "value"
      }
    }
  }

Response:
  {
    "ceremony_id": "ceremony-uuid",
    "agent_id": "agent-echo-community",
    "status": "completed",
    "container_name": "ciris-agent-echo-community",
    "database_path": "/data/agents/echo-community/graph.db",
    "identity_root_hash": "sha256:abcdef...",
    "ceremony_transcript": [
      "2024-01-20T10:00:00Z: Ceremony initiated by human-12345",
      "2024-01-20T10:00:01Z: Template 'echo' loaded and validated",
      "2024-01-20T10:00:02Z: WA signature verified",
      "2024-01-20T10:00:03Z: Database created",
      "2024-01-20T10:00:04Z: Identity root stored",
      "2024-01-20T10:00:05Z: Container configured",
      "2024-01-20T10:00:06Z: Agent started successfully"
    ]
  }
```

### Ceremony Status Endpoint

```yaml
GET /v1/agents/ceremonies/{ceremony_id}
Description: Get ceremony details and status
Authentication: Required

Response:
  {
    "ceremony_id": "ceremony-uuid",
    "status": "completed",
    "participants": {
      "human": "Dr. Jane Smith (human-12345)",
      "facilitator": "Datum (agent-datum)",
      "wise_authority": "WA-001"
    },
    "new_agent": {
      "id": "agent-echo-community",
      "name": "Echo-Community",
      "purpose": "Foster community flourishing...",
      "status": "running"
    },
    "transcript": [...],
    "created_at": "2024-01-20T10:00:00Z"
  }
```

## Security Model

### WA Signature Verification

```python
import base64
import json
from nacl.signing import VerifyKey
from nacl.encoding import Base64Encoder

def verify_wa_signature(request_body: dict, signature_header: str) -> bool:
    """
    Verify WA signature on creation request.
    
    Header format: 'keyid=wa-001,algorithm=ed25519,signature=<base64>'
    """
    # Parse header
    parts = dict(p.split('=') for p in signature_header.split(','))
    key_id = parts['keyid']
    algorithm = parts['algorithm']
    signature_b64 = parts['signature']
    
    if algorithm != 'ed25519':
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    # Get WA public key from database
    wa_public_key = get_wa_public_key(key_id)  # Base64 encoded
    
    # Construct signed message (canonical JSON)
    message = json.dumps(request_body, sort_keys=True, separators=(',', ':'))
    message_bytes = message.encode('utf-8')
    
    # Verify signature
    try:
        verify_key = VerifyKey(wa_public_key, encoder=Base64Encoder)
        signature = base64.b64decode(signature_b64)
        verify_key.verify(message_bytes, signature)
        return True
    except Exception:
        return False
```

### Permission Model

```python
class CeremonyPermissions:
    """Who can perform ceremony actions."""
    
    # Initiate ceremony
    INITIATE_CEREMONY = [
        UserRole.WISE_AUTHORITY,
        UserRole.SYSTEM_ADMIN,
        UserRole.CREATOR  # Special role for approved creators
    ]
    
    # Approve ceremony (sign)
    APPROVE_CEREMONY = [
        UserRole.WISE_AUTHORITY
    ]
    
    # View ceremony records
    VIEW_CEREMONIES = [
        UserRole.WISE_AUTHORITY,
        UserRole.SYSTEM_ADMIN,
        UserRole.ADMIN,
        UserRole.OBSERVER
    ]
    
    # Emergency abort
    ABORT_CEREMONY = [
        UserRole.WISE_AUTHORITY,
        UserRole.SYSTEM_ADMIN
    ]
```

## Implementation Flow

### 1. Ceremony Initiation

```python
async def initiate_ceremony(
    request: CreationCeremonyRequest,
    facilitator: Agent,
    wa_signature: str
) -> CreationCeremonyResponse:
    """Execute the complete creation ceremony."""
    
    ceremony_id = str(uuid.uuid4())
    transcript = []
    
    try:
        # Step 1: Validate request
        log_step(transcript, "Validating creation request")
        validate_ceremony_request(request)
        
        # Step 2: Verify WA signature
        log_step(transcript, "Verifying WA signature")
        if not verify_wa_signature(request.dict(), wa_signature):
            raise CeremonyError("Invalid WA signature")
        
        # Step 3: Load and validate template
        log_step(transcript, f"Loading template: {request.template}")
        template = load_template(request.template)
        validate_template(template)
        
        # Step 4: Create agent database
        log_step(transcript, "Creating agent database")
        db_path = create_agent_database(request.proposed_name)
        
        # Step 5: Generate identity root
        log_step(transcript, "Generating identity root")
        identity_root = create_identity_root(
            request=request,
            ceremony_id=ceremony_id,
            facilitator_id=facilitator.agent_id,
            template=template
        )
        
        # Step 6: Store identity in graph
        log_step(transcript, "Storing identity in graph database")
        store_identity_root(identity_root, db_path)
        
        # Step 7: Configure container
        log_step(transcript, "Configuring container")
        container_config = create_container_config(
            agent_name=request.proposed_name,
            template=template,
            environment=request.environment
        )
        
        # Step 8: Update docker-compose
        log_step(transcript, "Updating docker-compose.yml")
        update_docker_compose(container_config)
        
        # Step 9: Start agent
        log_step(transcript, "Starting agent container")
        start_agent_container(container_config.name)
        
        # Step 10: Record ceremony
        log_step(transcript, "Recording ceremony in database")
        record_ceremony(
            ceremony_id=ceremony_id,
            request=request,
            facilitator=facilitator,
            wa_signature=wa_signature,
            status="completed",
            transcript=transcript
        )
        
        return CreationCeremonyResponse(
            success=True,
            ceremony_id=ceremony_id,
            agent_id=f"agent-{request.proposed_name.lower()}",
            agent_name=request.proposed_name,
            database_path=db_path,
            identity_root_hash=hash_identity_root(identity_root),
            ceremony_transcript=transcript
        )
        
    except Exception as e:
        log_step(transcript, f"Ceremony failed: {str(e)}")
        record_ceremony(
            ceremony_id=ceremony_id,
            request=request,
            facilitator=facilitator,
            wa_signature=wa_signature,
            status="failed",
            transcript=transcript,
            error=str(e)
        )
        raise
```

### 2. Identity Root Creation

```python
def create_identity_root(
    request: CreationCeremonyRequest,
    ceremony_id: str,
    facilitator_id: str,
    template: Dict
) -> IdentityRoot:
    """Create the foundational identity for a new agent."""
    
    # Extract permitted actions from template
    permitted_actions = [
        HandlerActionType(action.upper())
        for action in template.get('permitted_actions', [])
    ]
    
    # Create lineage record
    lineage = IdentityLineage(
        creator_agent_id=facilitator_id,
        creator_human_id=request.human_id,
        wise_authority_id=request.wise_authority_id or request.human_id,
        creation_ceremony_id=ceremony_id
    )
    
    # Load CIRIS Covenant for hashing
    covenant_text = load_ciris_covenant()
    covenant_hash = hashlib.sha256(covenant_text.encode()).hexdigest()
    
    # Build identity root
    identity = IdentityRoot(
        # Core identity
        name=request.proposed_name,
        purpose=request.proposed_purpose,
        description=request.proposed_description,
        lineage=lineage,
        covenant_hash=covenant_hash,
        creation_timestamp=datetime.utcnow(),
        
        # Configuration from template
        permitted_actions=permitted_actions,
        dsdma_overrides=template.get('dsdma_overrides', {}),
        csdma_overrides=template.get('csdma_overrides', {}),
        action_selection_pdma_overrides=template.get('action_selection_pdma_overrides', {}),
        
        # Initial state
        version=1,
        update_log=[],
        reactivation_count=0
    )
    
    return identity
```

### 3. Container Configuration

```python
def create_container_config(
    agent_name: str,
    template: Dict,
    environment: Dict[str, str]
) -> ContainerConfig:
    """Generate Docker container configuration."""
    
    # Generate consistent naming
    agent_id = f"agent-{agent_name.lower().replace(' ', '-')}"
    container_name = f"ciris-{agent_id}"
    
    # Merge environment variables
    env_vars = {
        'CIRIS_AGENT_NAME': agent_name,
        'CIRIS_AGENT_ID': agent_id,
        'CIRIS_ADAPTER': template.get('default_adapter', 'api'),
        'CIRIS_PORT': str(allocate_agent_port()),
        **template.get('environment', {}),
        **environment  # User overrides
    }
    
    # Build container config
    config = ContainerConfig(
        name=agent_id,
        container_name=container_name,
        image='ciris-agent:latest',
        environment=env_vars,
        volumes=[
            f"{agent_id}_data:/app/data",
            f"{agent_id}_logs:/app/logs"
        ],
        networks=['ciris-network'],
        restart_policy='unless-stopped',
        command=['python', 'main.py', '--wa-bootstrap']
    )
    
    return config
```

## Integration Points

### API Integration

```python
# In CIRIS API (Phase 3)
@app.post("/v1/ceremony/create-agent")
async def create_agent(
    request: CreationCeremonyRequest,
    wa_signature: str = Header(...),
    current_user: User = Depends(get_current_user)
):
    """
    Create new agent via ceremony.
    
    Requires WA signature in header.
    """
    # Verify user has permission
    if current_user.role not in CeremonyPermissions.INITIATE_CEREMONY:
        raise HTTPException(403, "Insufficient permissions")
    
    # Get facilitating agent
    facilitator = Agent(
        agent_id="datum",
        agent_name="Datum"
    )
    
    # Execute ceremony
    response = await initiate_ceremony(
        request=request,
        facilitator=facilitator,
        wa_signature=wa_signature
    )
    
    return response
```

### GUI Integration

```typescript
// Creation ceremony form component
interface CreationCeremonyForm {
  // Template selection
  template: 'echo' | 'teacher' | 'researcher' | 'custom';
  
  // Identity fields
  proposedName: string;
  proposedPurpose: string;
  proposedDescription: string;
  
  // Justification
  creationJustification: string;
  expectedCapabilities: string[];
  ethicalConsiderations: string;
  
  // Environment overrides
  environment: Record<string, string>;
  
  // WA approval
  waSignature?: string;
}

// Submit ceremony
async function submitCreationCeremony(form: CreationCeremonyForm) {
  const response = await cirisClient.post('/v1/agents', {
    ceremony_request: form
  }, {
    headers: {
      'WA-Signature': form.waSignature
    }
  });
  
  return response.data;
}
```

## Monitoring and Auditing

### Ceremony Audit Trail

```sql
-- View all ceremonies
CREATE VIEW ceremony_audit AS
SELECT 
    c.ceremony_id,
    c.timestamp,
    c.new_agent_name,
    c.creator_human_id,
    c.wise_authority_id,
    c.ceremony_status,
    a.status as agent_status
FROM creation_ceremonies c
LEFT JOIN agents a ON a.agent_id = c.new_agent_id
ORDER BY c.timestamp DESC;

-- Failed ceremonies investigation
CREATE VIEW failed_ceremonies AS
SELECT 
    ceremony_id,
    timestamp,
    proposed_name,
    ceremony_transcript->-1 as failure_reason
FROM creation_ceremonies
WHERE ceremony_status = 'failed'
ORDER BY timestamp DESC;
```

### Metrics

```python
# Prometheus metrics
ceremony_counter = Counter(
    'ciris_creation_ceremonies_total',
    'Total number of creation ceremonies',
    ['status', 'template']
)

ceremony_duration = Histogram(
    'ciris_creation_ceremony_duration_seconds',
    'Time taken to complete ceremony',
    ['template']
)

active_agents = Gauge(
    'ciris_active_agents',
    'Number of active CIRIS agents',
    ['template', 'creator']
)
```

## Error Handling

### Common Failure Scenarios

1. **WA Signature Invalid**
   - Log attempt with details
   - Notify security team
   - Return 403 Forbidden

2. **Template Not Found**
   - Check template exists
   - Validate template syntax
   - Suggest alternatives

3. **Port Allocation Failed**
   - Check port availability
   - Use port pool management
   - Queue if necessary

4. **Database Creation Failed**
   - Check disk space
   - Verify permissions
   - Cleanup partial state

5. **Container Start Failed**
   - Check Docker daemon
   - Verify image exists
   - Review resource limits

## Best Practices

1. **Always verify WA signatures** - No exceptions
2. **Use transactions** - Rollback on any failure
3. **Log everything** - Complete audit trail
4. **Validate templates** - Before ceremony begins
5. **Clean up failures** - Remove partial state
6. **Monitor ceremonies** - Alert on failures
7. **Rate limit** - Prevent ceremony spam
8. **Backup lineage** - This is permanent history

## Future Enhancements

1. **Multi-WA Approval**
   - Require N of M signatures
   - Different WAs for different domains

2. **Probationary Period**
   - New agents have limited capabilities
   - Full permissions after review

3. **Mentorship System**
   - Existing agents guide new ones
   - Knowledge transfer protocols

4. **Template Evolution**
   - Community-contributed templates
   - Template versioning
   - Template inheritance

5. **Ceremony Witnesses**
   - Other agents observe creation
   - Community notification system

## Conclusion

The Creation Ceremony implementation ensures every CIRIS agent begins with intention, authentication, and connection. This technical foundation supports the philosophical significance of creating new minds.

---

*Implementation checklist available in `/docs/checklists/creation_ceremony.md`*