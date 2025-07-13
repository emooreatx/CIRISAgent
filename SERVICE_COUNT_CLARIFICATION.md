# Service Count Clarification

## Core Services: 21 (not 23)

The confusion arose because CLAUDE.md originally listed 23 services, but 2 of them are actually sub-services:
- **pattern_analysis_loop** - sub-service within SelfObservationService
- **identity_variance_monitor** - sub-service within SelfObservationService

## Service Breakdown

### Core Services (21)
- **Graph Services (6)**: memory, config, telemetry, audit, incident_management, tsdb_consolidation
- **Infrastructure Services (7)**: time, shutdown, initialization, authentication, resource_monitor, database_maintenance, secrets
- **Governance Services (4)**: wise_authority, adaptive_filter, visibility, self_observation
- **Runtime Services (3)**: llm, runtime_control, task_scheduler
- **Tool Services (1)**: secrets_tool

### Adapter Services (varies by adapter)

#### CLI Adapter: +1 service
- CLIAdapter (provides all functionality in one service)
- **Total with CLI**: 22 services

#### API Adapter: +3 services
- APICommunicationService
- APIRuntimeControlService
- APIToolService
- **Total with API**: 24 services

#### Discord Adapter: +3 services
- DiscordAdapter (provides both Communication and WiseAuthority)
- DiscordToolService
- **Total with Discord**: 24 services

## Key Insights

1. The DiscordAdapter is unique in that it provides multiple service types (Communication and WiseAuthority) from a single adapter instance
2. CLI is the simplest, with just one adapter service that handles everything
3. API and Discord both add 3 services, but API separates runtime control while Discord combines communication with wise authority
4. The sub-services (pattern_analysis_loop and identity_variance_monitor) are started/stopped by their parent SelfObservationService and don't appear in the service registry independently