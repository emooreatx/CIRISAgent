"""Service protocols package - organized by functional area."""

# Re-export base protocols from runtime
from ..runtime.base import (
    ServiceProtocol,
    ServiceProtocol as Service,  # Alias for backward compatibility
    GraphServiceProtocol,
    CoreServiceProtocol,
    VisibilityServiceProtocol as BaseVisibilityServiceProtocol,
)

# Graph service protocols - data persistence layer
from .graph import (
    MemoryServiceProtocol as MemoryService,
    AuditServiceProtocol as AuditService,
    TelemetryServiceProtocol as TelemetryService,
    GraphConfigServiceProtocol as ConfigService,
)

# Runtime service protocols - core operations
from .runtime import (
    LLMServiceProtocol as LLMService,
    ToolServiceProtocol as ToolService,
    SecretsServiceProtocol as SecretsService,
    RuntimeControlServiceProtocol as RuntimeControlService,
)

# Lifecycle service protocols - system state management
from .lifecycle import (
    TimeServiceProtocol,
    ShutdownServiceProtocol,
    InitializationServiceProtocol,
    TaskSchedulerServiceProtocol,
)

# Infrastructure service protocols
from .infrastructure import (
    AuthenticationServiceProtocol,
)

# Governance service protocols - security and oversight
from .governance import (
    WiseAuthorityServiceProtocol as WiseAuthorityService,
    VisibilityServiceProtocol,
    AdaptiveFilterServiceProtocol,
    CommunicationServiceProtocol as CommunicationService,
)

# Adaptation service protocols - self-improvement
from .adaptation import (
    SelfConfigurationServiceProtocol,
)

# Legacy protocol for compatibility
class GraphMemoryServiceProtocol(ServiceProtocol):
    """Legacy protocol for graph memory service operations."""

__all__ = [
    # Base protocols
    "Service",
    "ServiceProtocol",
    "GraphServiceProtocol",
    "CoreServiceProtocol",
    "BaseVisibilityServiceProtocol",
    # Graph services (5)
    "MemoryService",
    "AuditService",
    "TelemetryService",
    "ConfigService",
    # Runtime services (4)
    "LLMService",
    "ToolService",
    "SecretsService",
    "RuntimeControlService",
    # Lifecycle services (4)
    "TimeServiceProtocol",
    "ShutdownServiceProtocol",
    "InitializationServiceProtocol",
    "TaskSchedulerServiceProtocol",
    # Governance services (5)
    "AuthenticationServiceProtocol",
    "WiseAuthorityService",
    "VisibilityServiceProtocol",
    "AdaptiveFilterServiceProtocol",
    "CommunicationService",
    # Adaptation services (1)
    "SelfConfigurationServiceProtocol",
    # Legacy
    "GraphMemoryServiceProtocol",
]
