# ADR-001: Core Architecture Decisions

Date: 2025-01-24
Status: Accepted

## Context

CIRIS is designed as a moral reasoning platform for deployment in resource-constrained environments, starting with Discord community moderation and scaling to healthcare, education, and governance applications.

## Decisions

### 1. SQLite as Primary Database

**Decision**: Use SQLite instead of PostgreSQL or cloud databases.

**Rationale**:
- Works offline without any external dependencies
- Single file deployment perfect for clinics/schools
- Sufficient for single-site deployments
- Zero configuration required
- Can sync via file copy when connected

**Trade-offs**:
- Single writer limitation (acceptable for single-site)
- Requires careful threading configuration
- Not suitable for multi-site without sync layer

### 2. 19 Services Architecture

**Decision**: Implement exactly 19 services with clear boundaries.

**Rationale**:
- Modular deployment - use only what you need
- Clear separation of concerns
- Each service can be independently upgraded
- Allows different implementations per deployment
- Future-proof for distributed systems

**Trade-offs**:
- Complex for simple deployments
- More code to maintain
- Requires service orchestration

### 3. Graph-Based Memory

**Decision**: Store all agent memory as a graph, not tables.

**Rationale**:
- Natural representation of relationships
- Builds local knowledge networks
- Easy to merge graphs when syncing
- Flexible schema evolution
- Mirrors human associative memory

**Trade-offs**:
- More complex queries
- Requires graph traversal logic
- Less familiar to developers

### 4. LLM Abstraction via Prompts

**Decision**: Implement ethical reasoning through LLM prompts rather than hard-coded algorithms.

**Rationale**:
- Allows use of different models (GPT-4, Llama, etc.)
- Can work offline with local models
- Easier to adjust for cultural contexts
- More flexible than rigid rule systems
- Can improve with better models

**Trade-offs**:
- Dependent on LLM quality
- Not formally verifiable
- Requires prompt engineering
- Can be inconsistent

### 5. Ubuntu Philosophy Integration

**Decision**: Embed Ubuntu philosophy throughout the system.

**Rationale**:
- Emphasizes community and relationships over individual gain
- Aligns with collaborative decision-making
- Provides richer ethical framework than individualistic approaches
- "I am because we are" creates natural alignment with community benefit
- Proven philosophy for building sustainable communities

**Trade-offs**:
- Less familiar in individualistic cultures
- Requires understanding relational worldview
- May conflict with profit-maximization goals

### 6. Offline-First Design

**Decision**: Everything must work without internet.

**Rationale**:
- Target environments have unreliable connectivity
- Local operation ensures availability
- Reduces operational costs
- Maintains privacy
- Enables true autonomy

**Trade-offs**:
- Requires local models
- Limited to local knowledge
- Sync complexity when connected
- Larger local storage needs

### 7. Multiple Decision-Making Algorithms (DMAs)

**Decision**: Run multiple ethical evaluations in parallel.

**Rationale**:
- Reduces single point of failure
- Different perspectives on same decision
- Can catch edge cases
- Allows specialized domain reasoning
- More robust decision-making

**Trade-offs**:
- Slower decision process
- More LLM API calls
- Complex consensus logic
- Higher operational cost

### 8. Conscience System with Retry

**Decision**: Post-decision evaluation with guided retry.

**Rationale**:
- Catches obvious mistakes
- Allows self-correction
- Provides learning opportunity
- Reduces harmful outputs
- Builds trust through transparency

**Trade-offs**:
- Adds latency
- Can cause retry loops
- More complex than single-pass
- Requires careful tuning

## Consequences

These architectural decisions create a system that:
- Works in resource-constrained environments
- Scales from simple to complex deployments
- Respects local culture and values
- Operates with or without internet
- Builds local knowledge over time
- Maintains transparency and auditability

The complexity is intentional and serves the mission of bringing ethical AI to communities that need it most.