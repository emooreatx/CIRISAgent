"""
Service configuration for API Platform.

Provides a declarative, human-readable configuration for which agent services
the API adapter needs and how they should be mapped.
"""
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field


@dataclass
class ServiceMapping:
    """Defines how a single service should be mapped from runtime to API."""
    runtime_attr: str                    # Attribute name in runtime
    app_state_name: Optional[str] = None # Name in app.state (defaults to runtime_attr)
    special_handler: Optional[str] = None   # Special processing function name
    description: str = ""                # Human-readable description
    
    def __post_init__(self):
        # If no app_state_name specified, use runtime_attr
        if self.app_state_name is None:
            self.app_state_name = self.runtime_attr


class ApiServiceConfiguration:
    """
    Declarative configuration for API adapter service requirements.
    
    This clearly documents:
    1. The 21 core CIRIS services organized by category
    2. Additional services needed by the API
    3. Adapter-specific services that will be created
    
    Based on the official service list from CLAUDE.md:
    - Graph Services (6): memory, config, telemetry, audit, incident_management, tsdb_consolidation
    - Infrastructure Services (7): time, shutdown, initialization, authentication, resource_monitor, database_maintenance, secrets
    - Governance Services (4): wise_authority, adaptive_filter, visibility, self_observation
    - Runtime Services (3): llm, runtime_control, task_scheduler
    - Tool Services (1): secrets_tool
    """
    
    # ========== THE 21 CORE CIRIS SERVICES ==========
    
    # 6 Graph Services - Data persistence and tracking
    GRAPH_SERVICES = [
        ServiceMapping("memory_service", 
                      description="Graph-based memory storage and retrieval"),
        ServiceMapping("config_service", 
                      description="Configuration management"),
        ServiceMapping("telemetry_service", 
                      description="Telemetry data collection and storage"),
        ServiceMapping("audit_service", 
                      description="Audit trail and compliance logging"),
        ServiceMapping("incident_management_service", 
                      description="Incident tracking and management"),
        ServiceMapping("tsdb_consolidation_service", 
                      description="Time-series data consolidation"),
    ]
    
    # 7 Infrastructure Services - System operations
    INFRASTRUCTURE_SERVICES = [
        ServiceMapping("time_service", 
                      description="Centralized time management"),
        ServiceMapping("shutdown_service", 
                      description="Graceful shutdown coordination"),
        ServiceMapping("initialization_service", 
                      description="Service initialization management"),
        ServiceMapping("authentication_service", 
                      special_handler="_handle_auth_service",
                      description="User authentication and session management"),
        ServiceMapping("resource_monitor", 
                      description="System resource monitoring"),
        ServiceMapping("database_maintenance_service", 
                      description="Database maintenance operations"),
        ServiceMapping("secrets_service", 
                      description="Secrets and credential management"),
    ]
    
    # 4 Governance Services - System oversight and adaptation
    GOVERNANCE_SERVICES = [
        ServiceMapping("wa_auth_system", 
                      app_state_name="wise_authority_service",
                      description="Wise Authority decision system"),
        ServiceMapping("adaptive_filter_service", 
                      description="Adaptive content filtering"),
        ServiceMapping("visibility_service", 
                      description="System visibility and monitoring"),
        ServiceMapping("self_observation_service", 
                      description="Self-monitoring and adaptation"),
    ]
    
    # 3 Runtime Services - Execution and processing
    RUNTIME_SERVICES = [
        ServiceMapping("llm_service", 
                      description="Language model integration"),
        ServiceMapping("runtime_control_service", 
                      app_state_name="main_runtime_control_service",
                      description="Main runtime control from agent"),
        ServiceMapping("task_scheduler", 
                      description="Task scheduling and execution"),
    ]
    
    # 1 Tool Service - Specialized operations
    TOOL_SERVICES = [
        ServiceMapping("secrets_tool_service", 
                      description="Secrets management tool"),
    ]
    
    # Note: service_registry, agent_processor, and message_handler are infrastructure components,
    # not services, and should not be injected into app.state
    
    # Infrastructure Components - Required by API endpoints but not official services
    INFRASTRUCTURE_COMPONENTS = [
        ServiceMapping("service_registry",
                      description="Service registry for health checks and service discovery"),
    ]
    
    @classmethod
    def get_current_mappings_as_tuples(cls) -> List[Tuple[str, str, Optional[str]]]:
        """
        Returns all mappings in the same format as the existing code.
        This ensures backward compatibility during the refactor.
        """
        result = []
        all_mappings = (
            cls.GRAPH_SERVICES +
            cls.INFRASTRUCTURE_SERVICES +
            cls.GOVERNANCE_SERVICES +
            cls.RUNTIME_SERVICES +
            cls.TOOL_SERVICES +
            cls.INFRASTRUCTURE_COMPONENTS
        )
        
        for mapping in all_mappings:
            result.append((mapping.runtime_attr, mapping.app_state_name, mapping.special_handler))
        
        return result


@dataclass
class AdapterService:
    """Defines an adapter-created service."""
    attr_name: str              # Attribute name on the adapter (e.g., 'runtime_control')
    app_state_name: str         # Name in app.state
    description: str            # Human-readable description


# Adapter-created services configuration
ApiServiceConfiguration.ADAPTER_CREATED_SERVICES = [
    AdapterService("runtime_control", "runtime_control_service", 
                  "APIRuntimeControlService - API-specific runtime control with pause/resume"),
    AdapterService("communication", "communication_service", 
                  "APICommunicationService - Handles API message sending and response routing"),
    AdapterService("tool_service", "tool_service",
                  "APIToolService - Provides tool execution capabilities for the API"),
]