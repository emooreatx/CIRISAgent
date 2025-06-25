# CIRIS Deployment Scenarios

This document outlines the progressive deployment path for CIRIS, from simple community moderation to mission-critical applications.

## Current Production: Discord Community Moderation

**Status**: Active pilot deployment

**Use Case**: 
- Spam detection and removal
- Community guideline enforcement
- Positive interaction encouragement
- Conflict de-escalation

**Why It Matters**:
- Low-stakes environment for testing ethical decision-making
- Real-time feedback from community
- Demonstrates consistency and transparency
- Builds trust in the system

**Technical Requirements**:
- 4GB RAM
- Python 3.10+
- Internet for Discord API (can batch process offline)
- Llama4-scout or 4o-mini for cost efficiency

## Phase 2: Educational Assistant

**Target**: Schools and learning centers

**Use Cases**:
- Homework help with ethical guidelines
- Tutoring with patience and encouragement
- Resource allocation for computer lab time
- Student wellbeing monitoring

**Additional Requirements**:
- Local knowledge graph of curriculum
- Offline operation during school hours
- Sync when connected for updates
- Cultural adaptation for local context

## Phase 3: Rural Clinic Triage Assistant

**Target**: Healthcare facilities in resource-constrained areas

**Use Cases**:
- Patient intake and symptom recording
- Basic triage recommendations
- Medication interaction checking
- Resource allocation assistance
- Record keeping and follow-up scheduling

**Why CIRIS Architecture Fits**:
- **Offline-First**: SQLite works without internet
- **Graph Memory**: Builds local medical knowledge
- **Audit Trail**: Critical for medical decisions
- **Human Deferral**: Always escalates uncertain cases
- **Ubuntu Philosophy**: Culturally appropriate for African clinics

**Additional Requirements**:
- Medical protocol integration
- HIPAA-like privacy compliance
- Battery backup operation
- Multi-language support

## Phase 4: Agricultural Extension Support

**Target**: Farming communities

**Use Cases**:
- Crop disease identification
- Weather-based planting advice
- Market price information
- Cooperative resource sharing
- Sustainable farming practices

**Leverages**:
- Local knowledge accumulation
- Community-based learning
- Offline operation in fields
- SMS bridge for basic phones

## Phase 5: Community Governance Assistant

**Target**: Local government and NGOs

**Use Cases**:
- Meeting minute transcription
- Resource allocation recommendations
- Complaint tracking and routing
- Community feedback analysis
- Transparency reporting

**Key Features Used**:
- Complete audit trail
- Multi-stakeholder consideration
- Wisdom-based deferral
- Graph-based relationship tracking

## Technical Progression

### Starting Simple (Discord)
```bash
# Minimal deployment
python main.py --adapter discord --template echo
```

### Scaling Up (Clinic)
```bash
# Offline-capable with local model
python main.py --adapter api --template datum --llm llama3 --offline-mode
```

### Full Platform (Multi-Service)
```yaml
# Docker compose for complete deployment
services:
  ciris-api:
    # API for web/mobile access
  ciris-cli:
    # CLI for admin tasks
  ciris-sync:
    # Sync service for connected mode
```

## Why This Architecture Makes Sense

1. **19 Services**: Not over-engineering, but preparing for diverse deployments
2. **6 Buses**: Allows swapping providers (e.g., local LLM vs cloud)
3. **Graph Memory**: Each deployment builds local knowledge
4. **SQLite**: Perfect for single-site deployments
5. **Audit Everything**: Critical for medical/governance use cases
6. **Ubuntu Philosophy**: Resonates in target communities

## Resource Requirements by Deployment

| Scenario | RAM | Storage | Internet | LLM Model |
|----------|-----|---------|----------|-----------|
| Discord Bot | 4GB | 1GB | Required | 4o-mini |
| School Assistant | 4GB | 5GB | Optional | Llama3 |
| Clinic Triage | 8GB | 20GB | Rare | Llama3 |
| Agriculture | 4GB | 10GB | Optional | Llama3 |
| Governance | 8GB | 50GB | Daily | Llama4 |

## Deployment Philosophy

> "Start where you are, use what you have, do what you can." - Arthur Ashe

CIRIS is designed to be useful at every stage, not just at full deployment. A Discord bot today, a clinic assistant tomorrow, each deployment adds to the collective wisdom of the system.