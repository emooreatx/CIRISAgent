"""
Type-safe service container schemas for CIRIS Engine.

MISSION CRITICAL: Zero tolerance for Dict[str, Any] in service management.
"""
from typing import Optional, List, TYPE_CHECKING, Any
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ciris_engine.protocols.services import (
        AuditService, LLMService, MemoryService, 
        ToolService, WiseAuthorityService
    )
    from ciris_engine.services.wa_auth_service import WAAuthService
    from ciris_engine.secrets.service import SecretsService
    from ciris_engine.telemetry.core import BasicTelemetryCollector
    from ciris_engine.services.adaptive_filter_service import AdaptiveFilterService
    from ciris_engine.services.agent_config_service import AgentConfigService
    from ciris_engine.services.multi_service_transaction_orchestrator import MultiServiceTransactionOrchestrator
    from ciris_engine.services.core_tool_service import CoreToolService
    from ciris_engine.persistence.maintenance import DatabaseMaintenanceService


class ServiceContainer(BaseModel):
    """Type-safe container for all CIRIS services."""
    
    # Core services
    llm_service: Optional['LLMService'] = Field(None, description="LLM service for AI operations")
    memory_service: Optional['MemoryService'] = Field(None, description="Memory service for knowledge storage")
    audit_services: List['AuditService'] = Field(default_factory=list, description="Audit services for compliance")
    tool_services: List['ToolService'] = Field(default_factory=list, description="Tool services for capabilities")
    wa_services: List['WiseAuthorityService'] = Field(default_factory=list, description="Wise Authority services")
    
    # Security services
    secrets_service: Optional['SecretsService'] = Field(None, description="Secrets management service")
    wa_auth_system: Optional['WAAuthService'] = Field(None, description="WA authentication system")
    
    # Infrastructure services
    telemetry_service: Optional['BasicTelemetryCollector'] = Field(None, description="Telemetry and monitoring")
    adaptive_filter_service: Optional['AdaptiveFilterService'] = Field(None, description="Adaptive content filtering")
    agent_config_service: Optional['AgentConfigService'] = Field(None, description="Agent configuration management")
    transaction_orchestrator: Optional['MultiServiceTransactionOrchestrator'] = Field(None, description="Transaction coordination")
    core_tool_service: Optional['CoreToolService'] = Field(None, description="Core tool capabilities")
    maintenance_service: Optional['DatabaseMaintenanceService'] = Field(None, description="System maintenance service")
    
    class Config:
        arbitrary_types_allowed = True
    
    def get_service_by_type(self, service_type: str) -> Optional[List[Any]]:
        """Get services by type name."""
        service_map = {
            "llm": [self.llm_service] if self.llm_service else [],
            "memory": [self.memory_service] if self.memory_service else [],
            "audit": self.audit_services,
            "tool": self.tool_services,
            "wise_authority": self.wa_services,
            "secrets": [self.secrets_service] if self.secrets_service else [],
            "wa_auth": [self.wa_auth_system] if self.wa_auth_system else [],
            "telemetry": [self.telemetry_service] if self.telemetry_service else [],
            "adaptive_filter": [self.adaptive_filter_service] if self.adaptive_filter_service else [],
            "agent_config": [self.agent_config_service] if self.agent_config_service else [],
            "transaction": [self.transaction_orchestrator] if self.transaction_orchestrator else [],
            "core_tool": [self.core_tool_service] if self.core_tool_service else [],
            "maintenance": [self.maintenance_service] if self.maintenance_service else []
        }
        result = service_map.get(service_type, [])
        return result if isinstance(result, list) else []
    
    @property
    def audit_service(self) -> Optional['AuditService']:
        """Get primary audit service for backward compatibility."""
        return self.audit_services[0] if self.audit_services else None